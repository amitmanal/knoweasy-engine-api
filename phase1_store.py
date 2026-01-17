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
import json  # needed for Redis JSON serialization
import logging
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
    literal,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

import redis_store

logger = logging.getLogger(__name__)


# -------------------------
# Engine / metadata
# -------------------------


_ENGINE: Optional[Engine] = None

# -------------------------
# SQLAlchemy metadata + tables (Phase-1 minimal schema)
# -------------------------

metadata = MetaData()

student_profiles = Table(
    "student_profiles",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", BigInteger, nullable=False, unique=True, index=True),
    Column("full_name", String(200), nullable=True),
    Column("cls", Integer, nullable=True),
    Column("board", String(100), nullable=True),
    Column("target_exams_json", Text, nullable=False, default="[]"),
    Column("class_group", String(20), nullable=True),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

parent_codes = Table(
    "parent_codes",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("code", String(24), nullable=False, unique=True, index=True),
    Column("student_user_id", BigInteger, nullable=False, index=True),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("used_at", DateTime(timezone=True), nullable=True),
    Column("used_by_parent_user_id", BigInteger, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

parent_links = Table(
    "parent_links",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("parent_user_id", BigInteger, nullable=False, index=True),
    Column("student_user_id", BigInteger, nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

events = Table(
    "events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", BigInteger, nullable=False, index=True),
    Column("event_type", String(64), nullable=False, index=True),
    Column("meta_json", Text, nullable=False, default="{}"),
    Column("duration_sec", Integer, nullable=True),
    Column("value_num", Integer, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)



def _clean_sslmode(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip().strip('"').strip("'").strip()
    return v or None


def _get_engine() -> Optional[Engine]:
    """Return a SQLAlchemy engine if Postgres is configured; otherwise None.

    Phase-1 stability rule:
    - Missing/broken DB must NOT crash the API.
    - Endpoints fall back to Redis for core Phase-1 flows.
    """
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.warning("DATABASE_URL is not set; Phase-1 store will use Redis fallback.")
        return None

    connect_args: Dict[str, Any] = {}
    # If sslmode isn't in URL, allow DB_SSLMODE env (sanitized)
    if "sslmode=" not in db_url:
        sslmode = _clean_sslmode(os.getenv("DB_SSLMODE"))
        if sslmode:
            connect_args["sslmode"] = sslmode

    try:
        _ENGINE = create_engine(db_url, pool_pre_ping=True, connect_args=connect_args)
        return _ENGINE
    except Exception as e:
        logger.exception("Failed to create DB engine; Phase-1 store will use Redis fallback. Error: %s", e)
        _ENGINE = None
        return None

def ensure_tables() -> bool:
    """Ensure Phase-1 tables exist when DB is available.

    Returns True if DB tables were ensured, False if DB is unavailable.
    """
    engine = _get_engine()
    if engine is None:
        return False
    try:
        metadata.create_all(engine)
        return True
    except Exception as e:
        logger.exception("Phase-1 ensure_tables failed; continuing with Redis fallback. Error: %s", e)
        return False


# -------------------------
# Redis fallback (Phase-1 stability)
# -------------------------

def _r():
    return redis_store.get_redis()

def _redis_setex(key: str, ttl_seconds: int, value: Dict[str, Any]) -> bool:
    return redis_store.setex_json(key, ttl_seconds, value)

def _redis_get(key: str) -> Optional[Dict[str, Any]]:
    return redis_store.get_json(key)

def _redis_del(key: str) -> None:
    r = _r()
    if not r:
        return
    try:
        r.delete(key)
    except Exception:
        pass

def _redis_get_int(key: str) -> int:
    r = _r()
    if not r:
        return 0
    try:
        v = r.get(key)
        if v is None:
            return 0
        return int(v)
    except Exception:
        return 0

def _redis_incr(key: str, ttl_seconds: int) -> int:
    v = redis_store.incr_with_ttl(key, ttl_seconds)
    return int(v or 0)

def _redis_links_key(parent_user_id: int) -> str:
    return f"parent_links:{parent_user_id}"

# -------------------------
# Parent session helpers (Phase-1 persistent parent dashboard)
#
# We implement a lightweight parent session mechanism. When a parent enters a
# one-time link code, we return a long‑lived session token tied to a single
# student. This token is stored in Redis (fallback when DB is unavailable)
# with a TTL of 365 days. There is intentionally no parent user_id involved,
# making the parent dashboard read‑only and privacy‑safe.

def _redis_parent_session_key(token: str) -> str:
    """Return the Redis key for a parent session token."""
    return f"parent_session:{token}"

def create_parent_session(student_user_id: int, ttl_days: int = 365) -> Dict[str, Any]:
    """Create a new parent session for the given student.

    Returns a dict with the session token and expiry information. The session
    token is stored in Redis with a TTL so parents can reopen the dashboard
    across devices without linking again. We intentionally do not persist
    sessions in Postgres for Phase‑1 stability; if the DB is configured we
    still prefer Redis because it avoids migrations and potential 500 errors.
    """
    now = _utcnow()
    expires = now + timedelta(days=ttl_days)
    # Use a URL‑safe token; 32 bytes → ~43 characters. This is sufficient for
    # unpredictable tokens that are hard to guess.
    token = secrets.token_urlsafe(32)
    rkey = _redis_parent_session_key(token)
    # Store session payload. Use isoformat() for timestamps so values are JSON
    # serializable and human‑readable.
    payload = {
        "token": token,
        "student_user_id": int(student_user_id),
        "created_at": now.isoformat(),
        "expires_at": expires.isoformat(),
    }
    # TTL in seconds (365 days) – ensure sessions self‑expire.
    ttl_seconds = int(ttl_days * 24 * 3600)
    _redis_setex(rkey, ttl_seconds, payload)
    import json

    def _parse_meta(v):
        """Parse event metadata stored as JSON string in `meta_json`."""
        if v is None:
            return {}
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            try:
                return json.loads(v) or {}
            except Exception:
                return {}
        return {}

    # Build recent activity (safe JSON parse).
    recent_activity = []
    for r in recent:
        meta_raw = r.get("meta_json")
        if isinstance(meta_raw, str):
            try:
                import json
                meta = json.loads(meta_raw) or {}
            except Exception:
                meta = {}
        elif isinstance(meta_raw, dict):
            meta = meta_raw
        else:
            meta = {}
        recent_activity.append({
            "event_type": r.get("event_type"),
            "created_at": (r.get("created_at").isoformat() if r.get("created_at") else None),
            "meta": meta,
        })

    return {
        "parent_session": token,
        "student_user_id": int(student_user_id),
        "expires_at": expires.isoformat(),
        "expires_in_days": ttl_days,
    }

def get_parent_session(token: str) -> Optional[Dict[str, Any]]:
    """Return the parent session payload if valid and not expired.

    If the session does not exist or is expired, returns None. Expired
    sessions are automatically cleaned up by Redis via TTL so we simply
    attempt to read the record.
    """
    token_n = (token or "").strip()
    if not token_n:
        return None
    rkey = _redis_parent_session_key(token_n)
    data = _redis_get(rkey)
    if not data:
        return None
    # Parse expiry string into datetime for validation. If parsing fails we
    # assume expired to err on the side of safety.
    try:
        expires_at_str = data.get("expires_at")
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str)
            if expires_at.tzinfo is None:
                # assume UTC when missing tzinfo
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < _utcnow():
                # expired – remove and return None
                try:
                    _redis_del(rkey)
                except Exception:
                    pass
                return None
    except Exception:
        # If the payload is malformed, remove it for safety
        try:
            _redis_del(rkey)
        except Exception:
            pass
        return None
    return data

def claim_parent_code(code: str) -> Optional[int]:
    """Consume a one‑time parent link code and return the associated student ID.

    This wraps the existing link_parent_with_code() helper by passing a
    dummy parent_user_id=0. It marks the code as used (removing it from
    Redis) and returns the student_user_id on success. If the code is
    invalid, expired or already used, returns None.
    """
    try:
        ok, _msg, sid = link_parent_with_code(parent_user_id=0, code=code)
        if ok and sid:
            return int(sid)
        return None
    except Exception:
        # Never raise exceptions to callers; treat as invalid.
        return None

def _redis_student_profile_key(user_id: int) -> str:
    return f"student_profile:{user_id}"

def _redis_parent_code_key(code: str) -> str:
    return f"parent_code:{code}"

def _redis_get_linked_students(parent_user_id: int) -> List[int]:
    r = _r()
    if not r:
        return []
    key = _redis_links_key(parent_user_id)
    try:
        raw = r.get(key)
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, list):
            return [int(x) for x in data]
        return []
    except Exception:
        return []

def _redis_set_linked_students(parent_user_id: int, student_ids: List[int]) -> None:
    r = _r()
    if not r:
        return
    key = _redis_links_key(parent_user_id)
    try:
        # Keep long TTL (1 year) but still self-heals
        r.setex(key, 31536000, json.dumps(sorted(set(student_ids))))
    except Exception:
        pass

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
    # Normalize inputs first (works for both DB + Redis)
    board_n = _sanitize_board(board)
    class_int, class_group_n = _normalize_class_group(cls, class_group)

    # For classes 5-10, ignore target exams (Phase-1 product decision)
    if class_int is not None and class_int < 11:
        target_exams = None

    now = _utcnow()
    payload = {
        "user_id": int(user_id),
        "full_name": full_name,
        "cls": class_int,
        "board": board_n,
        "target_exams_json": json.dumps(target_exams or []),
        "class_group": class_group_n,
        "updated_at": now,
    }

    engine = _get_engine()
    if engine is None:
        prof = {
            "user_id": int(user_id),
            "full_name": full_name,
            "class": class_int,
            "board": board_n,
            "target_exams": target_exams or [],
            "class_group": class_group_n,
            "updated_at": now.isoformat(),
        }
        _redis_setex(_redis_student_profile_key(user_id), 31536000, prof)
        return prof

    ensure_tables()

    def _parse_meta(v):
        """Parse event metadata stored as JSON string in `meta_json`."""
        if v is None:
            return {}
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            try:
                return json.loads(v) or {}
            except Exception:
                return {}
        return {}

    with engine.begin() as conn:
        existing = conn.execute(select(student_profiles.c.user_id).where(student_profiles.c.user_id == user_id)).first()
        if existing:
            conn.execute(student_profiles.update().where(student_profiles.c.user_id == user_id).values(**payload))
        else:
            conn.execute(student_profiles.insert().values(**payload))

    prof = get_student_profile(user_id) or payload
    # Normalize key names for frontend convenience
    if "cls" in prof and "class" not in prof:
        prof["class"] = prof.get("cls")
    return prof

def get_student_profile(user_id: int) -> Optional[Dict[str, Any]]:
    engine = _get_engine()
    if engine is None:
        prof = _redis_get(_redis_student_profile_key(user_id))
        if not prof:
            return None
        # ensure shape
        if "cls" not in prof and "class" in prof:
            prof["cls"] = prof.get("class")
        return prof

    ensure_tables()
    with engine.begin() as conn:
        row = conn.execute(select(student_profiles).where(student_profiles.c.user_id == user_id)).mappings().first()
        if not row:
            return None
        prof = dict(row)
        try:
            prof["target_exams"] = json.loads(prof.get("target_exams_json") or "[]")
        except Exception:
            prof["target_exams"] = []
        if "cls" in prof and "class" not in prof:
            prof["class"] = prof.get("cls")
        return prof

def create_parent_code(student_user_id: int, ttl_seconds: int = 900) -> Dict[str, Any]:
    now = _utcnow()
    expires = now + timedelta(seconds=ttl_seconds)

    engine = _get_engine()
    if engine is None:
        # Redis fallback: store parent code with TTL
        code = _make_parent_code()
        rkey = _redis_parent_code_key(code)
        # avoid collisions
        for _ in range(5):
            if not _redis_get(rkey):
                break
            code = _make_parent_code()
            rkey = _redis_parent_code_key(code)
        _redis_setex(
            rkey,
            int(ttl_seconds),
            {
                "code": code,
                "student_user_id": int(student_user_id),
                "created_at": now.isoformat(),
                "expires_at": expires.isoformat(),
            },
        )
        return {"code": code, "expires_at": expires.isoformat(), "expires_in_seconds": int(ttl_seconds)}

    ensure_tables()
    code = _make_parent_code()
    with engine.begin() as conn:
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
    """Link a parent to a student via one-time parent code.

    Returns (ok, message, student_user_id)
    """
    code_n = (code or "").strip().upper()
    if not code_n:
        return False, "Invalid code.", None

    now = _utcnow()
    engine = _get_engine()
    if engine is None:
        rkey = _redis_parent_code_key(code_n)
        data = _redis_get(rkey)
        if not data:
            return False, "Code not found or expired. Ask your child to generate a new one.", None

        student_user_id = int(data.get("student_user_id") or 0)
        if not student_user_id:
            return False, "Invalid code. Ask your child to generate a new one.", None
        if student_user_id == int(parent_user_id):
            return False, "You cannot link to yourself.", None

        # one-time: delete code after use
        _redis_del(rkey)

        # store link
        linked = _redis_get_linked_students(int(parent_user_id))
        if student_user_id not in linked:
            linked.append(student_user_id)
        _redis_set_linked_students(int(parent_user_id), linked)

        return True, "Linked successfully.", student_user_id

    ensure_tables()
    with engine.begin() as conn:
        row = conn.execute(select(parent_codes).where(parent_codes.c.code == code_n)).mappings().first()
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

        # Mark the code as used exactly once. We include used_at IS NULL in the
        # WHERE clause so concurrent requests cannot both succeed. If no rows
        # are updated, we treat the code as already used and return an error.
        result = conn.execute(
            parent_codes.update()
            .where(
                and_(
                    parent_codes.c.code == code_n,
                    parent_codes.c.used_at.is_(None),
                )
            )
            .values(used_at=now, used_by_parent_user_id=parent_user_id)
        )
        try:
            count = result.rowcount
        except Exception:
            count = 0
        if not count:
            return False, "This code was already used. Ask your child to generate a new one.", None

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
    engine = _get_engine()
    if engine is None:
        linked = _redis_get_linked_students(int(parent_user_id))
        return int(student_user_id) in linked

    ensure_tables()
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
    engine = _get_engine()
    if engine is None:
        student_ids = _redis_get_linked_students(int(parent_user_id))
        out: List[Dict[str, Any]] = []
        for sid in student_ids:
            prof = get_student_profile(int(sid)) or {"user_id": int(sid)}
            out.append(
                {
                    "student_user_id": int(sid),
                    "full_name": prof.get("full_name"),
                    "board": prof.get("board"),
                    "class": prof.get("class") if "class" in prof else prof.get("cls"),
                    "class_group": prof.get("class_group"),
                    "target_exams": prof.get("target_exams") or [],
                    "updated_at": prof.get("updated_at"),
                }
            )
        return out

    ensure_tables()
    with engine.begin() as conn:
        q = (
            select(
                parent_links.c.student_user_id.label("student_user_id"),
                student_profiles.c.full_name,
                student_profiles.c.board,
                student_profiles.c.cls.label("class"),
                student_profiles.c.class_group,
                student_profiles.c.target_exams_json,
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
        d = dict(r)
        try:
            d["target_exams"] = json.loads(d.get("target_exams_json") or "[]")
        except Exception:
            d["target_exams"] = []
        d.pop("target_exams_json", None)
        out.append(d)
    return out

def track_event(
    user_id: int,
    event_type: str,
    meta: Optional[Dict[str, Any]] = None,
    duration_sec: Optional[int] = None,
    value_num: Optional[int] = None,
) -> Dict[str, Any]:
    et = (event_type or "").strip()[:64]
    if not et:
        raise ValueError("event_type is required")

    engine = _get_engine()
    now = _utcnow()

    if engine is None:
        # Redis fallback: keep lightweight counters for 30 days
        ttl = 30 * 24 * 3600
        base = f"events:{int(user_id)}:{et}"
        count = _redis_incr(base + ":count", ttl)
        if duration_sec is not None:
            _redis_incr(base + ":duration_sec", ttl)  # count occurrences
            r = _r()
            if r:
                try:
                    r.incrby(base + ":duration_sum", int(duration_sec))
                    r.expire(base + ":duration_sum", ttl)
                except Exception:
                    pass
        if value_num is not None:
            r = _r()
            if r:
                try:
                    r.incrby(base + ":value_sum", int(value_num))
                    r.expire(base + ":value_sum", ttl)
                    r.incrby(base + ":value_count", 1)
                    r.expire(base + ":value_count", ttl)
                except Exception:
                    pass
        return {"ok": True, "stored": "redis", "event_type": et, "count_30d": count, "ts": now.isoformat()}

    ensure_tables()
    payload = {
        "user_id": int(user_id),
        "event_type": et,
        "meta_json": json.dumps(meta or {}),
        "duration_sec": int(duration_sec) if duration_sec is not None else None,
        "value_num": float(value_num) if value_num is not None else None,
        "created_at": now,
    }

    with engine.begin() as conn:
        conn.execute(events.insert().values(**payload))

    return {"ok": True, "stored": "db", "event_type": et, "ts": now.isoformat()}

def analytics_summary(parent_user_id: int, student_user_id: int) -> Dict[str, Any]:
    """Return read-only analytics summary for a linked student."""
    engine = _get_engine()
    now = _utcnow()

    if engine is None:
        # Redis fallback summary (Phase-1 stability). Minimal but useful.
        def _sum_for(et: str) -> Dict[str, int]:
            base = f"events:{int(student_user_id)}:{et}"
            return {
                "count_30d": _redis_get_int(base + ":count"),
                "value_sum": _redis_get_int(base + ":value_sum"),
                "value_count": _redis_get_int(base + ":value_count"),
            }

        tests = _sum_for("test_submitted")
        avg_score = 0
        if tests["value_count"] > 0:
            avg_score = int(round(tests["value_sum"] / max(1, tests["value_count"])))

        return {
            "student_user_id": int(student_user_id),
            "generated_at": now.isoformat(),
            # Canonical keys
            "time_spent_minutes_7d": 0,
            "active_days_7d": 0,
            "tests_attempted_30d": int(tests["count_30d"]),
            "avg_score_30d": avg_score if tests["value_count"] > 0 else None,
            "recent_activity": [],
            # Aliases for older/newer UIs
            "time_spent_mins_7d": 0,
            "time_spent_minutes": 0,
            "active_days_7": 0,
            "tests_30d": int(tests["count_30d"]),
            "recent": [],
            # Phase-1 placeholders (kept for premium feel)
            "subject_strengths": [],
            "subject_weaknesses": [],
        }

    ensure_tables()

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

        # `events` stores metadata in `meta_json` (JSON). Older deployments used `meta` or had no meta column at all.
        # IMPORTANT: SQLAlchemy column objects do NOT support truthy checks.
        # Using `A or B` here can trigger "Boolean value of this clause is not defined".
        meta_col = getattr(events.c, "meta_json", None)
        if meta_col is None:
            meta_col = getattr(events.c, "meta", None)
        meta_sel = meta_col.label('meta_json') if meta_col is not None else literal(None).label('meta_json')

        recent = conn.execute(
            select(events.c.event_type, events.c.created_at, meta_sel)
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
        # `meta_json` is stored as a JSON string in DB.
        meta_raw = r.get("meta_json")
        if isinstance(meta_raw, str):
            try:
                import json
                meta = json.loads(meta_raw) or {}
            except Exception:
                meta = {}
        elif isinstance(meta_raw, dict):
            meta = meta_raw
        else:
            meta = {}
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

    # Build recent activity (safe JSON parse).
    recent_activity = []
    for r in recent:
        meta_raw = r.get("meta_json")
        if isinstance(meta_raw, str):
            try:
                import json
                meta = json.loads(meta_raw) or {}
            except Exception:
                meta = {}
        elif isinstance(meta_raw, dict):
            meta = meta_raw
        else:
            meta = {}
        # NOTE: Return both the newer compact keys (type/at/meta) AND the
        # older UI keys (event_type/created_at/meta_json).
        # This keeps parent.html dashboards working across multiple frontend
        # ZIP versions without needing coordinated deploys.
        ev_type = r.get("event_type")
        ev_at = r.get("created_at").isoformat() if r.get("created_at") else None
        recent_activity.append({
            # Newer keys
            "type": ev_type,
            "at": ev_at,
            "meta": meta,
            # Older keys expected by some frontends
            "event_type": ev_type,
            "created_at": ev_at,
            "meta_json": meta,
        })

    return {
        # Canonical keys
        "time_spent_minutes_7d": int(round((time_7d or 0) / 60)),
        "active_days_7d": int(active_days_7d or 0),
        "tests_attempted_30d": int(tests_30d or 0),
        "avg_score_30d": float(avg_score_30d) if avg_score_30d is not None else None,
        "last_active_at": (last_active.isoformat() if last_active else None),
        "subject_strengths": strengths,
        "subject_weaknesses": weaknesses,
        "recent_activity": recent_activity,
        # Aliases for UI compatibility
        "time_spent_mins_7d": int(round((time_7d or 0) / 60)),
        "time_spent_minutes": int(round((time_7d or 0) / 60)),
        "active_days_7": int(active_days_7d or 0),
        "tests_30d": int(tests_30d or 0),
        "recent": recent_activity,
    }
