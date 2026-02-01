"""Luma Database Store

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
from datetime import datetime, timezone

logger = logging.getLogger("knoweasy-engine-api")

# SQLAlchemy 2.x compatibility: plain strings are not executable.
# Use exec_driver_sql for raw SQL (no params) and text() for parameterized SQL.
try:
    from sqlalchemy import text as _sql_text
except Exception:  # pragma: no cover
    _sql_text = None


def _exec_sql(conn, sql: str, params: dict | None = None):
    """Execute SQL in a way that works across SQLAlchemy versions.

    - If params is None: uses exec_driver_sql (accepts raw strings)
    - If params provided: wraps with sqlalchemy.text
    """
    if params is None:
        return conn.exec_driver_sql(sql)
    if _sql_text is None:
        raise RuntimeError("sqlalchemy.text unavailable for parameterized SQL")
    return conn.execute(_sql_text(sql), params)


# Safe imports - never crash if DB is unavailable
try:
    from db import get_engine_safe
except Exception:
    def get_engine_safe():
        return None


# ============================================================================
# TABLE DEFINITIONS (Non-breaking, idempotent)
# ============================================================================

def ensure_tables() -> None:
    """Create Luma tables if they don't exist.
    
    This is called on startup and never crashes the app.
    Uses CREATE TABLE IF NOT EXISTS for idempotency.
    """
    engine = get_engine_safe()
    if not engine:
        logger.warning("luma_store: DB unavailable, tables not created")
        return
    
    try:
        with engine.begin() as conn:
            # Content table - stores Answer Blueprints
            _exec_sql(conn, """
                CREATE TABLE IF NOT EXISTS luma_content (
                    id TEXT PRIMARY KEY,
                    metadata_json TEXT NOT NULL,
                    blueprint_json TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    published BOOLEAN NOT NULL DEFAULT FALSE
                );
            """)
            
            # Progress table - user learning progress
            _exec_sql(conn, """
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
            """)
            
            # Analytics table - usage events
            _exec_sql(conn, """
                CREATE TABLE IF NOT EXISTS luma_analytics (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    content_id TEXT,
                    metadata_json TEXT,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            
            # Indexes for performance
            _exec_sql(conn, """
                CREATE INDEX IF NOT EXISTS idx_luma_content_published 
                ON luma_content(published) WHERE published = TRUE;
            """)
            
            _exec_sql(conn, """
                CREATE INDEX IF NOT EXISTS idx_luma_progress_user 
                ON luma_progress(user_id, last_visited_at DESC);
            """)
            
            _exec_sql(conn, """
                CREATE INDEX IF NOT EXISTS idx_luma_analytics_user 
                ON luma_analytics(user_id, timestamp DESC);
            """)
            
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
    """Insert new learning content.
    
    Args:
        content_id: Unique content identifier
        metadata: Content metadata (class, board, subject, etc)
        blueprint: Answer Blueprint structure
        published: Whether content is published
        
    Returns:
        Result dict with ok status
    """
    engine = get_engine_safe()
    if not engine:
        return {"ok": False, "error": "DB_UNAVAILABLE"}
    
    try:
        with engine.begin() as conn:
            _exec_sql(conn, """
                INSERT INTO luma_content (id, metadata_json, blueprint_json, published)
                VALUES (:id, :metadata, :blueprint, :published)
                ON CONFLICT (id) DO UPDATE SET
                    metadata_json = EXCLUDED.metadata_json,
                    blueprint_json = EXCLUDED.blueprint_json,
                    published = EXCLUDED.published,
                    updated_at = NOW()
                """, {
                    "id": content_id,
                    "metadata": json.dumps(metadata),
                    "blueprint": json.dumps(blueprint),
                    "published": published,
                })
        
        logger.info(f"luma_store: inserted content {content_id}")
        return {"ok": True, "content_id": content_id}
    
    except Exception as e:
        logger.exception(f"luma_store: insert_content failed: {e}")
        return {"ok": False, "error": str(e)}


def get_content(content_id: str) -> Optional[Dict[str, Any]]:
    """Get content by ID.
    
    Args:
        content_id: Content identifier
        
    Returns:
        Content dict or None if not found
    """
    engine = get_engine_safe()
    if not engine:
        return None
    
    try:
        with engine.connect() as conn:
            result = _exec_sql(conn, """
                SELECT id, metadata_json, blueprint_json, created_at, updated_at, published
                FROM luma_content
                WHERE id = :id AND published = TRUE
                """, {"id": content_id}).fetchone()
            
            if not result:
                return None
            
            return {
                "id": result[0],
                "metadata": json.loads(result[1]),
                "blueprint": json.loads(result[2]),
                "created_at": result[3].isoformat() if result[3] else None,
                "updated_at": result[4].isoformat() if result[4] else None,
                "published": result[5],
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
    """List published content with optional filters.
    
    Args:
        class_level: Filter by class (5-12)
        subject: Filter by subject
        board: Filter by board
        limit: Maximum results
        
    Returns:
        List of content dicts
    """
    engine = get_engine_safe()
    if not engine:
        return []
    
    try:
        # Build dynamic query based on filters
        conditions = ["published = TRUE"]
        params: Dict[str, Any] = {"limit": limit}
        
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
            results = conn.execute(
                f"""
                SELECT id, metadata_json, blueprint_json, created_at, updated_at
                FROM luma_content
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT :limit
                """,
                params
            ).fetchall()
            
            return [
                {
                    "id": r[0],
                    "metadata": json.loads(r[1]),
                    "blueprint": json.loads(r[2]),
                    "created_at": r[3].isoformat() if r[3] else None,
                    "updated_at": r[4].isoformat() if r[4] else None,
                }
                for r in results
            ]
    
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
    """Save or update user progress.
    
    Args:
        user_id: User ID
        content_id: Content ID
        completed: Completion status
        time_spent_seconds: Time spent (incremental)
        notes: User notes
        bookmarked: Bookmark status
        
    Returns:
        Result dict with ok status
    """
    engine = get_engine_safe()
    if not engine:
        return {"ok": False, "error": "DB_UNAVAILABLE"}
    
    try:
        with engine.begin() as conn:
            _exec_sql(conn, """
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
                """, {
                    "user_id": user_id,
                    "content_id": content_id,
                    "completed": completed,
                    "time_spent": time_spent_seconds,
                    "notes": notes,
                    "bookmarked": bookmarked,
                })
        
        return {"ok": True}
    
    except Exception as e:
        logger.exception(f"luma_store: save_progress failed: {e}")
        return {"ok": False, "error": str(e)}


def get_progress(user_id: int, content_id: str) -> Optional[Dict[str, Any]]:
    """Get user progress for specific content.
    
    Args:
        user_id: User ID
        content_id: Content ID
        
    Returns:
        Progress dict or None
    """
    engine = get_engine_safe()
    if not engine:
        return None
    
    try:
        with engine.connect() as conn:
            result = _exec_sql(conn, """
                SELECT completed, time_spent_seconds, notes, bookmarked, last_visited_at
                FROM luma_progress
                WHERE user_id = :user_id AND content_id = :content_id
                """, {"user_id": user_id, "content_id": content_id}).fetchone()
            
            if not result:
                return None
            
            return {
                "completed": result[0],
                "time_spent_seconds": result[1],
                "notes": result[2],
                "bookmarked": result[3],
                "last_visited_at": result[4].isoformat() if result[4] else None,
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
    """Log analytics event (best-effort, never crashes).
    
    Args:
        user_id: User ID
        event_type: Event type (view/complete/ai_ask/bookmark)
        content_id: Content ID if applicable
        metadata: Additional event data
    """
    engine = get_engine_safe()
    if not engine:
        return
    
    try:
        with engine.begin() as conn:
            _exec_sql(conn, """
                INSERT INTO luma_analytics (user_id, event_type, content_id, metadata_json)
                VALUES (:user_id, :event_type, :content_id, :metadata)
                """, {
                    "user_id": user_id,
                    "event_type": event_type,
                    "content_id": content_id,
                    "metadata": json.dumps(metadata) if metadata else None,
                })
    except Exception as e:
        # Analytics failures should never break the app
        logger.warning(f"luma_store: analytics logging failed: {e}")
