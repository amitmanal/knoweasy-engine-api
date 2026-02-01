"""
Luma Database Store

Database operations for Luma content, progress, and analytics.

Design Principles:
- CREATE TABLE IF NOT EXISTS (non-breaking migrations)
- Best-effort (never crash the app)
- Safe defaults if DB unavailable
- Atomic operations where needed
"""

from __future__ import annotations

import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("knoweasy-engine-api")

# Safe imports - never crash if DB is unavailable
try:
    from db import get_engine_safe
except Exception:
    def get_engine_safe():
        return None

# SQLAlchemy 2.x requires text() for raw SQL strings.
try:
    from sqlalchemy import text as _sql_text

    def _t(q: str):
        return _sql_text(q)
except Exception:
    def _t(q: str):
        return q


# ============================================================================
# HELPERS
# ============================================================================

def _to_json_str(value: Any) -> str:
    """
    Ensure we store JSON as a STRING in DB (TEXT column).
    Accepts dict/list/str/None safely.
    """
    if value is None:
        return "{}"
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return "{}"


def _from_json(value: Any, default: Any) -> Any:
    """
    Safe JSON loader:
    - If DB driver returns dict/list already -> return it
    - If returns str -> json.loads
    - If None/empty -> default
    """
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        try:
            value = value.decode("utf-8", errors="ignore")
        except Exception:
            return default
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return default
        try:
            return json.loads(s)
        except Exception:
            # If it's not valid JSON, fallback safely
            return default
    return default


# ============================================================================
# TABLE DEFINITIONS (Non-breaking, idempotent)
# ============================================================================

def ensure_tables() -> None:
    """Create Luma tables if they don't exist. Never crashes the app."""
    engine = get_engine_safe()
    if not engine:
        logger.warning("luma_store: DB unavailable, tables not created")
        return

    try:
        with engine.begin() as conn:
            conn.execute(_t("""
                CREATE TABLE IF NOT EXISTS luma_content (
                    id TEXT PRIMARY KEY,
                    metadata_json TEXT NOT NULL,
                    blueprint_json TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    published BOOLEAN NOT NULL DEFAULT FALSE
                );
            """))

            # Non-breaking migrations
            conn.execute(_t("""
                ALTER TABLE luma_content
                    ADD COLUMN IF NOT EXISTS metadata_json TEXT NOT NULL DEFAULT '{}'::text,
                    ADD COLUMN IF NOT EXISTS blueprint_json TEXT NOT NULL DEFAULT '{}'::text,
                    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    ADD COLUMN IF NOT EXISTS published BOOLEAN NOT NULL DEFAULT FALSE;
            """))

            conn.execute(_t("""
                CREATE TABLE IF NOT EXISTS luma_progress (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    content_id TEXT NOT NULL,
                    completed BOOLEAN NOT NULL DEFAULT FALSE,
                    time_spent_seconds INTEGER NOT NULL DEFAULT 0,
                    last_visited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    notes TEXT,
                    bookmarked BOOLEAN NOT NULL DEFAULT FALSE,
                    UNIQUE(user_id, content_id)
                );
            """))

            conn.execute(_t("""
                CREATE TABLE IF NOT EXISTS luma_analytics (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    content_id TEXT,
                    metadata_json TEXT,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """))

            conn.execute(_t("""
                CREATE INDEX IF NOT EXISTS idx_luma_content_published
                ON luma_content(published) WHERE published = TRUE;
            """))

            conn.execute(_t("""
                CREATE INDEX IF NOT EXISTS idx_luma_progress_user
                ON luma_progress(user_id, last_visited_at DESC);
            """))

            conn.execute(_t("""
                CREATE INDEX IF NOT EXISTS idx_luma_analytics_user
                ON luma_analytics(user_id, timestamp DESC);
            """))

        logger.info("luma_store: tables ensured successfully")
    except Exception as e:
        logger.exception(f"luma_store: table creation failed: {e}")


# ============================================================================
# CONTENT OPERATIONS
# ============================================================================

def insert_content(
    content_id: str,
    metadata: Dict[str, Any],
    blueprint: Dict[str, Any],
    published: bool = False
) -> Dict[str, Any]:
    """Insert or update learning content."""
    engine = get_engine_safe()
    if not engine:
        return {"ok": False, "error": "DB_UNAVAILABLE"}

    try:
        with engine.begin() as conn:
            conn.execute(
                _t("""
                INSERT INTO luma_content (id, metadata_json, blueprint_json, published)
                VALUES (:id, :metadata, :blueprint, :published)
                ON CONFLICT (id) DO UPDATE SET
                    metadata_json = EXCLUDED.metadata_json,
                    blueprint_json = EXCLUDED.blueprint_json,
                    published = EXCLUDED.published,
                    updated_at = NOW()
                """),
                {
                    "id": content_id,
                    "metadata": _to_json_str(metadata),
                    "blueprint": _to_json_str(blueprint),
                    "published": bool(published),
                }
            )
        return {"ok": True, "content_id": content_id}

    except Exception as e:
        logger.exception(f"luma_store: insert_content failed: {e}")
        return {"ok": False, "error": str(e)}


def get_content(content_id: str) -> Optional[Dict[str, Any]]:
    """
    Get content by ID.
    Phase-1 behavior: return content if it exists (do NOT block by published flag).
    """
    engine = get_engine_safe()
    if not engine:
        return None

    try:
        with engine.connect() as conn:
            row = conn.execute(
                _t("""
                SELECT id, metadata_json, blueprint_json, created_at, updated_at, published
                FROM luma_content
                WHERE id = :id
                """),
                {"id": content_id}
            ).fetchone()

            if not row:
                return None

            metadata = _from_json(row[1], {})
            blueprint = _from_json(row[2], {})

            return {
                "id": row[0],
                "metadata": metadata if isinstance(metadata, dict) else {},
                "blueprint": blueprint if isinstance(blueprint, dict) else {},
                "created_at": row[3].isoformat() if row[3] else None,
                "updated_at": row[4].isoformat() if row[4] else None,
                "published": bool(row[5]),
            }

    except Exception as e:
        logger.exception(f"luma_store: get_content failed: {e}")
        return None


def list_content(
    class_level: Optional[int] = None,
    subject: Optional[str] = None,
    board: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    List content with optional filters.
    Phase-1 behavior: do NOT block by published flag.
    """
    engine = get_engine_safe()
    if not engine:
        return []

    try:
        conditions = ["1=1"]
        params: Dict[str, Any] = {"limit": min(int(limit), 100)}

        if class_level is not None:
            conditions.append("metadata_json::jsonb->>'class_level' = :class_level")
            params["class_level"] = str(class_level)

        if subject:
            conditions.append("metadata_json::jsonb->>'subject' ILIKE :subject")
            params["subject"] = f"%{subject}%"

        if board:
            conditions.append("metadata_json::jsonb->>'board' ILIKE :board")
            params["board"] = f"%{board}%"

        where_clause = " AND ".join(conditions)

        with engine.connect() as conn:
            rows = conn.execute(
                _t(f"""
                SELECT id, metadata_json, blueprint_json, created_at, updated_at, published
                FROM luma_content
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT :limit
                """),
                params
            ).fetchall()

            out: List[Dict[str, Any]] = []
            for r in rows:
                md = _from_json(r[1], {})
                bp = _from_json(r[2], {})
                out.append({
                    "id": r[0],
                    "metadata": md if isinstance(md, dict) else {},
                    "blueprint": bp if isinstance(bp, dict) else {},
                    "created_at": r[3].isoformat() if r[3] else None,
                    "updated_at": r[4].isoformat() if r[4] else None,
                    "published": bool(r[5]),
                })
            return out

    except Exception as e:
        logger.exception(f"luma_store: list_content failed: {e}")
        return []


# ============================================================================
# PROGRESS OPERATIONS
# ============================================================================

def save_progress(
    user_id: int,
    content_id: str,
    completed: bool = False,
    time_spent_seconds: int = 0,
    notes: Optional[str] = None,
    bookmarked: bool = False
) -> Dict[str, Any]:
    engine = get_engine_safe()
    if not engine:
        return {"ok": False, "error": "DB_UNAVAILABLE"}

    try:
        with engine.begin() as conn:
            conn.execute(
                _t("""
                INSERT INTO luma_progress
                    (user_id, content_id, completed, time_spent_seconds, notes, bookmarked, last_visited_at)
                VALUES
                    (:user_id, :content_id, :completed, :time_spent, :notes, :bookmarked, NOW())
                ON CONFLICT (user_id, content_id) DO UPDATE SET
                    completed = EXCLUDED.completed,
                    time_spent_seconds = luma_progress.time_spent_seconds + EXCLUDED.time_spent_seconds,
                    notes = COALESCE(EXCLUDED.notes, luma_progress.notes),
                    bookmarked = EXCLUDED.bookmarked,
                    last_visited_at = NOW()
                """),
                {
                    "user_id": int(user_id),
                    "content_id": content_id,
                    "completed": bool(completed),
                    "time_spent": int(time_spent_seconds),
                    "notes": notes,
                    "bookmarked": bool(bookmarked),
                }
            )
        return {"ok": True}

    except Exception as e:
        logger.exception(f"luma_store: save_progress failed: {e}")
        return {"ok": False, "error": str(e)}


def get_progress(user_id: int, content_id: str) -> Optional[Dict[str, Any]]:
    engine = get_engine_safe()
    if not engine:
        return None

    try:
        with engine.connect() as conn:
            r = conn.execute(
                _t("""
                SELECT completed, time_spent_seconds, notes, bookmarked, last_visited_at
                FROM luma_progress
                WHERE user_id = :user_id AND content_id = :content_id
                """),
                {"user_id": int(user_id), "content_id": content_id}
            ).fetchone()

            if not r:
                return None

            return {
                "completed": bool(r[0]),
                "time_spent_seconds": int(r[1] or 0),
                "notes": r[2],
                "bookmarked": bool(r[3]),
                "last_visited_at": r[4].isoformat() if r[4] else None,
            }

    except Exception as e:
        logger.exception(f"luma_store: get_progress failed: {e}")
        return None


# ============================================================================
# ANALYTICS OPERATIONS
# ============================================================================

def log_event(
    user_id: int,
    event_type: str,
    content_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    engine = get_engine_safe()
    if not engine:
        return

    try:
        with engine.begin() as conn:
            conn.execute(
                _t("""
                INSERT INTO luma_analytics (user_id, event_type, content_id, metadata_json)
                VALUES (:user_id, :event_type, :content_id, :metadata)
                """),
                {
                    "user_id": int(user_id),
                    "event_type": event_type,
                    "content_id": content_id,
                    "metadata": _to_json_str(metadata) if metadata else None,
                }
            )
    except Exception as e:
        logger.warning(f"luma_store: analytics logging failed: {e}")
