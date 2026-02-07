from __future__ import annotations

import logging
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text as _t

from db import get_engine_safe
import study_store

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

@router.get("/syllabus")
def get_syllabus(
    track: str = Query(..., description="cbse/icse/maharashtra/neet/jee/cet/etc"),
    class_level: int = Query(..., ge=5, le=12),
    subject_code: str | None = Query(None, description="bio/chem/phy/math/sci/etc (optional)"),
):
    """CEO LOCK syllabus endpoint.

    If subject_code is provided -> returns flat chapter list for that subject.
    If subject_code is omitted -> returns board-style syllabus object compatible with frontend scripts:
      { meta: {...}, subjects: [{name, chapters:[{id,title,availability,content_id}]}] }
    """
    # Ensure syllabus tables exist (and self-heal known schema drift)
    try:
        study_store.ensure_tables()
    except Exception:
        pass

    e = get_engine_safe()
    if not e:
        raise HTTPException(503, {"ok": False, "error": "DB_UNAVAILABLE"})

    try:
        with e.connect() as c:
            if not _table_exists(c, "syllabus_map"):
                raise HTTPException(501, {"ok": False, "error": "SYLLABUS_MAP_TABLE_MISSING", "hint": "Run knoweasy_phase1_phase2_schema.sql"})

            if subject_code:
                rs = c.execute(_t("""
                    SELECT track, class_level, subject_code, chapter_slug, chapter_title,
                           content_id, availability, sort_order
                    FROM syllabus_map
                    WHERE track=:track AND class_level=:cls AND subject_code=:subj
                    ORDER BY sort_order ASC, chapter_title ASC
                """), {"track": track, "cls": class_level, "subj": subject_code}).fetchall()

                items = []
                for r in rs or []:
                    items.append({
                        "track": r[0],
                        "class_level": int(r[1]),
                        "subject_code": r[2],
                        "chapter_slug": r[3],
                        "chapter_title": r[4],
                        "content_id": r[5],
                        "availability": r[6] or ("available" if r[5] else "coming_soon"),
                        "sort_order": int(r[7] or 0),
                    })
                return {"ok": True, "items": items}

            # Full syllabus for class+track (grouped by subject_code)
            rs = c.execute(_t("""
                SELECT subject_code, chapter_slug, chapter_title, content_id, availability, sort_order
                FROM syllabus_map
                WHERE track=:track AND class_level=:cls
                ORDER BY subject_code ASC, sort_order ASC, chapter_title ASC
            """), {"track": track, "cls": class_level}).fetchall()

        subj_to_ch = defaultdict(list)
        for r in rs or []:
            subj_to_ch[r[0]].append({
                "id": r[1],
                "title": r[2],
                "content_id": r[3],
                "availability": r[4] or ("available" if r[3] else "coming_soon"),
                "sort_order": int(r[5] or 0),
            })

        # Human-friendly subject names (best-effort)
        pretty = {
            "math": "Mathematics",
            "phy": "Physics",
            "chem": "Chemistry",
            "bio": "Biology",
            "sci": "Science",
            "eng": "English",
            "hist": "History",
            "geo": "Geography",
            "civ": "Civics",
        }

        subjects = []
        for scode, chapters in subj_to_ch.items():
            subjects.append({
                "code": scode,
                "name": pretty.get(scode, scode.upper()),
                "chapters": [{"id": ch["id"], "title": ch["title"], "availability": ch["availability"], "content_id": ch["content_id"]} for ch in chapters],
            })

        return {
            "ok": True,
            "syllabus": {
                "meta": {"board": track, "class": str(class_level), "source": "DB syllabus_map"},
                "subjects": [{"name": s["name"], "code": s["code"], "chapters": s["chapters"]} for s in subjects],
            }
        }

    except HTTPException:
        raise
    except Exception as ex:
        logger.error(f"/api/syllabus failed: {ex}")
        raise HTTPException(500, {"ok": False, "error": "SYLLABUS_FETCH_FAILED"})
