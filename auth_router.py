from __future__ import annotations

import logging
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from auth_utils import normalize_email, is_valid_email, auth_is_configured, new_otp_code, new_session_token
from auth_store import (
    otp_can_send,
    store_otp,
    verify_otp,
    get_or_create_user,
    get_user_profile,
    update_user_profile,
    create_session,
    session_user,
    delete_session,
)
from email_service import send_otp_email, email_is_configured
from auth_schemas import RequestOtpIn, RequestOtpOut, VerifyOtpIn, VerifyOtpOut, LogoutIn, BasicOut, ProfileUpsertIn, ProfileOut

logger = logging.getLogger("knoweasy-engine-api.auth")

router = APIRouter(prefix="", tags=["auth"])

def _role_norm(role: str) -> str:
    r = (role or "").strip().lower()
    if r not in ("student", "parent"):
        return ""
    return r

@router.post("/auth/request-otp", response_model=RequestOtpOut)
def request_otp(payload: RequestOtpIn, x_request_id: str | None = Header(default=None, alias="X-Request-ID")):
    if not auth_is_configured():
        return JSONResponse(status_code=503, content={"ok": False, "message": "Auth not configured (missing AUTH_SECRET_KEY)", "cooldown_seconds": 0})

    email = normalize_email(payload.email)
    role = _role_norm(payload.role)
    rid = x_request_id or "-"

    # Mask email in logs (privacy)
    _local, _domain = (email.split("@", 1) + [""])[:2]
    masked_email = (
        (_local[:2] + "***" + (_local[-1:] if len(_local) > 2 else "")) + ("@" + _domain if _domain else "")
    ) if _local else "***"

    logger.info(f"[RID:{rid}] request_otp role={role} email={masked_email}")

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
        return JSONResponse(status_code=503, content={"ok": False, "message": "Email sender not configured (missing SMTP/Resend env vars).", "cooldown_seconds": 0})

    otp_plain, otp_hash = new_otp_code()
    store_otp(email, role, otp_hash)

    try:
        send_otp_email(to_email=email, otp=otp_plain)
    except Exception:
        logger.exception("Failed to send OTP email")
        return JSONResponse(status_code=500, content={"ok": False, "message": "Failed to send OTP. Please try again.", "cooldown_seconds": 0})

    return {"ok": True, "message": "OTP sent to your email.", "cooldown_seconds": 30}

@router.post("/auth/verify-otp", response_model=VerifyOtpOut)
def verify_otp_code(payload: VerifyOtpIn, x_request_id: str | None = Header(default=None, alias="X-Request-ID")):
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

    # Fetch the full user profile to determine whether the profile is complete.
    profile = get_user_profile(user_id) or {"email": email, "role": role}
    # Expose profile_complete at the top level for backward‑compatibility with older frontends.
    profile_complete = bool(profile.get("profile_complete") or False)
    return {
        "ok": True,
        "session_token": token_plain,
        "is_new_user": bool(is_new),
        "profile_complete": profile_complete,
        "user": profile,
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

    # Expose profile_complete at top level as well as in user object.  This
    # makes it easy for clients to read without drilling into user.
    return {
        "ok": True,
        "profile_complete": bool(u.get("profile_complete") or False),
        "user": {
            "email": u["email"],
            "role": u["role"],
            "full_name": u.get("full_name"),
            "board": u.get("board"),
            "class_level": u.get("class_level"),
            "profile_complete": bool(u.get("profile_complete") or False),
        },
    }



@router.get("/profile", response_model=ProfileOut)
def get_profile(authorization: str | None = Header(default=None, alias="Authorization")):
    token = _token_from_header(authorization)
    if not token:
        return JSONResponse(status_code=401, content={"ok": False, "error": "UNAUTHORIZED", "message": "Missing session token."})
    u = session_user(token)
    if not u:
        return JSONResponse(status_code=401, content={"ok": False, "error": "UNAUTHORIZED", "message": "Invalid or expired session."})
    return {"ok": True, "profile": {"email": u["email"], "role": u["role"], "full_name": u.get("full_name"), "board": u.get("board"), "class_level": u.get("class_level"), "profile_complete": bool(u.get("profile_complete") or False)}}

@router.post("/profile", response_model=ProfileOut)
def upsert_profile(payload: ProfileUpsertIn, authorization: str | None = Header(default=None, alias="Authorization")):
    token = _token_from_header(authorization)
    if not token:
        return JSONResponse(status_code=401, content={"ok": False, "error": "UNAUTHORIZED", "message": "Missing session token."})
    u = session_user(token)
    if not u:
        return JSONResponse(status_code=401, content={"ok": False, "error": "UNAUTHORIZED", "message": "Invalid or expired session."})

    full_name = (payload.full_name or "").strip()
    board = (payload.board or "").strip()
    class_level = int(payload.class_level)

    if len(full_name) < 2:
        return JSONResponse(status_code=400, content={"ok": False, "error": "BAD_NAME", "message": "Please enter your full name."})
    if not board:
        return JSONResponse(status_code=400, content={"ok": False, "error": "BAD_BOARD", "message": "Please select a board."})
    if class_level < 1 or class_level > 12:
        return JSONResponse(status_code=400, content={"ok": False, "error": "BAD_CLASS", "message": "Please select a valid class."})

    updated = update_user_profile(int(u["user_id"]), full_name=full_name, board=board, class_level=class_level)
    if not updated:
        return JSONResponse(status_code=404, content={"ok": False, "error": "NOT_FOUND", "message": "User not found."})
    return {"ok": True, "profile": {"email": updated["email"], "role": updated["role"], "full_name": updated.get("full_name"), "board": updated.get("board"), "class_level": updated.get("class_level"), "profile_complete": bool(updated.get("profile_complete") or False)}}


@router.post("/auth/profile", response_model=ProfileOut)
def auth_upsert_profile(payload: ProfileUpsertIn, authorization: str | None = Header(default=None, alias="Authorization")):
    """Backward-compatible alias for frontend."""
    return upsert_profile(payload, authorization)

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

@router.get("/auth/me")
def auth_me(authorization: str | None = Header(default=None, alias="Authorization")):
    """Backward-compatible alias for frontend."""
    return me(authorization)


@router.get("/auth/profile", response_model=ProfileOut)
def auth_get_profile(authorization: str | None = Header(default=None, alias="Authorization")):
    """Backward-compatible alias for frontend."""
    return get_profile(authorization)

