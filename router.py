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
    """Format orchestrator response to SolveResponse format.

    IMPORTANT:
    - Keep backward compatible fields (final_answer, confidence, flags...)
    - ALSO pass through premium fields (title, why_this_matters, sections) at top-level
      so the Hostinger PremiumRenderer can render the AnswerObject.
    """

    if not result:
        return {
            "final_answer": "I couldn't process your question. Please try again.",
            "steps": [],
            "assumptions": [],
            "confidence": 0.3,
            "flags": ["AI_ERROR"],
            "safe_note": None,
            "title": None,
            "why_this_matters": None,
            "sections": [],
            "providers_used": [],
            "meta": {"request_id": request_id},
        }

    # Handle explicit error cases
    if result.get("error") or (result.get("success") is False):
        msg = result.get("answer") or result.get("final_answer") or "Sorry, I encountered an issue. Please try again."
        return {
            "final_answer": msg,
            "steps": [],
            "assumptions": [],
            "confidence": 0.2,
            "flags": ["AI_ERROR"],
            "safe_note": None,
            "title": result.get("title"),
            "why_this_matters": result.get("why_this_matters"),
            "sections": result.get("sections") or [],
            "providers_used": result.get("providers_used") or [],
            "meta": {"request_id": request_id, "error": result.get("error")},
        }

    # Success case
    sections = result.get("sections") or []
    title = result.get("title")
    why = result.get("why_this_matters")
    providers_used = result.get("providers_used") or []

    # Plain string for legacy UI components
    answer = result.get("answer") or result.get("final_answer") or ""
    if not answer and sections:
        parts = []
        if title:
            parts.append(str(title))
        for sec in sections:
            if not isinstance(sec, dict):
                continue
            t = sec.get("title")
            c = sec.get("content")
            if t:
                parts.append(str(t))
            if c:
                parts.append(str(c))
        if why:
            parts.append("Why this matters")
            parts.append(str(why))
        answer = "\n\n".join([p for p in parts if str(p).strip()])

    # Confidence: allow orchestrator meta to drive it later; default stable
    conf = float(result.get("confidence", 0.85))

    # Informative flags
    flags = []
    if result.get("ai_strategy"):
        flags.append(str(result["ai_strategy"]).upper())
    if result.get("confidence_label"):
        flags.append(str(result["confidence_label"]).upper())
    for p in providers_used:
        flags.append(f"AI_{str(p).upper()}")
    if result.get("cached"):
        flags.append("CACHED")

    meta = dict(result.get("meta") or {})
    meta["request_id"] = request_id

    return {
        "final_answer": answer,
        "steps": result.get("steps", []),
        "assumptions": result.get("assumptions", []),
        "confidence": conf,
        "flags": flags,
        "safe_note": result.get("safe_note"),
        "title": title,
        "why_this_matters": why,
        "sections": sections,
        "providers_used": providers_used,
        "meta": meta,
    }

