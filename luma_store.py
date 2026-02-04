"""LUMA STORE - PRODUCTION PATCH (CEO LOCK adapter)

Supports BOTH:
- Legacy: {chapter_slug}-{board}-{class}-{subject}
- CEO LOCK: {chapter_slug}-{track}-{class_level}-{subject_code}-{seq}

If CEO tables (content_items / syllabus_map) exist, they are the source of truth.
Fallback remains luma_content for backward compatibility.
"""
from __future__ import annotations
import json, re, logging
from typing import Dict, Any, List, Optional
logger = logging.getLogger("knoweasy-engine-api")
try:
    from db import get_engine_safe
except: 
    def get_engine_safe(): return None
try:
    from sqlalchemy import text as _t
except: 
    def _t(q): return q

# CANONICAL ID FORMAT
SUBJ_MAP = {"mathematics":"math","physics":"phy","chemistry":"chem","biology":"bio","science":"sci"}
BRD_MAP = {"cbse":"cbse","icse":"icse","maharashtra":"maha","jee":"jee","jee mains":"jee","jee advanced":"jee-adv","neet":"neet"}


# --- CEO LOCK helpers ---
def _table_exists(conn, table_name: str) -> bool:
    try:
        r = conn.execute(_t("SELECT to_regclass(:t)"), {"t": table_name}).fetchone()
        return bool(r and r[0])
    except Exception:
        # If to_regclass unavailable, try information_schema
        try:
            r = conn.execute(_t(
                "SELECT 1 FROM information_schema.tables WHERE table_name=:t LIMIT 1"
            ), {"t": table_name}).fetchone()
            return bool(r)
        except Exception:
            return False

def _normalize_track(board_or_track: str) -> str:
    if not board_or_track:
        return ""
    b = board_or_track.lower().strip()
    return BRD_MAP.get(b, slugify(b))

def _normalize_subject(subject: str) -> str:
    if not subject:
        return ""
    s = subject.lower().strip()
    return SUBJ_MAP.get(s, slugify(s))

def _pick_best_seq(ids: list[str]) -> str | None:
    # Prefer -001, else lowest numeric suffix, else first
    if not ids:
        return None
    if any(i.endswith("-001") for i in ids):
        for i in ids:
            if i.endswith("-001"):
                return i
    def seq_key(i: str):
        m = re.search(r"-(\d{3,})$", i)
        return int(m.group(1)) if m else 10**9
    return sorted(ids, key=seq_key)[0]
def slugify(t):
    t=t.lower().strip()
    t=re.sub(r'[^\w\s-]','',t)
    return re.sub(r'[-\s]+','-',t)

def canonical_id(chapter,board,cls,subject):
    """DETERMINISTIC ID: same inputs = same ID always"""
    ch=slugify(chapter)
    b=BRD_MAP.get(board.lower(),slugify(board))
    s=SUBJ_MAP.get(subject.lower(),slugify(subject))
    return f"{ch}-{b}-{cls}-{s}"

def norm(s):
    if not s: return ""
    s=s.lower().strip()
    s=re.sub(r'[^\w\s]','',s)
    return re.sub(r'\s+',' ',s)

def _json_str(v):
    if v is None: return "{}"
    if isinstance(v,(dict,list)):
        try: return json.dumps(v,ensure_ascii=False)
        except: return "{}"
    if isinstance(v,str):
        s=v.strip()
        if not s: return "{}"
        try: return json.dumps(json.loads(s),ensure_ascii=False)
        except: return "{}"
    return "{}"

def _json_load(v,d):
    if v is None: return d
    if isinstance(v,(dict,list)): return v
    if isinstance(v,(bytes,bytearray)):
        try: v=v.decode("utf-8")
        except: return d
    if isinstance(v,str):
        s=v.strip()
        if not s: return d
        try: return json.loads(s)
        except: return d
    return d

def ensure_tables():
    e=get_engine_safe()
    if not e: 
        logger.warning("luma_store: DB unavailable")
        return
    try:
        with e.begin() as c:
            c.execute(_t("""CREATE TABLE IF NOT EXISTS luma_content(
                id TEXT PRIMARY KEY,
                metadata_json TEXT NOT NULL,
                blueprint_json TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                published BOOLEAN DEFAULT FALSE)"""))
            c.execute(_t("""CREATE TABLE IF NOT EXISTS luma_progress(
                user_id INTEGER,
                content_id TEXT,
                completed BOOLEAN DEFAULT FALSE,
                time_spent_seconds INTEGER DEFAULT 0,
                notes TEXT,
                bookmarked BOOLEAN DEFAULT FALSE,
                last_visited_at TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY(user_id,content_id))"""))
            c.execute(_t("""CREATE TABLE IF NOT EXISTS user_catalog(
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                title TEXT,
                doc_type TEXT,
                source TEXT,
                file_url TEXT,
                file_key TEXT,
                metadata_json TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW())"""))
    except Exception as ex:
        logger.warning(f"table setup: {ex}")

def get_content(cid):
    """Get content by content_id.

    Prefers CEO LOCK table content_items if present.
    Returns a normalized object:
      {content_id, metadata, blueprint, published}
    """
    e = get_engine_safe()
    if not e:
        return None

    try:
        with e.connect() as c:
            # CEO LOCK path
            if _table_exists(c, "content_items"):
                r = c.execute(_t("""
                    SELECT content_id, track, class_level, subject_code, chapter_slug, chapter_title,
                           blueprint_json, pdf_url, mindmap_url, cover_image_url, version, status,
                           created_at, updated_at
                    FROM content_items
                    WHERE content_id=:id
                    LIMIT 1
                """), {"id": cid}).fetchone()
                if r:
                    metadata = {
                        "track": r[1],
                        "class_level": r[2],
                        "subject_code": r[3],
                        "chapter_slug": r[4],
                        "chapter_title": r[5],
                        "pdf_url": r[7],
                        "mindmap_url": r[8],
                        "cover_image_url": r[9],
                        "version": int(r[10] or 1),
                    }
                    blueprint = _json_load(r[6], {})
                    published = (str(r[11] or "").lower() == "published")
                    return {"content_id": r[0], "metadata": metadata, "blueprint": blueprint, "published": published}

            # Legacy path
            r = c.execute(_t("SELECT id,metadata_json,blueprint_json,created_at,updated_at,published FROM luma_content WHERE id=:id"), {"id": cid}).fetchone()
        if not r:
            return None
        return {"content_id": r[0], "metadata": _json_load(r[1], {}), "blueprint": _json_load(r[2], {}), "published": bool(r[5])}
    except Exception as ex:
        logger.error(f"get_content: {ex}")
        return None

def list_content(class_level=None,subject=None,board=None,limit=50):
    e=get_engine_safe()
    if not e: return []
    try:
        with e.connect() as c:
            rs=c.execute(_t("SELECT id,metadata_json,blueprint_json,published FROM luma_content WHERE published=TRUE LIMIT :lim"),{"lim":limit}).fetchall()
        out=[]
        for r in rs:
            m=_json_load(r[1],{})
            if class_level and int(m.get("class_level",0))!=class_level: continue
            if subject and subject.lower() not in str(m.get("subject","")).lower(): continue
            if board and board.lower() not in str(m.get("board","")).lower(): continue
            out.append({"content_id":r[0],"metadata":m,"blueprint":_json_load(r[2],{}),"published":r[3]})
        return out
    except Exception as ex:
        logger.error(f"list_content: {ex}")
        return []

def resolve_content_id(board,class_level,subject,chapter):
    """Resolver that prefers CEO LOCK tables if present.

    Inputs:
      board: cbse/icse/maharashtra/neet/jee/etc (treated as track)
      class_level: int
      subject: human slug (biology/chemistry/mathematics/physics/science)
      chapter: chapter title/slug
    """
    cn = norm(chapter or "")
    if not cn:
        return {"ok": False, "content_id": None, "status": "not_found", "error": "NO_CHAPTER"}

    e = get_engine_safe()
    track = _normalize_track(board or "")
    subj = _normalize_subject(subject or "")
    ch_slug = slugify(chapter or "")
    cls = int(class_level) if class_level is not None else None

    # 1) CEO LOCK path: syllabus_map / content_items
    if e and cls is not None:
        try:
            with e.connect() as c:
                if _table_exists(c, "syllabus_map") and _table_exists(c, "content_items"):
                    # Try syllabus_map direct
                    r = c.execute(_t("""
                        SELECT content_id, availability
                        FROM syllabus_map
                        WHERE track=:track AND class_level=:cls AND subject_code=:subj AND chapter_slug=:ch
                        LIMIT 1
                    """), {"track": track, "cls": cls, "subj": subj, "ch": ch_slug}).fetchone()
                    if r and r[0]:
                        return {"ok": True, "content_id": r[0], "status": "published"}

                    # Else: search content_items by normalized chapter_slug
                    rs = c.execute(_t("""
                        SELECT content_id
                        FROM content_items
                        WHERE track=:track AND class_level=:cls AND subject_code=:subj AND chapter_slug=:ch AND status='published'
                    """), {"track": track, "cls": cls, "subj": subj, "ch": ch_slug}).fetchall()
                    ids = [row[0] for row in (rs or []) if row and row[0]]
                    best = _pick_best_seq(ids)
                    if best:
                        return {"ok": True, "content_id": best, "status": "published"}

                    # If chapter exists in syllabus_map but no content_id yet -> coming soon
                    r2 = c.execute(_t("""
                        SELECT 1 FROM syllabus_map
                        WHERE track=:track AND class_level=:cls AND subject_code=:subj AND chapter_slug=:ch AND availability='coming_soon'
                        LIMIT 1
                    """), {"track": track, "cls": cls, "subj": subj, "ch": ch_slug}).fetchone()
                    if r2:
                        return {"ok": False, "content_id": None, "status": "coming_soon", "error": "COMING_SOON"}
        except Exception as ex:
            logger.warning(f"resolve_content_id CEO path failed: {ex}")

    # 2) Legacy path (luma_content): fuzzy match on metadata
    items = list_content(board=board, class_level=class_level, subject=subject)
    best_id, best_score = None, -1
    for it in items:
        m = it.get("metadata") or {}
        ch_n = norm(m.get("chapter", ""))
        tp_n = norm(m.get("topic", ""))
        ti_n = norm(m.get("title", ""))
        sc = 0
        if ch_n == cn: sc = 100
        elif ch_n and (cn in ch_n or ch_n in cn): sc = 85
        elif tp_n and (cn in tp_n or tp_n in cn): sc = 70
        elif ti_n and (cn in ti_n or ti_n in cn): sc = 60
        if sc > best_score:
            best_score, best_id = sc, it.get("content_id")
    if best_id:
        return {"ok": True, "content_id": best_id, "status": "published"}
    return {"ok": False, "content_id": None, "status": "coming_soon", "error": "NO_MATCH"}

def save_progress(uid,cid,comp=False,tsec=0,notes=None,bm=False):
    e=get_engine_safe()
    if not e: return {"ok":False,"error":"DB_UNAVAILABLE"}
    try:
        with e.begin() as c:
            c.execute(_t("""INSERT INTO luma_progress(user_id,content_id,completed,time_spent_seconds,notes,bookmarked,last_visited_at)
                VALUES(:u,:c,:co,:t,:n,:b,NOW())
                ON CONFLICT(user_id,content_id)DO UPDATE SET 
                completed=EXCLUDED.completed,
                time_spent_seconds=luma_progress.time_spent_seconds+EXCLUDED.time_spent_seconds,
                notes=COALESCE(EXCLUDED.notes,luma_progress.notes),
                bookmarked=EXCLUDED.bookmarked,
                last_visited_at=NOW()"""),{"u":uid,"c":cid,"co":comp,"t":tsec,"n":notes,"b":bm})
        return {"ok":True}
    except Exception as ex:
        logger.error(f"save_progress: {ex}")
        return {"ok":False,"error":"SAVE_FAILED"}

def get_progress(uid,cid):
    e=get_engine_safe()
    if not e: return None
    try:
        with e.connect() as c:
            r=c.execute(_t("SELECT completed,time_spent_seconds,notes,bookmarked FROM luma_progress WHERE user_id=:u AND content_id=:c"),{"u":uid,"c":cid}).fetchone()
        if not r: return None
        return {"content_id":cid,"completed":r[0],"time_spent_seconds":r[1],"notes":r[2],"bookmarked":r[3]}
    except: return None

def list_catalog(uid,lim=50,off=0):
    e=get_engine_safe()
    if not e: return []
    try:
        with e.connect() as c:
            rs=c.execute(_t("SELECT id,title,doc_type,file_url FROM user_catalog WHERE user_id=:u ORDER BY created_at DESC LIMIT :l OFFSET :o"),{"u":uid,"l":lim,"o":off}).fetchall()
        return [{"id":r[0],"title":r[1],"doc_type":r[2],"file_url":r[3]}for r in rs]
    except: return []

def create_catalog_item(it):
    e=get_engine_safe()
    if not e: return False
    try:
        with e.begin() as c:
            c.execute(_t("INSERT INTO user_catalog(user_id,title,doc_type,source,file_url,file_key,metadata_json)VALUES(:u,:t,:d,:s,:f,:k,:m)"),it)
        return True
    except: return False

def delete_catalog_item(uid,iid):
    e=get_engine_safe()
    if not e: return False
    try:
        with e.begin() as c:
            c.execute(_t("DELETE FROM user_catalog WHERE id=:i AND user_id=:u"),{"i":iid,"u":uid})
        return True
    except: return False
