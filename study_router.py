"""
study_router.py — Study API endpoints (production)

Endpoints:
- GET /api/study/resolve — resolve chapter -> content_id + status
- GET /api/study/assets  — get active assets for a content_id
- GET /api/study/chapters — list chapters for a subject (used by frontend)
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

import study_store
from r2_client import presign_get_object

logger = logging.getLogger("knoweasy-engine-api")

router = APIRouter(prefix="/api/study", tags=["study"])

# Ensure tables on import
try:
    study_store.ensure_tables()
except Exception as e:
    logger.warning(f"study_router: ensure_tables: {e}")


@router.get("/resolve")
def resolve(
    track: str = Query(...),
    program: str = Query(...),
    class_num: int = Query(..., ge=5, le=12),
    subject_slug: str = Query(...),
    chapter_id: str = Query(""),
    chapter_title: Optional[str] = Query(None),
    asset_type: str = Query("luma"),
):
    """Resolve content behind a chapter. Never returns 500."""
    try:
        # Normalize
        track_n = (track or "").strip().lower()
        program_n = (program or "").strip().lower()
        subject_n = study_store._slugify(subject_slug)
        chapter_n = (chapter_id or "").strip().lower()
        if not chapter_n and chapter_title:
            chapter_n = study_store._slugify(chapter_title)

        result = study_store.resolve_asset(
            track=track_n, program=program_n, class_num=class_num,
            subject_slug=subject_n, chapter_id=chapter_n,
            chapter_title=chapter_title, asset_type=asset_type,
        )
        return result
    except Exception as e:
        logger.error(f"study/resolve error: {e}")
        return {"ok": False, "status": "error", "message": "Internal error"}


@router.get("/assets")
def study_assets(
    content_id: str = Query(...),
    expires: Optional[int] = Query(None, ge=30, le=3600),
):
    """Return active assets for a content_id with signed URLs."""
    cid = (content_id or "").strip()
    if not cid:
        return JSONResponse(status_code=400, content={"ok": False, "error": "MISSING_CONTENT_ID"})

    assets = study_store.get_active_content_assets(cid)
    by_type = {}
    for a in assets:
        at = a.get("asset_type")
        storage = (a.get("storage") or "").lower()
        url = a.get("url")
        obj_key = a.get("object_key")

        if storage == "r2" and obj_key:
            try:
                url = presign_get_object(object_key=obj_key, expires_in=expires)
            except Exception:
                url = None

        by_type[at] = {
            "exists": True,
            "url": url,
            "mime": a.get("mime_type"),
            "updated_at": a.get("updated_at"),
        }

    # Standard asset slots (always present in response)
    SLOTS = ["notes_pdf", "revision_html", "blueprint_json", "mindmap", "pyq", "test_json"]
    result = {}
    for slot in SLOTS:
        if slot in by_type:
            result[slot] = by_type[slot]
        else:
            result[slot] = {"exists": False, "url": None, "mime": None, "updated_at": None}
    # Also include any extra types
    for k, v in by_type.items():
        if k not in result:
            result[k] = v

    return {"ok": True, "content_id": cid, "assets": result}


@router.get("/chapters")
def list_chapters(
    track: str = Query(...),
    program: str = Query(...),
    class_num: int = Query(..., ge=5, le=12),
    subject_slug: str = Query(...),
):
    """List chapters for a subject (used by frontend study page)."""
    try:
        from db import get_engine_safe
        from sqlalchemy import text as _t
        engine = get_engine_safe()
        if not engine:
            return {"ok": False, "status": "db_unavailable", "chapters": []}

        track_db = study_store._track_to_db(track)
        program_n = study_store._normalize_program(track_db, program)
        subject_n = study_store._slugify(subject_slug)

        with engine.connect() as conn:
            rows = conn.execute(_t("""
                SELECT chapter_id, chapter_title, order_index
                FROM syllabus_chapters
                WHERE class_num=:c AND track=:t AND program=:p AND subject_slug=:s AND is_active=TRUE
                ORDER BY order_index ASC, chapter_title ASC
            """), {"c": class_num, "t": track_db, "p": program_n, "s": subject_n}).fetchall()

        chapters = [{"id": r[0], "title": r[1], "order": int(r[2] or 0)} for r in rows]
        return {"ok": True, "chapters": chapters}
    except Exception as e:
        logger.error(f"study/chapters error: {e}")
        return {"ok": False, "status": "error", "chapters": []}
