"""
study_store.py - Curriculum + Chapter Asset Wiring Store (Postgres)

Purpose:
- Provide a deterministic, exam-safe resolver from (class, track, program, subject, chapter_id, asset_type)
  -> either a content_id (for Luma JSON in DB) or a URL/path reference (for PDFs etc).
- Seed syllabus chapters from packaged syllabus JS files (boards) and derived entrance programs (optional).

Design:
- CREATE TABLE IF NOT EXISTS + non-breaking migrations
- Best-effort: never crash app if DB unavailable
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("knoweasy-engine-api")

def _table_exists(conn, table_name: str) -> bool:
    """Lightweight table existence check (Postgres)."""
    try:
        r = conn.execute(_t("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema='public' AND table_name=:t
            ) AS exists;
        """), {"t": table_name}).scalar()
        return bool(r)
    except Exception:
        return False



# Optional: read from new Luma content system (canonical)
try:
    from luma_store import get_content as luma_get_content, list_content as luma_list_content
except Exception:
    luma_get_content = None
    luma_list_content = None

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


# -----------------------------
# Constants / Enums
# -----------------------------

TRACK_BOARDS = "boards"
TRACK_ENTRANCE = "entrance"

# Programs (boards + entrance)
BOARD_PROGRAMS = {"cbse", "icse", "maharashtra"}
ENTRANCE_PROGRAMS = {"jee", "neet", "cet_pcm", "cet_pcb"}

ASSET_TYPES = {
    "luma",
    "notes",
    "mindmap",
    "formula",
    "pyq",
    "practice_mcq",
}

REF_KINDS = {"db", "url", "file"}
STATUS_VALUES = {"published", "coming_soon", "draft"}


# -----------------------------
# Helpers
# -----------------------------

_slug_re = re.compile(r"[^a-z0-9]+")

def _slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = _slug_re.sub("_", s).strip("_")
    return s


def ensure_tables() -> None:
    engine = get_engine_safe()
    if not engine:
        logger.warning("study_store: DB unavailable, tables not created")
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
                CREATE TABLE IF NOT EXISTS chapter_assets (
                    id BIGSERIAL PRIMARY KEY,
                    class_num INT NOT NULL,
                    track TEXT NOT NULL,
                    program TEXT NOT NULL,
                    subject_slug TEXT NOT NULL,
                    chapter_id TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'coming_soon',
                    ref_kind TEXT NOT NULL DEFAULT 'url',
                    ref_value TEXT NOT NULL DEFAULT '',
                    meta_json TEXT NOT NULL DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """))
            conn.execute(_t("""
                CREATE UNIQUE INDEX IF NOT EXISTS ux_chapter_asset_key
                ON chapter_assets (class_num, track, program, subject_slug, chapter_id, asset_type);
            """))

            # Non-breaking migrations (add columns if missing)
            conn.execute(_t("""ALTER TABLE syllabus_chapters ADD COLUMN IF NOT EXISTS meta_json TEXT NOT NULL DEFAULT '{}';"""))
            conn.execute(_t("""ALTER TABLE chapter_assets ADD COLUMN IF NOT EXISTS meta_json TEXT NOT NULL DEFAULT '{}';"""))

    except Exception as e:
        logger.warning(f"study_store: ensure_tables failed: {e}")


def _read_json_from_syllabus_js(fp: Path) -> Optional[Dict[str, Any]]:
    """
    Syllabus JS format:
    window.KnowEasySyllabus["11_cbse"] = { ... };
    Extract the { ... } as JSON and parse.
    """
    try:
        txt = fp.read_text(encoding="utf-8", errors="ignore")
        # Find first '{' after '='
        eq = txt.find("=")
        if eq < 0:
            return None
        brace = txt.find("{", eq)
        if brace < 0:
            return None
        # Remove trailing ';'
        data_str = txt[brace:].strip()
        if data_str.endswith(";"):
            data_str = data_str[:-1].strip()
        # Some files may end with "};" already handled
        return json.loads(data_str)
    except Exception as e:
        logger.warning(f"study_store: parse syllabus js failed for {fp.name}: {e}")
        return None


def _normalize_program(track: str, program: str) -> str:
    p = (program or "").strip().lower()
    if track == TRACK_BOARDS:
        if p in ("msb", "mh"):
            return "maharashtra"
        return p
    # entrance
    if p in ("jee_adv", "jee_main"):
        return "jee"
    if p in ("cet", "cet_engg"):
        return "cet_pcm"
    if p in ("cet_med",):
        return "cet_pcb"
    return p


def count_syllabus_rows() -> int:
    engine = get_engine_safe()
    if not engine:
        return 0
    try:
        with engine.connect() as conn:
            r = conn.execute(_t("SELECT COUNT(1) FROM syllabus_chapters;")).scalar()
            return int(r or 0)
    except Exception:
        return 0


def seed_syllabus_from_packaged_files(seed_dir: Path) -> Dict[str, Any]:
    """
    Seed boards syllabus from packaged JS files in seed_dir.
    Also derives entrance syllabi for class 11/12 from board anchors:
      - JEE/NEET from CBSE (default anchor)
      - CET_PCM/CET_PCB from Maharashtra (default anchor)
    This is a safe default and can be replaced by explicit entrance syllabi later.

    Returns counts for logging.
    """
    ensure_tables()
    engine = get_engine_safe()
    if not engine:
        return {"ok": False, "reason": "db_unavailable"}

    files = sorted(seed_dir.glob("*.js"))
    if not files:
        return {"ok": False, "reason": "no_seed_files"}

    inserted = 0
    skipped = 0

    def upsert_many(rows: List[Tuple[int, str, str, str, str, str, int, str]]):
        nonlocal inserted, skipped
        with engine.begin() as conn:
            for row in rows:
                try:
                    conn.execute(_t("""
                        INSERT INTO syllabus_chapters
                            (class_num, track, program, subject_slug, chapter_id, chapter_title, order_index, meta_json)
                        VALUES
                            (:class_num, :track, :program, :subject_slug, :chapter_id, :chapter_title, :order_index, :meta_json)
                        ON CONFLICT (class_num, track, program, subject_slug, chapter_id)
                        DO UPDATE SET
                            chapter_title = EXCLUDED.chapter_title,
                            order_index = EXCLUDED.order_index,
                            meta_json = EXCLUDED.meta_json,
                            updated_at = NOW();
                    """), {
                        "class_num": row[0],
                        "track": row[1],
                        "program": row[2],
                        "subject_slug": row[3],
                        "chapter_id": row[4],
                        "chapter_title": row[5],
                        "order_index": row[6],
                        "meta_json": row[7],
                    })
                    inserted += 1
                except Exception:
                    skipped += 1

    # First seed boards from JS
    boards_index: Dict[Tuple[int, str], Dict[str, List[Dict[str, Any]]]] = {}
    # key: (class_num, program) -> subject_slug -> list chapters with id/title/order
    for fp in files:
        data = _read_json_from_syllabus_js(fp)
        if not data:
            continue
        meta = data.get("meta") or {}
        class_num = int(str(meta.get("class") or "0") or "0")
        program = _normalize_program(TRACK_BOARDS, str(meta.get("board") or ""))
        subjects = data.get("subjects") or []
        if class_num < 5 or class_num > 12:
            continue
        if program not in BOARD_PROGRAMS:
            continue

        boards_index[(class_num, program)] = {}
        rows: List[Tuple[int, str, str, str, str, str, int, str]] = []

        for subj in subjects:
            name = str(subj.get("name") or "").strip()
            subject_slug = _slugify(name)
            chapters = subj.get("chapters") or []
            boards_index[(class_num, program)][subject_slug] = []
            for i, ch in enumerate(chapters):
                ch_id = str(ch.get("id") or "").strip()
                ch_title = str(ch.get("title") or "").strip()
                if not ch_id or not ch_title:
                    continue
                boards_index[(class_num, program)][subject_slug].append({
                    "chapter_id": ch_id,
                    "chapter_title": ch_title,
                    "order_index": i,
                })
                rows.append((
                    class_num,
                    TRACK_BOARDS,
                    program,
                    subject_slug,
                    ch_id,
                    ch_title,
                    i,
                    json.dumps({"source": fp.name, "meta": meta}, ensure_ascii=False),
                ))
        upsert_many(rows)

    # Derive entrance for 11/12
    def derive_from_board(anchor_program: str, entrance_program: str, class_num: int):
        src = boards_index.get((class_num, anchor_program))
        if not src:
            return
        rows: List[Tuple[int, str, str, str, str, str, int, str]] = []
        for subject_slug, chlist in src.items():
            # Entrance program subject filtering:
            # - JEE: physics/chemistry/mathematics
            # - NEET: physics/chemistry/biology
            # - CET_PCM: physics/chemistry/mathematics
            # - CET_PCB: physics/chemistry/biology
            allowed = None
            if entrance_program in ("jee", "cet_pcm"):
                allowed = {"physics", "chemistry", "mathematics", "math"}
            elif entrance_program in ("neet", "cet_pcb"):
                allowed = {"physics", "chemistry", "biology"}
            if allowed and subject_slug not in allowed:
                continue

            for item in chlist:
                rows.append((
                    class_num,
                    TRACK_ENTRANCE,
                    entrance_program,
                    subject_slug,
                    item["chapter_id"],
                    item["chapter_title"],
                    int(item["order_index"]),
                    json.dumps({"derived_from": anchor_program}, ensure_ascii=False),
                ))
        upsert_many(rows)

    for cls in (11, 12):
        derive_from_board("cbse", "jee", cls)
        derive_from_board("cbse", "neet", cls)
        derive_from_board("maharashtra", "cet_pcm", cls)
        derive_from_board("maharashtra", "cet_pcb", cls)

    return {"ok": True, "inserted": inserted, "skipped": skipped, "seed_files": len(files)}


def resolve_asset(
    *,
    track: str,
    program: str,
    class_num: int,
    subject_slug: str,
    chapter_id: str,
    asset_type: str,
    chapter_title: "Optional[str]" = None,
) -> "Dict[str, Any]":
    """Resolve an asset for a given (track, program, class, subject, chapter).

    Notes:
    - Older data uses underscores in slugs, while the frontend uses hyphens.
      We therefore try a few normalized variants for both chapter_id and subject_slug.
    - For entrance track, syllabus rows may not exist yet; we still allow resolving
      assets via chapter_assets.
    """
    ensure_tables()
    engine = get_engine_safe()
    if not engine:
        return {"ok": False, "status": "db_unavailable"}

    asset_type = (asset_type or "").strip().lower()
    track = (track or "").strip().lower()
    program = (program or "").strip().lower()
    subject_slug_in = (subject_slug or "").strip().lower()
    chapter_id_in = (chapter_id or "").strip().lower()
    chapter_title_in = (chapter_title or "").strip()

    if not chapter_id_in and chapter_title_in:
        chapter_id_in = _slugify(chapter_title_in).replace("_", "-")

    if not chapter_id_in:
        return {"ok": False, "status": "missing_chapter_id"}

    def _variants(s: str) -> "List[str]":
        out: "List[str]" = []
        if not s:
            return out
        out.append(s)
        out.append(s.replace("-", "_"))
        out.append(s.replace("_", "-"))
        sl = _slugify(s)
        out.append(sl)
        out.append(sl.replace("_", "-"))
        out.append(sl.replace("-", "_"))
        seen = set()
        uniq: "List[str]" = []
        for v in out:
            v = (v or "").strip().lower()
            if v and v not in seen:
                seen.add(v)
                uniq.append(v)
        return uniq

    subject_variants = _variants(subject_slug_in) or [subject_slug_in]
    chapter_variants = _variants(chapter_id_in)

    debug_info: Dict[str, Any] = {
        "input": {
            "track": track,
            "program": program,
            "class_num": int(class_num),
            "subject_slug": subject_slug_in,
            "chapter_id": chapter_id_in,
            "asset_type": asset_type,
        },
        "searched": {
            "subject_variants": subject_variants,
            "chapter_variants": chapter_variants,
        },
    }


# === CEO LOCK (Phase 1/2 schema) resolver ===
# If the newer canonical tables exist (syllabus_map + content_items),
# resolve chapter -> content_id deterministically without relying on legacy chapter_assets.
try:
    with engine.connect() as conn:
        if _table_exists(conn, "syllabus_map"):
            # Canonical normalize: subject_code + chapter_slug are lowercase, underscore slugs
            subj_norm = _slugify(subject_slug_in).replace("-", "_")
            chap_norm = _slugify(chapter_id_in).replace("-", "_")

            def _v2_variants(s: str) -> "List[str]":
                s = (s or "").strip().lower()
                if not s:
                    return []
                base = _slugify(s).replace("-", "_")
                cand = [
                    s, s.replace("-", "_"), s.replace("_", "-"),
                    base, base.replace("_", "-"), base.replace("-", "_"),
                ]
                seen=set(); out=[]
                for x in cand:
                    x=(x or "").strip().lower()
                    if x and x not in seen:
                        seen.add(x); out.append(x)
                return out

            subj_v = _v2_variants(subj_norm) or [subj_norm]
            chap_v = _v2_variants(chap_norm) or [chap_norm]

            row = conn.execute(_t("""
                SELECT track, class_level, subject_code, chapter_slug, chapter_title,
                       content_id, availability
                FROM syllabus_map
                WHERE track=:track AND class_level=:cls
                  AND subject_code = ANY(:subjects)
                  AND chapter_slug = ANY(:chapters)
                LIMIT 1
            """), {
                "track": track,
                "cls": int(class_num),
                "subjects": subj_v,
                "chapters": chap_v,
            }).mappings().first()

            debug_info["v2"] = {
                "used": True,
                "subjects": subj_v,
                "chapters": chap_v,
                "row_found": bool(row),
            }

            if not row:
                return {"ok": False, "status": "chapter_not_found", "debug": debug_info}

            content_id = (row.get("content_id") or "").strip()
            chapter_title_res = row.get("chapter_title") or chapter_title_in or chapter_id_in

            # If syllabus says coming soon or content_id missing, return gracefully.
            availability = (row.get("availability") or "").strip().lower()
            if not content_id or availability in ("coming_soon", "coming-soon", "soon"):
                return {
                    "ok": False,
                    "status": "coming_soon",
                    "chapter_title": chapter_title_res,
                    "debug": debug_info,
                }

            content = None
            try:
                if callable(luma_get_content):
                    content = luma_get_content(content_id)
            except Exception:
                content = None

            if not content:
                return {
                    "ok": False,
                    "status": "content_not_found",
                    "content_id": content_id,
                    "chapter_title": chapter_title_res,
                    "debug": debug_info,
                }

            asset = {
                "asset_type": asset_type,
                "status": "published",
                "ref_kind": "db",
                "ref_value": content_id,
                "meta_json": {},
            }
            return {
                "ok": True,
                "status": "resolved",
                "chapter_title": chapter_title_res,
                "asset": asset,
                "luma_content": content,
                "debug": debug_info,
            }
except Exception as ex:
    debug_info["v2_error"] = str(ex)

    # 1) best-effort chapter metadata
    chapter_row = None
    try:
        with engine.begin() as conn:
            chapter_row = conn.execute(_t("""
                SELECT class_num, track, program, subject_slug, chapter_id, chapter_title, chapter_order
                FROM syllabus_chapters
                WHERE class_num = :class_num
                  AND track = :track
                  AND program = :program
                  AND subject_slug = ANY(:subjects)
                  AND chapter_id = ANY(:chapters)
                LIMIT 1;
            """), {
                "class_num": int(class_num),
                "track": track,
                "program": program,
                "subjects": subject_variants,
                "chapters": chapter_variants,
            }).mappings().first()
    except Exception:
        chapter_row = None

    if not chapter_row and chapter_title_in:
        chapter_row = {
            "class_num": int(class_num),
            "track": track,
            "program": program,
            "subject_slug": subject_slug_in,
            "chapter_id": chapter_id_in,
            "chapter_title": chapter_title_in,
            "chapter_order": None,
        }

    if asset_type not in ("luma", "notes", "diagrams", "mindmap", "pyqs", "mcq"):
        return {"ok": False, "status": "invalid_asset_type"}

    try:
        with engine.begin() as conn:
            row = conn.execute(_t("""
                SELECT asset_type, status, ref_kind, ref_value, meta_json, updated_at
                FROM chapter_assets
                WHERE class_num = :class_num
                  AND track = :track
                  AND program = :program
                  AND subject_slug = ANY(:subjects)
                  AND chapter_id = ANY(:chapters)
                  AND asset_type = :asset_type
                LIMIT 1;
            """), {
                "class_num": int(class_num),
                "track": track,
                "program": program,
                "subjects": subject_variants,
                "chapters": chapter_variants,
                "asset_type": asset_type,
            }).mappings().first()
            if not row:
                # Fallback (no explicit chapter_assets mapping):
                # Try to locate a published Luma content item using its metadata (class/board/subject + chapter match).
                # This prevents "Coming Soon" when content exists but mapping hasn't been seeded yet.
                try:
                    if callable(luma_list_content):
                        # Canonicalize board/program
                        prog = program
                        b = (prog or "").strip().lower()
                        if track == TRACK_BOARDS:
                            canonical_board = "CBSE" if b == "cbse" else ("ICSE" if b == "icse" else ("Maharashtra" if b in ("mh","msb","maharashtra") else (prog or "").upper()))
                        else:
                            canonical_board = "NEET" if b == "neet" else ("JEE" if b.startswith("jee") else ("CET" if b.startswith("cet") else (prog or "").upper()))

                        s = (subject_slug_in or "").strip().lower()
                        canonical_subject = "Physics" if s == "physics" else ("Chemistry" if s == "chemistry" else ("Biology" if s in ("biology","bio") else ("Math" if s in ("math","mathematics") else subject_slug)))

                        candidates = luma_list_content(
                            class_level=int(class_num),
                            board=str(canonical_board),
                            subject=str(canonical_subject),
                            limit=100,
                        ) or []

                        want_slug = _slugify(chapter_title_in or chapter_id_in).replace("_", "-")
                        want_slug2 = _slugify(chapter_id_in).replace("_", "-")

                        def _cand_slug(c: Dict[str, Any]) -> str:
                            md = c.get("metadata") or {}
                            bp = c.get("blueprint") or {}
                            # prefer explicit chapter id/title in metadata
                            base = (md.get("chapter_id") or md.get("chapter") or bp.get("chapter") or bp.get("title") or c.get("title") or c.get("id") or "")
                            return _slugify(str(base)).replace("_", "-")

                        hit = None
                        for c in candidates:
                            cs = _cand_slug(c)
                            if cs == want_slug or cs == want_slug2:
                                hit = c
                                break

                        if hit and hit.get("id"):
                            # synthetic asset row
                            row = {
                                "asset_type": asset_type,
                                "status": "published",
                                "ref_kind": "db",
                                "ref_value": hit.get("id"),
                                "meta_json": "{}",
                                "updated_at": None,
                            }
                except Exception:
                    pass

                if not row:
                    if not chapter_row:
                        return {"ok": False, "status": "chapter_not_found", "debug": debug_info}
                    return {"ok": False, "status": "asset_not_found", "debug": debug_info}

            if chapter_row and chapter_row.get("chapter_title"):
                chapter_title_final = chapter_row["chapter_title"]
            elif chapter_title_in:
                chapter_title_final = chapter_title_in
            else:
                chapter_title_final = chapter_id_in.replace("-", " ").replace("_", " ").title()

            payload: "Dict[str, Any]" = {
                "ok": True,
                "status": "ok",
                "track": track,
                "program": program,
                "class_num": int(class_num),
                "subject_slug": subject_slug_in,
                "chapter_id": chapter_id_in,
                "chapter_title": chapter_title_final,
                "asset": dict(row),
                "debug": debug_info,
            }

            if asset_type == "luma" and row.get("ref_kind") == "db":
                content_id = row.get("ref_value")
                # Attach canonical content (best-effort). Do NOT fail resolution if content is missing;
                # frontend can still use content_id to attempt /api/luma/content/{id}.
                try:
                    c = get_luma_content_by_id(str(content_id or ""))
                    if c.get("ok"):
                        payload["luma_content"] = c.get("content") or c.get("luma_content")
                except Exception:
                    pass

            return payload
    except Exception as e:
        logger.warning(f"study_store: resolve_asset failed: {e}")
        return {"ok": False, "status": "error"}


def get_luma_content_by_id(content_id: str) -> Dict[str, Any]:
    """Fetch canonical Luma content by ID.

    IMPORTANT:
    - Legacy Study endpoints previously read from a different luma_content schema
      (content_id/title columns).
    - The new Luma system stores content in luma_content(id, metadata_json, blueprint_json, published).
    - This adapter makes Study routes compatible without duplicating data.
    """
    cid = (content_id or "").strip()
    if not cid:
        return {"ok": False, "status": "missing_content_id"}

    # Prefer canonical Luma store (published-only).
    if callable(luma_get_content):
        content = luma_get_content(cid)
        if content:
            return {"ok": True, "status": "ok", "content": content}
        return {"ok": False, "status": "not_found"}

    # Fallback: old table shape (if present)
    ensure_tables()
    engine = get_engine_safe()
    if not engine:
        return {"ok": False, "status": "db_unavailable"}

    try:
        with engine.begin() as conn:
            row = conn.execute(_t("""
                SELECT content_id, title, blueprint_json, created_at, updated_at
                FROM luma_content
                WHERE content_id = :cid
                LIMIT 1;
            """), {"cid": cid}).mappings().first()

            if not row:
                return {"ok": False, "status": "not_found"}

            return {"ok": True, "status": "ok", "luma_content": dict(row)}
    except Exception as e:
        logger.warning(f"study_store: get_luma_content_by_id failed: {e}")
        return {"ok": False, "status": "error"}


def upsert_luma_asset_mapping(
    *,
    class_num: int,
    track: str,
    program: str,
    subject_slug: str,
    chapter_id: str,
    # Back-compat: older callers used content_id
    content_id: Optional[str] = None,
    # New canonical args (used by /api/study/asset/set)
    status: str = "published",
    ref_kind: str = "db",
    ref_value: Optional[str] = None,
    meta_json: Any = None,
) -> Dict[str, Any]:
    """Upsert a chapter -> asset mapping row for Luma.

    Patch goals:
    - Accept `status` (fixes crash: unexpected keyword argument 'status')
    - Accept `ref_value` / `content_id` (either works)
    - Return a helpful result payload for API debugging
    """
    ensure_tables()
    engine = get_engine_safe()
    if not engine:
        return {"ok": False, "status": "db_unavailable"}

    track = (track or "").strip().lower()
    program = (program or "").strip().lower()
    subject_slug_n = _slugify(subject_slug)
    chapter_id_n = (chapter_id or "").strip().lower()
    status_n = (status or "published").strip().lower()
    if status_n not in STATUS_VALUES:
        status_n = "published"
    ref_kind_n = (ref_kind or "db").strip().lower()
    if ref_kind_n not in REF_KINDS:
        ref_kind_n = "db"

    # canonical ref_value
    rv = (ref_value or content_id or "").strip()
    if not rv:
        return {"ok": False, "status": "missing_ref_value"}

    # meta_json as string
    try:
        meta_s = json.dumps(meta_json or {}, ensure_ascii=False)
    except Exception:
        meta_s = "{}"

    try:
        with engine.begin() as conn:
            row = conn.execute(_t("""
                INSERT INTO chapter_assets
                    (class_num, track, program, subject_slug, chapter_id, asset_type, status, ref_kind, ref_value, meta_json)
                VALUES
                    (:class_num, :track, :program, :subject_slug, :chapter_id, 'luma', :status, :ref_kind, :ref_value, :meta_json)
                ON CONFLICT (class_num, track, program, subject_slug, chapter_id, asset_type)
                DO UPDATE SET
                    status=EXCLUDED.status,
                    ref_kind=EXCLUDED.ref_kind,
                    ref_value=EXCLUDED.ref_value,
                    meta_json=EXCLUDED.meta_json,
                    updated_at=NOW()
                RETURNING id;
            """), {
                "class_num": int(class_num),
                "track": track,
                "program": program,
                "subject_slug": subject_slug_n,
                "chapter_id": chapter_id_n,
                "status": status_n,
                "ref_kind": ref_kind_n,
                "ref_value": rv,
                "meta_json": meta_s,
            }).fetchone()

        return {"ok": True, "status": "upserted", "id": int(row[0]) if row else None}
    except Exception as e:
        logger.warning(f"study_store: upsert_luma_asset_mapping failed: {e}")
        return {"ok": False, "status": "error", "error": f"{e.__class__.__name__}: {str(e)}"}


def seed_luma_mappings_from_luma_content() -> Dict[str, Any]:
    """
    Best-effort mapping from existing luma_content rows into chapter_assets for 'luma' asset type.
    Uses metadata fields (class_level, board, subject, chapter) and matches chapter title to syllabus_chapters.
    """
    ensure_tables()
    engine = get_engine_safe()
    if not engine:
        return {"ok": False, "reason": "db_unavailable"}

    # Load syllabus title->chapter_id lookup per (class, boards program, subject_slug)
    title_lookup: Dict[Tuple[int, str, str], Dict[str, str]] = {}
    try:
        with engine.connect() as conn:
            rows = conn.execute(_t("""
                SELECT class_num, track, program, subject_slug, chapter_id, chapter_title
                FROM syllabus_chapters
                WHERE track='boards';
            """)).fetchall()
        for r in rows:
            cls, _, prog, subj, cid, ctitle = int(r[0]), r[1], r[2], r[3], r[4], r[5]
            key = (cls, prog, subj)
            title_lookup.setdefault(key, {})[_slugify(str(ctitle))] = cid
    except Exception as e:
        logger.warning(f"study_store: building title lookup failed: {e}")

    inserted = 0
    skipped = 0

    def infer_track_program(board_str: str) -> Tuple[str, str]:
        b = (board_str or "").strip().lower()
        if b in ("cbse", "icse", "maharashtra", "msb", "mh"):
            return (TRACK_BOARDS, _normalize_program(TRACK_BOARDS, b))
        if b in ("neet", "jee", "jee_adv", "jee_main", "cet", "cet_engg", "cet_med"):
            return (TRACK_ENTRANCE, _normalize_program(TRACK_ENTRANCE, b))
        # Default: treat as boards if unknown
        return (TRACK_BOARDS, _slugify(b) or "cbse")

    try:
        with engine.connect() as conn:
            rows = conn.execute(_t("""
                SELECT id, metadata_json, published
                FROM luma_content
                ORDER BY created_at DESC
                LIMIT 500;
            """)).fetchall()
    except Exception as e:
        return {"ok": False, "reason": f"read_luma_content_failed:{e}"}

    for r in rows:
        content_id = str(r[0])
        try:
            md = json.loads(r[1] or "{}")
        except Exception:
            md = {}
        if not bool(r[2]):
            continue
        cls = int(md.get("class_level") or 0) or 0
        board = str(md.get("board") or "").strip()
        subject = _slugify(str(md.get("subject") or ""))
        chapter_title = str(md.get("chapter") or md.get("topic") or "").strip()
        if not cls or not subject or not chapter_title:
            skipped += 1
            continue

        track, program = infer_track_program(board)

        # Determine chapter_id:
        # Prefer explicit metadata.chapter_id if present
        ch_id = str(md.get("chapter_id") or "").strip()
        if not ch_id:
            # Lookup by title in boards syllabus for same class/program/subject
            key = (cls, program if track == TRACK_BOARDS else ("cbse" if program in ("jee", "neet") else "maharashtra"), subject)
            lookup = title_lookup.get(key, {})
            ch_id = lookup.get(_slugify(chapter_title)) or ""
        if not ch_id:
            skipped += 1
            continue

        ok = upsert_luma_asset_mapping(
            class_num=cls,
            track=track,
            program=program,
            subject_slug=subject,
            chapter_id=ch_id,
            content_id=content_id,
        )
        if ok:
            inserted += 1
        else:
            skipped += 1

    return {"ok": True, "inserted": inserted, "skipped": skipped}
