# router.py - Enhanced v2
# KnowEasy AI Backend - Production Ready
# Features: Request tracing, comprehensive logging, proper AI metadata return

import hashlib
import json
import time
import os
import asyncio
import uuid
from typing import Dict, Tuple

from fastapi import APIRouter, Request, Header
from fastapi.responses import JSONResponse
import logging

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
from orchestrator import solve, get_orchestrator_stats
from db import db_log_solve, db_log_ai_usage

from redis_store import get_json as redis_get_json
from redis_store import setex_json as redis_setex_json
from redis_store import incr_with_ttl as redis_incr_with_ttl
from redis_store import setnx_ex as redis_setnx_ex

from auth_store import session_user
from payments_store import get_subscription
import billing_store

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger("knoweasy.router")

router = APIRouter()


# ============================================================================
# CONFIGURATION
# ============================================================================

_MAX_CONCURRENT_SOLVES = int(os.getenv("MAX_CONCURRENT_SOLVES", "40"))
_SOLVE_SEM = asyncio.Semaphore(max(1, _MAX_CONCURRENT_SOLVES))

# In-memory rate limit buckets (fallback if Redis unavailable)
_BUCKETS: Dict[str, Tuple[float, int]] = {}

_COST_USD_PER_1K = {
    "gemini": float(os.getenv("COST_USD_PER_1K_GEMINI", "0.05")) or 0.05,
    "openai": float(os.getenv("COST_USD_PER_1K_OPENAI", "0.15")) or 0.15,
    "claude": float(os.getenv("COST_USD_PER_1K_CLAUDE", "0.30")) or 0.30,
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _generate_request_id() -> str:
    """Generate unique request ID for tracing"""
    return str(uuid.uuid4())[:12]


def _estimate_tokens_from_chars(n_chars: int) -> int:
    """Rough token estimation: ~4 chars per token"""
    try:
        return max(1, int(n_chars) // 4)
    except Exception:
        return 1


def _estimate_cost_usd(provider: str, tokens_total: int) -> float:
    rate = _COST_USD_PER_1K.get((provider or "").lower(), 0.1)
    try:
        return (float(tokens_total) / 1000.0) * float(rate)
    except Exception:
        return 0.0


def _usd_to_inr(usd: float) -> float:
    try:
        fx = float(os.getenv("USD_INR", "83"))
        return float(usd) * fx
    except Exception:
        return 0.0


def _client_ip(req: Request) -> str:
    xff = req.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if req.client:
        return req.client.host or "unknown"
    return "unknown"


def _rate_limit_ok(ip: str) -> bool:
    """Check rate limit via Redis or in-memory fallback"""
    limit = RATE_LIMIT_PER_MINUTE + RATE_LIMIT_BURST
    window_s = int(RATE_LIMIT_WINDOW_SECONDS)

    now = time.time()
    bucket = int(now // window_s)
    redis_key = f"rl:{ip}:{bucket}"
    rc = redis_incr_with_ttl(redis_key, window_s)
    if rc is not None:
        return rc <= limit

    # In-memory fallback
    start, count = _BUCKETS.get(ip, (now, 0))
    if now - start >= window_s:
        start, count = now, 0

    if count >= limit:
        _BUCKETS[ip] = (start, count)
        return False

    _BUCKETS[ip] = (start, count + 1)
    return True


def _safe_failure(message: str, code: str, request_id: str = "") -> SolveResponse:
    """Create safe failure response"""
    return SolveResponse(
        final_answer=message,
        steps=[],
        assumptions=[],
        confidence=0.2,
        flags=[code],
        safe_note="Try rephrasing your question or adding more context.",
        meta={
            "engine": "knoweasy-orchestrator-v2",
            "request_id": request_id,
            "error_code": code
        },
    )


def _cache_key(payload: dict) -> str:
    """Generate stable cache key"""
    normalized = {
        "board": (payload.get("board") or "").strip().lower(),
        "class": str(payload.get("class_") or payload.get("class_level") or payload.get("class") or "").strip(),
        "subject": (payload.get("subject") or "").strip().lower(),
        "chapter": (payload.get("chapter") or "").strip().lower(),
        "exam_mode": str(payload.get("exam_mode") or "").strip().upper(),
        "language": (payload.get("language") or "en").strip().lower(),
        "study_mode": (payload.get("study_mode") or "chat").strip().lower(),
        # IMPORTANT: mode/answer_mode must be part of cache key, otherwise
        # Lite/Tutor/Mastery could incorrectly share the same cached answer.
        "mode": (payload.get("mode") or "").strip().lower(),
        "answer_mode": (payload.get("answer_mode") or payload.get("answerMode") or "").strip().lower(),
        "question": (payload.get("question") or "").strip(),
    }
    blob = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    return f"cache:solve:{hashlib.sha256(blob.encode()).hexdigest()[:32]}"


def _normalize_answer_mode(v: str) -> str:
    m = str(v or "").strip().lower()
    if not m:
        return "luma_tutor"

    # Backward compatible aliases (old UI)
    if m in {"quick"}:
        return "luma_lite"
    if m in {"deep"}:
        return "luma_tutor"
    if m in {"exam"}:
        return "luma_mastery"

    # New canonical mode names
    if m in {"lite", "luma_lite"}:
        return "luma_lite"
    if m in {"tutor", "luma_tutor"}:
        return "luma_tutor"
    if m in {"mastery", "luma_mastery"}:
        return "luma_mastery"

    # Legacy internal keys still supported
    if m in {"one_liner"}:
        return "luma_lite"
    if m in {"step_by_step"}:
        return "luma_tutor"
    if m in {"cbse_board"}:
        return "luma_mastery"

    return m

def _extract_context(payload: dict) -> dict:
    """Extract structured context from payload"""
    luma_context = payload.get("context") or {}
    
    raw_mode = str(payload.get("answer_mode") or payload.get("answerMode") or payload.get("mode") or "").strip().lower()
    normalized_mode = _normalize_answer_mode(raw_mode)
    return {
        "board": str(payload.get("board") or "cbse").strip().upper(),
        "class": str(payload.get("class_") or payload.get("class_level") or payload.get("class") or "11").strip(),
        "subject": str(payload.get("subject") or "").strip(),
        "chapter": str(payload.get("chapter") or "").strip(),
        "exam_mode": str(payload.get("exam_mode") or "BOARD").strip().upper(),
        "language": str(payload.get("language") or "en").strip().lower(),
        "study_mode": str(payload.get("study_mode") or "chat").strip().lower(),
        # Canonical mode for the orchestrator (Luma Lite / Tutor / Mastery)
        "answer_mode": normalized_mode,
        # Keep raw "mode" field for backward compatibility / UI display
        "mode": raw_mode,
        "visible_text": str(luma_context.get("visible_text") or "")[:600],
        "anchor_example": str(luma_context.get("anchor_example") or "")[:300],
        "section": str(luma_context.get("section") or ""),
        "card_type": str(luma_context.get("card_type") or ""),
    }


def _determine_user_tier(user_ctx: dict | None, sub: dict | None) -> str:
    """Determine user tier from subscription"""
    if not user_ctx or not sub:
        return "free"
    
    try:
        plan = str((sub.get("plan") or "free")).lower().strip()
        if plan in ("max", "family", "premium", "enterprise"):
            return "max"
        elif plan in ("pro", "plus", "standard"):
            return "pro"
        return "free"
    except Exception:
        return "free"


def _format_response(result: dict, request_id: str) -> dict:
    """Format orchestrator response to SolveResponse format"""
    
    if not result:
        return {
            "final_answer": "I couldn't process your question. Please try again.",
            "steps": [],
            "assumptions": [],
            "confidence": 0.3,
            "flags": ["AI_ERROR"],
            "safe_note": None,
            "meta": {"request_id": request_id}
        }
    
    # Handle error cases
    if result.get("error") or not result.get("success", True):
        return {
            "final_answer": result.get("answer") or "Sorry, I encountered an issue. Please try again.",
            "steps": [],
            "assumptions": [],
            "confidence": 0.2,
            "flags": ["AI_ERROR"],
            "safe_note": None,
            "meta": {
                "request_id": request_id,
                "error": result.get("error")
            }
        }
    
    # Success case
    answer = result.get("answer") or result.get("final_answer") or ""
    
    # Build informative flags
    flags = []
    if result.get("ai_strategy"):
        flags.append(result["ai_strategy"].upper())
    if result.get("confidence_label"):
        flags.append(str(result["confidence_label"]).upper())
    if result.get("providers_used"):
        for p in result["providers_used"]:
            flags.append(f"AI_{p.upper()}")
    if result.get("cached"):
        flags.append("CACHED")
    
    return {
        "final_answer": answer,
        "steps": result.get("steps", []),
        "assumptions": result.get("assumptions", []),
        "confidence": float(result.get("confidence", 0.85)),
        "flags": flags,
        "safe_note": result.get("safe_note"),
        "meta": {
            "engine": "knoweasy-orchestrator-v2",
            "request_id": request_id,
            "ai_strategy": result.get("ai_strategy"),
            "providers_used": result.get("providers_used", []),
            "complexity": result.get("complexity"),
            "tokens": result.get("tokens_used", result.get("tokens", 0)),
            "response_time_ms": result.get("response_time_ms", 0),
            "credits_used": result.get("credits_used", 0),
            "cost_inr": result.get("cost_inr", 0),
            "premium_formatting": result.get("premium_formatting", False),
            "sections": result.get("sections"),
            "confidence_label": result.get("confidence_label"),
            "verified": bool(result.get("verified")),
            "verifier_provider": result.get("verifier_provider"),
        }
    }


# ============================================================================
# MAIN SOLVE ENDPOINT
# ============================================================================

@router.post("/solve", response_model=SolveResponse)
async def solve_route(
    req: SolveRequest,
    request: Request,
    x_ke_key: str | None = Header(default=None, alias="X-KE-KEY"),
):
    """
    Main AI solve endpoint - Production Grade
    
    Features:
    - Request tracing via request_id
    - Rate limiting (Redis + in-memory fallback)
    - Auth validation
    - Caching with TTL
    - Credit billing
    - Comprehensive logging
    """
    
    # Generate request ID for tracing
    trace_id = _generate_request_id()
    start_time = time.perf_counter()
    
    logger.info(f"📥 [{trace_id}] New /solve request from {_client_ip(request)}")
    
    # API key validation (optional guardrail)
    if KE_API_KEY:
        if not x_ke_key or x_ke_key.strip() != KE_API_KEY:
            logger.warning(f"🔒 [{trace_id}] Unauthorized request")
            return JSONResponse(
                status_code=401,
                content=_safe_failure(
                    "Unauthorized request. Please open the app from the official KnowEasy website.",
                    "UNAUTHORIZED",
                    trace_id
                ).model_dump(),
            )

    # Rate limiting
    ip = _client_ip(request)
    if not _rate_limit_ok(ip):
        logger.warning(f"⚠️ [{trace_id}] Rate limited: {ip}")
        return JSONResponse(
            status_code=429,
            content=_safe_failure(
                "Too many requests right now. Please try again in a minute 😊",
                "RATE_LIMITED",
                trace_id
            ).model_dump(),
        )

    # Auth handling
    auth_header = (request.headers.get("authorization") or "").strip()
    user_ctx = None
    sub = None
    wallet = None
    credits_units_charged = 0

    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        try:
            user_ctx = session_user(token)
            logger.info(f"👤 [{trace_id}] Authenticated user: {user_ctx.get('user_id')}")
        except Exception as e:
            logger.warning(f"🔒 [{trace_id}] Auth failed: {e}")
            return JSONResponse(
                status_code=401,
                content=_safe_failure(
                    "Session expired. Please login again.",
                    "AUTH_EXPIRED",
                    trace_id
                ).model_dump(),
            )
        
        try:
            sub = get_subscription(int(user_ctx["user_id"]))
        except Exception:
            sub = None

    # Payload and caching
    payload = req.model_dump()

    # Idempotency handling
    client_request_id = (getattr(req, "request_id", None) or "").strip() or None
    if client_request_id:
        rid_key = f"rid:solve:{client_request_id}"
        prior = redis_get_json(rid_key)
        if prior and isinstance(prior, dict) and prior.get("final_answer"):
            logger.info(f"♻️ [{trace_id}] Returning idempotent cached response")
            return SolveResponse(**prior)

        try:
            lock_key = f"lock:rid:solve:{client_request_id}"
            got_lock = redis_setnx_ex(lock_key, 30, "1")
            if not got_lock:
                await asyncio.sleep(0.35)
                prior2 = redis_get_json(rid_key)
                if prior2 and isinstance(prior2, dict) and prior2.get("final_answer"):
                    return SolveResponse(**prior2)
        except Exception:
            pass

    # Cache check
    cache_key = _cache_key(payload)
    cached = redis_get_json(cache_key)
    
    if cached:
        logger.info(f"⚡ [{trace_id}] Cache HIT")
        
        try:
            db_log_solve(req=req, out=cached, latency_ms=0, error=None)
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
                "engine": "knoweasy-orchestrator-v2",
                "request_id": trace_id,
                "served_from_cache": True,
                "billing": {
                    "user_id": int(user_ctx["user_id"]) if user_ctx else None,
                    "credits_units_charged": 0,
                },
                **(cached.get("meta") or {})
            },
        )

    # Billing pre-check
    planned_units = 0
    planned_plan = None

    if user_ctx:
        try:
            planned_plan = (((sub or {}).get("plan") or "free") if isinstance(sub, dict) else "free").lower().strip() or "free"
            q = (req.question or "").strip()
            planned_units = 120 + max(0, len(q) // 20)
            planned_units = max(60, min(600, int(planned_units)))

            try:
                w_preview = billing_store.get_wallet(int(user_ctx["user_id"]), planned_plan)
                total_preview = int(w_preview.get("included_credits_balance") or 0) + int(w_preview.get("booster_credits_balance") or 0)
                if total_preview < int(planned_units):
                    logger.warning(f"💰 [{trace_id}] Insufficient credits")
                    return JSONResponse(
                        status_code=402,
                        content=_safe_failure(
                            "You have used all your AI credits. Please buy a Booster Pack or upgrade your plan.",
                            "OUT_OF_CREDITS",
                            trace_id
                        ).model_dump(),
                    )
            except ValueError:
                return JSONResponse(
                    status_code=402,
                    content=_safe_failure(
                        "You have used all your AI credits. Please buy a Booster Pack or upgrade your plan.",
                        "OUT_OF_CREDITS",
                        trace_id
                    ).model_dump(),
                )
            except Exception:
                planned_units = 0
                planned_plan = None
        except Exception:
            planned_units = 0
            planned_plan = None

    # ========================================================================
    # EXECUTE AI SOLVE
    # ========================================================================
    
    try:
        async with _SOLVE_SEM:
            question = str(req.question or "").strip()
            context = _extract_context(payload)
            user_tier = _determine_user_tier(user_ctx, sub)
            
            logger.info(f"🤖 [{trace_id}] Calling orchestrator | tier={user_tier} | mode={context.get('study_mode')}")
            
            # Call the orchestrator (properly awaited)
            raw_result = await solve(question, context, user_tier)
            
            # Format response
            out = _format_response(raw_result, trace_id)

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(f"✅ [{trace_id}] Solve complete | {latency_ms}ms | strategy={raw_result.get('ai_strategy')}")

        # Log to database
        try:
            db_log_solve(req=req, out=out, latency_ms=latency_ms, error=None)
        except Exception:
            pass

        # Cache successful response
        if isinstance(out, dict) and out.get("final_answer"):
            try:
                redis_setex_json(cache_key, SOLVE_CACHE_TTL_SECONDS, out)
            except Exception:
                pass

        # Billing: Deduct credits on success
        if user_ctx and planned_plan and planned_units and isinstance(out, dict) and out.get("final_answer"):
            actual_credits = raw_result.get("credits_used") or planned_units
            try:
                wallet_out = billing_store.consume_credits(
                    int(user_ctx["user_id"]),
                    planned_plan,
                    int(actual_credits),
                    meta={
                        "route": "/solve",
                        "request_id": trace_id,
                        "ai_strategy": raw_result.get("ai_strategy"),
                        "subject": req.subject,
                        "board": req.board,
                    },
                )
                wallet = wallet_out
                credits_units_charged = int(wallet_out.get("consumed") or actual_credits)
                logger.info(f"💳 [{trace_id}] Credits charged: {credits_units_charged}")
            except ValueError:
                credits_units_charged = 0
                try:
                    wallet = billing_store.get_wallet(int(user_ctx["user_id"]), planned_plan)
                except Exception:
                    wallet = None
            except Exception:
                credits_units_charged = 0

        # Telemetry logging
        try:
            q = (req.question or "")
            question_len = len(q)
            ans = str(out.get("final_answer", "") or "")
            answer_len = len(ans)
            tokens_in = _estimate_tokens_from_chars(question_len)
            tokens_out = _estimate_tokens_from_chars(answer_len)
            tokens_total = raw_result.get("tokens_used") or (tokens_in + tokens_out)
            provider = raw_result.get("provider") or "gemini"
            
            cost_usd = _estimate_cost_usd(provider, tokens_total)
            
            db_log_ai_usage({
                "user_id": int(user_ctx["user_id"]) if user_ctx else None,
                "role": (user_ctx.get("role") if user_ctx else None),
                "plan": planned_plan,
                "request_type": "TEXT",
                "credit_bucket": int(planned_units) if planned_units else 0,
                "credits_charged": credits_units_charged,
                "model_primary": provider,
                "ai_strategy": raw_result.get("ai_strategy"),
                "cache_hit": False,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "estimated_cost_usd": cost_usd,
                "estimated_cost_inr": _usd_to_inr(cost_usd),
                "latency_ms": latency_ms,
                "status": "SUCCESS" if ans else "FAILED",
                "question_len": question_len,
                "answer_len": answer_len,
                "error": None,
            })
        except Exception:
            pass

        # Build final response
        final_flags = list(out.get("flags", []) or [])
        if user_ctx:
            final_flags.append("AUTH")

        # Add AI metadata to meta for frontend
        meta = out.get("meta") or {}
        meta["billing"] = {
            "user_id": int(user_ctx["user_id"]) if user_ctx else None,
            "plan": planned_plan,
            "credits_units_charged": credits_units_charged,
            "wallet": wallet,
            "served_from_cache": False,
        }

        resp = SolveResponse(
            final_answer=out.get("final_answer", ""),
            steps=out.get("steps", []),
            assumptions=out.get("assumptions", []),
            confidence=float(out.get("confidence", 0.85)),
            flags=final_flags,
            safe_note=out.get("safe_note"),
            meta=meta,
        )

        # Save for idempotency
        if client_request_id and resp.final_answer:
            try:
                rid_key = f"rid:solve:{client_request_id}"
                redis_setex_json(rid_key, 10 * 60, resp.model_dump())
            except Exception:
                pass

        return resp

    except asyncio.TimeoutError:
        logger.error(f"⏱️ [{trace_id}] Semaphore timeout")
        return JSONResponse(
            status_code=503,
            content=_safe_failure(
                "High traffic right now. Please try again in a few seconds 😊",
                "TIMEOUT",
                trace_id
            ).model_dump(),
        )
    except Exception as e:
        logger.error(f"❌ [{trace_id}] Error: {e}")
        
        try:
            db_log_solve(req=req, out=None, latency_ms=None, error=str(e))
        except Exception:
            pass

        return _safe_failure(
            "Luma had a small hiccup while solving. Please try again in a few seconds 😊",
            "SERVER_ERROR",
            trace_id
        )


# ============================================================================
# ADDITIONAL ENDPOINTS
# ============================================================================

@router.post("/ask", response_model=SolveResponse)
async def ask_route(
    req: SolveRequest,
    request: Request,
    x_ke_key: str | None = Header(default=None, alias="X-KE-KEY"),
):
    """Backward-compatible alias for /solve"""
    return await solve_route(req, request, x_ke_key=x_ke_key)


@router.get("/ai/stats")
async def ai_stats():
    """Get AI orchestrator statistics (for monitoring)"""
    try:
        stats = get_orchestrator_stats()
        return {"status": "ok", "stats": stats}
    except Exception as e:
        return {"status": "error", "error": str(e)}
