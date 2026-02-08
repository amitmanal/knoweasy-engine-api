"""
LUMA ROUTER v2 — Serves chapter learning JSONs
Replaces: luma_router.py, luma_store.py, luma_schemas.py, luma_config.py

Endpoints:
  GET  /api/luma/content   — Fetch Luma JSON for a chapter (by content_id or chapter params)
  POST /api/luma/progress  — Save user progress (authenticated)
  GET  /api/luma/progress   — Get user progress (authenticated)
"""
from __future__ import annotations
import json, logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Query
from study_store import resolve_asset, get_active_content_assets
from db import get_pool
from config import R2_PUBLIC_BASE

logger = logging.getLogger("knoweasy-engine-api")
router = APIRouter(prefix="/api/luma", tags=["luma"])

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _track_api_to_db(track: str) -> str:
    """Normalize API track to DB track."""
    if track in ("board", "boards"):
        return "boards"
    return track  # entrance stays entrance

async def _get_user_id(authorization: str = Header(None)) -> Optional[int]:
    if not authorization:
        return None
    try:
        from auth_utils import decode_token
        if not authorization.startswith("Bearer "):
            return None
        tok = authorization.split(" ", 1)[1]
        payload = decode_token(tok)
        return int(payload["sub"]) if payload and "sub" in payload else None
    except Exception:
        return None

# ─── GET /api/luma/content ────────────────────────────────────────────────────

@router.get("/content")
async def get_luma_content(
    content_id: Optional[str] = None,
    track: Optional[str] = None,
    program: Optional[str] = None,
    class_num: Optional[int] = None,
    subject_slug: Optional[str] = None,
    chapter_id: Optional[str] = None,
):
    """
    Returns Luma JSON for a chapter.
    
    Priority:
      1. If content_id given → look up directly
      2. If chapter params given → resolve content_id first
    
    Returns the luma_json asset URL or inline JSON if stored in DB.
    """
    # Step 1: Resolve content_id
    cid = content_id
    if not cid and chapter_id:
        # Use resolve_asset to find content
        result = resolve_asset(
            track=track or "board",
            program=program or "cbse",
            class_num=class_num or 11,
            subject_slug=subject_slug or "",
            chapter_id=chapter_id,
        )
        if result and result.get("ok"):
            cid = result.get("content_id")
    
    if not cid or cid == "coming-soon":
        return {
            "ok": False,
            "status": "coming_soon",
            "message": "Content is being prepared. Check back soon!",
            "chapter_id": chapter_id,
        }

    # Step 2: Get luma_json asset
    assets = get_active_content_assets(cid)
    luma_asset = None
    for a in assets:
        if a.get("asset_type") == "luma_json":
            luma_asset = a
            break

    if not luma_asset:
        return {
            "ok": False,
            "status": "no_luma_content",
            "content_id": cid,
            "message": "Luma learning content not yet available for this chapter.",
        }

    # Step 3: Return URL to JSON
    url = luma_asset.get("url") or ""
    if not url and luma_asset.get("object_key"):
        url = f"{R2_PUBLIC_BASE}/{luma_asset['object_key']}" if R2_PUBLIC_BASE else ""

    return {
        "ok": True,
        "status": "published",
        "content_id": cid,
        "luma_url": url,
        "asset_type": "luma_json",
        "mime_type": luma_asset.get("mime_type", "application/json"),
        "updated_at": luma_asset.get("updated_at"),
    }


# ─── POST /api/luma/progress ─────────────────────────────────────────────────

@router.post("/progress")
async def save_luma_progress(
    req: dict,
    authorization: str = Header(None),
):
    """Save user's Luma learning progress for a chapter."""
    user_id = await _get_user_id(authorization)
    if not user_id:
        raise HTTPException(401, "Unauthorized")

    content_id = req.get("content_id")
    if not content_id:
        raise HTTPException(400, "content_id required")

    pool = get_pool()
    if not pool:
        raise HTTPException(503, "Database unavailable")

    try:
        with pool.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO luma_progress (user_id, content_id, section_index, card_index, completed, time_spent_sec, bookmarks)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, content_id) DO UPDATE SET
                        section_index = EXCLUDED.section_index,
                        card_index = EXCLUDED.card_index,
                        completed = EXCLUDED.completed,
                        time_spent_sec = luma_progress.time_spent_sec + EXCLUDED.time_spent_sec,
                        bookmarks = EXCLUDED.bookmarks,
                        updated_at = NOW()
                """, (
                    user_id,
                    content_id,
                    req.get("section_index", 0),
                    req.get("card_index", 0),
                    req.get("completed", False),
                    req.get("time_spent_sec", 0),
                    json.dumps(req.get("bookmarks", [])),
                ))
            conn.commit()
            pool.putconn(conn)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Save luma progress error: {e}")
        return {"ok": False, "error": str(e)}


@router.get("/progress")
async def get_luma_progress(
    content_id: str = Query(...),
    authorization: str = Header(None),
):
    """Get user's Luma learning progress."""
    user_id = await _get_user_id(authorization)
    if not user_id:
        raise HTTPException(401, "Unauthorized")

    pool = get_pool()
    if not pool:
        return {"ok": False, "progress": None}

    try:
        with pool.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT section_index, card_index, completed, time_spent_sec, bookmarks, updated_at
                    FROM luma_progress WHERE user_id = %s AND content_id = %s
                """, (user_id, content_id))
                row = cur.fetchone()
            pool.putconn(conn)

        if not row:
            return {"ok": True, "progress": None}

        return {
            "ok": True,
            "progress": {
                "section_index": row[0],
                "card_index": row[1],
                "completed": row[2],
                "time_spent_sec": row[3],
                "bookmarks": json.loads(row[4]) if row[4] else [],
                "updated_at": str(row[5]) if row[5] else None,
            }
        }
    except Exception as e:
        logger.error(f"Get luma progress error: {e}")
        return {"ok": False, "progress": None}


# ─── Table Setup ──────────────────────────────────────────────────────────────

def ensure_tables():
    """Create luma_progress table if not exists."""
    pool = get_pool()
    if not pool:
        return
    try:
        with pool.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS luma_progress (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        content_id TEXT NOT NULL,
                        section_index INTEGER DEFAULT 0,
                        card_index INTEGER DEFAULT 0,
                        completed BOOLEAN DEFAULT FALSE,
                        time_spent_sec INTEGER DEFAULT 0,
                        bookmarks JSONB DEFAULT '[]',
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW(),
                        UNIQUE(user_id, content_id)
                    )
                """)
            conn.commit()
            pool.putconn(conn)
        logger.info("luma_progress table ready")
    except Exception as e:
        logger.warning(f"luma_progress table setup: {e}")
