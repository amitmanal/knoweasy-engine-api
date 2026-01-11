
from __future__ import annotations

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from auth_store import session_user
from billing_store import get_plans, get_billing_summary

router = APIRouter(prefix="/billing", tags=["billing"])


def _token_from_header(authorization: str | None) -> str:
    if not authorization:
        return ""
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return ""


@router.get("/plans")
def plans():
    return {"ok": True, "plans": get_plans()}


@router.get("/me")
def me(authorization: str | None = Header(default=None, alias="Authorization")):
    token = _token_from_header(authorization)
    if not token:
        return JSONResponse(status_code=401, content={"ok": False, "error": "UNAUTHORIZED", "message": "Missing session token."})
    u = session_user(token)
    if not u:
        return JSONResponse(status_code=401, content={"ok": False, "error": "UNAUTHORIZED", "message": "Invalid or expired session."})

    summary = get_billing_summary(int(u["user_id"]))
    return {"ok": True, "billing": summary}
