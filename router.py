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
from config import (
    AI_PROVIDER,
    AI_MODE,
    GEMINI_PRIMARY_MODEL,
    OPENAI_MODEL,
)
from schemas import SolveRequest, SolveResponse
from orchestrator import solve
from db import db_log_solve, db_log_ai_usage

from redis_store import get_json as redis_get_json
from redis_store import setex_json as redis_setex_json
from redis_store import incr_with_ttl as redis_incr_with_ttl
from redis_store import setnx_ex as redis_setnx_ex

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

_COST_USD_PER_1K = {
    "gemini": float(os.getenv("COST_USD_PER_1K_GEMINI", "0")) or None,
    "openai": float(os.getenv("COST_USD_PER_1K_OPENAI", "0")) or None,
    "claude": float(os.getenv("COST_USD_PER_1K_CLAUDE", "0")) or None,
}


def _estimate_tokens_from_chars(n_chars: int) -> int:
    # Rough heuristic: ~4 chars per token (works reasonably for English + mixed).
    try:
        n = int(n_chars)
    except Exception:
        n = 0
    return max(1, n // 4)


def _estimate_cost_usd(provider: str, tokens_total: int) -> float | None:
    rate = _COST_USD_PER_1K.get((provider or "").lower())
    if not rate:
        return None
    try:
        return (float(tokens_total) / 1000.0) * float(rate)
    except Exception:
        return None


def _usd_to_inr(usd: float | None) -> float | None:
    if usd is None:
        return None
    try:
        fx = float(os.getenv("USD_INR", "83"))
        return float(usd) * fx
    except Exception:
        return None


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
    # NOTE: `SolveRequest` accepts both `class` and `class_level` on input, but
    # the Pydantic model field name is `class_`. `req.model_dump()` therefore
    # contains `class_`.
    #
    # IMPORTANT: Include all fields that can change the prompt/answer.
    # Otherwise, we risk serving a cached answer from a different context
    # (e.g., wrong chapter/exam_mode/language).
    normalized = {
        "board": (payload.get("board") or "").strip(),
        "class": str(payload.get("class_") or payload.get("class_level") or payload.get("class") or "").strip(),
        "subject": (payload.get("subject") or "").strip(),
        "chapter": (payload.get("chapter") or "").strip(),
        "exam_mode": str(payload.get("exam_mode") or "").strip(),
        "language": (payload.get("language") or "").strip(),
        "explain_like": str(payload.get("explain_like") or payload.get("explain_level") or payload.get("explain_level") or "").strip(),
        "answer_mode": (payload.get("answer_mode") or "").strip(),
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

    # -------- Optional auth (best-effort) --------
    # If a Bearer token is present, we validate session and (on cache MISS)
    # enforce plan/credits. If no token, behave as anonymous free.
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

        # Subscription lookup is cheap; we do it early so cached responses can
        # still return plan info in meta (without charging credits).
        try:
            sub = get_subscription(int(user_ctx["user_id"]))
        except Exception:
            sub = None

    # -------- Cache FIRST (best-effort) --------
    # IMPORTANT: Never charge credits on cache hit.
    payload = req.model_dump()

    # -------- Trust-safe retry (idempotency by request_id) --------
    # If the client provides request_id, we replay the exact prior response
    # (including billing meta) so offline retries never double-charge.
    request_id = (getattr(req, "request_id", None) or "").strip() or None
    if request_id:
        rid_key = f"rid:solve:{request_id}"
        prior = redis_get_json(rid_key)
        if prior and isinstance(prior, dict) and prior.get("final_answer"):
            return SolveResponse(**prior)

        # Best-effort lock reduces rare parallel double-processing for same request_id.
        # If Redis is unavailable, we simply proceed (cache behavior remains).
        try:
            lock_key = f"lock:rid:solve:{request_id}"
            got_lock = redis_setnx_ex(lock_key, 30, "1")
            if not got_lock:
                # Another worker may be processing. Wait briefly and re-check.
                time.sleep(0.35)
                prior2 = redis_get_json(rid_key)
                if prior2 and isinstance(prior2, dict) and prior2.get("final_answer"):
                    return SolveResponse(**prior2)
        except Exception:
            pass
    cache_key = _cache_key(payload)

    cached = redis_get_json(cache_key)
    if cached:
        # Still log "served from cache" as best effort
        try:
            db_log_solve(req=req, out=cached, latency_ms=0, error=None)
        except Exception:
            pass
        # Phase-4A telemetry (best-effort; never affects user)
        try:
            q = (req.question or "")
            question_len = len(q)
            answer_len = len(str(cached.get("final_answer", "") or ""))
            tokens_in = _estimate_tokens_from_chars(question_len)
            tokens_out = _estimate_tokens_from_chars(answer_len)
            tokens_total = tokens_in + tokens_out
            provider = (AI_PROVIDER or "gemini").lower()
            cost_usd = _estimate_cost_usd(provider, tokens_total)
            db_log_ai_usage(
                {
                    "user_id": int(user_ctx["user_id"]) if user_ctx else None,
                    "role": (user_ctx.get("role") if user_ctx else None),
                    "plan": (sub.get("plan") if isinstance(sub, dict) else None) if user_ctx else None,
                    "request_type": "TEXT",
                    "credit_bucket": 0,
                    "credits_charged": 0,
                    "model_primary": provider,
                    "model_escalated": None,
                    "cache_hit": True,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "estimated_cost_usd": cost_usd,
                    "estimated_cost_inr": _usd_to_inr(cost_usd),
                    "latency_ms": 0,
                    "status": "CACHE",
                    "question_len": question_len,
                    "answer_len": answer_len,
                    "error": None,
                }
            )
        except Exception:
            pass

        cached_flags = list(cached.get("flags", []) or [])
        cached_flags.append("CACHED")
        if user_ctx:
            cached_flags.append("AUTH")

        return SolveResponse(
            final_answer=cached.get("final_answer", ""),
            steps=cached.get("steps", []),
            assumptions=cached.get("assumptions", []),
            confidence=float(cached.get("confidence", 0.5)),
            flags=cached_flags,
            safe_note=cached.get("safe_note"),
            meta={
                "engine": "knoweasy-orchestrator-phase1",
                "billing": {
                    "user_id": int(user_ctx["user_id"]) if user_ctx else None,
                    "plan": (sub.get("plan") if isinstance(sub, dict) else None) if user_ctx else None,
                    "credits_units_charged": 0,
                    "wallet": None,
                    "served_from_cache": True,
                },
            },
        )

    # -------- Billing ONLY on cache miss (best-effort) --------
    # TRUST RULE: Never deduct credits unless we are returning a real answer.
    # We do a lightweight sufficiency check up-front, then deduct only after a successful solve.
    planned_units = 0
    planned_plan = None

    if user_ctx:
        try:
            planned_plan = (((sub or {}).get("plan") or "free") if isinstance(sub, dict) else "free").lower().strip() or "free"

            q = (req.question or "").strip()
            # Simple, stable units estimator (tunable later)
            planned_units = 120 + max(0, len(q) // 20)
            planned_units = max(60, min(600, int(planned_units)))

            # Pre-check wallet so we can fail fast (no solve) when clearly out of credits.
            # Note: final atomic deduction happens after solve success.
            try:
                w_preview = billing_store.get_wallet(int(user_ctx["user_id"]), planned_plan)
                total_preview = int(w_preview.get("included_credits_balance") or 0) + int(w_preview.get("booster_credits_balance") or 0)
                if total_preview < int(planned_units):
                    return JSONResponse(
                        status_code=402,
                        content=_safe_failure(
                            "You have used all your AI credits. Please buy a Booster Pack or upgrade your plan.",
                            "OUT_OF_CREDITS",
                        ).model_dump(),
                    )
            except ValueError:
                return JSONResponse(
                    status_code=402,
                    content=_safe_failure(
                        "You have used all your AI credits. Please buy a Booster Pack or upgrade your plan.",
                        "OUT_OF_CREDITS",
                    ).model_dump(),
                )
            except Exception:
                # If billing pre-check fails, we do NOT block solving (stability first)
                planned_units = 0
                planned_plan = None
        except Exception:
            planned_units = 0
            planned_plan = None

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
        try:
            db_log_solve(req=req, out=out, latency_ms=latency_ms, error=None)
        except Exception:
            pass

        # Cache successful output (best-effort)
        if isinstance(out, dict) and out.get("final_answer"):
            try:
                redis_setex_json(cache_key, SOLVE_CACHE_TTL_SECONDS, out)
            except Exception:
                pass


        # -------- Deduct credits ONLY after successful solve --------
        # If solve did not produce a final answer, we charge nothing.
        if user_ctx and planned_plan and planned_units and isinstance(out, dict) and out.get("final_answer"):
            try:
                wallet_out = billing_store.consume_credits(
                    int(user_ctx["user_id"]),
                    planned_plan,
                    int(planned_units),
                    meta={
                        "route": "/solve",
                        "answer_mode": req.answer_mode,
                        "subject": req.subject,
                        "board": req.board,
                        "exam_mode": req.exam_mode,
                        "chapter": req.chapter,
                        "language": req.language,
                    },
                )
                wallet = wallet_out
                credits_units_charged = int(wallet_out.get("consumed") or planned_units)
            except ValueError:
                # Race/concurrency edge: user spent credits in another request.
                # Do NOT block the answer; do NOT charge.
                credits_units_charged = 0
                try:
                    wallet = billing_store.get_wallet(int(user_ctx["user_id"]), planned_plan)
                except Exception:
                    wallet = None
                try:
                    flags = list(out.get("flags", []) or [])
                    flags.append("BILLING_DESYNC")
                    out["flags"] = flags
                except Exception:
                    pass
            except Exception:
                credits_units_charged = 0
                # Do not block solve on billing write failure.
                # Keep wallet as None to avoid showing incorrect balances.


        # Phase-4A telemetry (best-effort; never affects user)
        try:
            q = (req.question or "")
            question_len = len(q)
            # include steps length in answer_len rough
            ans = str(out.get("final_answer", "") or "")
            steps = out.get("steps") or []
            answer_len = len(ans) + sum(len(str(x)) for x in steps)
            tokens_in = _estimate_tokens_from_chars(question_len)
            tokens_out = _estimate_tokens_from_chars(answer_len)
            tokens_total = tokens_in + tokens_out
            provider = (AI_PROVIDER or "gemini").lower()
            model_variant = None
            if provider == "gemini":
                model_variant = GEMINI_PRIMARY_MODEL
            elif provider == "openai":
                model_variant = OPENAI_MODEL

            cost_usd = _estimate_cost_usd(provider, tokens_total)
            db_log_ai_usage(
                {
                    "user_id": int(user_ctx["user_id"]) if user_ctx else None,
                    "role": (user_ctx.get("role") if user_ctx else None),
                    "plan": (sub.get("plan") if isinstance(sub, dict) else None) if user_ctx else None,
                    "request_type": "TEXT",
                    "credit_bucket": int(planned_units) if planned_units else 0,
                    "credits_charged": int(credits_units_charged) if credits_units_charged else 0,
                    "model_primary": provider,
                    "model_escalated": None,
                    "cache_hit": False,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "estimated_cost_usd": cost_usd,
                    "estimated_cost_inr": _usd_to_inr(cost_usd),
                    "latency_ms": int(latency_ms) if latency_ms is not None else None,
                    "status": "SUCCESS" if ans else "FAILED",
                    "question_len": question_len,
                    "answer_len": answer_len,
                    "error": None,
                }
            )
        except Exception:
            pass

        resp = SolveResponse(
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
                    "served_from_cache": False,
                },
            },
        )

        # Persist idempotent replay (best-effort). This protects trust when
        # the user retries after network drop: same request_id returns same
        # response without additional credit deductions.
        if request_id and resp.final_answer:
            try:
                rid_key = f"rid:solve:{request_id}"
                redis_setex_json(rid_key, 10 * 60, resp.model_dump())
            except Exception:
                pass

        return resp

    except Exception as e:
        # Don't leak raw errors to the student UI; keep response stable + CORS-safe.
        try:
            db_log_solve(req=req, out=None, latency_ms=None, error=str(e))
        except Exception:
            pass

        try:
            q = (req.question or "")
            question_len = len(q)
            tokens_in = _estimate_tokens_from_chars(question_len)
            provider = (AI_PROVIDER or "gemini").lower()
            db_log_ai_usage({
                "user_id": int(user_ctx["user_id"]) if user_ctx else None,
                "role": (user_ctx.get("role") if user_ctx else None),
                "plan": (sub.get("plan") if isinstance(sub, dict) else None) if user_ctx else None,
                "request_type": "TEXT",
                "credit_bucket": int(planned_units) if planned_units else 0,
                "credits_charged": 0,
                "model_primary": provider,
                "model_escalated": None,
                "cache_hit": False,
                "tokens_in": tokens_in,
                "tokens_out": 0,
                "estimated_cost_usd": None,
                "estimated_cost_inr": None,
                "latency_ms": None,
                "status": "FAILED",
                "question_len": question_len,
                "answer_len": 0,
                "error": str(e),
            })
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
