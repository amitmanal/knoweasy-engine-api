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

from redis_store import get_json as redis_get_json
from redis_store import setex_json as redis_setex_json
from redis_store import incr_with_ttl as redis_incr_with_ttl

from auth_store import session_user
from payments_store import get_subscription
import billing_store

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
        "class_level": (payload.get("class_level") or "").strip(),
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

    ip = _client_ip(request)
    if not _rate_limit_ok(ip):
        return JSONResponse(
            status_code=429,
            content=_safe_failure(
                "Too many requests right now. Please try again in a minute 😊",
                "RATE_LIMITED",
            ).model_dump(),
        )

    # -------- Optional auth + credit enforcement (best-effort) --------
    # If a Bearer token is present, we enforce plan/credits. If not present, we behave as anonymous free.
    auth_header = (request.headers.get("authorization") or request.headers.get("Authorization") or "").strip()
    user_ctx = None
    sub = None
    wallet = None
    credits_units_charged = 0

    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        try:
            user_ctx = session_user(token)
        except Exception:
            return JSONResponse(
                status_code=401,
                content=_safe_failure(
                    "Session expired. Please login again.",
                    "AUTH_EXPIRED",
                ).model_dump(),
            )

        try:
            sub = get_subscription(int(user_ctx["user_id"]))
            plan = (sub.get("plan") or "free").lower().strip() or "free"

            q = (req.question or "").strip()
            # Simple, stable units estimator (tunable later)
            units = 120 + max(0, len(q) // 20)
            units = max(60, min(600, int(units)))

            # Consume credits (402 if insufficient)
            try:
                out = billing_store.consume_credits(int(user_ctx["user_id"]), plan, units, meta={"route": "/solve", "answer_mode": req.answer_mode, "subject": req.subject, "board": req.board})
                wallet = out
                credits_units_charged = int(out.get("consumed") or units)
            except ValueError:
                return JSONResponse(
                    status_code=402,
                    content=_safe_failure(
                        "You have used all your AI credits. Please buy a Booster Pack or upgrade your plan.",
                        "OUT_OF_CREDITS",
                    ).model_dump(),
                )
        except Exception:
            # If billing fails, we do NOT block solving (stability first)
            pass

    # -------- Cache (best-effort) --------
    payload = req.model_dump()
    cache_key = _cache_key(payload)

    cached = redis_get_json(cache_key)
    if cached:
        # Still log "served from cache" as best effort
        try:
            db_log_solve(req=req, out=cached, latency_ms=0, error=None)
        except Exception:
            pass

        # Attach billing info (best-effort) without breaking old clients
        try:
            if user_ctx and isinstance(out, dict):
                out_flags = list(out.get("flags", []) or [])
                out_flags.append("BILLED")
                out["flags"] = out_flags
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
            flags=(out.get("flags", []) or []) + (["AUTH"] if user_ctx else []),
            safe_note=out.get("safe_note"),
            meta={
                "engine": "knoweasy-orchestrator-phase1",
                "billing": {
                    "user_id": int(user_ctx["user_id"]) if user_ctx else None,
                    "plan": (sub.get("plan") if isinstance(sub, dict) else None) if user_ctx else None,
                    "credits_units_charged": int(credits_units_charged) if user_ctx else 0,
                    "wallet": wallet if user_ctx else None,
                },
            },
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
