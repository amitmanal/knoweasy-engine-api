from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, Query

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
