"""shared_engine.py — Single shared SQLAlchemy engine for all KnowEasy stores.

CRITICAL FIX: Previously db.py, auth_store.py, payments_store.py, and phase1_store.py
each created their own Engine with default pool_size=5. That meant 4 × 15 = 60 max
connections — enough to exhaust Render Postgres limits instantly under load.

Now every module imports `get_engine()` from here. ONE pool, properly tuned.
"""

from __future__ import annotations

import os
import logging
from typing import Any, Dict, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger("knoweasy.shared_engine")

_ENGINE: Optional[Engine] = None


def _env_int(key: str, default: int) -> int:
    v = os.getenv(key)
    if v is None or str(v).strip() == "":
        return default
    try:
        return int(str(v).strip())
    except Exception:
        return default


def _clean_sslmode(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    v = str(raw).strip().strip('"').strip("'").strip()
    allowed = {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}
    return v if v in allowed else None


def get_engine() -> Optional[Engine]:
    """Return the ONE shared SQLAlchemy engine, or None if DB is disabled/unconfigured."""
    global _ENGINE

    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        return None

    if _ENGINE is not None:
        return _ENGINE

    connect_args: Dict[str, Any] = {}
    if "sslmode=" not in url.lower():
        sslmode = _clean_sslmode(os.getenv("DB_SSLMODE"))
        if sslmode:
            connect_args = {"sslmode": sslmode}

    try:
        _ENGINE = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=_env_int("DB_POOL_SIZE", 10),
            max_overflow=_env_int("DB_MAX_OVERFLOW", 20),
            pool_recycle=_env_int("DB_POOL_RECYCLE", 1800),
            pool_timeout=_env_int("DB_POOL_TIMEOUT", 30),
            connect_args=connect_args,
        )
        logger.info(
            "Shared DB engine created (pool_size=%d, max_overflow=%d)",
            _env_int("DB_POOL_SIZE", 10),
            _env_int("DB_MAX_OVERFLOW", 20),
        )
        return _ENGINE
    except Exception:
        logger.exception("Failed to create shared DB engine")
        return None


def db_health() -> Dict[str, Any]:
    engine = get_engine()
    if engine is None:
        return {"enabled": False, "connected": False, "reason": "DATABASE_URL missing"}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        pool = engine.pool
        return {
            "enabled": True,
            "connected": True,
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        }
    except Exception as e:
        return {"enabled": True, "connected": False, "reason": str(e)}
