"""
db.py - Postgres helpers for KnowEasy Engine API (Render)

PHASE-1C / C-1 hardening:
- db_log_solve() accepts dict OR Pydantic objects (v1/v2).
- DB failures never crash API, BUT are visible in Render logs (no silent failures).
- FIX: sanitize DB_SSLMODE to avoid psycopg2 'invalid sslmode value: "require "' errors.
"""

from __future__ import annotations

import os
import logging
from typing import Any, Dict, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


logger = logging.getLogger(__name__)

# -----------------------------
# Env helpers
# -----------------------------


def _db_enabled() -> bool:
    return (os.getenv("DB_ENABLED", "true") or "true").strip().lower() in ("1", "true", "yes", "on")


def _database_url() -> Optional[str]:
    url = os.getenv("DATABASE_URL")
    if not url:
        return None
    url = url.strip()
    return url or None


def _clean_sslmode(raw: Optional[str]) -> Optional[str]:
    """Return a safe sslmode string or None."""
    if not raw:
        return None
    v = str(raw).strip()

    # Remove accidental wrapping quotes (common copy/paste issue)
    v = v.strip('"').strip("'").strip()

    # psycopg2 allowed values
    allowed = {
        "disable",
        "allow",
        "prefer",
        "require",
        "verify-ca",
        "verify-full",
    }
    if v in allowed:
        return v

    # If it's invalid, ignore it rather than crash DB connection attempts
    logger.warning("Ignoring invalid DB_SSLMODE value: %r", raw)
    return None


# -----------------------------
# Engine (cached)
# -----------------------------

_ENGINE: Optional[Engine] = None


def _get_engine() -> Optional[Engine]:
    global _ENGINE

    if not _db_enabled():
        return None

    url = _database_url()
    if not url:
        return None

    if _ENGINE is not None:
        return _ENGINE

    # If DATABASE_URL already contains sslmode=, do NOT override it.
    url_lower = url.lower()
    has_sslmode_in_url = "sslmode=" in url_lower

    connect_args = {}
    if not has_sslmode_in_url:
        sslmode = _clean_sslmode(os.getenv("DB_SSLMODE"))
        if sslmode:
            connect_args = {"sslmode": sslmode}

    try:
        _ENGINE = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
        return _ENGINE
    except Exception:
        logger.exception("Failed to create DB engine")
        return None


# -----------------------------
# Init / Health
# -----------------------------


def db_init() -> Dict[str, Any]:
    """Create DB tables used by the API (best-effort)."""
    engine = _get_engine()
    if engine is None:
        return {"ok": True, "enabled": False, "reason": "DB disabled or DATABASE_URL missing/invalid"}

    create_ask_logs_sql = """
    CREATE TABLE IF NOT EXISTS ask_logs (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        board TEXT,
        class_level TEXT,
        subject TEXT,
        question TEXT NOT NULL,
        answer TEXT,
        latency_ms INTEGER,
        error TEXT
    );
    """


    # Phase-4B: user-visible chat history (Chat AI + Luma)
    create_chat_history_sql = """
    CREATE TABLE IF NOT EXISTS chat_history (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        user_id INTEGER NOT NULL,
        surface TEXT NOT NULL DEFAULT 'chat_ai',
        question TEXT NOT NULL,
        learning_object_json TEXT,
        mode TEXT,
        language TEXT
    );
    """

    # Phase-4B: compressed learning memory cards (opt-in)
    create_learning_memory_sql = """
    CREATE TABLE IF NOT EXISTS learning_memory_cards (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        user_id INTEGER NOT NULL,
        card_key TEXT NOT NULL,
        card_json TEXT NOT NULL,
        expires_at TIMESTAMPTZ,
        UNIQUE(user_id, card_key)
    );
    """

    # Phase-4A: internal AI usage telemetry (private; never user-visible)
    create_ai_usage_sql = """
    CREATE TABLE IF NOT EXISTS ai_usage_logs (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

        user_id INTEGER,
        role TEXT,
        plan TEXT,

        request_type TEXT,
        credit_bucket INTEGER,
        credits_charged INTEGER,

        model_primary TEXT,
        model_escalated TEXT,
        cache_hit BOOLEAN,

        tokens_in INTEGER,
        tokens_out INTEGER,
        estimated_cost_usd NUMERIC,
        estimated_cost_inr NUMERIC,

        latency_ms INTEGER,
        status TEXT,

        question_len INTEGER,
        answer_len INTEGER,

        error TEXT
    );
    """

    try:
        with engine.begin() as conn:
            conn.execute(text(create_ask_logs_sql))
            conn.execute(text(create_ai_usage_sql))
            conn.execute(text(create_chat_history_sql))
            conn.execute(text(create_learning_memory_sql))
        return {"ok": True, "enabled": True}
    except Exception as e:
        logger.exception("db_init failed")
        return {"ok": False, "enabled": True, "reason": str(e)}


def db_health() -> Dict[str, Any]:
    engine = _get_engine()
    if engine is None:
        return {"enabled": False, "connected": False, "reason": "DB disabled or DATABASE_URL missing/invalid"}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"enabled": True, "connected": True}
    except SQLAlchemyError as e:
        return {"enabled": True, "connected": False, "reason": str(e)}


# -----------------------------
# Logging (ask_logs)
# -----------------------------


def _coerce_mapping(obj: Any) -> Dict[str, Any]:
    """Convert common request/response objects to a plain dict.

    Supports:
    - dict
    - Pydantic v2 models (model_dump)
    - Pydantic v1 models (dict)
    - objects with __dict__ (best-effort)
    """
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj

    # Pydantic v2
    if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
        try:
            return obj.model_dump()
        except Exception:
            pass

    # Pydantic v1
    if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
        try:
            return obj.dict()
        except Exception:
            pass

    # Best-effort fallback
    try:
        return dict(getattr(obj, "__dict__", {}) or {})
    except Exception:
        return {}


def db_log_solve(req: Any, out: Any, latency_ms: int, error: Optional[str]) -> None:
    """Best-effort insert into ask_logs. Never raises."""
    engine = _get_engine()
    if engine is None:
        return

    req_d = _coerce_mapping(req)
    out_d = _coerce_mapping(out)

    board = (req_d.get("board") or "").strip() or None
    class_level = (str(req_d.get("class") or req_d.get("class_level") or "")).strip() or None
    subject = (req_d.get("subject") or "").strip() or None

    question = req_d.get("question") or req_d.get("prompt") or ""
    question = question if isinstance(question, str) else str(question)

    answer = out_d.get("answer") or out_d.get("text") or out_d.get("output") or ""
    answer = answer if isinstance(answer, str) else str(answer)

    insert_sql = """
    INSERT INTO ask_logs (board, class_level, subject, question, answer, latency_ms, error)
    VALUES (:board, :class_level, :subject, :question, :answer, :latency_ms, :error);
    """

    try:
        with engine.begin() as conn:
            conn.execute(
                text(insert_sql),
                {
                    "board": board,
                    "class_level": class_level,
                    "subject": subject,
                    "question": question,
                    "answer": answer,
                    "latency_ms": int(latency_ms) if latency_ms is not None else None,
                    "error": error,
                },
            )
    except Exception:
        logger.exception("db_log_solve failed")
        return


# -----------------------------
# Logging (ai_usage_logs)
# -----------------------------


def _safe_int(v):
    try:
        if v is None:
            return None
        return int(v)
    except Exception:
        return None


def _safe_float(v):
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def db_log_ai_usage(event: dict) -> None:
    """Best-effort insert into ai_usage_logs. Never raises."""
    engine = _get_engine()
    if engine is None:
        return

    d = event or {}

    insert_sql = """
    INSERT INTO ai_usage_logs (
        user_id, role, plan,
        request_type, credit_bucket, credits_charged,
        model_primary, model_escalated, cache_hit,
        tokens_in, tokens_out, estimated_cost_usd, estimated_cost_inr,
        latency_ms, status, question_len, answer_len, error
    ) VALUES (
        :user_id, :role, :plan,
        :request_type, :credit_bucket, :credits_charged,
        :model_primary, :model_escalated, :cache_hit,
        :tokens_in, :tokens_out, :estimated_cost_usd, :estimated_cost_inr,
        :latency_ms, :status, :question_len, :answer_len, :error
    );
    """

    try:
        with engine.begin() as conn:
            conn.execute(
                text(insert_sql),
                {
                    "user_id": _safe_int(d.get("user_id")),
                    "role": (d.get("role") or None),
                    "plan": (d.get("plan") or None),
                    "request_type": (d.get("request_type") or None),
                    "credit_bucket": _safe_int(d.get("credit_bucket")),
                    "credits_charged": _safe_int(d.get("credits_charged")),
                    "model_primary": (d.get("model_primary") or None),
                    "model_escalated": (d.get("model_escalated") or None),
                    "cache_hit": bool(d.get("cache_hit")) if d.get("cache_hit") is not None else None,
                    "tokens_in": _safe_int(d.get("tokens_in")),
                    "tokens_out": _safe_int(d.get("tokens_out")),
                    "estimated_cost_usd": d.get("estimated_cost_usd"),
                    "estimated_cost_inr": d.get("estimated_cost_inr"),
                    "latency_ms": _safe_int(d.get("latency_ms")),
                    "status": (d.get("status") or None),
                    "question_len": _safe_int(d.get("question_len")),
                    "answer_len": _safe_int(d.get("answer_len")),
                    "error": (d.get("error") or None),
                },
            )
    except Exception:
        logger.exception("db_log_ai_usage failed")
        return


__all__ = ["db_init", "db_health", "db_log_solve", "db_log_ai_usage"]



# -----------------------------
# Chat History (chat_history)
# -----------------------------

def db_add_chat_history(
    user_id: int,
    surface: str,
    question: str,
    learning_object: dict | None,
    mode: str | None,
    language: str | None,
) -> None:
    """Best-effort insert into chat_history. Never raises."""
    engine = _get_engine()
    if engine is None:
        return
    try:
        lo_json = None
        if learning_object is not None:
            import json as _json
            lo_json = _json.dumps(learning_object, ensure_ascii=False)
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO chat_history (user_id, surface, question, learning_object_json, mode, language)
                    VALUES (:user_id, :surface, :question, :lo, :mode, :language)
                    """
                ),
                {
                    "user_id": int(user_id),
                    "surface": (surface or "chat_ai")[:20],
                    "question": str(question or "")[:4000],
                    "lo": lo_json,
                    "mode": (mode or "")[:40] or None,
                    "language": (language or "")[:10] or None,
                },
            )
    except Exception:
        logger.exception("db_add_chat_history failed")


def db_list_chat_history(user_id: int, limit: int = 30) -> list[dict]:
    """Return most recent chat history rows for user. Best-effort."""
    engine = _get_engine()
    if engine is None:
        return []
    try:
        limit = max(1, min(int(limit), 100))
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, created_at, surface, question, learning_object_json, mode, language
                    FROM chat_history
                    WHERE user_id = :user_id
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                {"user_id": int(user_id), "limit": limit},
            ).mappings().all()
        out = []
        import json as _json
        for r in rows:
            lo = None
            raw = r.get("learning_object_json")
            if raw:
                try:
                    lo = _json.loads(raw)
                except Exception:
                    lo = None
            out.append(
                {
                    "id": int(r["id"]),
                    "created_at": str(r["created_at"]),
                    "surface": r.get("surface"),
                    "question": r.get("question"),
                    "learning_object": lo,
                    "mode": r.get("mode"),
                    "language": r.get("language"),
                }
            )
        return out
    except Exception:
        logger.exception("db_list_chat_history failed")
        return []


def db_clear_chat_history(user_id: int) -> None:
    engine = _get_engine()
    if engine is None:
        return
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM chat_history WHERE user_id = :user_id"), {"user_id": int(user_id)})
    except Exception:
        logger.exception("db_clear_chat_history failed")


# -----------------------------
# Learning Memory (learning_memory_cards)
# -----------------------------

def db_upsert_memory_card(user_id: int, card_key: str, card_json: dict, expires_at_iso: str | None = None) -> None:
    engine = _get_engine()
    if engine is None:
        return
    try:
        import json as _json
        payload = _json.dumps(card_json or {}, ensure_ascii=False)
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO learning_memory_cards (user_id, card_key, card_json, expires_at)
                    VALUES (:user_id, :card_key, :card_json, :expires_at)
                    ON CONFLICT (user_id, card_key)
                    DO UPDATE SET card_json = EXCLUDED.card_json, updated_at = NOW(), expires_at = EXCLUDED.expires_at
                    """
                ),
                {
                    "user_id": int(user_id),
                    "card_key": str(card_key)[:80],
                    "card_json": payload,
                    "expires_at": expires_at_iso,
                },
            )
    except Exception:
        logger.exception("db_upsert_memory_card failed")


def db_get_memory_cards(user_id: int) -> list[dict]:
    engine = _get_engine()
    if engine is None:
        return []
    try:
        import json as _json
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT card_key, card_json, updated_at, expires_at
                    FROM learning_memory_cards
                    WHERE user_id = :user_id
                    ORDER BY updated_at DESC
                    """
                ),
                {"user_id": int(user_id)},
            ).mappings().all()
        out = []
        for r in rows:
            cj = {}
            try:
                cj = _json.loads(r.get("card_json") or "{}")
            except Exception:
                cj = {}
            out.append(
                {
                    "card_key": r.get("card_key"),
                    "card": cj,
                    "updated_at": str(r.get("updated_at")),
                    "expires_at": str(r.get("expires_at")) if r.get("expires_at") else None,
                }
            )
        return out
    except Exception:
        logger.exception("db_get_memory_cards failed")
        return []


def db_reset_memory_cards(user_id: int) -> None:
    engine = _get_engine()
    if engine is None:
        return
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM learning_memory_cards WHERE user_id = :user_id"), {"user_id": int(user_id)})
    except Exception:
        logger.exception("db_reset_memory_cards failed")
