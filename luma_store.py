"""LUMA STORE - PRODUCTION PATCH
Canonical ID: {chapter-slug}-{board}-{class}-{subject}
One chapter = One ID (deterministic)"""
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
    e=get_engine_safe()
    if not e: return None
    try:
        with e.connect() as c:
            r=c.execute(_t("SELECT id,metadata_json,blueprint_json,created_at,updated_at,published FROM luma_content WHERE id=:id"),{"id":cid}).fetchone()
        if not r: return None
        return {"content_id":r[0],"metadata":_json_load(r[1],{}),"blueprint":_json_load(r[2],{}),"published":bool(r[5])}
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
    """CANONICAL RESOLVER: returns content_id or None"""
    cn=norm(chapter or "")
    if not cn: return {"ok":False,"content_id":None,"status":"not_found","error":"NO_CHAPTER"}
    items=list_content(board=board,class_level=class_level,subject=subject)
    best_id,best_score=None,-1
    for it in items:
        m=it["metadata"]
        ch_n=norm(m.get("chapter",""))
        tp_n=norm(m.get("topic",""))
        ti_n=norm(m.get("title",""))
        sc=0
        if ch_n==cn: sc=100
        elif ch_n and(cn in ch_n or ch_n in cn): sc=85
        elif tp_n and(cn in tp_n or tp_n in cn): sc=70
        elif ti_n and(cn in ti_n or ti_n in cn): sc=60
        if sc>best_score:
            best_score,best_id=sc,it["content_id"]
    if best_id:
        return {"ok":True,"content_id":best_id,"status":"published"}
    return {"ok":False,"content_id":None,"status":"coming_soon","error":"NO_MATCH"}

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
