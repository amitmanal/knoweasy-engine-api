from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Body, Request

import study_store

# Optional adapter to canonical Luma content system
try:
    from luma_store import get_content as luma_get_content
except Exception:
    luma_get_content = None

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
async def asset_set(
    seed_token: str = Query(...),
    request: Request = None,
):
    """Upsert an asset mapping for a chapter.

    Patch goals:
    - Accept JSON *and* x-www-form-urlencoded (PowerShell default) payloads
    - Normalize chapter_id variants (_ and -) so resolve is reliable
    - Return inserted/updated row id(s) for debugging
    """
    expected = os.getenv("STUDY_SEED_TOKEN")
    if not expected or seed_token != expected:
        raise HTTPException(status_code=403, detail="Invalid seed token")

    # Parse payload robustly
    payload: dict = {}
    try:
        if request is None:
            payload = {}
        else:
            ctype = (request.headers.get("content-type") or "").lower()
            if "application/json" in ctype:
                payload = await request.json()
            elif "application/x-www-form-urlencoded" in ctype or "multipart/form-data" in ctype:
                form = await request.form()
                payload = dict(form)
            else:
                # Try JSON first, then form
                try:
                    payload = await request.json()
                except Exception:
                    try:
                        form = await request.form()
                        payload = dict(form)
                    except Exception:
                        payload = {}
    except Exception:
        payload = {}

    if not payload:
        raise HTTPException(
            status_code=400,
            detail=(
                "Body missing or unreadable. Send JSON (recommended) or form-encoded. "
                "Example JSON: {track, program, class_num, subject_slug, chapter_id, asset_type, status, ref_kind, ref_value}"
            ),
        )

    track = (payload.get("track") or "").strip().lower()
    program = (payload.get("program") or "").strip().lower()
    class_num = int(payload.get("class_num") or payload.get("class") or 0)
    subject_slug = (payload.get("subject_slug") or payload.get("subject") or "").strip().lower()
    chapter_id = (payload.get("chapter_id") or "").strip().lower()
    chapter_title = (payload.get("chapter_title") or payload.get("title") or "").strip()

    asset_type = (payload.get("asset_type") or "luma").strip().lower()
    status = (payload.get("status") or "published").strip().lower()
    ref_kind = (payload.get("ref_kind") or "db").strip().lower()
    ref_value = (payload.get("ref_value") or payload.get("content_id") or "").strip()
    meta_json = payload.get("meta_json") or payload.get("meta") or {}

    if not chapter_id and chapter_title:
        # Canonical: use underscore slug for internal, and we will also store hyphen alias
        chapter_id = study_store._slugify(chapter_title)  # type: ignore

    if not (track and program and class_num and subject_slug and chapter_id and ref_value):
        raise HTTPException(status_code=400, detail="Missing required fields")

    if asset_type != "luma":
        raise HTTPException(status_code=400, detail="Only asset_type=luma is supported")

    # Normalize: store both underscore and hyphen variants so either resolves
    chapter_id_u = chapter_id.replace("-", "_")
    chapter_id_h = chapter_id.replace("_", "-")

    results = []
    for cid in [chapter_id_u, chapter_id_h]:
        out = study_store.upsert_luma_asset_mapping(
            track=track,
            program=program,
            class_num=class_num,
            subject_slug=subject_slug,
            chapter_id=cid,
            status=status,
            ref_kind=ref_kind,
            ref_value=ref_value,
            meta_json=meta_json,
        )
        results.append({"chapter_id": cid, "result": out})

    return {
        "ok": True,
        "status": "upserted",
        "normalized": {"underscore": chapter_id_u, "hyphen": chapter_id_h},
        "results": results,
    }



@router.get("/asset/get")
async def asset_get(content_id: str = ""):
    """Compatibility adapter.

    Historically the frontend used /api/study/asset/get?content_id=X.
    The canonical Luma system now serves content at /api/luma/content/{id}.

    This endpoint now proxies to the canonical source and returns the SAME shape as /api/luma/content/{id}:
    { ok: true, content: {...} }
    """
    if not content_id:
        return {"ok": False, "status": "missing_content_id"}

    # Prefer canonical Luma store
    if callable(luma_get_content):
        c = luma_get_content(content_id)
        if not c:
            return {"ok": False, "status": "not_found"}
        return {"ok": True, "content": c}

    # Fallback to legacy study_store helper
    return study_store.get_luma_content_by_id(content_id)

@router.get("/resolve")
def resolve(
    class_num: int = Query(..., ge=5, le=12),

    # Preferred (new): track + program + subject_slug + chapter_id/chapter_title
    track: str | None = Query(None),
    program: str | None = Query(None),
    subject_slug: str | None = Query(None),
    chapter_id: str | None = Query(None),
    chapter_title: str | None = Query(None),

    # Back-compat (older frontends)
    board: str | None = Query(None),
    subject: str | None = Query(None),
    chapter_slug: str | None = Query(None, alias="chapter_slug"),
    title: str | None = Query(None, alias="title"),

    asset_type: str = Query("luma"),
):
    # ---------- normalize + infer ----------
    subj = (subject_slug or subject or "").strip()
    if not subj:
        raise HTTPException(status_code=422, detail="subject_slug is required")
    subject_slug_in = subj.lower()

    chap_id = (chapter_id or chapter_slug or "").strip()
    chap_title = (chapter_title or title or "").strip()

    track_in = (track or "").strip().lower() or None
    program_in = (program or "").strip().lower() or None
    board_in = (board or "").strip().lower() or None

    if track_in is None:
        if board_in:
            track_in = "board"
        elif program_in in {"neet", "jee", "cet"}:
            track_in = "entrance"
        else:
            track_in = "board"

    if track_in == "entrance":
        if not program_in:
            if board_in in {"neet", "jee", "cet"}:
                program_in = board_in
            else:
                raise HTTPException(status_code=422, detail="program is required for entrance track")
    else:
        # board track: keep data in program field for storage/lookup
        if not board_in:
            if program_in and program_in not in {"neet", "jee", "cet"}:
                board_in = program_in
            else:
                board_in = "cbse"
        program_in = board_in

    class_num_in = int(class_num)

    res = resolve_asset(
        track=track_in,
        program=program_in,
        class_num=class_num_in,
        subject_slug=subject_slug_in,
        chapter_id=chap_id or chap_title,  # allow title-only calls
        chapter_title=chap_title or None,
        asset_type=asset_type,
    )

    if not res:
        return {"ok": True, "status": "not_found", "kind": "none", "content_id": None, "chapter_title": chap_title or chap_id}

    return {"ok": True, "status": "resolved", **res}

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
