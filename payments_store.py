"""payments_store.py

Minimal payment/subscription persistence for KnowEasy.

This module is intentionally migration-light (CREATE TABLE IF NOT EXISTS +
ALTER TABLE ADD COLUMN IF NOT EXISTS) and must never crash the API.

Important compatibility note
----------------------------
Older versions of the code used a (plan, status, expires_at) shape.
The current API expects:
  - plan
  - billing_cycle
  - is_active
  - cycle_end_at

We keep backward compatibility while making the router logic authoritative.
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
    """Create/repair tables. Must be safe to call on every request."""
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
            billing_cycle TEXT NOT NULL DEFAULT 'monthly',
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
            payment_type TEXT NOT NULL DEFAULT 'subscription',
            billing_cycle TEXT NOT NULL DEFAULT 'monthly',
            booster_sku TEXT,
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
            repairs = [
                "ALTER TABLE IF EXISTS subscriptions ADD COLUMN IF NOT EXISTS plan TEXT NOT NULL DEFAULT 'free';",
                "ALTER TABLE IF EXISTS subscriptions ADD COLUMN IF NOT EXISTS billing_cycle TEXT NOT NULL DEFAULT 'monthly';",
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
                "ALTER TABLE IF EXISTS payments ADD COLUMN IF NOT EXISTS payment_type TEXT DEFAULT 'subscription';",
                "ALTER TABLE IF EXISTS payments ADD COLUMN IF NOT EXISTS billing_cycle TEXT DEFAULT 'monthly';",
                "ALTER TABLE IF EXISTS payments ADD COLUMN IF NOT EXISTS booster_sku TEXT;",
                "ALTER TABLE IF EXISTS payments ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();",
            ]
            for stmt in repairs:
                try:
                    conn.execute(text(stmt))
                except Exception:
                    logger.debug("payments_store schema repair skipped: %s", stmt, exc_info=True)

    except Exception:
        logger.exception("payments_store.ensure_tables failed (non-fatal)")

    _TABLES_READY = True


def _as_utc(dt) -> Optional[datetime]:
    if dt is None:
        return None
    try:
        if getattr(dt, "tzinfo", None) is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def get_subscription(user_id: int) -> Dict[str, Any]:
    """Return a router-friendly subscription shape.

    Always returns keys:
      plan, billing_cycle, is_active, cycle_end_at, status
    """
    ensure_tables()
    eng = _get_engine()
    if eng is None:
        return {"plan": "free", "billing_cycle": "monthly", "is_active": False, "cycle_end_at": None, "status": "none"}

    try:
        with eng.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT plan, billing_cycle, status, expires_at
                    FROM subscriptions
                    WHERE user_id=:user_id
                    LIMIT 1
                    """
                ),
                {"user_id": int(user_id)},
            ).mappings().first()

            if not row:
                return {"plan": "free", "billing_cycle": "monthly", "is_active": False, "cycle_end_at": None, "status": "none"}

            plan = (row.get("plan") or "free").lower()
            billing_cycle = (row.get("billing_cycle") or "monthly").lower()
            status = (row.get("status") or "active").lower()
            expires_at = _as_utc(row.get("expires_at"))

            now = datetime.now(timezone.utc)
            if expires_at is not None and expires_at <= now:
                # consider expired regardless of status
                return {"plan": "free", "billing_cycle": billing_cycle, "is_active": False, "cycle_end_at": expires_at, "status": "expired"}

            is_active = (status == "active") and (plan in ("pro", "max"))
            return {"plan": plan, "billing_cycle": billing_cycle, "is_active": bool(is_active), "cycle_end_at": expires_at, "status": status}

    except Exception:
        logger.exception("get_subscription failed")
        return {"plan": "free", "billing_cycle": "monthly", "is_active": False, "cycle_end_at": None, "status": "error"}


def upsert_subscription(
    user_id: int,
    plan: str,
    billing_cycle: str = "monthly",
    duration_days: Optional[int] = None,
) -> Dict[str, Any]:
    """Activate subscription.

    - If duration_days provided, it wins.
    - Else, monthly=30 days, yearly=365 days.
    """
    ensure_tables()
    eng = _get_engine()

    plan = (plan or "free").lower().strip()
    billing_cycle = (billing_cycle or "monthly").lower().strip()

    if duration_days is None:
        duration_days = 365 if billing_cycle == "yearly" else 30

    starts_at = datetime.now(timezone.utc)
    expires_at = starts_at + timedelta(days=int(duration_days))

    if eng is None:
        return {"plan": plan, "billing_cycle": billing_cycle, "status": "active", "expires_at": expires_at}

    try:
        with eng.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO subscriptions (user_id, plan, billing_cycle, status, starts_at, expires_at, updated_at)
                    VALUES (:user_id, :plan, :billing_cycle, 'active', :starts_at, :expires_at, NOW())
                    ON CONFLICT (user_id)
                    DO UPDATE SET
                        plan=EXCLUDED.plan,
                        billing_cycle=EXCLUDED.billing_cycle,
                        status='active',
                        starts_at=EXCLUDED.starts_at,
                        expires_at=EXCLUDED.expires_at,
                        updated_at=NOW()
                    """
                ),
                {
                    "user_id": int(user_id),
                    "plan": plan,
                    "billing_cycle": billing_cycle,
                    "starts_at": starts_at,
                    "expires_at": expires_at,
                },
            )
        return {"plan": plan, "billing_cycle": billing_cycle, "status": "active", "expires_at": expires_at}
    except Exception:
        logger.exception("upsert_subscription failed")
        return {"plan": plan, "billing_cycle": billing_cycle, "status": "active", "expires_at": expires_at}


def record_order(
    user_id: int,
    plan: str,
    amount_paise: int,
    currency: str,
    razorpay_order_id: str,
    payment_type: str = "subscription",
    billing_cycle: str = "monthly",
    booster_sku: str | None = None,
) -> None:
    ensure_tables()
    eng = _get_engine()
    if eng is None:
        return
    try:
        with eng.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO payments (user_id, plan, amount_paise, currency, razorpay_order_id, status, payment_type, billing_cycle, booster_sku)
                    VALUES (:user_id, :plan, :amount_paise, :currency, :razorpay_order_id, 'created', :payment_type, :billing_cycle, :booster_sku)
                    ON CONFLICT (razorpay_order_id)
                    DO NOTHING
                    """
                ),
                {
                    "user_id": int(user_id),
                    "plan": plan,
                    "amount_paise": int(amount_paise),
                    "currency": currency or "INR",
                    "razorpay_order_id": razorpay_order_id,
                    "payment_type": payment_type or "subscription",
                    "billing_cycle": billing_cycle or "monthly",
                    "booster_sku": booster_sku,
                },
            )
    except Exception:
        logger.exception("record_order failed")


def get_payment_by_order_id(razorpay_order_id: str) -> Optional[Dict[str, Any]]:
    ensure_tables()
    eng = _get_engine()
    if eng is None:
        return None
    try:
        with eng.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT user_id, plan, amount_paise, currency, razorpay_order_id, razorpay_payment_id, status,
                           payment_type, billing_cycle, booster_sku
                    FROM payments
                    WHERE razorpay_order_id=:oid
                    LIMIT 1
                    """
                ),
                {"oid": razorpay_order_id},
            ).mappings().first()
            return dict(row) if row else None
    except Exception:
        logger.exception("get_payment_by_order_id failed")
        return None


def mark_payment_paid(razorpay_order_id: str, razorpay_payment_id: str) -> None:
    """Idempotent: if already paid, keep it paid."""
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
                    SET status='paid', razorpay_payment_id=:pid
                    WHERE razorpay_order_id=:oid
                    """
                ),
                {"oid": razorpay_order_id, "pid": razorpay_payment_id},
            )
    except Exception:
        logger.exception("mark_payment_paid failed")
