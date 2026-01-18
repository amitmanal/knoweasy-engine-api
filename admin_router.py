# admin_router.py
"""Private internal cost dashboard endpoints.

Enabled only when ADMIN_API_KEY is set.
Auth via header: X-Admin-Key.

These endpoints are for operators only (you).
They never affect user flows.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse

from db import db_cost_summary, db_cost_top_users

router = APIRouter(prefix="/admin", tags=["admin"])


def _admin_key() -> str:
    return (os.getenv("ADMIN_API_KEY") or "").strip()


def _require_admin(x_admin_key: str | None) -> None:
    key = _admin_key()
    # If not enabled, behave like it doesn't exist (security by obscurity).
    if not key:
        raise PermissionError("ADMIN_DISABLED")
    if not x_admin_key or x_admin_key.strip() != key:
        raise PermissionError("ADMIN_FORBIDDEN")


@router.get("/cost/summary")
def cost_summary(
    days: int = Query(default=7, ge=1, le=365),
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
):
    """Aggregate costs + credits over the last N days."""
    try:
        _require_admin(x_admin_key)
    except PermissionError as e:
        code = str(e)
        if code == "ADMIN_DISABLED":
            return JSONResponse(status_code=404, content={"ok": False, "error": "NOT_FOUND"})
        return JSONResponse(status_code=403, content={"ok": False, "error": "FORBIDDEN"})

    out = db_cost_summary(days=days)
    return JSONResponse(status_code=200, content=out)


@router.get("/cost/top-users")
def cost_top_users(
    days: int = Query(default=7, ge=1, le=365),
    limit: int = Query(default=20, ge=1, le=200),
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
):
    """Top users by cost/requests over the last N days."""
    try:
        _require_admin(x_admin_key)
    except PermissionError as e:
        code = str(e)
        if code == "ADMIN_DISABLED":
            return JSONResponse(status_code=404, content={"ok": False, "error": "NOT_FOUND"})
        return JSONResponse(status_code=403, content={"ok": False, "error": "FORBIDDEN"})

    out = db_cost_top_users(days=days, limit=limit)
    return JSONResponse(status_code=200, content=out)
