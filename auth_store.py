"""DB store for authentication (users, otp_codes, sessions).

We use SQLAlchemy Core + raw SQL for:
- minimal dependencies
- no migration framework required
- safe CREATE TABLE IF NOT EXISTS
"""

from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from auth_utils import hash_value, constant_time_equal

logger = logging.getLogger("knoweasy-engine-api.auth")

_ENGINE: Optional[Engine] = None
_TABLES_READY: bool = False

def _clean_sslmode(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    v = v.strip().strip('"').strip("'").strip()
    return v or None

def _get_engine() -> Optional[Engine]:
    global _ENGINE
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        return None

    if _ENGINE is not None:
        return _ENGINE

    url_lower = url.lower()
    has_sslmode_in_url = "sslmode=" in url_lower
    connect_args: Dict[str, Any] = {}
    if not has_sslmode_in_url:
        sslmode = _clean_sslmode(os.getenv("DB_SSLMODE"))
        if sslmode:
            connect_args = {"sslmode": sslmode}

    try:
        _ENGINE = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
        return _ENGINE
    except Exception:
        logger.exception("Failed to create auth DB engine")
        return None

def ensure_tables() -> None:
    global _TABLES_READY
    if _TABLES_READY:
        return
    eng = _get_engine()
    if eng is None:
        raise RuntimeError("DATABASE_URL not configured")

    # Minimal schema. We can extend in Phase-2.2+.
    ddl = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('student','parent')),
            status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(email, role)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS otp_codes (
            id SERIAL PRIMARY KEY,
            email TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('student','parent')),
            otp_hash TEXT NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            attempts INT NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_seen_at TIMESTAMPTZ,
            UNIQUE(token_hash)
        );
        """,
        # Helpful indexes for performance.
        """CREATE INDEX IF NOT EXISTS idx_otp_email_role_created ON otp_codes(email, role, created_at DESC);""",
        """CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, expires_at);""",
    ]

    with eng.begin() as conn:
        for stmt in ddl:
            conn.execute(text(stmt))

    _TABLES_READY = True

# -------------------------
# OTP rules
# -------------------------
OTP_EXPIRES_MIN = 10
OTP_RESEND_COOLDOWN_SEC = 30
OTP_SEND_LIMIT_WINDOW_MIN = 15
OTP_SEND_LIMIT_COUNT = 3
OTP_MAX_ATTEMPTS = 5
OTP_LOCK_MIN = 10

def otp_can_send(email: str, role: str) -> Tuple[bool, int]:
    """Returns (allowed, retry_after_seconds)."""
    ensure_tables()
    eng = _get_engine()
    assert eng is not None

    now = datetime.now(timezone.utc)

    with eng.begin() as conn:
        # cooldown: last OTP created_at within 30s
        row = conn.execute(
            text("""
                SELECT created_at
                FROM otp_codes
                WHERE email=:email AND role=:role
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"email": email, "role": role},
        ).mappings().first()

        if row:
            last_created = row["created_at"]
            # last_created may be naive; treat as UTC
            if last_created.tzinfo is None:
                last_created = last_created.replace(tzinfo=timezone.utc)
            delta = (now - last_created).total_seconds()
            if delta < OTP_RESEND_COOLDOWN_SEC:
                return False, int(OTP_RESEND_COOLDOWN_SEC - delta)

        # window count
        window_start = now - timedelta(minutes=OTP_SEND_LIMIT_WINDOW_MIN)
        count = conn.execute(
            text("""
                SELECT COUNT(*) AS c
                FROM otp_codes
                WHERE email=:email AND role=:role AND created_at >= :window_start
            """),
            {"email": email, "role": role, "window_start": window_start},
        ).mappings().first()["c"]

        if int(count) >= OTP_SEND_LIMIT_COUNT:
            # suggest retry at window end
            return False, int(OTP_SEND_LIMIT_WINDOW_MIN * 60)

    return True, 0

def store_otp(email: str, role: str, otp_hash: str) -> None:
    ensure_tables()
    eng = _get_engine()
    assert eng is not None
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=OTP_EXPIRES_MIN)
    with eng.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO otp_codes(email, role, otp_hash, expires_at)
                VALUES (:email, :role, :otp_hash, :expires_at)
            """),
            {"email": email, "role": role, "otp_hash": otp_hash, "expires_at": expires_at},
        )

def _latest_otp_row(conn, email: str, role: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text("""
            SELECT id, otp_hash, expires_at, attempts, created_at
            FROM otp_codes
            WHERE email=:email AND role=:role
            ORDER BY created_at DESC
            LIMIT 1
        """),
        {"email": email, "role": role},
    ).mappings().first()
    return dict(row) if row else None

def verify_otp(email: str, role: str, otp_plain: str) -> Tuple[bool, str, int]:
    """Returns (ok, reason_code, retry_after_seconds)."""
    ensure_tables()
    eng = _get_engine()
    assert eng is not None

    now = datetime.now(timezone.utc)
    otp_h = hash_value(otp_plain)
    if not otp_h:
        return False, "AUTH_NOT_CONFIGURED", 0

    with eng.begin() as conn:
        row = _latest_otp_row(conn, email, role)
        if not row:
            return False, "OTP_NOT_FOUND", 0

        expires_at = row["expires_at"]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        # Lockout on too many attempts: based on created_at time + lock minutes
        attempts = int(row["attempts"] or 0)
        created_at = row["created_at"]
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        lock_until = created_at + timedelta(minutes=OTP_LOCK_MIN)
        if attempts >= OTP_MAX_ATTEMPTS and now < lock_until:
            return False, "OTP_LOCKED", int((lock_until - now).total_seconds())

        if now > expires_at:
            return False, "OTP_EXPIRED", 0

        if not constant_time_equal(row["otp_hash"], otp_h):
            # increment attempts
            conn.execute(
                text("""UPDATE otp_codes SET attempts = attempts + 1 WHERE id=:id"""),
                {"id": row["id"]},
            )
            return False, "OTP_INVALID", 0

        return True, "OK", 0

# -------------------------
# Users + sessions
# -------------------------
SESSION_DAYS = 30

def get_or_create_user(email: str, role: str) -> Tuple[int, bool]:
    """Return (user_id, is_new_user)."""
    ensure_tables()
    eng = _get_engine()
    assert eng is not None

    with eng.begin() as conn:
        row = conn.execute(
            text("""SELECT id FROM users WHERE email=:email AND role=:role"""),
            {"email": email, "role": role},
        ).mappings().first()
        if row:
            return int(row["id"]), False

        # insert
        row2 = conn.execute(
            text("""
                INSERT INTO users(email, role)
                VALUES (:email, :role)
                RETURNING id
            """),
            {"email": email, "role": role},
        ).mappings().first()
        return int(row2["id"]), True

def create_session(user_id: int, token_hash: str) -> None:
    ensure_tables()
    eng = _get_engine()
    assert eng is not None
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=SESSION_DAYS)
    with eng.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO sessions(user_id, token_hash, expires_at, last_seen_at)
                VALUES (:user_id, :token_hash, :expires_at, :now)
            """),
            {"user_id": user_id, "token_hash": token_hash, "expires_at": expires_at, "now": now},
        )

def session_user(token_plain: str) -> Optional[Dict[str, Any]]:
    ensure_tables()
    eng = _get_engine()
    assert eng is not None
    token_h = hash_value(token_plain)
    if not token_h:
        return None

    now = datetime.now(timezone.utc)
    with eng.begin() as conn:
        row = conn.execute(
            text("""
                SELECT u.id AS user_id, u.email, u.role, s.expires_at
                FROM sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = :token_hash
                LIMIT 1
            """),
            {"token_hash": token_h},
        ).mappings().first()

        if not row:
            return None

        expires_at = row["expires_at"]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if now > expires_at:
            # Expired: cleanup
            conn.execute(text("""DELETE FROM sessions WHERE token_hash=:token_hash"""), {"token_hash": token_h})
            return None

        # Touch last seen
        conn.execute(
            text("""UPDATE sessions SET last_seen_at=:now WHERE token_hash=:token_hash"""),
            {"now": now, "token_hash": token_h},
        )

        return {"user_id": int(row["user_id"]), "email": row["email"], "role": row["role"]}

def delete_session(token_plain: str) -> None:
    ensure_tables()
    eng = _get_engine()
    assert eng is not None
    token_h = hash_value(token_plain)
    if not token_h:
        return
    with eng.begin() as conn:
        conn.execute(text("""DELETE FROM sessions WHERE token_hash=:token_hash"""), {"token_hash": token_h})
