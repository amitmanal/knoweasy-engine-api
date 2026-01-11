# router.py
import hashlib
import json
import time
import os
import threading
from typing import Dict, Tuple

from fastapi import APIRouter, Request, Header
from fastapi.responses import JSONResponse

from config import (
    RATE_LIMIT_PER_MINUTE,
    RATE_LIMIT_BURST,
    RATE_LIMIT_WINDOW_SECONDS,
    KE_API_KEY,
    SOLVE_CACHE_TTL_SECONDS,
)
from schemas import SolveRequest, SolveResponse
from orchestrator import solve
from db import db_log_solve
from auth_store import session_user
from billing_store import consume_credits, get_or_create_subscription

from redis_store import get_json as redis_get_json
from redis_store import setex_json as redis_setex_json
from redis_store import incr_with_ttl as redis_incr_with_ttl

router = APIRouter()


# Global concurrency guardrail (prevents provider overload under spikes).
# Limits concurrent /solve executions per instance.
_MAX_CONCURRENT_SOLVES = int(os.getenv("MAX_CONCURRENT_SOLVES", "40"))
_SOLVE_QUEUE_WAIT_SECONDS = int(os.getenv("SOLVE_QUEUE_WAIT_SECONDS", "12"))
_SOLVE_SEM = threading.BoundedSemaphore(value=max(1, _MAX_CONCURRENT_SOLVES))

# In-memory rate limit buckets: {ip: (window_start_epoch, count)}
# Used ONLY if Redis is not enabled.
_BUCKETS: Dict[str, Tuple[float, int]] = {}


def _client_ip(req: Request) -> str:
    xff = req.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if req.client:
        return req.client.host or "unknown"
    return "unknown"


def _rate_limit_ok(ip: str) -> bool:
    """
    Rate limit priority:
    1) Redis (distributed)
    2) In-memory fallback (single-instance)
    """
    limit = RATE_LIMIT_PER_MINUTE + RATE_LIMIT_BURST
    window_s = int(RATE_LIMIT_WINDOW_SECONDS)

    # ---- Redis path (distributed) ----
    # key rotates per minute-window; we still set TTL = window_s
    # Use integer window bucket (floor(now/window_s)).
    now = time.time()
    bucket = int(now // window_s)
    redis_key = f"rl:{ip}:{bucket}"
    rc = redis_incr_with_ttl(redis_key, window_s)
    if rc is not None:
        return rc <= limit

    # ---- In-memory fallback ----
    start, count = _BUCKETS.get(ip, (now, 0))
    if now - start >= window_s:
        start, count = now, 0

    if count >= limit:
        _BUCKETS[ip] = (start, count)
        return False

    _BUCKETS[ip] = (start, count + 1)
    return True


def _safe_failure(message: str, code: str) -> SolveResponse:
    return SolveResponse(
        final_answer=message,
        steps=[],
        assumptions=[],
        confidence=0.2,
        flags=[code],
        safe_note="Try adding chapter/topic or any given options/conditions.",
        meta={"engine": "knoweasy-orchestrator-phase1"},
    )


def _cache_key(payload: dict) -> str:
    """
    Stable cache key for same user question+context.
    We only use relevant fields so UI noise won't bust cache.
    """
    normalized = {
        "board": (payload.get("board") or "").strip(),
        "class_level": (str(payload.get("class") or payload.get("class_") or payload.get("class_level") or "").strip() or None),
        "subject": (payload.get("subject") or "").strip(),
        "question": (payload.get("question") or "").strip(),
    }
    blob = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    h = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]
    return f"cache:solve:{h}"


@router.post("/solve", response_model=SolveResponse)
def solve_route(
    req: SolveRequest,
    request: Request,
    x_ke_key: str | None = Header(default=None, alias="X-KE-KEY"),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    # Optional shared key guardrail (not security, but reduces random abuse).
    if KE_API_KEY:
        if not x_ke_key or x_ke_key.strip() != KE_API_KEY:
            return JSONResponse(
                status_code=401,
                content=_safe_failure(
                    "Unauthorized request. Please open the app from the official KnowEasy website.",
                    "UNAUTHORIZED",
                ).model_dump(),
            )


    # -------- Auth + Credits (Phase-2 skeleton) --------
    # AI actions require login so we can enforce plan/credits safely.
    token = ""
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1].strip()

    if not token:
        return JSONResponse(
            status_code=401,
            content=_safe_failure(
                "Please sign in to use AI features (doubts/solutions).",
                "LOGIN_REQUIRED",
            ).model_dump(),
        )

    u = session_user(token)
    if not u:
        return JSONResponse(
            status_code=401,
            content=_safe_failure(
                "Your session expired. Please sign in again.",
                "SESSION_EXPIRED",
            ).model_dump(),
        )

    try:
        consume_credits(int(u["user_id"]), action="solve", cost=1, meta={"path": str(request.url.path)})
    except ValueError as ve:
        reason = str(ve)
        if reason == "INSUFFICIENT_CREDITS":
            # Provide a consistent response the UI can show.
            sub = get_or_create_subscription(int(u["user_id"]))
            bal = int(sub.get("credits_balance") or 0)
            return JSONResponse(
                status_code=402,
                content=_safe_failure(
                    "Daily AI limit reached. Try again tomorrow or upgrade your plan.",
                    "NO_CREDITS",
                ).model_dump() | {"credits_balance": bal},
            )
        return JSONResponse(
            status_code=500,
            content=_safe_failure(
                "Credits system not ready. Please try again in a minute.",
                "CREDITS_ERROR",
            ).model_dump(),
        )

    ip = _client_ip(request)
    if not _rate_limit_ok(ip):
        return JSONResponse(
            status_code=429,
            content=_safe_failure(
                "Too many requests right now. Please try again in a minute 😊",
                "RATE_LIMITED",
            ).model_dump(),
        )

    # -------- Cache (best-effort) --------
    payload = req.model_dump(by_alias=True)
    cache_key = _cache_key(payload)

    cached = redis_get_json(cache_key)
    if cached:
        # Still log "served from cache" as best effort
        try:
            db_log_solve(req=req, out=cached, latency_ms=0, error=None)
        except Exception:
            pass

        return SolveResponse(
            final_answer=cached.get("final_answer", ""),
            steps=cached.get("steps", []),
            assumptions=cached.get("assumptions", []),
            confidence=float(cached.get("confidence", 0.5)),
            flags=cached.get("flags", []) + ["CACHED"],
            safe_note=cached.get("safe_note"),
            meta={"engine": "knoweasy-orchestrator-phase1"},
        )

    try:
        t0 = time.perf_counter()
        acquired = _SOLVE_SEM.acquire(timeout=_SOLVE_QUEUE_WAIT_SECONDS)
        if not acquired:
            return JSONResponse(
                status_code=503,
                content=_safe_failure(
                    "High traffic right now. Please try again in a few seconds 😊",
                    "OVERLOADED",
                ).model_dump(),
            )

        try:
            out = solve(payload)
        finally:
            try:
                _SOLVE_SEM.release()
            except Exception:
                pass

        latency_ms = int((time.perf_counter() - t0) * 1000)

        # Best-effort DB log (never breaks the response)
        db_log_solve(req=req, out=out, latency_ms=latency_ms, error=None)

        # Cache successful output (best-effort)
        if isinstance(out, dict) and out.get("final_answer"):
            try:
                redis_setex_json(cache_key, SOLVE_CACHE_TTL_SECONDS, out)
            except Exception:
                pass

        return SolveResponse(
            final_answer=out.get("final_answer", ""),
            steps=out.get("steps", []),
            assumptions=out.get("assumptions", []),
            confidence=float(out.get("confidence", 0.5)),
            flags=out.get("flags", []),
            safe_note=out.get("safe_note"),
            meta={"engine": "knoweasy-orchestrator-phase1"},
        )

    except Exception as e:
        # Don't leak raw errors to the student UI; keep response stable + CORS-safe.
        try:
            db_log_solve(req=req, out=None, latency_ms=None, error=str(e))
        except Exception:
            pass

        return _safe_failure(
            "Luma had a small hiccup while solving. Please try again in a few seconds 😊",
            "SERVER_ERROR",
        )


# Backward-compatible alias (some older frontends may call /ask)
@router.post("/ask", response_model=SolveResponse)
def ask_route(
    req: SolveRequest,
    request: Request,
    x_ke_key: str | None = Header(default=None, alias="X-KE-KEY"),
):
    return solve_route(req, request, x_ke_key=x_ke_key)