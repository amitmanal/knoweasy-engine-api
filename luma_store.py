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

def _to_json_str(value: Any, *, require_object: bool = True) -> str:
    """Serialize JSON safely for TEXT columns.

    Why:
    - Your DB columns are TEXT, but downstream code (and list filters) assume valid JSON.
    - Accepting arbitrary strings without validation can poison the table and later queries.

    Behavior:
    - dict/list -> json.dumps
    - str -> validate it's JSON (and optionally an object) then re-dump for canonical form
    - None -> '{}'

    NOTE: We *never* raise out of this helper; store a safe default instead.
    """
    if value is None:
        return "{}"

    # If caller passed a Python object, dump it.
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return "{}"

    # If caller passed a string, validate and normalize.
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return "{}"
        try:
            obj = json.loads(s)
        except Exception:
            return "{}"
        if require_object and not isinstance(obj, dict):
            # For metadata_json / blueprint_json we expect an object.
            return "{}"
        try:
            return json.dumps(obj, ensure_ascii=False)
        except Exception:
            return "{}"

    # Unknown types: safest fallback.
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

            
            # User Catalog (uploads / saved resources)
            conn.execute(_t("""
                CREATE TABLE IF NOT EXISTS luma_catalog (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    doc_type TEXT NOT NULL DEFAULT 'link',
                    source TEXT NOT NULL DEFAULT 'user',
                    file_url TEXT NOT NULL,
                    file_key TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}'::text,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """))

            # Non-breaking migrations
            conn.execute(_t("""
                ALTER TABLE luma_catalog
                    ADD COLUMN IF NOT EXISTS title TEXT NOT NULL DEFAULT 'Untitled',
                    ADD COLUMN IF NOT EXISTS doc_type TEXT NOT NULL DEFAULT 'link',
                    ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'user',
                    ADD COLUMN IF NOT EXISTS file_url TEXT NOT NULL DEFAULT '',
                    ADD COLUMN IF NOT EXISTS file_key TEXT,
                    ADD COLUMN IF NOT EXISTS metadata_json TEXT NOT NULL DEFAULT '{}'::text,
                    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
            """))

            conn.execute(_t("""
                CREATE INDEX IF NOT EXISTS idx_luma_catalog_user_created
                ON luma_catalog(user_id, created_at DESC);
            """))

            conn.execute(_t("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_luma_catalog_user_filekey
                ON luma_catalog(user_id, file_key)
                WHERE file_key IS NOT NULL AND file_key <> '';
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
                    "metadata": _to_json_str(metadata, require_object=True),
                    "blueprint": _to_json_str(blueprint, require_object=True),
                    "published": bool(published),
                }
            )
        return {"ok": True, "content_id": content_id}

    except Exception as e:
        logger.exception(f"luma_store: insert_content failed: {e}")
        return {"ok": False, "error": str(e)}


def get_content(content_id: str, *, include_unpublished: bool = False) -> Optional[Dict[str, Any]]:
    """Get content by ID.

    Production rule:
    - Public reads should only return published content.
    - Admin tooling can opt-in to unpublished via include_unpublished=True.
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

            if (not include_unpublished) and (not bool(row[5])):
                return None

            metadata = _from_json(row[1], {})
            blueprint = _from_json(row[2], {})

            md = metadata if isinstance(metadata, dict) else {}
            bp = blueprint if isinstance(blueprint, dict) else {}

            # Canonical title: prefer blueprint.title, fallback to metadata topic/chapter, then id
            title = ""
            if isinstance(bp, dict):
                title = str(bp.get("title") or "").strip()
            if not title:
                title = str(md.get("topic") or md.get("chapter") or "").strip()
            if not title:
                title = str(row[0])

            return {
                "id": row[0],
                "title": title,
                "metadata": md,
                "blueprint": bp,
                "published": bool(row[5]),
                "created_at": row[3].isoformat() if row[3] else None,
                "updated_at": row[4].isoformat() if row[4] else None,
            }

    except Exception as e:
        logger.exception(f"luma_store: get_content failed: {e}")
        return None


def list_content(
    class_level: Optional[int] = None,
    subject: Optional[str] = None,
    board: Optional[str] = None,
    limit: int = 50,
    *,
    include_unpublished: bool = False
) -> List[Dict[str, Any]]:
    """
    List content with optional filters.
    Phase-1 behavior: do NOT block by published flag.
    """
    engine = get_engine_safe()
    if not engine:
        return []

    try:
        # IMPORTANT:
        # Your JSON columns are TEXT. Casting TEXT -> jsonb in SQL will throw if any row contains
        # invalid JSON, which turns simple list endpoints into INTERNAL_ERROR.
        #
        # For production safety (and your current scale), we fetch recent rows and filter in Python.
        # Later, if you migrate columns to JSONB with constraints, you can move filters back to SQL.

        lim = min(int(limit), 100)

        with engine.connect() as conn:
            rows = conn.execute(
                _t("""
                SELECT id, metadata_json, blueprint_json, created_at, updated_at, published
                FROM luma_content
                ORDER BY created_at DESC
                LIMIT :limit
                """),
                {"limit": lim}
            ).fetchall()

        out: List[Dict[str, Any]] = []
        for r in rows:
            md_raw = _from_json(r[1], {})
            bp_raw = _from_json(r[2], {})

            md = md_raw if isinstance(md_raw, dict) else {}
            bp = bp_raw if isinstance(bp_raw, dict) else {}

            # Production rule: public listing should not leak unpublished content.
            if (not include_unpublished) and (not bool(r[5])):
                continue

            # Apply optional filters in Python (safe even if some rows are malformed).
            if class_level is not None:
                v = str(md.get("class_level", "")).strip()
                if v != str(class_level):
                    continue

            if subject:
                sv = str(md.get("subject", ""))
                if subject.lower() not in sv.lower():
                    continue

            if board:
                bv = str(md.get("board", ""))
                if board.lower() not in bv.lower():
                    continue

            # Canonical title: prefer blueprint.title, fallback to metadata topic/chapter, then id
            title = ""
            if isinstance(bp, dict):
                title = str(bp.get("title") or "").strip()
            if not title:
                title = str(md.get("topic") or md.get("chapter") or "").strip()
            if not title:
                title = str(r[0])

            out.append({
                "id": r[0],
                "title": title,
                "metadata": md,
                "blueprint": bp,
                "published": bool(r[5]),
                "created_at": r[3].isoformat() if r[3] else None,
                "updated_at": r[4].isoformat() if r[4] else None,
            })

        return out

    except Exception as e:
        logger.exception(f"luma_store: list_content failed: {e}")
        return []


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


# ============================================================================
# CATALOG OPERATIONS (User Library)
# ============================================================================

def create_catalog_item(
    *,
    user_id: int,
    title: str,
    doc_type: str,
    source: str,
    file_url: str,
    file_key: str = "",
    metadata: Any = None,
) -> Optional[Dict[str, Any]]:
    """Create a catalog row for a user's saved resource.

    Best-effort: returns created row dict, or None.
    """
    ensure_tables()
    engine = get_engine_safe()
    if not engine:
        return None

    title = (title or "Untitled").strip()[:200] or "Untitled"
    doc_type = (doc_type or "link").strip().lower()[:40] or "link"
    source = (source or "user").strip().lower()[:40] or "user"
    file_url = (file_url or "").strip()
    file_key = (file_key or "").strip()[:240]

    if not file_url:
        return None

    meta_json = _to_json_str(metadata or {}, require_object=True)

    try:
        with engine.begin() as conn:
            row = conn.execute(
                _t("""
                    INSERT INTO luma_catalog (user_id, title, doc_type, source, file_url, file_key, metadata_json)
                    VALUES (:user_id, :title, :doc_type, :source, :file_url, :file_key, :metadata_json)
                    ON CONFLICT (user_id, file_key) WHERE (file_key IS NOT NULL AND file_key <> '')
                    DO UPDATE SET title=EXCLUDED.title, doc_type=EXCLUDED.doc_type, source=EXCLUDED.source, file_url=EXCLUDED.file_url, metadata_json=EXCLUDED.metadata_json
                    RETURNING id, user_id, title, doc_type, source, file_url, file_key, metadata_json, created_at
                """),
                {
                    "user_id": int(user_id),
                    "title": title,
                    "doc_type": doc_type,
                    "source": source,
                    "file_url": file_url,
                    "file_key": file_key,
                    "metadata_json": meta_json,
                },
            ).mappings().first()

            if not row:
                return None

            return {
                "id": row.get("id"),
                "user_id": row.get("user_id"),
                "title": row.get("title"),
                "doc_type": row.get("doc_type"),
                "source": row.get("source"),
                "file_url": row.get("file_url"),
                "file_key": row.get("file_key") or "",
                "metadata": _from_json(row.get("metadata_json"), {}),
                "created_at": str(row.get("created_at")) if row.get("created_at") is not None else None,
            }
    except Exception:
        logger.exception("luma_store: create_catalog_item failed")
        return None


def list_catalog(
    *,
    user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """List a user's catalog items (newest first)."""
    ensure_tables()
    engine = get_engine_safe()
    if not engine:
        return []
    try:
        limit = max(1, min(int(limit or 50), 200))
        offset = max(0, int(offset or 0))
    except Exception:
        limit, offset = 50, 0

    try:
        with engine.begin() as conn:
            rows = conn.execute(
                _t("""
                    SELECT id, user_id, title, doc_type, source, file_url, file_key, metadata_json, created_at
                    FROM luma_catalog
                    WHERE user_id = :user_id
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                """),
                {"user_id": int(user_id), "limit": limit, "offset": offset},
            ).mappings().all()

            out = []
            for r in rows or []:
                out.append(
                    {
                        "id": r.get("id"),
                        "user_id": r.get("user_id"),
                        "title": r.get("title"),
                        "doc_type": r.get("doc_type"),
                        "source": r.get("source"),
                        "file_url": r.get("file_url"),
                        "file_key": r.get("file_key") or "",
                        "metadata": _from_json(r.get("metadata_json"), {}),
                        "created_at": str(r.get("created_at")) if r.get("created_at") is not None else None,
                    }
                )
            return out
    except Exception:
        logger.exception("luma_store: list_catalog failed")
        return []


def delete_catalog_item(*, user_id: int, item_id: int) -> bool:
    """Delete one catalog item owned by user."""
    ensure_tables()
    engine = get_engine_safe()
    if not engine:
        return False
    try:
        with engine.begin() as conn:
            res = conn.execute(
                _t("""
                    DELETE FROM luma_catalog
                    WHERE id = :id AND user_id = :user_id
                """),
                {"id": int(item_id), "user_id": int(user_id)},
            )
            return (res.rowcount or 0) > 0
    except Exception:
        logger.exception("luma_store: delete_catalog_item failed")
        return False
