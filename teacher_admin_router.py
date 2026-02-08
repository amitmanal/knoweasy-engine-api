"""
teacher_admin_router.py — Teacher/Admin endpoints for content publishing

Endpoints:
- GET  /api/teacher/catalog     — full catalog (tracks, programs, classes, subjects, chapters)
- POST /api/teacher/ensure      — create/return content_id for a chapter
- POST /api/teacher/upload      — upload file (PDF/JSON) to R2 or DB blob
- POST /api/teacher/publish     — set content status to published/draft
- GET  /api/teacher/seed        — seed syllabus from JS files (one-time setup)
"""

from __future__ import annotations
import os, re, uuid, logging, json
from typing import Any, Dict, Optional, List
from fastapi import APIRouter, Header, HTTPException, UploadFile, File, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger("knoweasy-engine-api")
router = APIRouter(prefix="/api/teacher", tags=["teacher_admin"])


def _admin_key() -> str:
    return (os.getenv("ADMIN_API_KEY") or "").strip()


def _require_auth(x_admin_key: Optional[str] = None, authorization: Optional[str] = None):
    """Check admin key OR valid session token. Returns None if OK, else raises."""
    key = _admin_key()
    # 1) Admin API key
    if key and x_admin_key and x_admin_key.strip() == key:
        return
    # 2) Bearer token session
    if authorization and authorization.lower().startswith("bearer "):
        try:
            from auth_store import session_user
            token = authorization.split(" ", 1)[1].strip()
            u = session_user(token)
            if u:
                return  # any authenticated user can upload (teacher check can be added later)
        except Exception:
            pass
    # 3) No auth configured = allow (dev mode)
    if not key:
        return
    raise HTTPException(403, {"ok": False, "error": "FORBIDDEN", "hint": "Provide X-Admin-Key header or Authorization Bearer token"})


def _safe_name(name: str) -> str:
    n = re.sub(r"[^a-zA-Z0-9._-]+", "_", (name or "").strip())
    return n[:120] or "file"


# ─── Catalog ────────────────────────────────────────────────────────────────

@router.get("/catalog")
def catalog(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    authorization: Optional[str] = Header(None),
):
    """Return full catalog for dropdowns: tracks, programs, classes, subjects+chapters."""
    _require_auth(x_admin_key, authorization)

    from db import get_engine_safe
    from sqlalchemy import text as _t
    e = get_engine_safe()
    if not e:
        raise HTTPException(503, {"ok": False, "error": "DB_UNAVAILABLE"})

    try:
        with e.connect() as c:
            # Check if table exists
            check = c.execute(_t("SELECT to_regclass('syllabus_chapters')")).fetchone()
            if not check or not check[0]:
                return {"ok": False, "error": "SYLLABUS_NOT_SEEDED",
                        "hint": "Call GET /api/teacher/seed?token=YOUR_STUDY_SEED_TOKEN first"}

            rows = c.execute(_t("""
                SELECT DISTINCT track, program, class_num, subject_slug, chapter_id, chapter_title, order_index
                FROM syllabus_chapters WHERE is_active=TRUE
                ORDER BY track, program, class_num, subject_slug, order_index
            """)).fetchall()

        tracks = sorted(set(r[0] for r in rows))
        programs = sorted(set(r[1] for r in rows))
        classes = sorted(set(int(r[2]) for r in rows))

        # Build subjects dict
        subjects_map: Dict[str, Dict] = {}
        chapters_list = []
        for r in rows:
            sc = r[3]
            if sc not in subjects_map:
                subjects_map[sc] = {"code": sc, "name": sc.replace("_", " ").title()}
            chapters_list.append({
                "track": r[0], "program": r[1], "class_num": int(r[2]),
                "subject_slug": sc, "chapter_id": r[4], "chapter_title": r[5],
                "order_index": int(r[6] or 0),
            })

        return {
            "ok": True,
            "tracks": tracks,
            "programs": programs,
            "classes": classes,
            "subjects": list(subjects_map.values()),
            "chapters": chapters_list,
            "total_chapters": len(chapters_list),
        }
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(500, {"ok": False, "error": str(ex)})


# ─── Ensure Content ID ─────────────────────────────────────────────────────

class EnsureReq(BaseModel):
    track: str
    program: str
    class_level: int
    subject_code: str
    chapter_slug: str

@router.post("/ensure")
def ensure_content(
    req: EnsureReq,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    authorization: Optional[str] = Header(None),
):
    _require_auth(x_admin_key, authorization)
    import study_store
    result = study_store.ensure_content_item(
        track=req.track, program=req.program, class_num=req.class_level,
        subject_slug=req.subject_code, chapter_id=req.chapter_slug,
    )
    return result


# ─── Upload (R2 with DB blob fallback) ──────────────────────────────────────

ALLOWED_ASSET_TYPES = {
    "luma_json", "blueprint_json", "notes_pdf", "notes",
    "mindmap", "formula", "pyq", "quiz_json", "test_json",
    "revision_html", "diagram", "worksheet", "keypoints",
}

@router.post("/upload")
async def upload_asset(
    content_id: str = Query(...),
    asset_type: str = Query(...),
    file: UploadFile = File(...),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    authorization: Optional[str] = Header(None),
):
    """Upload a file for a content item. Tries R2 first, falls back to DB blob."""
    _require_auth(x_admin_key, authorization)

    cid = content_id.strip()
    at = asset_type.strip().lower()
    if not cid:
        return JSONResponse(400, {"ok": False, "error": "MISSING_CONTENT_ID"})
    if at not in ALLOWED_ASSET_TYPES:
        return JSONResponse(400, {"ok": False, "error": "INVALID_ASSET_TYPE", "allowed": sorted(ALLOWED_ASSET_TYPES)})

    fname = _safe_name(file.filename or "file")
    mime = (file.content_type or "").strip().lower()
    data = await file.read()
    max_bytes = int(os.getenv("ADMIN_UPLOAD_MAX_BYTES", "20000000"))  # 20MB
    if len(data) > max_bytes:
        return JSONResponse(413, {"ok": False, "error": "FILE_TOO_LARGE", "max_bytes": max_bytes})

    # Try R2 first
    storage = "r2"
    suffix = uuid.uuid4().hex[:8]
    object_key = f"v1/content/{cid}/{at}/{suffix}__{fname}"

    try:
        from r2_client import get_r2_client, get_bucket_name
        client = get_r2_client()
        bucket = get_bucket_name()
        client.put_object(Bucket=bucket, Key=object_key, Body=data, ContentType=mime or "application/octet-stream")
        url = f"/api/study/assets?content_id={cid}"
        logger.info(f"Uploaded to R2: {object_key} ({len(data)} bytes)")
    except Exception as r2_err:
        logger.warning(f"R2 upload failed, falling back to DB blob: {r2_err}")
        # Fallback: store in DB
        storage = "db"
        object_key = f"blob:{cid}:{at}"
        url = f"/api/assets/blob?content_id={cid}&asset_type={at}"
        try:
            from db import get_engine_safe
            from sqlalchemy import text as _t
            e = get_engine_safe()
            if not e:
                return JSONResponse(503, {"ok": False, "error": "STORAGE_UNAVAILABLE"})
            _ensure_blob_table(e)
            with e.begin() as conn:
                conn.execute(_t("""
                    INSERT INTO content_asset_blobs (content_id, asset_type, mime_type, filename, size_bytes, data)
                    VALUES (:cid, :at, :mime, :fn, :sz, :data)
                    ON CONFLICT (content_id, asset_type)
                    DO UPDATE SET mime_type=EXCLUDED.mime_type, filename=EXCLUDED.filename,
                                  size_bytes=EXCLUDED.size_bytes, data=EXCLUDED.data
                """), {"cid": cid, "at": at, "mime": mime, "fn": fname, "sz": len(data), "data": data})
        except Exception as db_err:
            return JSONResponse(500, {"ok": False, "error": "UPLOAD_FAILED", "detail": str(db_err)})

    # Register in content_assets table
    import study_store
    study_store.set_content_asset(
        content_id=cid, asset_type=at, storage=storage,
        object_key=object_key, url=url, mime_type=mime,
        size_bytes=len(data), activate=True,
    )

    return {"ok": True, "content_id": cid, "asset_type": at, "storage": storage,
            "object_key": object_key, "size_bytes": len(data), "filename": fname}


# ─── Publish ────────────────────────────────────────────────────────────────

class PublishReq(BaseModel):
    content_id: str
    status: str = "published"

@router.post("/publish")
def publish(
    req: PublishReq,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    authorization: Optional[str] = Header(None),
):
    _require_auth(x_admin_key, authorization)
    import study_store
    result = study_store.set_content_status(req.content_id, req.status)
    return result


# ─── Seed Syllabus ──────────────────────────────────────────────────────────

@router.get("/seed")
def seed_syllabus(token: str = Query(""), x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")):
    """One-time: seed syllabus_chapters from JS files in seed/syllabus/."""
    expected = (os.getenv("STUDY_SEED_TOKEN") or "").strip()
    admin = _admin_key()
    ok = False
    if expected and token == expected:
        ok = True
    if admin and x_admin_key and x_admin_key.strip() == admin:
        ok = True
    if not ok:
        raise HTTPException(403, {"ok": False, "error": "BAD_TOKEN"})

    import study_store
    study_store.ensure_tables()
    from pathlib import Path
    seed_dir = Path(__file__).parent / "seed" / "syllabus"
    if not seed_dir.exists():
        return {"ok": False, "error": "SEED_DIR_NOT_FOUND", "path": str(seed_dir)}
    result = study_store.seed_syllabus_from_packaged_files(seed_dir)
    return result


# ─── Blob table helper ──────────────────────────────────────────────────────

def _ensure_blob_table(engine):
    try:
        from sqlalchemy import text as _t
        with engine.begin() as conn:
            conn.execute(_t("""
                CREATE TABLE IF NOT EXISTS content_asset_blobs (
                    id BIGSERIAL PRIMARY KEY,
                    content_id TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    mime_type TEXT,
                    filename TEXT,
                    size_bytes BIGINT,
                    data BYTEA NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(content_id, asset_type)
                );
            """))
    except Exception:
        pass
