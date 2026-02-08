"""
study_store.py — Content Registry + Syllabus Store (Postgres)

Production store for:
- syllabus_chapters: canonical syllabus (seeded from JS files)
- content_items: content registry (one row per chapter's publishable content)
- content_assets: asset files (R2/hostinger) linked to content_items

Architecture:
- Single source of truth: Postgres
- track mapping: API 'board' <-> DB 'boards'
- All queries use variant matching for robustness
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("knoweasy-engine-api")

try:
    from db import get_engine_safe
except Exception:
    def get_engine_safe():
        return None

try:
    from sqlalchemy import text as _sql_text
    def _t(q: str):
        return _sql_text(q)
except Exception:
    def _t(q: str):
        return q

# ─── Constants ───────────────────────────────────────────────────────────────

TRACK_BOARDS = "boards"
TRACK_ENTRANCE = "entrance"
TRACKS = {TRACK_BOARDS, TRACK_ENTRANCE}

BOARD_PROGRAMS = {"cbse", "icse", "maharashtra"}
ENTRANCE_PROGRAMS = {"jee", "neet", "cet_pcm", "cet_pcb"}
ALL_PROGRAMS = BOARD_PROGRAMS | ENTRANCE_PROGRAMS

ASSET_TYPES = {
    "luma", "luma_json", "notes", "notes_pdf", "revision_html", "blueprint_json",
    "mindmap", "formula", "pyq", "practice_mcq", "test_json",
    "pdf", "image", "audio", "video", "misc",
}

REF_KINDS = {"db", "url", "file", "r2"}
STATUS_VALUES = {"published", "coming_soon", "draft"}

DEBUG = os.getenv("DEBUG", "").strip().lower() in ("1", "true", "yes")

# ─── Helpers ─────────────────────────────────────────────────────────────────

_slug_re = re.compile(r"[^a-z0-9]+")

def _slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = _slug_re.sub("_", s).strip("_")
    return s

def _normalize_program(track: str, program: str) -> str:
    p = (program or "").strip().lower()
    if track in (TRACK_BOARDS, "board"):
        if p in ("msb", "mh", "maha", "maharastra"):
            return "maharashtra"
        return p
    if p in ("jee_adv", "jee_main"):
        return "jee"
    if p in ("cet", "cet_engg", "mhtcet"):
        return "cet_pcm"
    if p in ("cet_med",):
        return "cet_pcb"
    return p

def _track_to_db(track: str) -> str:
    t = (track or "").strip().lower()
    return "boards" if t == "board" else t

def _track_to_api(track: str) -> str:
    t = (track or "").strip().lower()
    return "board" if t == "boards" else t

def _variants(s: str) -> List[str]:
    if not s:
        return []
    seen = set()
    out = []
    for v in [s, s.replace("-", "_"), s.replace("_", "-"), _slugify(s),
              _slugify(s).replace("_", "-"), _slugify(s).replace("-", "_")]:
        v = (v or "").strip().lower()
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out

# ─── Table Creation ──────────────────────────────────────────────────────────

def ensure_tables() -> None:
    engine = get_engine_safe()
    if not engine:
        return
    try:
        with engine.begin() as conn:
            conn.execute(_t("""
                CREATE TABLE IF NOT EXISTS syllabus_chapters (
                    id BIGSERIAL PRIMARY KEY,
                    class_num INT NOT NULL,
                    track TEXT NOT NULL,
                    program TEXT NOT NULL,
                    subject_slug TEXT NOT NULL,
                    chapter_id TEXT NOT NULL,
                    chapter_title TEXT NOT NULL,
                    order_index INT NOT NULL DEFAULT 0,
                    meta_json TEXT NOT NULL DEFAULT '{}',
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """))
            conn.execute(_t("""
                CREATE UNIQUE INDEX IF NOT EXISTS ux_syllabus_chapter_key
                ON syllabus_chapters (class_num, track, program, subject_slug, chapter_id);
            """))
            conn.execute(_t("""
                CREATE TABLE IF NOT EXISTS content_items (
                    content_id TEXT PRIMARY KEY,
                    track TEXT NOT NULL,
                    program TEXT NOT NULL,
                    class_num INT NOT NULL,
                    subject_slug TEXT NOT NULL,
                    chapter_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',
                    meta_json TEXT NOT NULL DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """))
            conn.execute(_t("""
                CREATE UNIQUE INDEX IF NOT EXISTS ux_content_items_key
                ON content_items (track, program, class_num, subject_slug, chapter_id);
            """))
            conn.execute(_t("""
                CREATE TABLE IF NOT EXISTS content_assets (
                    id BIGSERIAL PRIMARY KEY,
                    content_id TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    storage TEXT NOT NULL DEFAULT 'r2',
                    object_key TEXT,
                    url TEXT,
                    mime_type TEXT,
                    size_bytes BIGINT,
                    checksum TEXT,
                    meta_json TEXT NOT NULL DEFAULT '{}',
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """))
            conn.execute(_t("""
                CREATE INDEX IF NOT EXISTS ix_content_assets_cid
                ON content_assets (content_id, asset_type, is_active);
            """))
            # Migrations
            conn.execute(_t("ALTER TABLE syllabus_chapters ADD COLUMN IF NOT EXISTS meta_json TEXT NOT NULL DEFAULT '{}';"))
            conn.execute(_t("ALTER TABLE content_assets ADD COLUMN IF NOT EXISTS size_bytes BIGINT;"))
            conn.execute(_t("ALTER TABLE content_assets ADD COLUMN IF NOT EXISTS checksum TEXT;"))
    except Exception as e:
        logger.warning(f"study_store: ensure_tables: {e}")

# ─── Syllabus Seeding ────────────────────────────────────────────────────────

def _read_json_from_syllabus_js(fp: Path) -> Optional[Dict[str, Any]]:
    try:
        txt = fp.read_text(encoding="utf-8", errors="ignore").strip()
        m = re.search(r'\]\s*=\s*({.*})\s*;?\s*$', txt, flags=re.DOTALL)
        if m:
            return json.loads(m.group(1).strip())
        m = re.search(r'export\s+default\s+({.*})\s*;?\s*$', txt, flags=re.DOTALL)
        if m:
            return json.loads(m.group(1).strip())
        eq = txt.rfind("=")
        if eq < 0:
            return None
        brace = txt.find("{", eq)
        if brace < 0:
            return None
        return json.loads(txt[brace:].strip().rstrip(";").strip())
    except Exception as e:
        logger.warning(f"study_store: parse JS {fp.name}: {e}")
        return None

def seed_syllabus_from_packaged_files(seed_dir: Path, reset: bool = False) -> Dict[str, Any]:
    ensure_tables()
    engine = get_engine_safe()
    if not engine:
        return {"ok": False, "reason": "db_unavailable"}
    files = sorted(seed_dir.glob("*.js"))
    if not files:
        return {"ok": False, "reason": "no_seed_files"}

    inserted = 0
    skipped = 0
    first_error: Optional[str] = None

    if reset:
        try:
            with engine.begin() as conn:
                conn.execute(_t("TRUNCATE TABLE syllabus_chapters RESTART IDENTITY;"))
        except Exception as e:
            logger.warning(f"study_store: reset: {e}")

    def upsert_rows(rows):
        nonlocal inserted, skipped, first_error
        for r in rows:
            try:
                with engine.begin() as conn:
                    conn.execute(_t("""
                        INSERT INTO syllabus_chapters
                            (class_num, track, program, subject_slug, chapter_id, chapter_title, order_index, meta_json)
                        VALUES (:class_num, :track, :program, :subject_slug, :chapter_id, :chapter_title, :order_index, :meta_json)
                        ON CONFLICT (class_num, track, program, subject_slug, chapter_id)
                        DO UPDATE SET chapter_title=EXCLUDED.chapter_title, order_index=EXCLUDED.order_index,
                            meta_json=EXCLUDED.meta_json, updated_at=NOW();
                    """), r)
                inserted += 1
            except Exception as e:
                skipped += 1
                if not first_error:
                    first_error = str(e)

    boards_index: Dict[Tuple[int, str], Dict[str, List[Dict]]] = {}

    for fp in files:
        data = _read_json_from_syllabus_js(fp)
        if not data:
            continue
        meta = data.get("meta") or {}
        class_num = int(str(meta.get("class") or "0") or "0")
        program = _normalize_program(TRACK_BOARDS, str(meta.get("board") or ""))
        if class_num < 5 or class_num > 12 or program not in BOARD_PROGRAMS:
            continue

        boards_index[(class_num, program)] = {}
        rows = []
        for subj in (data.get("subjects") or []):
            subj_name = str(subj.get("name") or "").strip()
            subject_slug = _slugify(subj_name)
            boards_index[(class_num, program)][subject_slug] = []
            for i, ch in enumerate(subj.get("chapters") or []):
                ch_id = str(ch.get("id") or "").strip()
                ch_title = str(ch.get("title") or "").strip()
                if not ch_id or not ch_title:
                    continue
                boards_index[(class_num, program)][subject_slug].append({
                    "chapter_id": ch_id, "chapter_title": ch_title, "order_index": i,
                })
                rows.append({
                    "class_num": class_num, "track": TRACK_BOARDS, "program": program,
                    "subject_slug": subject_slug, "chapter_id": ch_id, "chapter_title": ch_title,
                    "order_index": i, "meta_json": json.dumps({"source": fp.name}),
                })
        upsert_rows(rows)

    def derive_entrance(anchor, ent_prog, cls):
        src = boards_index.get((cls, anchor))
        if not src:
            return
        allowed = None
        if ent_prog in ("jee", "cet_pcm"):
            allowed = {"physics", "chemistry", "mathematics", "math"}
        elif ent_prog in ("neet", "cet_pcb"):
            allowed = {"physics", "chemistry", "biology"}
        rows = []
        for ss, chlist in src.items():
            if allowed and ss not in allowed:
                continue
            for item in chlist:
                rows.append({
                    "class_num": cls, "track": TRACK_ENTRANCE, "program": ent_prog,
                    "subject_slug": ss, "chapter_id": item["chapter_id"],
                    "chapter_title": item["chapter_title"], "order_index": item["order_index"],
                    "meta_json": json.dumps({"derived_from": anchor}),
                })
        upsert_rows(rows)

    for cls in (11, 12):
        derive_entrance("cbse", "jee", cls)
        derive_entrance("cbse", "neet", cls)
        derive_entrance("maharashtra", "cet_pcm", cls)
        derive_entrance("maharashtra", "cet_pcb", cls)

    out = {"ok": True, "inserted": inserted, "skipped": skipped, "seed_files": len(files)}
    if first_error:
        out["first_error"] = first_error
    return out

# ─── Resolve ─────────────────────────────────────────────────────────────────

def resolve_asset(*, track: str, program: str, class_num: int, subject_slug: str,
                  chapter_id: str, asset_type: str = "luma", chapter_title: Optional[str] = None) -> Dict[str, Any]:
    """Resolve content for a chapter. Never crashes — always returns structured JSON."""
    engine = get_engine_safe()
    if not engine:
        return {"ok": False, "status": "db_unavailable"}

    track_db = _track_to_db(track)
    program_n = _normalize_program(track_db, program)
    subject_variants = _variants(subject_slug)
    chapter_variants = _variants(chapter_id)
    if not chapter_variants and chapter_title:
        chapter_variants = _variants(_slugify(chapter_title))
    if not chapter_variants:
        return {"ok": False, "status": "missing_chapter_id"}

    debug_info = {"track_db": track_db, "program": program_n, "class_num": class_num,
                  "subject_variants": subject_variants, "chapter_variants": chapter_variants} if DEBUG else {}

    chapter_exists = False
    chapter_title_found = None
    try:
        with engine.connect() as conn:
            ch = conn.execute(_t(
                "SELECT chapter_title FROM syllabus_chapters "
                "WHERE track=:t AND program=:p AND class_num=:c "
                "AND subject_slug = ANY(:sv::text[]) AND chapter_id = ANY(:cv::text[]) AND is_active=true LIMIT 1"
            ), {"t": track_db, "p": program_n, "c": int(class_num),
                "sv": subject_variants, "cv": chapter_variants}).mappings().first()
        if ch:
            chapter_exists = True
            chapter_title_found = ch.get("chapter_title")
    except Exception as e:
        if DEBUG:
            debug_info["syllabus_err"] = str(e)

    try:
        with engine.connect() as conn:
            ci = conn.execute(_t(
                "SELECT content_id, status FROM content_items "
                "WHERE track=:t AND program=:p AND class_num=:c "
                "AND subject_slug = ANY(:sv::text[]) AND chapter_id = ANY(:cv::text[]) LIMIT 1"
            ), {"t": track_db, "p": program_n, "c": int(class_num),
                "sv": subject_variants, "cv": chapter_variants}).mappings().first()
        if ci:
            cid = ci.get("content_id")
            st = (ci.get("status") or "draft").strip().lower()
            if st == "published":
                return {"ok": True, "status": "published", "content_id": cid,
                        "chapter_title": chapter_title_found or chapter_title or chapter_id,
                        **({"debug": debug_info} if DEBUG else {})}
            return {"ok": False, "status": "coming_soon", "content_id": cid,
                    "chapter_title": chapter_title_found or chapter_title or chapter_id,
                    **({"debug": debug_info} if DEBUG else {})}
    except Exception as e:
        if DEBUG:
            debug_info["content_err"] = str(e)

    if chapter_exists:
        return {"ok": False, "status": "coming_soon",
                "chapter_title": chapter_title_found or chapter_title or chapter_id,
                **({"debug": debug_info} if DEBUG else {})}
    return {"ok": False, "status": "chapter_not_found", **({"debug": debug_info} if DEBUG else {})}

# ─── Content Items ───────────────────────────────────────────────────────────

def ensure_content_item(*, track: str, program: str, class_num: int,
                        subject_slug: str, chapter_id: str, **kw) -> Dict[str, Any]:
    ensure_tables()
    engine = get_engine_safe()
    if not engine:
        return {"ok": False, "error": "DB_UNAVAILABLE"}
    track_db = _track_to_db(track)
    program_n = _normalize_program(track_db, program)
    subj = _slugify(subject_slug)
    chap = _slugify(chapter_id)
    cid = f"{chap}-{track_db}-{program_n}-{class_num}-{subj}"
    try:
        with engine.begin() as conn:
            ex = conn.execute(_t(
                "SELECT content_id FROM content_items "
                "WHERE track=:t AND program=:p AND class_num=:c AND subject_slug=:s AND chapter_id=:ch LIMIT 1"
            ), {"t": track_db, "p": program_n, "c": class_num, "s": subj, "ch": chap}).mappings().first()
            if ex:
                return {"ok": True, "content_id": ex["content_id"], "status": "existing"}
            conn.execute(_t("""
                INSERT INTO content_items (content_id, track, program, class_num, subject_slug, chapter_id, status)
                VALUES (:cid,:t,:p,:c,:s,:ch,'draft') ON CONFLICT (content_id) DO NOTHING
            """), {"cid": cid, "t": track_db, "p": program_n, "c": class_num, "s": subj, "ch": chap})
        return {"ok": True, "content_id": cid, "status": "created"}
    except Exception as e:
        logger.error(f"ensure_content_item: {e}")
        return {"ok": False, "error": str(e)}

def set_content_status(content_id: str, status: str) -> Dict[str, Any]:
    engine = get_engine_safe()
    if not engine:
        return {"ok": False, "error": "DB_UNAVAILABLE"}
    s = (status or "draft").strip().lower()
    if s not in STATUS_VALUES:
        return {"ok": False, "error": f"Invalid status: {s}"}
    try:
        with engine.begin() as conn:
            conn.execute(_t("UPDATE content_items SET status=:s, updated_at=NOW() WHERE content_id=:cid"),
                         {"s": s, "cid": content_id})
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ─── Content Assets ──────────────────────────────────────────────────────────

def set_content_asset(content_id: str, asset_type: str, storage: str,
                      object_key: Optional[str] = None, url: Optional[str] = None,
                      mime_type: Optional[str] = None, size_bytes: Optional[int] = None,
                      checksum: Optional[str] = None, meta: Optional[Dict] = None,
                      activate: bool = True) -> Dict[str, Any]:
    ensure_tables()
    e = get_engine_safe()
    if not e:
        return {"ok": False, "error": "DB_UNAVAILABLE"}
    cid = (content_id or "").strip()
    at = (asset_type or "").strip().lower()
    if not cid or not at:
        return {"ok": False, "error": "MISSING_FIELDS"}
    try:
        with e.begin() as conn:
            if activate:
                conn.execute(_t("UPDATE content_assets SET is_active=FALSE, updated_at=NOW() WHERE content_id=:cid AND asset_type=:at AND is_active=TRUE"),
                             {"cid": cid, "at": at})
            r = conn.execute(_t("""
                INSERT INTO content_assets (content_id,asset_type,storage,object_key,url,mime_type,size_bytes,checksum,meta_json,is_active)
                VALUES (:cid,:at,:st,:okey,:url,:mime,:size,:cs,:meta,:active) RETURNING id
            """), {"cid": cid, "at": at, "st": (storage or "r2").strip().lower(),
                   "okey": object_key, "url": url, "mime": mime_type,
                   "size": size_bytes, "cs": checksum,
                   "meta": json.dumps(meta or {}), "active": bool(activate)}).fetchone()
        return {"ok": True, "id": int(r[0]) if r else None}
    except Exception as ex:
        logger.error(f"set_content_asset: {ex}")
        return {"ok": False, "error": str(ex)}

def get_active_content_assets(content_id: str) -> List[Dict[str, Any]]:
    e = get_engine_safe()
    if not e:
        return []
    cid = (content_id or "").strip()
    if not cid:
        return []
    try:
        with e.connect() as conn:
            rs = conn.execute(_t("""
                SELECT id, asset_type, storage, object_key, url, mime_type, size_bytes, checksum, meta_json, updated_at
                FROM content_assets WHERE content_id=:cid AND is_active=TRUE ORDER BY created_at DESC
            """), {"cid": cid}).fetchall()
        return [{"id": int(r[0]), "asset_type": r[1], "storage": r[2], "object_key": r[3],
                 "url": r[4], "mime_type": r[5], "size_bytes": r[6], "checksum": r[7],
                 "meta": json.loads(r[8] or "{}"), "updated_at": str(r[9]) if r[9] else None}
                for r in (rs or [])]
    except Exception as e:
        logger.error(f"get_active_content_assets: {e}")
        return []

def count_syllabus_rows() -> int:
    engine = get_engine_safe()
    if not engine:
        return 0
    try:
        with engine.connect() as conn:
            return int(conn.execute(_t("SELECT COUNT(1) FROM syllabus_chapters;")).scalar() or 0)
    except Exception:
        return 0
