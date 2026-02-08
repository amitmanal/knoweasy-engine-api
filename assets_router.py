from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from db import get_engine_safe
from sqlalchemy import text as _t

from r2_client import presign_get_object

logger = logging.getLogger("knoweasy-engine-api")

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("/signed-url")
def signed_url(
    object_key: str = Query(..., description="R2 object key, e.g. v1/content/<content_id>/assets/pdf/notes__abcd1234.pdf"),
    expires: int | None = Query(None, ge=30, le=3600, description="Signed URL expiry in seconds (30..3600). Default from env."),
):
    try:
        url = presign_get_object(object_key=object_key, expires_in=expires)
        return {"ok": True, "object_key": object_key, "url": url}
    except Exception as e:
        logger.warning(f"signed_url failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/blob")
def get_blob(
    content_id: str = Query(...),
    asset_type: str = Query(...),
):
    e = get_engine_safe()
    if not e:
        raise HTTPException(status_code=503, detail="DB_UNAVAILABLE")
    at = (asset_type or "").strip().lower()
    try:
        with e.connect() as conn:
            row = conn.execute(_t(
                "SELECT mime_type, data FROM content_asset_blobs WHERE content_id=:cid AND asset_type=:at LIMIT 1"
            ), {"cid": content_id, "at": at}).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="NOT_FOUND")
        mime = row[0] or ("application/pdf" if at.endswith("pdf") else "application/json")
        data = row[1]
        return Response(content=data, media_type=mime)
    except HTTPException:
        raise
    except Exception as ex:
        logger.warning(f"blob fetch failed: {ex}")
        raise HTTPException(status_code=500, detail="ERROR")
