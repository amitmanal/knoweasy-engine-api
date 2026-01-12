"""Analytics + Parent dashboard store (Phase-3 V1)

Tables:
- app_events: generic event log for usage, tests, etc.
- link_codes: student-generated codes for parent linking
- parent_student_links: link relationships + requests

Design goals:
- Additive, no migrations framework required
- Safe CREATE/ALTER IF NOT EXISTS
- Idempotent operations where possible
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import text

# Reuse the central DB engine rather than constructing a new one.
from db import _get_engine as _shared_engine

_ENGINE = None
_READY = False

def _db_url() -> str:
    """Kept for backward compatibility but unused.  The engine is
    now obtained from the shared db module."""
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL not configured")
    return url

def _get_engine():
    """Return the shared SQLAlchemy engine from the central db module.
    This wrapper exists to maintain the local API but delegates
    to db._get_engine(), avoiding creation of multiple engines."""
    return _shared_engine()

def ensure_tables() -> None:
    global _READY
    if _READY:
        return
    eng = _get_engine()
    ddl = [
        # Event log
        """
        CREATE TABLE IF NOT EXISTS app_events (
            id SERIAL PRIMARY KEY,
            user_id INT,
            role TEXT,
            event_type TEXT NOT NULL,
            page TEXT,
            duration_sec INT,
            score FLOAT,
            meta_json TEXT,
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_app_events_user_time
        ON app_events (user_id, occurred_at DESC);
        """,
        # Link codes
        """
        CREATE TABLE IF NOT EXISTS link_codes (
            id SERIAL PRIMARY KEY,
            student_user_id INT NOT NULL,
            code TEXT NOT NULL UNIQUE,
            expires_at TIMESTAMPTZ NOT NULL,
            used BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_link_codes_student
        ON link_codes (student_user_id, created_at DESC);
        """,
        # Parent-student links
        """
        CREATE TABLE IF NOT EXISTS parent_student_links (
            id SERIAL PRIMARY KEY,
            parent_user_id INT NOT NULL,
            student_user_id INT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('pending','active','rejected','revoked')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ,
            UNIQUE(parent_user_id, student_user_id)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_parent_links_parent
        ON parent_student_links (parent_user_id, status);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_parent_links_student
        ON parent_student_links (student_user_id, status);
        """,
    ]
    with eng.begin() as conn:
        for stmt in ddl:
            conn.execute(text(stmt))
    _READY = True

# ----------------------
# Events
# ----------------------
def record_event(
    user_id: Optional[int],
    role: Optional[str],
    event_type: str,
    page: Optional[str] = None,
    duration_sec: Optional[int] = None,
    score: Optional[float] = None,
    meta: Optional[Dict[str, Any]] = None,
    occurred_at: Optional[datetime] = None,
) -> None:
    ensure_tables()
    eng = _get_engine()
    meta_json = None
    if meta is not None:
        # Keep as compact string to avoid extra deps
        import json
        meta_json = json.dumps(meta, ensure_ascii=False)
    ts = occurred_at or datetime.now(timezone.utc)
    with eng.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO app_events (user_id, role, event_type, page, duration_sec, score, meta_json, occurred_at)
                VALUES (:uid, :role, :etype, :page, :dur, :score, :meta, :ts)
            """),
            {
                "uid": user_id,
                "role": role,
                "etype": event_type,
                "page": page,
                "dur": duration_sec,
                "score": score,
                "meta": meta_json,
                "ts": ts,
            },
        )

def get_student_summary(student_user_id: int, days: int = 7) -> Dict[str, Any]:
    ensure_tables()
    eng = _get_engine()
    since = datetime.now(timezone.utc) - timedelta(days=days)
    with eng.begin() as conn:
        # total duration
        row = conn.execute(
            text("""
                SELECT
                    COALESCE(SUM(COALESCE(duration_sec,0)),0) AS total_sec,
                    COALESCE(SUM(CASE WHEN event_type='solve' THEN 1 ELSE 0 END),0) AS solves,
                    COALESCE(SUM(CASE WHEN event_type='test_attempt' THEN 1 ELSE 0 END),0) AS tests,
                    COALESCE(AVG(CASE WHEN event_type='test_attempt' THEN score ELSE NULL END), NULL) AS avg_score
                FROM app_events
                WHERE user_id=:uid AND occurred_at >= :since
            """),
            {"uid": student_user_id, "since": since},
        ).mappings().first()
    total_min = int(round((row["total_sec"] or 0) / 60.0))
    avg_score = row["avg_score"]
    if avg_score is not None:
        avg_score = float(avg_score)
    return {
        "days": days,
        "total_minutes": total_min,
        "solves": int(row["solves"] or 0),
        "tests": int(row["tests"] or 0),
        "avg_score": avg_score,
    }

# ----------------------
# Linking
# ----------------------
def generate_link_code(student_user_id: int, ttl_minutes: int = 30) -> Dict[str, Any]:
    ensure_tables()
    eng = _get_engine()
    # generate a 6-char code (A-Z0-9) that's easy to type
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(12):
        code = "".join(secrets.choice(alphabet) for _ in range(6))
        expires = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
        try:
            with eng.begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO link_codes (student_user_id, code, expires_at, used)
                        VALUES (:sid, :code, :exp, FALSE)
                    """),
                    {"sid": student_user_id, "code": code, "exp": expires},
                )
            return {"code": code, "expires_at": expires.isoformat()}
        except Exception:
            continue
    raise RuntimeError("Could not generate link code. Please try again.")

def _consume_code(code: str) -> Optional[int]:
    """Mark code as used and return student_user_id if valid."""
    ensure_tables()
    eng = _get_engine()
    now = datetime.now(timezone.utc)
    with eng.begin() as conn:
        row = conn.execute(
            text("""
                SELECT id, student_user_id, expires_at, used
                FROM link_codes
                WHERE code=:code
                LIMIT 1
            """),
            {"code": code},
        ).mappings().first()
        if not row:
            return None
        if row["used"]:
            return None
        if row["expires_at"] and row["expires_at"] < now:
            return None
        # mark used
        conn.execute(
            text("""
                UPDATE link_codes SET used=TRUE
                WHERE id=:id
            """),
            {"id": row["id"]},
        )
        return int(row["student_user_id"])

def create_link_request(parent_user_id: int, code: str) -> Dict[str, Any]:
    ensure_tables()
    student_id = _consume_code(code.strip().upper())
    if not student_id:
        return {"ok": False, "message": "Invalid or expired code. Ask the student to generate a new code."}
    eng = _get_engine()
    now = datetime.now(timezone.utc)
    with eng.begin() as conn:
        # Upsert request
        existing = conn.execute(
            text("""
                SELECT id, status FROM parent_student_links
                WHERE parent_user_id=:pid AND student_user_id=:sid
            """),
            {"pid": parent_user_id, "sid": student_id},
        ).mappings().first()
        if existing:
            # If already active, keep it
            if existing["status"] == "active":
                return {"ok": True, "status": "active", "student_user_id": student_id, "link_id": int(existing["id"])}
            # Reset to pending
            conn.execute(
                text("""
                    UPDATE parent_student_links
                    SET status='pending', updated_at=:now
                    WHERE id=:id
                """),
                {"id": existing["id"], "now": now},
            )
            link_id = int(existing["id"])
        else:
            row = conn.execute(
                text("""
                    INSERT INTO parent_student_links (parent_user_id, student_user_id, status, updated_at)
                    VALUES (:pid, :sid, 'pending', :now)
                    RETURNING id
                """),
                {"pid": parent_user_id, "sid": student_id, "now": now},
            ).first()
            link_id = int(row[0]) if row else 0
    return {"ok": True, "status": "pending", "student_user_id": student_id, "link_id": link_id}

def list_student_requests(student_user_id: int) -> List[Dict[str, Any]]:
    ensure_tables()
    eng = _get_engine()
    with eng.begin() as conn:
        rows = conn.execute(
            text("""
                SELECT l.id, l.parent_user_id, u.email AS parent_email, l.status, l.created_at, l.updated_at
                FROM parent_student_links l
                LEFT JOIN users u ON u.id = l.parent_user_id
                WHERE l.student_user_id=:sid AND l.status='pending'
                ORDER BY l.created_at DESC
            """),
            {"sid": student_user_id},
        ).mappings().all()
    return [dict(r) for r in rows]

def decide_request(student_user_id: int, link_id: int, decision: str) -> Dict[str, Any]:
    ensure_tables()
    eng = _get_engine()
    now = datetime.now(timezone.utc)
    decision = decision.lower().strip()
    if decision not in ("approve", "reject"):
        return {"ok": False, "message": "Invalid decision."}
    new_status = "active" if decision == "approve" else "rejected"
    with eng.begin() as conn:
        row = conn.execute(
            text("""
                SELECT id, parent_user_id, student_user_id, status
                FROM parent_student_links
                WHERE id=:id
            """),
            {"id": link_id},
        ).mappings().first()
        if not row or int(row["student_user_id"]) != int(student_user_id):
            return {"ok": False, "message": "Request not found."}
        if row["status"] != "pending":
            return {"ok": True, "status": row["status"]}
        conn.execute(
            text("""
                UPDATE parent_student_links
                SET status=:st, updated_at=:now
                WHERE id=:id
            """),
            {"st": new_status, "now": now, "id": link_id},
        )
    return {"ok": True, "status": new_status}

def list_parent_children(parent_user_id: int) -> List[Dict[str, Any]]:
    ensure_tables()
    eng = _get_engine()
    with eng.begin() as conn:
        rows = conn.execute(
            text("""
                SELECT l.id AS link_id, l.student_user_id, u.email AS student_email, u.full_name, u.board, u.class_level, l.status
                FROM parent_student_links l
                LEFT JOIN users u ON u.id = l.student_user_id
                WHERE l.parent_user_id=:pid AND l.status='active'
                ORDER BY l.updated_at DESC NULLS LAST, l.created_at DESC
            """),
            {"pid": parent_user_id},
        ).mappings().all()
    return [dict(r) for r in rows]
