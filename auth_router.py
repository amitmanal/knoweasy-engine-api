from __future__ import annotations

import logging
import os
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from auth_utils import normalize_email, is_valid_email, auth_is_configured, new_otp_code, new_session_token
from auth_store import (
    otp_can_send,
    store_otp,
    verify_otp,
    get_or_create_user,
    create_session,
    session_user,
    delete_session,
)
from email_service import email_is_configured, email_provider_debug, send_otp_email
from auth_schemas import RequestOtpIn, RequestOtpOut, VerifyOtpIn, VerifyOtpOut, LogoutIn, BasicOut

logger = logging.getLogger("knoweasy-engine-api.auth")

router = APIRouter(prefix="", tags=["auth"])

def _role_norm(role: str) -> str:
    r = (role or "").strip().lower()
    if r not in ("student", "parent"):
        return ""
    return r

@router.post("/auth/request-otp", response_model=RequestOtpOut)
def request_otp(payload: RequestOtpIn, request: Request):
    rid = getattr(getattr(request, "state", None), "rid", "") or "-"
    if not auth_is_configured():
        return JSONResponse(status_code=503, content={"ok": False, "message": "Auth not configured (missing AUTH_SECRET_KEY)", "cooldown_seconds": 0})

    email = normalize_email(payload.email)
    role = _role_norm(payload.role)
    if not role:
        return JSONResponse(status_code=400, content={"ok": False, "message": "Invalid role. Use 'student' or 'parent'.", "cooldown_seconds": 0})
    if not is_valid_email(email):
        return JSONResponse(status_code=400, content={"ok": False, "message": "Invalid email address.", "cooldown_seconds": 0})

    allowed, retry_after = otp_can_send(email, role)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"ok": False, "message": "Please wait before requesting another code.", "cooldown_seconds": int(retry_after)},
        )

    if not email_is_configured():
        dbg = email_provider_debug()
        logger.error(f"[RID:{rid}] Email not configured. debug={dbg}")
        return JSONResponse(status_code=503, content={"ok": False, "message": "Email sender not configured (missing Resend/SMTP env vars).", "cooldown_seconds": 0})

    otp_plain, otp_hash = new_otp_code()
    store_otp(email, role, otp_hash)

    try:
        logger.info(
            f"[RID:{rid}] Sending OTP email. to={_mask_email(email)} role={role} provider={email_provider_debug().get('provider')}"
        )
        send_otp_email(to_email=email, otp=otp_plain)
        logger.info(f"[RID:{rid}] OTP email send triggered")
    except Exception as e:
        # In production we keep the user-facing message simple, but we *do* want actionable debug
        # for the operator (you) without exposing secrets publicly.
        logger.exception(f"[RID:{rid}] Failed to send OTP email: {e}")

        admin_key = (os.getenv("ADMIN_API_KEY") or "").strip()
        req_admin = request.headers.get("X-Admin-Key", "").strip() if request else ""
        is_admin = bool(admin_key and req_admin and req_admin == admin_key)

        payload = {
            "ok": False,
            "error": "OTP_EMAIL_FAILED",
            "message": "Failed to send OTP. Please try again.",
            "cooldown_seconds": 0,
        }
        if is_admin:
            payload["debug"] = {
                "provider": email_provider_debug(),
                "hint": "If using Resend, ensure EMAIL_FROM (or FROM_EMAIL) uses a verified domain in Resend, and RESEND_API_KEY is correct.",
            }
        return JSONResponse(status_code=500, content=payload)

    return {"ok": True, "message": "OTP sent to your email.", "cooldown_seconds": 30}


def _mask_email(email: str) -> str:
    try:
        local, domain = email.split("@", 1)
        if len(local) <= 2:
            local_mask = local[:1] + "*"
        else:
            local_mask = local[:2] + "***"
        return f"{local_mask}@{domain}"
    except Exception:
        return "***"

@router.post("/auth/verify-otp", response_model=VerifyOtpOut)
def verify_otp_code(payload: VerifyOtpIn):
    if not auth_is_configured():
        return JSONResponse(status_code=503, content={"ok": False, "error": "AUTH_NOT_CONFIGURED", "message": "Auth not configured (missing AUTH_SECRET_KEY)"})

    email = normalize_email(payload.email)
    role = _role_norm(payload.role)
    otp = (payload.otp or "").strip()

    if not role:
        return JSONResponse(status_code=400, content={"ok": False, "error": "BAD_ROLE", "message": "Invalid role. Use 'student' or 'parent'."})
    if not is_valid_email(email):
        return JSONResponse(status_code=400, content={"ok": False, "error": "BAD_EMAIL", "message": "Invalid email address."})
    if not otp or len(otp) < 4:
        return JSONResponse(status_code=400, content={"ok": False, "error": "BAD_OTP", "message": "Invalid code."})

    ok, reason, retry_after = verify_otp(email, role, otp)
    if not ok:
        status = 400
        if reason in ("OTP_LOCKED",):
            status = 429
        elif reason in ("OTP_EXPIRED", "OTP_NOT_FOUND", "OTP_INVALID"):
            status = 400
        elif reason == "AUTH_NOT_CONFIGURED":
            status = 503

        return JSONResponse(
            status_code=status,
            content={
                "ok": False,
                "error": reason,
                "message": _human_reason(reason),
                "retry_after_seconds": int(retry_after) if retry_after else 0,
            },
        )

    user_id, is_new = get_or_create_user(email, role)
    token_plain, token_hash = new_session_token()
    create_session(user_id, token_hash)

    return {
        "ok": True,
        "session_token": token_plain,
        "is_new_user": bool(is_new),
        "user": {"email": email, "role": role},
    }

def _human_reason(reason: str) -> str:
    if reason == "OTP_INVALID":
        return "Incorrect code. Try again."
    if reason == "OTP_EXPIRED":
        return "Code expired. Request a new one."
    if reason == "OTP_NOT_FOUND":
        return "No code found. Request a new one."
    if reason == "OTP_LOCKED":
        return "Too many attempts. Please wait and try again."
    if reason == "AUTH_NOT_CONFIGURED":
        return "Login system not configured."
    return "Unable to verify code."

@router.get("/me")
def me(authorization: str | None = Header(default=None, alias="Authorization")):
    token = _token_from_header(authorization)
    if not token:
        return JSONResponse(status_code=401, content={"ok": False, "error": "UNAUTHORIZED", "message": "Missing session token."})

    u = session_user(token)
    if not u:
        return JSONResponse(status_code=401, content={"ok": False, "error": "UNAUTHORIZED", "message": "Invalid or expired session."})

    return {"ok": True, "user": {"email": u["email"], "role": u["role"]}}

@router.post("/auth/logout", response_model=BasicOut)
def logout(payload: LogoutIn):
    token = (payload.session_token or "").strip()
    if not token:
        return JSONResponse(status_code=400, content={"ok": False, "message": "Missing session token."})
    delete_session(token)
    return {"ok": True, "message": "Logged out."}

def _token_from_header(authorization: str | None) -> str:
    if not authorization:
        return ""
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return ""
