"""LUMA ROUTER - PRODUCTION PATCH
Canonical resolver enforced"""
from __future__ import annotations
import logging
from typing import Optional
from fastapi import APIRouter,HTTPException,Header
from luma_store import resolve_content_id,get_content,list_content,save_progress,get_progress,list_catalog,create_catalog_item,delete_catalog_item
logger=logging.getLogger("knoweasy-engine-api")
router=APIRouter(prefix="/api/luma",tags=["luma"])
try:
    import luma_store
    luma_store.ensure_tables()
except Exception as e:
    logger.warning(f"table setup: {e}")

async def get_uid(authorization:str=Header(None))->Optional[int]:
    if not authorization: return None
    try:
        from auth_utils import decode_token
        if not authorization.startswith("Bearer "): return None
        tok=authorization.split(" ",1)[1]
        pay=decode_token(tok)
        return int(pay["sub"])if pay and"sub"in pay else None
    except: return None

async def require_user(authorization:str=Header(None))->int:
    u=await get_uid(authorization)
    if u is None: raise HTTPException(401,"Unauthorized")
    return u

@router.get("/resolve")
async def resolve_endpoint(board:str|None=None,class_level:int|None=None,subject:str|None=None,chapter:str|None=None):
    """CANONICAL RESOLVER: returns content_id only
    Example: /api/luma/resolve?board=cbse&class_level=11&subject=biology&chapter=photosynthesis
    Returns: {"ok":true,"content_id":"photosynthesis-cbse-11-bio","status":"published"}"""
    return resolve_content_id(board,class_level,subject,chapter)

@router.get("/content/{content_id}")
async def get_content_endpoint(content_id:str):
    """Get content by canonical ID
    Returns: {"content_id":"...","metadata":{...},"blueprint":{...}}"""
    c=get_content(content_id)
    if not c: raise HTTPException(404,{"ok":False,"error":"NOT_FOUND"})
    return {"ok":True,"content":c}

@router.get("/content")
async def list_content_endpoint(class_level:int|None=None,subject:str|None=None,board:str|None=None,limit:int=50):
    """List published content"""
    return {"ok":True,"contents":list_content(class_level,subject,board,min(limit,100))}

@router.post("/progress/save")
async def save_progress_endpoint(req:dict,user_id:int=Header(None,alias="x-user-id")):
    """Save progress (auth required)"""
    if not user_id: raise HTTPException(401,"Unauthorized")
    r=save_progress(user_id,req["content_id"],req.get("completed",False),req.get("time_spent_seconds",0),req.get("notes"),req.get("bookmarked",False))
    if not r["ok"]: raise HTTPException(500,r["error"])
    return r

@router.get("/progress/{content_id}")
async def get_progress_endpoint(content_id:str,user_id:int=Header(None,alias="x-user-id")):
    """Get progress"""
    if not user_id: raise HTTPException(401,"Unauthorized")
    p=get_progress(user_id,content_id)
    return {"ok":True,"progress":p}if p else{"ok":False,"progress":None}

@router.get("/catalog")
async def catalog_list(user_id:int=Header(None,alias="x-user-id"),limit:int=50,offset:int=0):
    """List user catalog"""
    if not user_id: raise HTTPException(401,"Unauthorized")
    return {"ok":True,"items":list_catalog(user_id,limit,offset)}

@router.post("/catalog")
async def catalog_create(req:dict,user_id:int=Header(None,alias="x-user-id")):
    """Create catalog item"""
    if not user_id: raise HTTPException(401,"Unauthorized")
    req["user_id"]=user_id
    create_catalog_item(req)
    return {"ok":True}

@router.delete("/catalog/{item_id}")
async def catalog_delete(item_id:int,user_id:int=Header(None,alias="x-user-id")):
    """Delete catalog item"""
    if not user_id: raise HTTPException(401,"Unauthorized")
    delete_catalog_item(user_id,item_id)
    return {"ok":True}

@router.get("/health")
async def health():
    """Health check"""
    return {"ok":True,"service":"luma","endpoints":["/resolve","/content/{id}","/content","/progress/save","/progress/{id}","/catalog"]}
