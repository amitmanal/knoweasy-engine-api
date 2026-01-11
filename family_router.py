from __future__ import annotations

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from auth_store import session_user
from analytics_store import (
    record_event,
    generate_link_code,
    create_link_request,
    list_student_requests,
    decide_request,
    list_parent_children,
    get_student_summary,
)

router = APIRouter(prefix="/family", tags=["family"])


def _token_from_header(authorization: str | None) -> str:
    if not authorization:
        return ""
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return ""


@router.post("/event")
async def post_event(payload: dict, authorization: str | None = Header(default=None, alias="Authorization")):
    """Record a lightweight usage event. Safe to call frequently."""
    token = _token_from_header(authorization)
    u = session_user(token) if token else None
    event_type = (payload.get("event_type") or "").strip()
    if not event_type:
        return JSONResponse(status_code=400, content={"ok": False, "message": "event_type required"})
    page = payload.get("page")
    duration_sec = payload.get("duration_sec")
    score = payload.get("score")
    meta = payload.get("meta")
    try:
        duration_sec = int(duration_sec) if duration_sec is not None else None
    except Exception:
        duration_sec = None
    try:
        score = float(score) if score is not None else None
    except Exception:
        score = None

    try:
        record_event(
            user_id=(u.get("user_id") if u else None),
            role=(u.get("role") if u else None),
            event_type=event_type,
            page=page,
            duration_sec=duration_sec,
            score=score,
            meta=(meta if isinstance(meta, dict) else None),
        )
    except Exception:
        # Never break app due to analytics
        return {"ok": True}
    return {"ok": True}


@router.post("/student/link-code")
def student_link_code(authorization: str | None = Header(default=None, alias="Authorization")):
    token = _token_from_header(authorization)
    u = session_user(token) if token else None
    if not u:
        return JSONResponse(status_code=401, content={"ok": False, "message": "Login required"})
    if u.get("role") != "student":
        return JSONResponse(status_code=403, content={"ok": False, "message": "Only students can generate link code"})
    try:
        out = generate_link_code(int(u["user_id"]))
        return {"ok": True, **out}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "message": "Could not generate code. Try again."})


@router.post("/parent/request-link")
def parent_request_link(payload: dict, authorization: str | None = Header(default=None, alias="Authorization")):
    token = _token_from_header(authorization)
    u = session_user(token) if token else None
    if not u:
        return JSONResponse(status_code=401, content={"ok": False, "message": "Login required"})
    if u.get("role") != "parent":
        return JSONResponse(status_code=403, content={"ok": False, "message": "Only parents can request linking"})
    code = (payload.get("code") or "").strip().upper()
    if not code:
        return JSONResponse(status_code=400, content={"ok": False, "message": "Code required"})
    out = create_link_request(int(u["user_id"]), code)
    if not out.get("ok"):
        return JSONResponse(status_code=400, content=out)
    return out


@router.get("/student/requests")
def student_requests(authorization: str | None = Header(default=None, alias="Authorization")):
    token = _token_from_header(authorization)
    u = session_user(token) if token else None
    if not u:
        return JSONResponse(status_code=401, content={"ok": False, "message": "Login required"})
    if u.get("role") != "student":
        return JSONResponse(status_code=403, content={"ok": False, "message": "Only students can view requests"})
    rows = list_student_requests(int(u["user_id"]))
    return {"ok": True, "requests": rows}


@router.post("/student/requests/{link_id}")
def student_decide(link_id: int, payload: dict, authorization: str | None = Header(default=None, alias="Authorization")):
    token = _token_from_header(authorization)
    u = session_user(token) if token else None
    if not u:
        return JSONResponse(status_code=401, content={"ok": False, "message": "Login required"})
    if u.get("role") != "student":
        return JSONResponse(status_code=403, content={"ok": False, "message": "Only students can decide requests"})
    decision = (payload.get("decision") or "").strip().lower()
    out = decide_request(int(u["user_id"]), int(link_id), decision)
    if not out.get("ok"):
        return JSONResponse(status_code=400, content=out)
    return out


@router.get("/parent/children")
def parent_children(authorization: str | None = Header(default=None, alias="Authorization")):
    token = _token_from_header(authorization)
    u = session_user(token) if token else None
    if not u:
        return JSONResponse(status_code=401, content={"ok": False, "message": "Login required"})
    if u.get("role") != "parent":
        return JSONResponse(status_code=403, content={"ok": False, "message": "Only parents can view children"})
    rows = list_parent_children(int(u["user_id"]))
    return {"ok": True, "children": rows}


@router.get("/parent/dashboard/{student_user_id}")
def parent_dashboard(student_user_id: int, authorization: str | None = Header(default=None, alias="Authorization")):
    token = _token_from_header(authorization)
    u = session_user(token) if token else None
    if not u:
        return JSONResponse(status_code=401, content={"ok": False, "message": "Login required"})
    if u.get("role") != "parent":
        return JSONResponse(status_code=403, content={"ok": False, "message": "Only parents can access dashboard"})
    # verify link active
    children = list_parent_children(int(u["user_id"]))
    allowed = any(int(c.get("student_user_id") or 0) == int(student_user_id) for c in children)
    if not allowed:
        return JSONResponse(status_code=403, content={"ok": False, "message": "Student not linked"})
    summary7 = get_student_summary(int(student_user_id), days=7)
    summary30 = get_student_summary(int(student_user_id), days=30)
    return {"ok": True, "student_user_id": student_user_id, "summary_7d": summary7, "summary_30d": summary30}
