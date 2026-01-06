"""
db.py - Postgres helpers for KnowEasy Engine API (Render)

This module is intentionally defensive:
- If DB is disabled or DATABASE_URL is missing, all DB calls become no-ops.
- On startup, db_init() creates the 'ask_logs' table if it does not exist.
- db_log_solve() writes one row per /ask call (best-effort; failures never crash the API).
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


# -----------------------------
# Env helpers
# -----------------------------

def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None:
        return default
    try:
        return int(str(v).strip())
    except Exception:
        return default


DB_ENABLED: bool = _env_bool("DB_ENABLED", default=False)
DATABASE_URL: str = os.getenv("DATABASE_URL", "").strip()

# Render Postgres often needs SSL (especially external URL).
# Keep default as 'require' unless you know you don't need it.
DB_SSLMODE: str = os.getenv("DB_SSLMODE", "require").strip() or "require"

# Bound how long a DB connect can block (seconds). Keeps /health fast and avoids request hangs.
DB_CONNECT_TIMEOUT_SECONDS: int = _env_int("DB_CONNECT_TIMEOUT_SECONDS", default=3)


# -----------------------------
# Engine (lazy singleton)
# -----------------------------

_ENGINE: Optional[Engine] = None


def _get_engine() -> Optional[Engine]:
    global _ENGINE

    if not DB_ENABLED:
        return None

    if not DATABASE_URL:
        return None

    if _ENGINE is not None:
        return _ENGINE

    connect_args: Dict[str, Any] = {}
    if DB_SSLMODE:
        connect_args["sslmode"] = DB_SSLMODE

    # psycopg2 supports connect_timeout (seconds). Safe to pass even if unused by driver.
    if DB_CONNECT_TIMEOUT_SECONDS and DB_CONNECT_TIMEOUT_SECONDS > 0:
        connect_args["connect_timeout"] = int(DB_CONNECT_TIMEOUT_SECONDS)

    # Tiny pool for free tiers; pre_ping avoids stale connections.
    _ENGINE = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=3,
        pool_recycle=300,
        connect_args=connect_args,
    )
    return _ENGINE


# -----------------------------
# Public API used by main.py/router.py
# -----------------------------

def db_init() -> Dict[str, Any]:
    """Initialize DB (create tables). Safe to call multiple times."""
    engine = _get_engine()
    if engine is None:
        return {
            "enabled": False,
            "ok": False,
            "reason": "DB is disabled or DATABASE_URL is missing",
        }

    ddl = text(
        """
        CREATE TABLE IF NOT EXISTS ask_logs (
            id BIGSERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            board TEXT,
            class_level TEXT,
            subject TEXT,
            question TEXT,
            answer TEXT,
            latency_ms INTEGER,
            error TEXT
        );
        """
    )

    try:
        with engine.begin() as conn:
            conn.execute(ddl)
        return {"enabled": True, "ok": True}
    except SQLAlchemyError as e:
        # Never crash the API on DB issues.
        return {"enabled": True, "ok": False, "reason": str(e)}
    except Exception as e:
        return {"enabled": True, "ok": False, "reason": f"{e.__class__.__name__}: {e}"}


def db_health() -> Dict[str, Any]:
    """Lightweight health probe for DB. Must never raise."""
    engine = _get_engine()
    if engine is None:
        return {
            "enabled": False,
            "connected": False,
            "reason": "DB is disabled or DATABASE_URL is missing",
        }

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"enabled": True, "connected": True}
    except SQLAlchemyError as e:
        return {"enabled": True, "connected": False, "reason": str(e)}
    except Exception as e:
        return {"enabled": True, "connected": False, "reason": f"{e.__class__.__name__}: {e}"}


def db_log_solve(req: Dict[str, Any], out: Dict[str, Any], latency_ms: int, error: Optional[str]) -> None:
    """Best-effort insert into ask_logs. Never raises."""
    engine = _get_engine()
    if engine is None:
        return

    board = (req.get("board") or "").strip() or None
    class_level = (str(req.get("class") or req.get("class_level") or "")).strip() or None
    subject = (req.get("subject") or "").strip() or None

    question = req.get("question") or req.get("prompt") or ""
    question = question.strip() if isinstance(question, str) else str(question)

    # Try common output shapes
    answer = out.get("answer")
    if answer is None:
        answer = out.get("final_answer")
    if answer is None:
        answer = out.get("result")
    answer = answer.strip() if isinstance(answer, str) else (str(answer) if answer is not None else None)

    insert_sql = text(
        """
        INSERT INTO ask_logs (board, class_level, subject, question, answer, latency_ms, error)
        VALUES (:board, :class_level, :subject, :question, :answer, :latency_ms, :error);
        """
    )

    try:
        with engine.begin() as conn:
            conn.execute(
                insert_sql,
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
        # Never crash request path due to DB.
        return
