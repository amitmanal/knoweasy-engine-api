"""Phase-1 data layer (Parent-Student linking + basic analytics).

This module adds **minimal, stable** persistence needed by the Phase-1 frontend:

Endpoints supported by this store (via phase1_router.py):
- POST /student/profile
- POST /student/parent-code
- POST /parent/link
- GET  /parent/students
- GET  /parent/analytics/summary
- POST /events/track

Notes
-----
* We intentionally keep tables small and flexible so we can evolve without
  migrations becoming painful.
* Analytics are derived from lightweight event tracking (events table).
* Parents can only access students that are explicitly linked.
"""

from __future__ import annotations

import os
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    and_,
    create_engine,
    func,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


# -------------------------
# Engine / metadata
# -------------------------


_ENGINE: Optional[Engine] = None


def _get_engine() -> Engine:
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set")

    connect_args: Dict[str, Any] = {}
    if db_url.startswith("postgres"):
        # Render + managed Postgres commonly require SSL
        if os.getenv("DB_SSLMODE"):
            connect_args["sslmode"] = os.getenv("DB_SSLMODE")

    _ENGINE = create_engine(db_url, pool_pre_ping=True, connect_args=connect_args)
    return _ENGINE


metadata = MetaData()


student_profiles = Table(
    "student_profiles",
    metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("full_name", Text, nullable=True),
    Column("class", Integer, nullable=True),  # effective class number, or 11 for 11_12 bundle
    Column("class_group", String(16), nullable=True),  # "5".."10" or "11_12"
    Column("board", String(64), nullable=True),  # cbse/maharashtra/icse/...
    Column("target_exams", JSON, nullable=True),  # list[str]
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
)


parent_codes = Table(
    "parent_codes",
    metadata,
    Column("code", String(16), primary_key=True),
    Column("student_user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("used_at", DateTime(timezone=True), nullable=True),
    Column("used_by_parent_user_id", Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
)


parent_links = Table(
    "parent_links",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("parent_user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("student_user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    UniqueConstraint("parent_user_id", "student_user_id", name="uq_parent_student"),
)


events = Table(
    "events",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("event_type", String(64), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("duration_sec", Integer, nullable=True),
    Column("value_num", Integer, nullable=True),  # e.g., score percent
    Column("meta", JSON, nullable=True),
)


def ensure_tables() -> None:
    """Create Phase-1 tables if they don't exist."""
    engine = _get_engine()
    metadata.create_all(engine)


# -------------------------
# Helpers
# -------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_parent_code(prefix: str = "KNE-") -> str:
    # 6 chars gives ~2B combos with uppercase+digits; sufficient for 15-min, one-time codes.
    alphabet = string.ascii_uppercase + string.digits
    token = "".join(secrets.choice(alphabet) for _ in range(6))
    return f"{prefix}{token}"


def _sanitize_board(board: Optional[str]) -> Optional[str]:
    if not board:
        return None
    b = str(board).strip().lower()
    return b or None


def _normalize_class_group(cls: Optional[int], class_group: Optional[str]) -> Tuple[Optional[int], Optional[str]]:
    """Return (class_int, class_group_str).

    - For 5..10 we keep class_int=5..10 and class_group="5".."10".
    - For the bundled 11–12 subscription we store class_group="11_12" and class_int=11 (effective).
    """
    if class_group:
        cg = str(class_group).strip().lower().replace("-", "_")
        if cg in ("11_12", "11+12", "11 12", "11_12 "):
            return 11, "11_12"
        if cg.isdigit() and 5 <= int(cg) <= 10:
            return int(cg), cg

    if cls is None:
        return None, None
    try:
        c = int(cls)
    except Exception:
        return None, None

    if 5 <= c <= 10:
        return c, str(c)
    if c in (11, 12):
        return 11, "11_12"
    return c, str(c)


# -------------------------
# Student profile
# -------------------------


def upsert_student_profile(
    user_id: int,
    full_name: Optional[str],
    cls: Optional[int],
    board: Optional[str],
    target_exams: Optional[List[str]],
    class_group: Optional[str] = None,
) -> Dict[str, Any]:
    ensure_tables()
    engine = _get_engine()

    board_n = _sanitize_board(board)
    class_int, class_group_n = _normalize_class_group(cls, class_group)

    # For classes 5-10, ignore target exams (Phase-1 product decision)
    if class_int is not None and class_int < 11:
        target_exams = []
    target_exams = target_exams or []

    payload = {
        "user_id": user_id,
        "full_name": (full_name or None),
        "class": class_int,
        "class_group": class_group_n,
        "board": board_n,
        "target_exams": target_exams,
        "updated_at": _utcnow(),
    }

    with engine.begin() as conn:
        existing = conn.execute(select(student_profiles.c.user_id).where(student_profiles.c.user_id == user_id)).first()
        if existing:
            conn.execute(
                student_profiles.update().where(student_profiles.c.user_id == user_id).values(**payload)
            )
        else:
            conn.execute(student_profiles.insert().values(**payload))

    return get_student_profile(user_id) or payload


def get_student_profile(user_id: int) -> Optional[Dict[str, Any]]:
    ensure_tables()
    engine = _get_engine()
    with engine.begin() as conn:
        row = conn.execute(select(student_profiles).where(student_profiles.c.user_id == user_id)).mappings().first()
        return dict(row) if row else None


# -------------------------
# Parent code + linking
# -------------------------


def create_parent_code(student_user_id: int, ttl_seconds: int = 900) -> Dict[str, Any]:
    ensure_tables()
    engine = _get_engine()

    now = _utcnow()
    expires = now + timedelta(seconds=ttl_seconds)

    # Create a fresh code. We don't try to reuse; codes are short-lived.
    code = _make_parent_code()
    with engine.begin() as conn:
        # Extremely low collision chance, but handle gracefully.
        for _ in range(5):
            exists = conn.execute(select(parent_codes.c.code).where(parent_codes.c.code == code)).first()
            if not exists:
                break
            code = _make_parent_code()
        conn.execute(
            parent_codes.insert().values(
                code=code,
                student_user_id=student_user_id,
                expires_at=expires,
                created_at=now,
            )
        )

    return {"code": code, "expires_at": expires.isoformat(), "expires_in_seconds": ttl_seconds}


def link_parent_with_code(parent_user_id: int, code: str) -> Tuple[bool, str, Optional[int]]:
    """Consume a parent code and create a link.

    Returns (ok, message, student_user_id)
    """
    ensure_tables()
    engine = _get_engine()

    code_n = (code or "").strip().upper()
    if not code_n:
        return False, "Invalid code.", None

    now = _utcnow()
    with engine.begin() as conn:
        row = conn.execute(
            select(parent_codes).where(parent_codes.c.code == code_n)
        ).mappings().first()
        if not row:
            return False, "Code not found. Ask your child to generate a new one.", None
        if row.get("used_at") is not None:
            return False, "This code was already used. Ask your child to generate a new one.", None
        expires_at = row.get("expires_at")
        if expires_at and isinstance(expires_at, datetime):
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < now:
                return False, "This code expired. Ask your child to generate a new one.", None

        student_user_id = int(row["student_user_id"])
        if student_user_id == parent_user_id:
            return False, "You cannot link to yourself.", None

        # Mark code used (one-time)
        conn.execute(
            parent_codes.update()
            .where(parent_codes.c.code == code_n)
            .values(used_at=now, used_by_parent_user_id=parent_user_id)
        )

        # Create link (idempotent)
        existing = conn.execute(
            select(parent_links.c.id).where(
                and_(
                    parent_links.c.parent_user_id == parent_user_id,
                    parent_links.c.student_user_id == student_user_id,
                )
            )
        ).first()
        if not existing:
            conn.execute(
                parent_links.insert().values(
                    parent_user_id=parent_user_id,
                    student_user_id=student_user_id,
                    created_at=now,
                )
            )

    return True, "Linked successfully.", student_user_id


def is_parent_linked(parent_user_id: int, student_user_id: int) -> bool:
    ensure_tables()
    engine = _get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            select(parent_links.c.id).where(
                and_(
                    parent_links.c.parent_user_id == parent_user_id,
                    parent_links.c.student_user_id == student_user_id,
                )
            )
        ).first()
        return bool(row)


def list_parent_students(parent_user_id: int) -> List[Dict[str, Any]]:
    ensure_tables()
    engine = _get_engine()

    with engine.begin() as conn:
        q = (
            select(
                parent_links.c.student_user_id,
                student_profiles.c.full_name,
                student_profiles.c.board,
                student_profiles.c["class"],
                student_profiles.c.class_group,
                student_profiles.c.target_exams,
                student_profiles.c.updated_at,
            )
            .select_from(
                parent_links.outerjoin(
                    student_profiles,
                    student_profiles.c.user_id == parent_links.c.student_user_id,
                )
            )
            .where(parent_links.c.parent_user_id == parent_user_id)
            .order_by(parent_links.c.created_at.desc())
        )
        rows = conn.execute(q).mappings().all()

    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "student_user_id": int(r["student_user_id"]),
                "full_name": r.get("full_name") or "Student",
                "board": r.get("board"),
                "class": r.get("class"),
                "class_group": r.get("class_group"),
                "target_exams": r.get("target_exams") or [],
                "updated_at": (r.get("updated_at").isoformat() if r.get("updated_at") else None),
            }
        )
    return out


# -------------------------
# Event tracking + analytics
# -------------------------


def track_event(
    user_id: int,
    event_type: str,
    meta: Optional[Dict[str, Any]] = None,
    duration_sec: Optional[int] = None,
    value_num: Optional[int] = None,
) -> Dict[str, Any]:
    ensure_tables()
    engine = _get_engine()

    et = (event_type or "").strip()[:64]
    if not et:
        raise ValueError("event_type is required")

    payload = {
        "user_id": int(user_id),
        "event_type": et,
        "created_at": _utcnow(),
        "duration_sec": int(duration_sec) if duration_sec is not None else None,
        "value_num": int(value_num) if value_num is not None else None,
        "meta": meta or {},
    }
    with engine.begin() as conn:
        conn.execute(events.insert().values(**payload))
    return {"ok": True}


def analytics_summary(parent_user_id: int, student_user_id: int) -> Dict[str, Any]:
    """Return read-only analytics summary for a linked student."""
    ensure_tables()
    engine = _get_engine()

    # Access control is enforced by router before calling this.
    now = _utcnow()
    since_7d = now - timedelta(days=7)
    since_30d = now - timedelta(days=30)

    with engine.begin() as conn:
        # Time spent (we accept any event with duration_sec; product can standardize later)
        time_7d = conn.execute(
            select(func.coalesce(func.sum(events.c.duration_sec), 0)).where(
                and_(events.c.user_id == student_user_id, events.c.created_at >= since_7d)
            )
        ).scalar_one()

        active_days_7d = conn.execute(
            select(func.count(func.distinct(func.date(events.c.created_at)))).where(
                and_(events.c.user_id == student_user_id, events.c.created_at >= since_7d)
            )
        ).scalar_one()

        # Tests: we treat event_type='test_submitted' with value_num as score %.
        tests_30d = conn.execute(
            select(func.count()).where(
                and_(events.c.user_id == student_user_id, events.c.created_at >= since_30d, events.c.event_type == "test_submitted")
            )
        ).scalar_one()

        avg_score_30d = conn.execute(
            select(func.avg(events.c.value_num)).where(
                and_(events.c.user_id == student_user_id, events.c.created_at >= since_30d, events.c.event_type == "test_submitted")
            )
        ).scalar()

        last_active = conn.execute(
            select(func.max(events.c.created_at)).where(events.c.user_id == student_user_id)
        ).scalar()

        recent = conn.execute(
            select(events.c.event_type, events.c.created_at, events.c.meta)
            .where(events.c.user_id == student_user_id)
            .order_by(events.c.created_at.desc())
            .limit(25)
        ).mappings().all()

    # Minimal strengths/weaknesses placeholder: derived from meta.subject + value_num score.
    # This gives a "Silicon Valley" feel without needing a full test engine yet.
    subj_scores: Dict[str, List[int]] = {}
    for r in recent:
        if r.get("event_type") != "test_submitted":
            continue
        meta = r.get("meta") or {}
        subj = meta.get("subject")
        if not subj:
            continue
        try:
            score = int(meta.get("score") or 0)
        except Exception:
            score = None
        if score is None:
            continue
        subj_scores.setdefault(str(subj), []).append(score)

    subj_avgs = [
        {"subject": k, "score": round(sum(v) / max(len(v), 1), 1)}
        for k, v in subj_scores.items()
        if v
    ]
    subj_avgs.sort(key=lambda x: x["score"], reverse=True)

    strengths = subj_avgs[:3]
    weaknesses = list(reversed(subj_avgs[-3:])) if len(subj_avgs) >= 3 else []

    return {
        "time_spent_minutes_7d": int(round((time_7d or 0) / 60)),
        "active_days_7d": int(active_days_7d or 0),
        "tests_attempted_30d": int(tests_30d or 0),
        "avg_score_30d": float(avg_score_30d) if avg_score_30d is not None else None,
        "last_active_at": (last_active.isoformat() if last_active else None),
        "subject_strengths": strengths,
        "subject_weaknesses": weaknesses,
        "recent_activity": [
            {
                "event_type": r.get("event_type"),
                "created_at": (r.get("created_at").isoformat() if r.get("created_at") else None),
                "meta": r.get("meta") or {},
            }
            for r in recent
        ],
    }
