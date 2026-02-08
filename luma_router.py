"""
LUMA ROUTER v2 — Serves chapter learning JSONs
Replaces: luma_router.py, luma_store.py, luma_schemas.py, luma_config.py

Endpoints:
  GET  /api/luma/content   — Fetch Luma JSON for a chapter
  POST /api/luma/progress  — Save user progress (authenticated)
  GET  /api/luma/progress   — Get user progress (authenticated)
"""
from __future__ import annotations
import json, logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Query
from sqlalchemy import text

import os

try:
    from db import get_engine_safe
except ImportError:
    def get_engine_safe():
        return None

from study_store import resolve_asset, get_active_content_assets

R2_PUBLIC_BASE = os.getenv("R2_PUBLIC_BASE", "")

logger = logging.getLogger("knoweasy-engine-api")
router = APIRouter(prefix="/api/luma", tags=["luma"])

# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _get_user_id(authorization: str = Header(None)) -> Optional[int]:
    if not authorization:
        return None
    try:
        if not authorization.startswith("Bearer "):
            return None
        tok = authorization.split(" ", 1)[1].strip()
        from auth_store import session_user
        u = session_user(tok)
        if u and u.get("id"):
            return int(u["id"])
        return None
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
    Returns Luma JSON URL for a chapter.
    Priority: content_id → resolve from chapter params.
    """
    cid = content_id
    if not cid and chapter_id:
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

    # Find luma_json asset
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

    url = luma_asset.get("url") or ""
    obj_key = luma_asset.get("object_key") or ""
    storage = (luma_asset.get("storage") or "").lower()

    if not url and obj_key:
        if R2_PUBLIC_BASE:
            url = f"{R2_PUBLIC_BASE}/{obj_key}"
        elif storage == "r2":
            # Generate presigned URL for R2 objects
            try:
                from r2_client import presign_get_object
                url = presign_get_object(object_key=obj_key)
            except Exception:
                url = ""
        elif storage == "db":
            url = f"/api/assets/blob?content_id={cid}&asset_type=luma_json"

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
async def save_luma_progress(req: dict, authorization: str = Header(None)):
    user_id = await _get_user_id(authorization)
    if not user_id:
        raise HTTPException(401, "Unauthorized")

    content_id = req.get("content_id")
    if not content_id:
        raise HTTPException(400, "content_id required")

    engine = get_engine_safe()
    if not engine:
        raise HTTPException(503, "Database unavailable")

    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO luma_progress (user_id, content_id, section_index, card_index, completed, time_spent_sec, bookmarks)
                VALUES (:uid, :cid, :si, :ci, :done, :ts, :bm)
                ON CONFLICT (user_id, content_id) DO UPDATE SET
                    section_index = EXCLUDED.section_index,
                    card_index = EXCLUDED.card_index,
                    completed = EXCLUDED.completed,
                    time_spent_sec = luma_progress.time_spent_sec + EXCLUDED.time_spent_sec,
                    bookmarks = EXCLUDED.bookmarks,
                    updated_at = NOW()
            """), {
                "uid": user_id,
                "cid": content_id,
                "si": req.get("section_index", 0),
                "ci": req.get("card_index", 0),
                "done": req.get("completed", False),
                "ts": req.get("time_spent_sec", 0),
                "bm": json.dumps(req.get("bookmarks", [])),
            })
        return {"ok": True}
    except Exception as e:
        logger.error(f"Save luma progress error: {e}")
        return {"ok": False, "error": str(e)}


@router.get("/progress")
async def get_luma_progress(content_id: str = Query(...), authorization: str = Header(None)):
    user_id = await _get_user_id(authorization)
    if not user_id:
        raise HTTPException(401, "Unauthorized")

    engine = get_engine_safe()
    if not engine:
        return {"ok": False, "progress": None}

    try:
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT section_index, card_index, completed, time_spent_sec, bookmarks, updated_at
                FROM luma_progress WHERE user_id = :uid AND content_id = :cid
            """), {"uid": user_id, "cid": content_id}).fetchone()

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
    engine = get_engine_safe()
    if not engine:
        return
    try:
        with engine.begin() as conn:
            conn.execute(text("""
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
            """))
        logger.info("luma_progress table ready")
    except Exception as e:
        logger.warning(f"luma_progress table setup: {e}")
