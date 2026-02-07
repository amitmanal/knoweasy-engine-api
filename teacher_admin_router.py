from __future__ import annotations

import os
import re
import uuid
from typing import Any, Dict, Optional

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


def _safe_name(name: str) -> str:
    n = (name or "").strip()
    n = re.sub(r"[^a-zA-Z0-9._-]+", "_", n)
    return n[:120] or "file"


class PresignReq(BaseModel):
    content_id: str
    asset_type: str = Field(..., description="notes_pdf|revision_html|blueprint_json|mindmap|pyq|test_json|etc")
    filename: str
    mime_type: Optional[str] = None


class PublishAsset(BaseModel):
    asset_type: str
    storage: str = Field(..., description="r2|hostinger")
    object_key: Optional[str] = None
    url: Optional[str] = None
    mime_type: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class PublishReq(BaseModel):
    content_id: str
    assets: list[PublishAsset]


class EnsureContentReq(BaseModel):
    track: str
    program: str
    class_level: int
    subject_code: str
    chapter_slug: str
    chapter_title: Optional[str] = None


@router.get("/catalog")
def catalog(
    track: str,
    program: str,
    class_level: int,
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    """Return subjects+chapters for dropdowns (teacher UI)."""
    try:
        _require_admin(x_admin_key)
    except PermissionError as e:
        if str(e) == "ADMIN_DISABLED":
            return JSONResponse(status_code=404, content={"ok": False, "error": "NOT_FOUND"})
        return JSONResponse(status_code=403, content={"ok": False, "error": "FORBIDDEN"})

    e = get_engine_safe()
    if not e:
        raise HTTPException(503, {"ok": False, "error": "DB_UNAVAILABLE"})

    # Normalize like syllabus endpoint
    from syllabus_router import _norm_track_program
    t, p = _norm_track_program(track, program)
    cls = int(class_level)

    # Use syllabus_chapters (canonical)
    try:
        with e.connect() as c:
            rows = c.execute(_t("""
                SELECT subject_slug, chapter_id, chapter_title
                FROM syllabus_chapters
                WHERE track=:t AND program=:p AND class_num=:cls AND is_active=TRUE
                ORDER BY subject_slug ASC, order_index ASC, chapter_title ASC
            """), {"t": t, "p": p, "cls": cls}).fetchall()

        subjects: Dict[str, Dict[str, Any]] = {}
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
            "key": {"track": t, "program": p, "class_level": cls},
            "subjects": list(subjects.values()),
        }
    except Exception as ex:
        raise HTTPException(500, {"ok": False, "error": "QUERY_FAILED", "message": str(ex)})


@router.post("/assets/presign")
def presign_upload(
    req: PresignReq,
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    """Return presigned PUT url for direct upload to R2."""
    try:
        _require_admin(x_admin_key)
    except PermissionError as e:
        if str(e) == "ADMIN_DISABLED":
            return JSONResponse(status_code=404, content={"ok": False, "error": "NOT_FOUND"})
        return JSONResponse(status_code=403, content={"ok": False, "error": "FORBIDDEN"})

    cid = req.content_id.strip()
    at = req.asset_type.strip().lower()
    fname = _safe_name(req.filename)
    suffix = uuid.uuid4().hex[:8]

    object_key = f"v1/content/{cid}/{at}/{suffix}__{fname}"
    try:
        put_url = presign_put_object(object_key=object_key, content_type=req.mime_type)
        return {
            "ok": True,
            "content_id": cid,
            "asset_type": at,
            "object_key": object_key,
            "put_url": put_url,
        }
    except Exception as ex:
        raise HTTPException(400, {"ok": False, "error": "PRESIGN_FAILED", "message": str(ex)})


@router.post("/content/ensure")
def ensure_content_id(
    req: EnsureContentReq,
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    """Ensure there is a content_id mapping for this chapter (for assets registry)."""
    try:
        _require_admin(x_admin_key)
    except PermissionError as e:
        if str(e) == "ADMIN_DISABLED":
            return JSONResponse(status_code=404, content={"ok": False, "error": "NOT_FOUND"})
        return JSONResponse(status_code=403, content={"ok": False, "error": "FORBIDDEN"})

    # Normalize to internal style used by study_store
    from syllabus_router import _norm_track_program
    t, p = _norm_track_program(req.track, req.program)
    cls = int(req.class_level)
    subj = study_store._slugify(req.subject_code)  # type: ignore
    ch = study_store._slugify(req.chapter_slug)  # type: ignore

    # Try resolve existing luma mapping first
    r = study_store.resolve_asset(
        track=t,
        program=p,
        class_num=cls,
        subject_slug=subj,
        chapter_id=ch,
        chapter_title=req.chapter_title,
        asset_type="luma",
    )
    if r.get("ok") and (r.get("asset") or {}).get("ref_kind") == "db":
        return {"ok": True, "content_id": (r.get("asset") or {}).get("ref_value"), "status": "existing"}

    # Create deterministic content_id
    cid = f"{ch}-{t}-{p}-{cls}-{subj}-001"
    # Store mapping using existing chapter_assets table (compat) as luma=db
    out = study_store.upsert_asset_mapping(
        track=t,
        program=p,
        class_num=cls,
        subject_slug=subj,
        chapter_id=ch,
        asset_type="luma",
        status="published",
        ref_kind="db",
        ref_value=cid,
        meta_json={"auto": True},
    )
    return {"ok": True, "content_id": cid, "status": "created", "result": out}


@router.post("/publish")
def publish_assets(
    req: PublishReq,
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    """Activate assets for a content_id (writes to content_assets table)."""
    try:
        _require_admin(x_admin_key)
    except PermissionError as e:
        if str(e) == "ADMIN_DISABLED":
            return JSONResponse(status_code=404, content={"ok": False, "error": "NOT_FOUND"})
        return JSONResponse(status_code=403, content={"ok": False, "error": "FORBIDDEN"})

    cid = (req.content_id or "").strip()
    if not cid:
        raise HTTPException(400, {"ok": False, "error": "MISSING_CONTENT_ID"})

    results = []
    for a in req.assets:
        results.append(study_store.set_content_asset(
            content_id=cid,
            asset_type=a.asset_type,
            storage=a.storage,
            object_key=a.object_key,
            url=a.url,
            mime_type=a.mime_type,
            meta=a.meta,
            activate=True,
        ))

    return {"ok": True, "content_id": cid, "results": results}
