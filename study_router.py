from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Body

import study_store

logger = logging.getLogger("knoweasy-engine-api")

router = APIRouter(prefix="/api/study", tags=["study"])

# Ensure tables on import (best-effort)
try:
    study_store.ensure_tables()
except Exception as e:
    logger.warning(f"study_router: ensure_tables failed: {e}")


@router.get("/chapters")
def list_chapters(
    class_num: int = Query(..., ge=5, le=12),
    track: str = Query(..., description="boards|entrance"),
    program: str = Query(..., description="cbse|icse|maharashtra|jee|neet|cet_pcm|cet_pcb"),
    subject_slug: str = Query(...),
):
    """
    Return ordered chapters for a given (class, track, program, subject).
    Deterministic; uses syllabus_chapters table.
    """
    engine = study_store.get_engine_safe() if hasattr(study_store, "get_engine_safe") else None
    # use internal engine via study_store
    try:
        from db import get_engine_safe
        engine = get_engine_safe()
    except Exception:
        engine = None
    if not engine:
        return {"ok": False, "status": "db_unavailable", "chapters": []}

    study_store.ensure_tables()

    track = (track or "").strip().lower()
    program = study_store._normalize_program(track, program)  # type: ignore
    subject_slug = study_store._slugify(subject_slug)  # type: ignore

    try:
        from sqlalchemy import text as _sql_text
        q = _sql_text("""
            SELECT chapter_id, chapter_title, order_index
            FROM syllabus_chapters
            WHERE class_num=:class_num AND track=:track AND program=:program
              AND subject_slug=:subject_slug AND is_active=TRUE
            ORDER BY order_index ASC, chapter_title ASC;
        """)
        with engine.connect() as conn:
            rows = conn.execute(q, {
                "class_num": class_num,
                "track": track,
                "program": program,
                "subject_slug": subject_slug,
            }).fetchall()
        chapters = [{"id": r[0], "title": r[1], "order": int(r[2] or 0)} for r in rows]
        return {"ok": True, "chapters": chapters}
    except Exception as e:
        logger.warning(f"study_router: list_chapters failed: {e}")
        return {"ok": False, "status": "error", "chapters": []}


@router.post("/asset/set")
def asset_set(
    seed_token: str = Query(...),
    payload: dict = Body(...),
):
    """Upsert an asset mapping for a chapter.

    This is an admin/seed endpoint protected by STUDY_SEED_TOKEN.
    Frontend can use it to publish a Luma content_id for a chapter.
    """
    expected = os.getenv("STUDY_SEED_TOKEN")
    if not expected or seed_token != expected:
        raise HTTPException(status_code=403, detail="Invalid seed token")

    track = (payload.get("track") or "").strip().lower()
    program = (payload.get("program") or "").strip().lower()
    class_num = int(payload.get("class_num") or payload.get("class") or 0)
    subject_slug = (payload.get("subject_slug") or payload.get("subject") or "").strip().lower()
    chapter_id = (payload.get("chapter_id") or "").strip().lower()
    chapter_title = (payload.get("chapter_title") or payload.get("title") or "").strip()

    asset_type = (payload.get("asset_type") or "luma").strip().lower()
    status = (payload.get("status") or "published").strip().lower()
    ref_kind = (payload.get("ref_kind") or "db").strip().lower()
    ref_value = (payload.get("ref_value") or "").strip()
    meta_json = payload.get("meta_json") or payload.get("meta") or {}

    if not chapter_id and chapter_title:
        # use same slug style the frontend uses
        chapter_id = re.sub(r"\s+", " ", chapter_title).strip().lower()
        chapter_id = re.sub(r"[^a-z0-9]+", "-", chapter_id).strip("-")

    if not (track and program and class_num and subject_slug and chapter_id and ref_value):
        raise HTTPException(status_code=400, detail="Missing required fields")

    if asset_type != "luma":
        raise HTTPException(status_code=400, detail="Only asset_type=luma is supported")

    out = study_store.upsert_luma_asset_mapping(
        track=track,
        program=program,
        class_num=class_num,
        subject_slug=subject_slug,
        chapter_id=chapter_id,
        status=status,
        ref_kind=ref_kind,
        ref_value=ref_value,
        meta_json=meta_json,
    )
    return {"ok": True, "status": "upserted", "result": out, "chapter_id": chapter_id}


@router.get("/resolve")
def resolve(
    class_num: int = Query(..., ge=5, le=12),
    track: str = Query(...),
    program: str = Query(...),
    subject_slug: str = Query(...),
    chapter_id: str = Query(""),
    chapter_title: Optional[str] = Query(None),
    asset_type: str = Query("luma"),
):
    """Resolve the content behind a chapter.

    - For boards track, syllabus_chapters usually exists.
    - For entrance track, syllabus may be absent; we still resolve via chapter_assets.
    """
    result = study_store.resolve_asset(
        track=track,
        program=program,
        class_num=class_num,
        subject_slug=subject_slug,
        chapter_id=chapter_id,
        chapter_title=chapter_title,
        asset_type=asset_type,
    )

    # pass through errors
    if not result.get("ok"):
        return result

    asset = result.get("asset") or {}
    if asset_type == "luma" and asset.get("ref_kind") == "db":
        cid = asset.get("ref_value")
        content = result.get("luma_content")
        # Return a stable, frontend-friendly shape
        return {
            "ok": True,
            "status": "resolved",
            "kind": "db",
            "content_id": cid,
            "chapter_title": result.get("chapter_title"),
            "asset": asset,
            "content": content,
        }

    # Non-db or other assets
    return {
        "ok": True,
        "status": "resolved",
        "kind": asset.get("ref_kind"),
        "ref_value": asset.get("ref_value"),
        "chapter_title": result.get("chapter_title"),
        "asset": asset,
    }

@router.post("/seed")
def seed(seed_token: Optional[str] = Query(None, description="Set STUDY_SEED_TOKEN in env; pass it here to run once")):
    """
    Seed syllabus_chapters and luma mappings.
    Safe for production: requires token.
    """
    expected = (os.getenv("STUDY_SEED_TOKEN") or "").strip()
    if not expected:
        raise HTTPException(status_code=403, detail="Seeding disabled")
    if (seed_token or "").strip() != expected:
        raise HTTPException(status_code=403, detail="Invalid seed token")

    # Seed syllabus from packaged files (if present)
    seed_dir = Path(__file__).parent / "seed" / "syllabus"
    out = {"syllabus": None, "luma_mappings": None}

    if seed_dir.exists():
        out["syllabus"] = study_store.seed_syllabus_from_packaged_files(seed_dir)
    else:
        out["syllabus"] = {"ok": False, "reason": "seed_dir_missing"}

    out["luma_mappings"] = study_store.seed_luma_mappings_from_luma_content()
    return {"ok": True, "result": out}
