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

from fastapi import APIRouter, Request, Header, HTTPException
from fastapi.responses import JSONResponse, Response
import logging
from datetime import datetime, timedelta

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
from db import db_log_solve, db_log_ai_usage, db_add_chat_history, db_list_chat_history, db_clear_chat_history, db_get_memory_cards, db_upsert_memory_card, db_reset_memory_cards

from redis_store import get_json as redis_get_json
from redis_store import setex_json as redis_setex_json
from redis_store import incr_with_ttl as redis_incr_with_ttl
from redis_store import setnx_ex as redis_setnx_ex

from auth_store import session_user
from payments_store import get_subscription
import billing_store

from pdf_service import render_learning_object_pdf

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
        "answer_mode": _normalize_answer_mode(payload.get("answer_mode") or payload.get("mode") or ""),
        "language": (payload.get("language") or "en").strip().lower(),
        "study_mode": (payload.get("study_mode") or "chat").strip().lower(),
        "question": (payload.get("question") or "").strip(),
    }
    blob = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    return f"cache:solve:{hashlib.sha256(blob.encode()).hexdigest()[:32]}"


def _normalize_answer_mode(v: str) -> str:
    m = str(v or "").strip().lower()
    if not m:
        return "step_by_step"

    # Phase-4: canonical 3 modes
    if m in {"lite", "luma_lite"}:
        return "one_liner"
    if m in {"tutor", "luma_tutor"}:
        return "step_by_step"
    if m in {"mastery", "luma_mastery"}:
        return "cbse_board"

    # Back-compat with older UI strings
    if m in {"quick"}:
        return "one_liner"
    if m in {"deep"}:
        return "step_by_step"
    if m in {"exam"}:
        return "cbse_board"

    return m


def _class_to_age(class_str: str) -> int:
    """Best-effort age estimation from Indian class level.
    This is used ONLY for safety ceilings, not for personalization claims.
    """
    try:
        n = int(re.search(r"(\d{1,2})", str(class_str or "")).group(1))
    except Exception:
        n = 11
    # Typical: age ≈ class + 5 (Class 1 ~6y)
    return max(5, min(20, n + 5))


def _apply_age_safety(answer_mode: str, context: dict) -> tuple[str, str | None]:
    """Apply age-safe depth ceilings.
    Returns (safe_answer_mode, safe_note_if_downgraded).
    """
    cls = str(context.get("class") or context.get("class_level") or "11")
    age = _class_to_age(cls)

    m = (answer_mode or "step_by_step").lower().strip()
    # mastery maps to cbse_board earlier; detect both labels
    is_mastery = m in {"cbse_board", "mastery", "luma_mastery", "exam"}
    is_tutor = m in {"step_by_step", "tutor", "luma_tutor", "deep"}

    # Ceiling rules (conservative)
    if age <= 9 and is_mastery:
        return ("step_by_step", "Kept it simpler for your level (safe learning depth). You can ask for more detail anytime.")
    if age <= 7 and (is_mastery or is_tutor):
        return ("one_liner", "Kept it very simple for your level (safe learning depth). You can ask for more detail anytime.")

    return (m, None)


def _extract_context(payload: dict) -> dict:
    """Extract structured context from payload"""
    luma_context = payload.get("context") or {}
    
    return {
        "board": str(payload.get("board") or "cbse").strip().upper(),
        "class": str(payload.get("class_") or payload.get("class_level") or payload.get("class") or "11").strip(),
        "subject": str(payload.get("subject") or "").strip(),
        "chapter": str(payload.get("chapter") or "").strip(),
        "exam_mode": str(payload.get("exam_mode") or "BOARD").strip().upper(),
        "language": str(payload.get("language") or "en").strip().lower(),
        "study_mode": str(payload.get("study_mode") or "chat").strip().lower(),
        "mode": str(payload.get("mode") or "").strip().lower(),
        "answer_mode": str(payload.get("answer_mode") or payload.get("answerMode") or payload.get("answerMode".lower()) or "") .strip().lower(),
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
        # Back-compat fields
        "final_answer": answer,
        "answer": answer,

        # Tutor scaffolding
        "steps": result.get("steps", []),
        "assumptions": result.get("assumptions", []),

        # Trust signals
        "confidence": float(result.get("confidence", 0.85)),
        "flags": flags,
        "safe_note": result.get("safe_note"),

        # AnswerObject (preferred)
        "title": result.get("title") or (result.get("learning_object") or {}).get("title"),
        "why_this_matters": result.get("why_this_matters") or (result.get("learning_object") or {}).get("why_this_matters"),
        "sections": result.get("sections") or (result.get("learning_object") or {}).get("sections"),
        "providers_used": result.get("providers_used") or (result.get("learning_object") or {}).get("providers_used"),
        "equation": result.get("equation") or (result.get("learning_object") or {}).get("equation"),

        # Keep nested object too (optional)
        "learning_object": result.get("learning_object"),

        "meta": {
            "engine": "knoweasy-orchestrator-v2",
            "request_id": request_id,
            "ai_strategy": result.get("ai_strategy"),
            "providers_used": result.get("providers_used", []),
            "complexity": result.get("complexity"),
            "mode": result.get("mode") or result.get("answer_mode"),
            "cached": bool(result.get("cached")),
            "latency_ms": int(result.get("latency_ms", 0)),
        }
    }


def _mode_label_from_answer_mode(answer_mode: str) -> str:
    m = str(answer_mode or "").strip().lower()
    if m in {"lite", "one_liner", "luma_lite"}:
        return "Luma Lite"
    if m in {"tutor", "step_by_step", "luma_tutor"}:
        return "Luma Tutor"
    if m in {"mastery", "cbse_board", "luma_mastery"}:
        return "Luma Mastery"
    return "Luma Tutor"



def _default_visual_plan(subject: str, question: str) -> dict | None:
    """Return a small, deterministic visual spec (no extra AI calls).

    Frontend can render this as a "Visual plan" card or later convert to diagrams.
    """
    s = (subject or "").lower()
    q = (question or "").lower()

    if any(k in s for k in ["math", "maths", "physics", "chem", "chemistry"]):
        return {
            "kind": "diagram",
            "title": "Given → Required → Formula → Steps",
            "steps": [
                "Write 'Given' values with units",
                "Write 'Required' (what to find)",
                "Choose the correct formula/law",
                "Substitute values carefully (units!)",
                "Compute and box the final answer",
            ],
        }

    if any(k in q for k in ["difference", "compare", "vs", "versus"]):
        return {
            "kind": "table",
            "title": "Comparison table",
            "steps": [
                "Make 2 columns: A vs B",
                "Add 5–7 rows for key features",
                "End with 1-line summary",
            ],
        }

    if any(k in s for k in ["history", "civics", "geography", "economics", "sst", "social"]):
        return {
            "kind": "concept_map",
            "title": "Mini concept map",
            "steps": [
                "Center: main idea",
                "4 branches: key sub-topics",
                "2 bullets under each branch",
            ],
        }

    return None




def _pick_key_points(text: str, max_points: int = 4) -> list[str]:
    t = (text or "").strip()
    if not t:
        return []
    # Split into sentences (best-effort)
    parts = re.split(r"(?<=[.!?])\s+", t)
    points = []
    for s in parts:
        s = s.strip()
        if 12 <= len(s) <= 160:
            points.append(s)
        if len(points) >= max_points:
            break
    return points


def _common_mistakes_hint(subject: str) -> list[str]:
    s = (subject or "").lower()
    if any(k in s for k in ["math", "maths", "physics"]):
        return [
            "Unit conversion mistake (cm ↔ m, g ↔ kg)",
            "Sign error (+/−) or wrong formula selection",
            "Skipping steps and losing track of variables",
        ]
    if "chem" in s:
        return [
            "Wrong valency/charge while balancing",
            "Mixing up moles, mass, and molar mass",
            "Forgetting conditions (temperature/pressure/catalyst)",
        ]
    return [
        "Memorizing without understanding the core idea",
        "Not reading the question carefully (what is actually asked)",
    ]


def _format_explanation_by_mode(answer: str, answer_mode: str) -> tuple[str, list[str]]:
    m = (answer_mode or "").lower().strip()
    mode_label = _mode_label_from_answer_mode(m)

    if mode_label == "Luma Lite":
        points = _pick_key_points(answer, 3)
        # Keep it short
        short = (answer or "").strip()
        if len(short) > 700:
            short = short[:700].rsplit(" ", 1)[0] + "…"
        return short, points

    if mode_label == "Luma Tutor":
        points = _pick_key_points(answer, 4)
        return (answer or "").strip(), points

    # Luma Mastery
    points = _pick_key_points(answer, 5)
    return (answer or "").strip(), points


def _build_learning_object(*, question: str, answer: str, context: dict, answer_mode: str) -> dict:
    """Create the canonical AnswerObject (Learning Object) payload.

    IMPORTANT: This must match the product schema:
    AnswerObject {
      title, why_this_matters, explanation_blocks, visuals, examples,
      common_mistakes, exam_relevance_footer, follow_up_chips, language, mode
    }

    This wrapper is deterministic and stable.
    External model calls happen in orchestrator.py.
    """
    try:
        from learning_object import build_answer_object, ensure_answer_object_dict
    except Exception:
        build_answer_object = None  # type: ignore
        ensure_answer_object_dict = None  # type: ignore

    board = str(context.get("board") or "").strip()
    klass = str(context.get("class") or context.get("class_level") or "").strip()
    subject = str(context.get("subject") or "").strip()
    exam_mode = str(context.get("exam_mode") or "").strip()
    lang = str(context.get("language") or "en").strip().lower()
    study_mode = str(context.get("study_mode") or "chat").strip().lower()

    mode = (answer_mode or "").lower().strip()
    if mode not in {"lite", "tutor", "mastery"}:
        mode = "tutor"

    if build_answer_object:
        ao = build_answer_object(
            question=question,
            raw_answer=answer,
            language=lang,
            mode=mode,
            board=board,
            class_level=klass,
            subject=subject,
            exam_mode=exam_mode,
            study_mode=study_mode,
        )
        return ensure_answer_object_dict(ao)

    # ultra-safe fallback
    return {
        "title": (question or "Answer")[:120],
        "why_this_matters": "This helps you learn the concept clearly and apply it.",
        "explanation_blocks": [{"title": "Explanation", "content": (answer or "").strip()}],
        "visuals": [],
        "examples": [],
        "common_mistakes": [],
        "exam_relevance_footer": "",
        "follow_up_chips": ["Give me a 2-line recap", "Show 2 practice questions"],
        "language": lang or "en",
        "mode": mode,
    }

@router.post("/export/pdf")
async def export_pdf(request: Request):
    """Export a learning_object to a premium, exam-safe PDF."""

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid JSON"})

    lo = payload.get("learning_object") if isinstance(payload, dict) else None
    if not isinstance(lo, dict):
        return JSONResponse(status_code=400, content={"ok": False, "error": "learning_object is required"})

    mode_in = str(payload.get("mode") or lo.get("mode") or "")
    mode_label = mode_in if "luma" in mode_in.lower() else _mode_label_from_answer_mode(mode_in)
    try:
        pdf_bytes = render_learning_object_pdf(lo, brand="KnowEasy", mode_label=mode_label)
    except Exception as e:
        logger.exception("PDF export failed")
        return JSONResponse(status_code=500, content={"ok": False, "error": "PDF export failed"})

    filename = "KnowEasy_Answer.pdf"
    headers = {
        "Content-Disposition": f"attachment; filename=\"{filename}\""
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


# ============================================================================
# CHAT HISTORY + LEARNING MEMORY (Chat AI only by default; Luma can also store)
# ============================================================================

def _require_auth_user(request: Request) -> dict:
    auth_header = (request.headers.get("authorization") or "").strip()
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="AUTH_REQUIRED")
    token = auth_header.split(" ", 1)[1].strip()
    return session_user(token)


@router.get("/history/list")
async def history_list(request: Request, limit: int = 30):
    """List recent chat history for the logged-in user."""
    try:
        user_ctx = _require_auth_user(request)
        items = db_list_chat_history(int(user_ctx["user_id"]), limit=limit)
        return {"ok": True, "items": items}
    except HTTPException as e:
        raise e
    except Exception:
        return JSONResponse(status_code=500, content={"ok": False, "error": "HISTORY_FETCH_FAILED"})


@router.post("/history/clear")
async def history_clear(request: Request):
    """Clear all chat history for the logged-in user."""
    try:
        user_ctx = _require_auth_user(request)
        db_clear_chat_history(int(user_ctx["user_id"]))
        return {"ok": True}
    except HTTPException as e:
        raise e
    except Exception:
        return JSONResponse(status_code=500, content={"ok": False, "error": "HISTORY_CLEAR_FAILED"})


@router.get("/memory/cards")
async def memory_cards(request: Request):
    """Return compressed learning memory cards (opt-in feature)."""
    try:
        user_ctx = _require_auth_user(request)
        cards = db_get_memory_cards(int(user_ctx["user_id"]))
        return {"ok": True, "cards": cards}
    except HTTPException as e:
        raise e
    except Exception:
        return JSONResponse(status_code=500, content={"ok": False, "error": "MEMORY_FETCH_FAILED"})


@router.post("/memory/reset")
async def memory_reset(request: Request):
    """Reset (delete) learning memory cards for the logged-in user."""
    try:
        user_ctx = _require_auth_user(request)
        db_reset_memory_cards(int(user_ctx["user_id"]))
        return {"ok": True}
    except HTTPException as e:
        raise e
    except Exception:
        return JSONResponse(status_code=500, content={"ok": False, "error": "MEMORY_RESET_FAILED"})



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

    # Payload and context (auto-detect friendly; selectors may be empty)
    payload = req.model_dump()
    context = _extract_context(payload)
    req_answer_mode = _normalize_answer_mode(payload.get("answer_mode") or payload.get("mode") or "")
    req_answer_mode, safety_note = _apply_age_safety(req_answer_mode, context)
    if safety_note:
        context["_safety_note"] = safety_note

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

        lo = cached.get("learning_object") if isinstance(cached, dict) else None
        if not isinstance(lo, dict):
            lo = _build_learning_object(question=req.question, answer=cached.get("final_answer", ""), context=context, answer_mode=req_answer_mode)

        return SolveResponse(
            final_answer=cached.get("final_answer", ""),
            steps=cached.get("steps", []),
            assumptions=cached.get("assumptions", []),
            confidence=float(cached.get("confidence", 0.5)),
            flags=cached_flags,
            safe_note=cached.get("safe_note") or context.get("_safety_note"),
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
            learning_object=lo,
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
            # context already prepared above (auto-detect friendly)
            user_tier = _determine_user_tier(user_ctx, sub)
            
            logger.info(f"🤖 [{trace_id}] Calling orchestrator | tier={user_tier} | mode={context.get('study_mode')}")
            
            # Call the orchestrator (properly awaited)
            raw_result = await solve(question, context=context, answer_mode=req.answer_mode, user_tier=user_tier)
            
            # Format response
            out = _format_response(raw_result, trace_id)

            # Phase-4: deterministic Answer-as-Learning-Object wrapper
            try:
                out["learning_object"] = _build_learning_object(
                    question=question,
                    answer=out.get("final_answer", ""),
                    context=context,
                    answer_mode=req_answer_mode,
                )
            except Exception:
                # Fail-safe: never break /solve due to wrapper
                out["learning_object"] = None
            

            # Phase-4B: Store chat history (trust-first; disabled for private_session)
            try:
                if user_ctx and (not bool(getattr(req, "private_session", False))) and out.get("final_answer"):
                    surface = (getattr(req, "surface", None) or context.get("study_mode") or "chat_ai")
                    db_add_chat_history(
                        user_id=int(user_ctx["user_id"]),
                        surface=str(surface or "chat_ai")[:20],
                        question=question,
                        learning_object=out.get("learning_object"),
                        mode=req_answer_mode,
                        language=context.get("language"),
                    )
            except Exception:
                pass

            # Phase-4B: Update compressed learning memory cards (opt-in)
            try:
                if user_ctx and bool(getattr(req, "memory_opt_in", False)) and (not bool(getattr(req, "private_session", False))):
                    _update_learning_memory_cards(int(user_ctx["user_id"]), context, question)
            except Exception:
                pass

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
            safe_note=out.get("safe_note") or context.get("_safety_note"),
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
