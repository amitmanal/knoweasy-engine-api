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
    engine = _get_engine()
    if engine is None:
        return {"ok": True, "enabled": False, "reason": "DB disabled or DATABASE_URL missing/invalid"}

    create_sql = """
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

    try:
        with engine.begin() as conn:
            conn.execute(text(create_sql))
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


__all__ = ["db_init", "db_health", "db_log_solve"]
