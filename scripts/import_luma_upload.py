"""Import Luma JSON files into CEO LOCK tables (content_items + syllabus_map).

Usage:
  python -m scripts.import_luma_upload /path/to/luma_upload

Environment:
  Uses DATABASE_URL / Render Postgres via db.get_engine_safe()

Notes:
  - Does NOT delete existing rows.
  - Upserts content_items by content_id.
  - Upserts syllabus_map (sets availability based on content_id presence).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

from sqlalchemy import text as _t

from db import get_engine_safe

def _load_json(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))

def main(folder: str) -> int:
    root = Path(folder)
    if not root.exists():
        print(f"Folder not found: {root}")
        return 2

    e = get_engine_safe()
    if not e:
        print("DB unavailable (check DATABASE_URL)")
        return 3

    files = sorted([p for p in root.rglob("*.json") if p.is_file() and p.name != "manifest.json"])
    if not files:
        print("No JSON files found")
        return 0

    with e.begin() as c:
        # Ensure CEO tables exist
        r = c.execute(_t("SELECT to_regclass('content_items')")).fetchone()
        if not r or not r[0]:
            print("content_items table missing. Run knoweasy_phase1_phase2_schema.sql first.")
            return 4
        r = c.execute(_t("SELECT to_regclass('syllabus_map')")).fetchone()
        if not r or not r[0]:
            print("syllabus_map table missing. Run knoweasy_phase1_phase2_schema.sql first.")
            return 4

        up_ci = _t("""
            INSERT INTO content_items(
                content_id, track, class_level, subject_code, chapter_slug, chapter_title,
                tags, difficulty, status, blueprint_json, pdf_url, mindmap_url, cover_image_url,
                version
            )
            VALUES(
                :content_id, :track, :class_level, :subject_code, :chapter_slug, :chapter_title,
                :tags, :difficulty, :status, :blueprint_json, :pdf_url, :mindmap_url, :cover_image_url,
                :version
            )
            ON CONFLICT (content_id) DO UPDATE SET
                track=EXCLUDED.track,
                class_level=EXCLUDED.class_level,
                subject_code=EXCLUDED.subject_code,
                chapter_slug=EXCLUDED.chapter_slug,
                chapter_title=EXCLUDED.chapter_title,
                tags=EXCLUDED.tags,
                difficulty=EXCLUDED.difficulty,
                status=EXCLUDED.status,
                blueprint_json=EXCLUDED.blueprint_json,
                pdf_url=COALESCE(EXCLUDED.pdf_url, content_items.pdf_url),
                mindmap_url=COALESCE(EXCLUDED.mindmap_url, content_items.mindmap_url),
                cover_image_url=COALESCE(EXCLUDED.cover_image_url, content_items.cover_image_url),
                version=GREATEST(EXCLUDED.version, content_items.version),
                updated_at=NOW()
        """)
        up_sm = _t("""
            INSERT INTO syllabus_map(
                track, class_level, subject_code, chapter_slug, chapter_title,
                content_id, availability, sort_order
            )
            VALUES(
                :track, :class_level, :subject_code, :chapter_slug, :chapter_title,
                :content_id, :availability, :sort_order
            )
            ON CONFLICT (track, class_level, subject_code, chapter_slug) DO UPDATE SET
                chapter_title=EXCLUDED.chapter_title,
                content_id=COALESCE(EXCLUDED.content_id, syllabus_map.content_id),
                availability=EXCLUDED.availability,
                sort_order=EXCLUDED.sort_order
        """)

        imported = 0
        for p in files:
            data = _load_json(p)
            cid = data.get("content_id") or data.get("id") or p.stem
            meta = data.get("metadata") or {}
            blueprint = data.get("blueprint") or data.get("blueprint_json") or data.get("blueprintJson") or {}
            track = meta.get("track") or meta.get("board") or meta.get("program") or "cbse"
            class_level = int(meta.get("class_level") or meta.get("class") or meta.get("class_num") or 11)
            subject_code = meta.get("subject_code") or meta.get("subject") or "sci"
            chapter_slug = meta.get("chapter_slug") or meta.get("chapter_id") or meta.get("chapter") or meta.get("chapterTitle") or meta.get("chapter_title") or ""
            chapter_title = meta.get("chapter_title") or meta.get("chapterTitle") or chapter_slug

            # tags & difficulty
            tags = meta.get("tags") or []
            if isinstance(tags, str):
                tags = [tags]
            difficulty = meta.get("difficulty") or "medium"
            status = meta.get("status") or "published"
            version = int(meta.get("version") or data.get("version") or 1)

            c.execute(up_ci, {
                "content_id": cid,
                "track": str(track),
                "class_level": class_level,
                "subject_code": str(subject_code),
                "chapter_slug": str(chapter_slug),
                "chapter_title": str(chapter_title),
                "tags": tags,
                "difficulty": str(difficulty),
                "status": str(status),
                "blueprint_json": json.dumps(blueprint, ensure_ascii=False),
                "pdf_url": meta.get("pdf_url"),
                "mindmap_url": meta.get("mindmap_url"),
                "cover_image_url": meta.get("cover_image_url"),
                "version": version,
            })

            # Put into syllabus_map too
            sort_order = int(meta.get("sort_order") or 0)
            availability = "available"
            c.execute(up_sm, {
                "track": str(track),
                "class_level": class_level,
                "subject_code": str(subject_code),
                "chapter_slug": str(chapter_slug),
                "chapter_title": str(chapter_title),
                "content_id": cid,
                "availability": availability,
                "sort_order": sort_order,
            })
            imported += 1

    print(f"Imported/updated: {imported} items")
    return 0

if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "./luma_upload"
    raise SystemExit(main(folder))
