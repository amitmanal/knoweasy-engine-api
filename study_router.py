from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

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


@router.get("/resolve")
def resolve(
    class_num: int = Query(..., ge=5, le=12),
    track: str = Query(...),
    program: str = Query(...),
    subject_slug: str = Query(...),
    chapter_id: str = Query(...),
    asset_type: str = Query("luma"),
):
    """
    Resolve a tab click (asset_type) into either:
    - Luma content_id (ref_kind=db)
    - URL/file ref (ref_kind=url|file)
    - coming_soon
    """
    res = study_store.resolve_asset(
        class_num=class_num,
        track=track,
        program=program,
        subject_slug=subject_slug,
        chapter_id=chapter_id,
        asset_type=asset_type,
    )

    if res.get("ok"):
        # For Luma, standardize key name
        if res.get("ref_kind") == "db":
            return {"ok": True, "status": "published", "kind": "luma", "content_id": res.get("ref_value"), "inherited": bool(res.get("inherited"))}
        return {"ok": True, "status": "published", "kind": res.get("asset_type", asset_type), "ref_kind": res.get("ref_kind"), "ref_value": res.get("ref_value"), "inherited": bool(res.get("inherited"))}

    status = res.get("status") or "coming_soon"
    return {"ok": False, "status": status}


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
