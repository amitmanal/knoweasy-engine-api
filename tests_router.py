"""tests_router.py - Phase-2 Test Engine API routes (isolated).

All endpoints require Authorization: Bearer <token>

Role rules:
- Student: can list/start/submit/view own history
- Parent: read-only analytics for linked students
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from auth_store import session_user
import phase1_store
import tests_store


logger = logging.getLogger("knoweasy.tests")
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


def _uid(u: Dict[str, Any]) -> int:
    raw = u.get("user_id") if isinstance(u, dict) else None
    if raw is None:
        raw = u.get("id") if isinstance(u, dict) else None
    if raw is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        return int(raw)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")


def require_role(role: str):
    def _dep(u: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        if (u.get("role") or "").lower() != role:
            raise HTTPException(status_code=403, detail=f"Requires role: {role}")
        return u

    return _dep


@router.get("/tests/catalog")
def tests_catalog(
    cls: Optional[int] = Query(default=None),
    board: Optional[str] = Query(default=None),
    subject: Optional[str] = Query(default=None),
    chapter: Optional[str] = Query(default=None),
    u: Dict[str, Any] = Depends(require_role("student")),
):
    filters = {
        "cls": cls,
        "board": board,
        "subject_slug": subject,
        "chapter_slug": chapter,
    }
    items = tests_store.list_tests_catalog(filters)
    return {"ok": True, "tests": items}


@router.get("/tests/{test_id}")
def test_detail(test_id: int, u: Dict[str, Any] = Depends(require_role("student"))):
    t = tests_store.get_test_public(int(test_id))
    if not t:
        raise HTTPException(status_code=404, detail="Test not found")
    return {"ok": True, "test": t}


@router.post("/tests/{test_id}/start")
def test_start(test_id: int, u: Dict[str, Any] = Depends(require_role("student"))):
    ok, msg, attempt = tests_store.start_attempt(_uid(u), int(test_id))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "attempt": attempt}


@router.post("/tests/attempts/{attempt_id}/submit")
def test_submit(attempt_id: int, payload: Dict[str, Any], u: Dict[str, Any] = Depends(require_role("student"))):
    ok, msg, result = tests_store.submit_attempt(_uid(u), int(attempt_id), payload)
    if not ok:
        if msg.lower() == "forbidden":
            raise HTTPException(status_code=403, detail="Forbidden")
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "status": msg, "result": result}


@router.get("/tests/me/history")
def my_history(u: Dict[str, Any] = Depends(require_role("student"))):
    items = tests_store.list_user_history(_uid(u), limit=50)
    return {"ok": True, "history": items}


@router.get("/tests/me/attempts/{attempt_id}")
def my_attempt(attempt_id: int, u: Dict[str, Any] = Depends(require_role("student"))):
    result = tests_store.get_attempt_result(_uid(u), int(attempt_id))
    if not result:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return {"ok": True, "result": result}


# -------------------------
# Parent (read-only)
# -------------------------


@router.get("/parent/tests/summary")
def parent_tests_summary(student_id: int, u: Dict[str, Any] = Depends(require_role("parent"))):
    parent_id = _uid(u)
    if not phase1_store.is_parent_linked(parent_id, int(student_id)):
        raise HTTPException(status_code=403, detail="Forbidden")
    summary = tests_store.parent_summary(int(student_id))
    return {"ok": True, "summary": summary}


@router.get("/parent/tests/history")
def parent_tests_history(student_id: int, u: Dict[str, Any] = Depends(require_role("parent"))):
    parent_id = _uid(u)
    if not phase1_store.is_parent_linked(parent_id, int(student_id)):
        raise HTTPException(status_code=403, detail="Forbidden")
    items = tests_store.list_user_history(int(student_id), limit=50)
    return {"ok": True, "history": items}
