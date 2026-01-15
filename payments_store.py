"""payments_store.py

Minimal payment/subscription persistence for KnowEasy.

Design goals
- No migration framework
- CREATE TABLE IF NOT EXISTS
- Best-effort DB usage: never crash API

Stores
- subscriptions: current plan + expiry per user
- payments: audit trail of orders/payments
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger("knoweasy-engine-api.payments")

_ENGINE: Optional[Engine] = None
_TABLES_READY: bool = False


def _clean_sslmode(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    v = str(v).strip().strip('"').strip("'").strip()
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
        logger.exception("Failed to create payments DB engine")
        return None


def ensure_tables() -> None:
    global _TABLES_READY
    if _TABLES_READY:
        return

    eng = _get_engine()
    if eng is None:
        _TABLES_READY = True
        return

    ddl = [
        """
        CREATE TABLE IF NOT EXISTS subscriptions (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL,
            plan TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            starts_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(user_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS payments (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL,
            plan TEXT NOT NULL,
            amount_paise INT NOT NULL,
            currency TEXT NOT NULL DEFAULT 'INR',
            razorpay_order_id TEXT NOT NULL,
            razorpay_payment_id TEXT,
            razorpay_signature TEXT,
            status TEXT NOT NULL DEFAULT 'created',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(razorpay_order_id)
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_payments_user_created ON payments(user_id, created_at DESC);",
    ]

    try:
        with eng.begin() as conn:
            for stmt in ddl:
                conn.execute(text(stmt))
            # --- lightweight schema repair (idempotent) ---
            # Older DBs may have subscriptions/payments tables missing columns.
            # We repair using ALTER TABLE ... ADD COLUMN IF NOT EXISTS (Postgres-safe).
            repairs = [
                "ALTER TABLE IF EXISTS subscriptions ADD COLUMN IF NOT EXISTS plan TEXT NOT NULL DEFAULT 'free';",
                "ALTER TABLE IF EXISTS subscriptions ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active';",
                "ALTER TABLE IF EXISTS subscriptions ADD COLUMN IF NOT EXISTS starts_at TIMESTAMPTZ NOT NULL DEFAULT NOW();",
                "ALTER TABLE IF EXISTS subscriptions ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;",
                "ALTER TABLE IF EXISTS subscriptions ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();",
                "ALTER TABLE IF EXISTS subscriptions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();",
                "ALTER TABLE IF EXISTS payments ADD COLUMN IF NOT EXISTS plan TEXT;",
                "ALTER TABLE IF EXISTS payments ADD COLUMN IF NOT EXISTS amount_paise INT;",
                "ALTER TABLE IF EXISTS payments ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'INR';",
                "ALTER TABLE IF EXISTS payments ADD COLUMN IF NOT EXISTS razorpay_order_id TEXT;",
                "ALTER TABLE IF EXISTS payments ADD COLUMN IF NOT EXISTS razorpay_payment_id TEXT;",
                "ALTER TABLE IF EXISTS payments ADD COLUMN IF NOT EXISTS razorpay_signature TEXT;",
                "ALTER TABLE IF EXISTS payments ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'created';",
                "ALTER TABLE IF EXISTS payments ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();",
            ]
            for stmt in repairs:
                try:
                    conn.execute(text(stmt))
                except Exception:
                    # Non-fatal: if table doesn't exist yet or dialect doesn't support IF EXISTS/IF NOT EXISTS
                    logger.debug("payments_store schema repair skipped: %s", stmt, exc_info=True)

    except Exception:
        logger.exception("payments_store.ensure_tables failed (non-fatal)")

    _TABLES_READY = True


def get_subscription(user_id: int) -> Dict[str, Any]:
    """Return current subscription info; if none, return Free."""
    ensure_tables()
    eng = _get_engine()
    if eng is None:
        return {"plan": "free", "status": "active", "expires_at": None}

    try:
        with eng.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT plan, status, expires_at
                    FROM subscriptions
                    WHERE user_id=:user_id
                    LIMIT 1
                    """
                ),
                {"user_id": int(user_id)},
            ).mappings().first()
            if not row:
                return {"plan": "free", "status": "active", "expires_at": None}

            expires_at = row.get("expires_at")
            if expires_at is not None:
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at <= datetime.now(timezone.utc):
                    return {"plan": "free", "status": "expired", "expires_at": expires_at}

            return {"plan": row.get("plan") or "free", "status": row.get("status") or "active", "expires_at": expires_at}
    except Exception:
        logger.exception("get_subscription failed")
        return {"plan": "free", "status": "active", "expires_at": None}


def upsert_subscription(user_id: int, plan: str, duration_days: int) -> Dict[str, Any]:
    """Activate subscription for duration_days from now."""
    ensure_tables()
    eng = _get_engine()
    starts_at = datetime.now(timezone.utc)
    expires_at = starts_at + timedelta(days=int(duration_days))

    if eng is None:
        return {"plan": plan, "status": "active", "expires_at": expires_at}

    try:
        with eng.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO subscriptions (user_id, plan, status, starts_at, expires_at, updated_at)
                    VALUES (:user_id, :plan, 'active', :starts_at, :expires_at, NOW())
                    ON CONFLICT (user_id)
                    DO UPDATE SET
                        plan=EXCLUDED.plan,
                        status='active',
                        starts_at=EXCLUDED.starts_at,
                        expires_at=EXCLUDED.expires_at,
                        updated_at=NOW()
                    """
                ),
                {
                    "user_id": int(user_id),
                    "plan": plan,
                    "starts_at": starts_at,
                    "expires_at": expires_at,
                },
            )
        return {"plan": plan, "status": "active", "expires_at": expires_at}
    except Exception:
        logger.exception("upsert_subscription failed")
        return {"plan": plan, "status": "active", "expires_at": expires_at}


def record_order(user_id: int, plan: str, amount_paise: int, currency: str, razorpay_order_id: str) -> None:
    ensure_tables()
    eng = _get_engine()
    if eng is None:
        return
    try:
        with eng.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO payments(user_id, plan, amount_paise, currency, razorpay_order_id, status)
                    VALUES (:user_id, :plan, :amount_paise, :currency, :order_id, 'created')
                    ON CONFLICT (razorpay_order_id) DO NOTHING
                    """
                ),
                {
                    "user_id": int(user_id),
                    "plan": plan,
                    "amount_paise": int(amount_paise),
                    "currency": currency,
                    "order_id": razorpay_order_id,
                },
            )
    except Exception:
        logger.exception("record_order failed")


def mark_payment_paid(user_id: int, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> None:
    ensure_tables()
    eng = _get_engine()
    if eng is None:
        return
    try:
        with eng.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE payments
                    SET status='paid',
                        razorpay_payment_id=:payment_id,
                        razorpay_signature=:sig
                    WHERE razorpay_order_id=:order_id AND user_id=:user_id
                    """
                ),
                {
                    "user_id": int(user_id),
                    "order_id": razorpay_order_id,
                    "payment_id": razorpay_payment_id,
                    "sig": razorpay_signature,
                },
            )
    except Exception:
        logger.exception("mark_payment_paid failed")


def get_payment_by_order_id(razorpay_order_id: str) -> Optional[Dict[str, Any]]:
    """Fetch the latest payment row for a given Razorpay order_id."""
    ensure_tables()
    eng = _get_engine()
    if eng is None:
        return None

    with eng.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT *
                FROM payments
                WHERE razorpay_order_id = :oid
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"oid": razorpay_order_id},
        ).mappings().first()

    return dict(row) if row else None
