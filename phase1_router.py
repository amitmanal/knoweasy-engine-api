"""Phase-1 API routes for KnowEasy.

Implements endpoints used by the Phase-1 frontend ZIP (parent dashboard + student profile).

Auth
----
All endpoints require the existing session token via:
  Authorization: Bearer <token>

Role rules:
- /student/* -> role must be "student"
- /parent/*  -> role must be "parent"
Parents are read-only and may only access linked students.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from auth_store import session_user

import phase1_store


router = APIRouter()


def _token_from_auth_header(authorization: Optional[str]) -> str:
    if not authorization:
        return ""
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return authorization.strip()


def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    token = _token_from_auth_header(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    u = session_user(token)
    if not u:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return u


def require_role(role: str):
    def _dep(u: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        if (u.get("role") or "").lower() != role:
            raise HTTPException(status_code=403, detail=f"Requires role: {role}")
        return u

    return _dep


@router.post("/student/profile")
def student_profile(payload: Dict[str, Any], u: Dict[str, Any] = Depends(require_role("student"))):
    """Upsert student profile.

    Expected payload from frontend:
    { full_name, class, board, target_exams }
    """
    full_name = payload.get("full_name")
    cls = payload.get("class")
    board = payload.get("board")
    target_exams = payload.get("target_exams")
    class_group = payload.get("class_group")

    prof = phase1_store.upsert_student_profile(
        user_id=int(u["id"]),
        full_name=full_name,
        cls=cls,
        board=board,
        target_exams=target_exams,
        class_group=class_group,
    )
    return {"ok": True, "profile": prof}


@router.post("/student/parent-code")
def generate_parent_code(u: Dict[str, Any] = Depends(require_role("student"))):
    data = phase1_store.create_parent_code(student_user_id=int(u["id"]), ttl_seconds=900)
    return {"ok": True, **data}


@router.post("/parent/link")
def parent_link(payload: Dict[str, Any], u: Dict[str, Any] = Depends(require_role("parent"))):
    code = payload.get("code") or ""
    ok, message, student_user_id = phase1_store.link_parent_with_code(parent_user_id=int(u["id"]), code=code)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True, "message": message, "student_user_id": student_user_id}


@router.get("/parent/students")
def parent_students(u: Dict[str, Any] = Depends(require_role("parent"))):
    students = phase1_store.list_parent_students(parent_user_id=int(u["id"]))
    return {"ok": True, "students": students}


@router.get("/parent/analytics/summary")
def parent_analytics_summary(student_user_id: int, u: Dict[str, Any] = Depends(require_role("parent"))):
    if not phase1_store.is_parent_linked(parent_user_id=int(u["id"]), student_user_id=int(student_user_id)):
        raise HTTPException(status_code=403, detail="Not linked to this student")
    summary = phase1_store.analytics_summary(parent_user_id=int(u["id"]), student_user_id=int(student_user_id))
    return {"ok": True, "summary": summary}


@router.post("/events/track")
def events_track(payload: Dict[str, Any], u: Dict[str, Any] = Depends(get_current_user)):
    """Lightweight event tracking.

    Payload from frontend:
    { event_type: str, duration_sec?: number, value_num?: number, meta?: {...} }
    """
    try:
        event_type = payload.get("event_type")
        meta = payload.get("meta")
        duration_sec = payload.get("duration_sec")
        value_num = payload.get("value_num")
        phase1_store.track_event(
            user_id=int(u["id"]),
            event_type=event_type,
            meta=meta,
            duration_sec=duration_sec,
            value_num=value_num,
        )
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
