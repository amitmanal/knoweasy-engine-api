from __future__ import annotations

import logging
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text as _t

from db import get_engine_safe

logger = logging.getLogger("knoweasy-engine-api")

router = APIRouter(prefix="/api", tags=["syllabus"])


def _table_exists(conn, table_name: str) -> bool:
    try:
        r = conn.execute(_t("SELECT to_regclass(:t)"), {"t": table_name}).fetchone()
        return bool(r and r[0])
    except Exception:
        try:
            r = conn.execute(_t(
                "SELECT 1 FROM information_schema.tables WHERE table_name=:t LIMIT 1"
            ), {"t": table_name}).fetchone()
            return bool(r)
        except Exception:
            return False


def _norm_track_program(track: str | None, program: str | None) -> tuple[str, str]:
    """Canonicalize keys.

    Canonical:
      track = board | entrance
      program (board) = cbse | icse | maharashtra
      program (entrance) = jee | neet | cet_pcm | cet_pcb

    Back-compat:
      - if track is a board (cbse/icse/maharashtra) and program missing -> treat as track=board, program=<track>
      - if track is an exam (jee/neet/cet_*) and program missing -> treat as track=entrance, program=<track>
    """
    t = (track or "").strip().lower()
    p = (program or "").strip().lower()

    # legacy normalizations
    if t in {"msb", "mh", "maha", "maharastra"}:
        t = "maharashtra"
    if p in {"msb", "mh", "maha", "maharastra"}:
        p = "maharashtra"

    # Back-compat overload mode: track carries program
    board_programs = {"cbse", "icse", "maharashtra"}
    entrance_programs = {"jee", "neet", "cet_pcm", "cet_pcb", "cet_engg", "cet_med", "cet", "mhtcet"}

    if not p and t in board_programs:
        return "board", t
    if not p and t in entrance_programs:
        # normalize CET variants
        if t in {"cet_engg", "cet", "mhtcet"}:
            t = "cet_pcm"
        if t == "cet_med":
            t = "cet_pcb"
        return "entrance", t

    # Canonical mode
    if t in {"boards", "board"}:
        t = "board"
    if t in {"entrance", "exam", "exams"}:
        t = "entrance"

    if t == "board":
        if p in {"msb", "mh", "maha", "maharastra"}:
            p = "maharashtra"
        if p not in board_programs:
            # safe fallback
            p = "cbse"
    elif t == "entrance":
        if p in {"cet_engg", "cet", "mhtcet"}:
            p = "cet_pcm"
        if p == "cet_med":
            p = "cet_pcb"
        if p not in {"jee", "neet", "cet_pcm", "cet_pcb"}:
            p = "neet"
    else:
        # unknown -> assume board
        t, p = "board", (p or "cbse")

    return t, p


@router.get("/syllabus")
def get_syllabus(
    track: str = Query(..., description="board|entrance (back-compat: cbse/icse/maharashtra/jee/neet/cet_*)"),
    class_level: int = Query(..., ge=5, le=12),
    program: str | None = Query(None, description="cbse|icse|maharashtra|jee|neet|cet_pcm|cet_pcb"),
    subject_code: str | None = Query(None, description="optional: return only this subject's chapters"),
    debug: int = Query(0, description="set 1 for debug payload"),
):
    """Syllabus endpoint compatible with old Hostinger scripts, but DB-driven.

    Returns when subject_code omitted:
      { ok:true, syllabus:{ meta:{...}, subjects:[{code,name,chapters:[{id,title,availability,content_id}]}] } }

    NOTE:
      - Uses syllabus_chapters as the source of truth (track+program supported).
      - Falls back to syllabus_map for legacy deployments.
    """
    e = get_engine_safe()
    if not e:
        raise HTTPException(503, {"ok": False, "error": "DB_UNAVAILABLE"})

    track_n, program_n = _norm_track_program(track, program)
    # IMPORTANT: DB uses track='boards' (plural) for board syllabus rows, while our public API is canonical
    # and returns track='board'. Always query the DB with the correct stored track.
    track_db = "boards" if track_n == "board" else track_n
    subj = (subject_code or "").strip().lower() or None

    dbg = {
        "track_in": track,
        "program_in": program,
        "track": track_n,
        "track_db": track_db,
        "program": program_n,
        "class_level": int(class_level),
        "subject_code": subj,
        "source_table": None,
        "subjects": 0,
        "chapters": 0,
    }

    try:
        with e.connect() as c:
            has_ch = _table_exists(c, "syllabus_chapters")
            has_map = _table_exists(c, "syllabus_map")

            # Prefer syllabus_chapters (canonical)
            if has_ch:
                dbg["source_table"] = "syllabus_chapters"
                if subj:
                    rs = c.execute(_t("""
                        SELECT subject_slug, chapter_id, chapter_title
                        FROM syllabus_chapters
                        WHERE track=:track AND program=:program AND class_num=:cls
                          AND subject_slug=:subj AND is_active=TRUE
                        ORDER BY order_index ASC, chapter_title ASC
                    """), {"track": track_db, "program": program_n, "cls": int(class_level), "subj": subj}).fetchall()
                    items = []
                    for r in rs or []:
                        items.append({
                            "track": track_n,
                            "program": program_n,
                            "class_level": int(class_level),
                            "subject_code": r[0],
                            "chapter_slug": r[1],
                            "chapter_title": r[2],
                            "content_id": "",
                            "availability": "coming_soon",
                            "sort_order": 0,
                        })
                    return {"ok": True, "items": items, **({"debug": dbg} if debug else {})}

                rs = c.execute(_t("""
                    SELECT subject_slug, chapter_id, chapter_title
                    FROM syllabus_chapters
                    WHERE track=:track AND program=:program AND class_num=:cls AND is_active=TRUE
                    ORDER BY subject_slug ASC, order_index ASC, chapter_title ASC
                """), {"track": track_db, "program": program_n, "cls": int(class_level)}).fetchall()

                subj_to_ch = defaultdict(list)
                for r in rs or []:
                    subj_to_ch[r[0]].append({
                        "id": r[1],
                        "title": r[2],
                        "content_id": None,
                        "availability": "coming_soon",
                    })

                subjects = []
                for scode, chapters in subj_to_ch.items():
                    subjects.append({
                        "code": scode,
                        "name": scode.replace("_", " ").title(),
                        "chapters": chapters,
                    })

                dbg["subjects"] = len(subjects)
                dbg["chapters"] = sum(len(s["chapters"]) for s in subjects)

                return {
                    "ok": True,
                    "syllabus": {
                        "meta": {"track": track_n, "program": program_n, "class": str(class_level), "source": "DB syllabus_chapters"},
                        "subjects": subjects,
                    },
                    **({"debug": dbg} if debug else {}),
                }

            # Fallback: syllabus_map (legacy: track overloaded as board/exam)
            if has_map:
                dbg["source_table"] = "syllabus_map"
                legacy_track = program_n if track_n == "board" else program_n  # old schema uses 'track' as program
                if subj:
                    rs = c.execute(_t("""
                        SELECT track, class_level, subject_code, chapter_slug, chapter_title, content_id, availability, sort_order
                        FROM syllabus_map
                        WHERE track=:track AND class_level=:cls AND subject_code=:subj
                        ORDER BY sort_order ASC, chapter_title ASC
                    """), {"track": legacy_track, "cls": int(class_level), "subj": subj}).fetchall()
                    items = []
                    for r in rs or []:
                        items.append({
                            "track": legacy_track,
                            "class_level": int(r[1]),
                            "subject_code": r[2],
                            "chapter_slug": r[3],
                            "chapter_title": r[4],
                            "content_id": r[5],
                            "availability": r[6] or ("available" if r[5] else "coming_soon"),
                            "sort_order": int(r[7] or 0),
                        })
                    return {"ok": True, "items": items, **({"debug": dbg} if debug else {})}

                rs = c.execute(_t("""
                    SELECT subject_code, chapter_slug, chapter_title, content_id, availability, sort_order
                    FROM syllabus_map
                    WHERE track=:track AND class_level=:cls
                    ORDER BY subject_code ASC, sort_order ASC, chapter_title ASC
                """), {"track": legacy_track, "cls": int(class_level)}).fetchall()

                subj_to_ch = defaultdict(list)
                for r in rs or []:
                    subj_to_ch[r[0]].append({
                        "id": r[1],
                        "title": r[2],
                        "content_id": r[3],
                        "availability": r[4] or ("available" if r[3] else "coming_soon"),
                    })

                subjects = []
                for scode, chapters in subj_to_ch.items():
                    subjects.append({
                        "code": scode,
                        "name": scode.replace("_", " ").title(),
                        "chapters": chapters,
                    })

                dbg["subjects"] = len(subjects)
                dbg["chapters"] = sum(len(s["chapters"]) for s in subjects)

                return {
                    "ok": True,
                    "syllabus": {
                        "meta": {"track": track_n, "program": program_n, "class": str(class_level), "source": "DB syllabus_map (legacy)"},
                        "subjects": subjects,
                    },
                    **({"debug": dbg} if debug else {}),
                }

            raise HTTPException(501, {"ok": False, "error": "SYLLABUS_TABLES_MISSING", "hint": "Run /api/study/seed once (token) or apply schema SQL."})

    except HTTPException:
        raise
    except Exception as ex:
        logger.error(f"/api/syllabus failed: {ex}")
        raise HTTPException(500, {"ok": False, "error": "SYLLABUS_FETCH_FAILED"})
