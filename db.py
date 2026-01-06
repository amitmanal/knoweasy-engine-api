"""DB helper (Phase-1)

Goal:
- Optional Postgres logging for /solve requests
- Never break the app if DB is down or misconfigured

We intentionally avoid migrations for now.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    func,
    text,
)

from config import DATABASE_URL, DB_ENABLED, DB_SSLMODE


def _add_sslmode_if_missing(db_url: str, sslmode: str) -> str:
    """Append sslmode if not already present."""
    parsed = urlparse(db_url)
    q = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if "sslmode" not in q and sslmode:
        q["sslmode"] = sslmode
        parsed = parsed._replace(query=urlencode(q))
        return urlunparse(parsed)
    return db_url


_engine = None
_metadata = MetaData()


ask_logs = Table(
    "ask_logs",
    _metadata,
    Column("id", String(36), primary_key=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("board", String(32)),
    Column("class_level", String(8)),
    Column("subject", String(64)),
    Column("question", Text),
    Column("final_answer", Text),
    Column("confidence", String(16)),
    Column("provider", String(32)),
    Column("model", String(64)),
    Column("latency_ms", String(16)),
    Column("error", Text),
    Column("meta", JSON, nullable=True),
)


@dataclass
class DBStatus:
    enabled: bool
    ok: bool
    details: str


def get_engine():
    global _engine
    if _engine is not None:
        return _engine

    if not DB_ENABLED or not DATABASE_URL:
        _engine = None
        return None

    url = _add_sslmode_if_missing(DATABASE_URL, DB_SSLMODE)
    # Conservative pool values for free tier
    _engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=2,
        pool_timeout=30,
        pool_recycle=1800,
    )
    return _engine


def init_db() -> DBStatus:
    """Create tables if DB is configured. Never raises."""
    if not DB_ENABLED:
        return DBStatus(enabled=False, ok=False, details="DB disabled")
    if not DATABASE_URL:
        return DBStatus(enabled=False, ok=False, details="DATABASE_URL not set")

    try:
        eng = get_engine()
        if eng is None:
            return DBStatus(enabled=False, ok=False, details="DB not initialized")
        _metadata.create_all(eng)
        # Lightweight ping
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return DBStatus(enabled=True, ok=True, details="ok")
    except Exception as e:
        return DBStatus(enabled=True, ok=False, details=f"{type(e).__name__}: {e}")


def db_health() -> DBStatus:
    if not DB_ENABLED:
        return DBStatus(enabled=False, ok=False, details="DB disabled")
    if not DATABASE_URL:
        return DBStatus(enabled=False, ok=False, details="DATABASE_URL not set")
    try:
        eng = get_engine()
        if eng is None:
            return DBStatus(enabled=True, ok=False, details="engine not ready")
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return DBStatus(enabled=True, ok=True, details="ok")
    except Exception as e:
        return DBStatus(enabled=True, ok=False, details=f"{type(e).__name__}: {e}")


def safe_log_solve(
    *,
    board: str | None,
    class_level: str | None,
    subject: str | None,
    question: str,
    final_answer: str | None,
    confidence: float | None,
    provider: str | None,
    model: str | None,
    latency_ms: int | None,
    error: str | None,
    meta: dict | None = None,
):
    """Best-effort DB logging. Never raises."""
    try:
        eng = get_engine()
        if eng is None:
            return
        payload = {
            "id": str(uuid.uuid4()),
            "board": board,
            "class_level": class_level,
            "subject": subject,
            "question": (question or "")[:20000],
            "final_answer": (final_answer or "")[:50000],
            "confidence": "" if confidence is None else f"{confidence:.2f}",
            "provider": provider,
            "model": model,
            "latency_ms": "" if latency_ms is None else str(int(latency_ms)),
            "error": error,
            "meta": meta or {},
        }
        with eng.begin() as conn:
            conn.execute(ask_logs.insert().values(**payload))
    except Exception:
        # Silent by design for Phase-1 (no DB should ever break solving)
        return


class Timer:
    def __init__(self):
        self._t0 = time.time()

    def ms(self) -> int:
        return int((time.time() - self._t0) * 1000)

# Backward-compatible name used by router.py
def db_log_solve(req, out, latency_ms=None, error=None):
    """Alias for safe_log_solve (kept for compatibility with older imports)."""
    return safe_log_solve(req=req, out=out, latency_ms=latency_ms, error=error)
