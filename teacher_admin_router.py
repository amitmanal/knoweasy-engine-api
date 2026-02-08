"""
teacher_admin_router.py — Admin endpoints for content publishing (X-Admin-Key protected)

Endpoints:
- GET  /api/admin/catalog        — subjects+chapters for dropdowns
- POST /api/admin/content/ensure — create/return content_id
- POST /api/admin/assets/presign — presigned PUT URL for R2
- POST /api/admin/publish        — activate assets + set status
"""

from __future__ import annotations

import os
import re
import uuid
from typing import Any, Dict, Optional, List

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from db import get_engine_safe
from sqlalchemy import text as _t

import study_store
from r2_client import presign_put_object

router = APIRouter(prefix="/api/admin", tags=["teacher_admin"])


def _admin_key() -> str:
    return (os.getenv("ADMIN_API_KEY") or "").strip()


def _require_admin(x_admin_key: Optional[str]) -> None:
    key = _admin_key()
    if not key:
        raise PermissionError("ADMIN_DISABLED")
    if not x_admin_key or x_admin_key.strip() != key:
        raise PermissionError("ADMIN_FORBIDDEN")


def _handle_auth(x_admin_key: Optional[str]):
    try:
        _require_admin(x_admin_key)
    except PermissionError as e:
        if str(e) == "ADMIN_DISABLED":
            return JSONResponse(status_code=404, content={"ok": False, "error": "NOT_FOUND"})
        return JSONResponse(status_code=403, content={"ok": False, "error": "FORBIDDEN"})
    return None


def _safe_name(name: str) -> str:
    n = re.sub(r"[^a-zA-Z0-9._-]+", "_", (name or "").strip())
    return n[:120] or "file"


# ─── Models ──────────────────────────────────────────────────────────────────

class PresignReq(BaseModel):
    content_id: str
    asset_type: str
    filename: str
    mime_type: Optional[str] = None


class PublishAsset(BaseModel):
    asset_type: str
    storage: str = "r2"
    object_key: Optional[str] = None
    url: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    checksum: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class PublishReq(BaseModel):
    content_id: str
    status: str = "published"
    assets: List[PublishAsset] = []


class EnsureContentReq(BaseModel):
    track: str
    program: str
    class_level: int
    subject_code: str
    chapter_slug: str


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/catalog")
def catalog(
    track: str,
    program: str,
    class_level: int,
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    """Return subjects+chapters for admin dropdowns."""
    err = _handle_auth(x_admin_key)
    if err:
        return err

    e = get_engine_safe()
    if not e:
        raise HTTPException(503, {"ok": False, "error": "DB_UNAVAILABLE"})

    from syllabus_router import _norm_track_program
    t, p = _norm_track_program(track, program)
    # DB uses 'boards' not 'board'
    track_db = "boards" if t == "board" else t

    try:
        with e.connect() as c:
            rows = c.execute(_t("""
                SELECT subject_slug, chapter_id, chapter_title
                FROM syllabus_chapters
                WHERE track=:t AND program=:p AND class_num=:cls AND is_active=TRUE
                ORDER BY subject_slug ASC, order_index ASC
            """), {"t": track_db, "p": p, "cls": int(class_level)}).fetchall()

        subjects: Dict[str, Dict] = {}
        for r in rows or []:
            sc = r[0]
            subjects.setdefault(sc, {
                "subject_code": sc,
                "subject_name": sc.replace("_", " ").title(),
                "chapters": [],
            })
            subjects[sc]["chapters"].append({
                "chapter_slug": r[1],
                "chapter_title": r[2],
            })

        return {
            "ok": True,
            "key": {"track": t, "program": p, "class_level": int(class_level)},
            "subjects": list(subjects.values()),
        }
    except Exception as ex:
        raise HTTPException(500, {"ok": False, "error": str(ex)})


@router.post("/content/ensure")
def ensure_content_id(
    req: EnsureContentReq,
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    """Ensure a content_id mapping exists for this chapter."""
    err = _handle_auth(x_admin_key)
    if err:
        return err

    result = study_store.ensure_content_item(
        track=req.track, program=req.program, class_num=req.class_level,
        subject_slug=req.subject_code, chapter_id=req.chapter_slug,
    )
    return result


@router.post("/assets/presign")
def presign_upload(
    req: PresignReq,
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    """Return presigned PUT URL for direct upload to R2."""
    err = _handle_auth(x_admin_key)
    if err:
        return err

    cid = req.content_id.strip()
    at = req.asset_type.strip().lower()
    fname = _safe_name(req.filename)
    suffix = uuid.uuid4().hex[:8]
    object_key = f"v1/content/{cid}/{at}/{suffix}__{fname}"

    try:
        put_url = presign_put_object(object_key=object_key, content_type=req.mime_type)
        return {"ok": True, "content_id": cid, "asset_type": at,
                "object_key": object_key, "put_url": put_url}
    except Exception as ex:
        raise HTTPException(400, {"ok": False, "error": str(ex)})


@router.post("/publish")
def publish_assets(
    req: PublishReq,
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    """Activate assets and set content status."""
    err = _handle_auth(x_admin_key)
    if err:
        return err

    cid = (req.content_id or "").strip()
    if not cid:
        raise HTTPException(400, {"ok": False, "error": "MISSING_CONTENT_ID"})

    # Write assets
    results = []
    for a in req.assets:
        results.append(study_store.set_content_asset(
            content_id=cid, asset_type=a.asset_type, storage=a.storage,
            object_key=a.object_key, url=a.url, mime_type=a.mime_type,
            size_bytes=a.size_bytes, checksum=a.checksum, meta=a.meta, activate=True,
        ))

    # Set content status
    status_result = study_store.set_content_status(cid, req.status)

    return {"ok": True, "content_id": cid, "status": req.status,
            "assets_result": results, "status_result": status_result}
