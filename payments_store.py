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

def get_engine_safe() -> Optional[Engine]:
    """Public, best-effort engine accessor for other modules (billing_store, etc.)."""
    try:
        return _get_engine()
    except Exception:
        return None


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
            billing_cycle TEXT,
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
            payment_type TEXT NOT NULL DEFAULT 'subscription',
            billing_cycle TEXT,
            booster_sku TEXT,
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
                "ALTER TABLE IF EXISTS subscriptions ADD COLUMN IF NOT EXISTS billing_cycle TEXT;",
                "ALTER TABLE IF EXISTS subscriptions ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active';",
                "ALTER TABLE IF EXISTS subscriptions ADD COLUMN IF NOT EXISTS starts_at TIMESTAMPTZ NOT NULL DEFAULT NOW();",
                "ALTER TABLE IF EXISTS subscriptions ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;",
                "ALTER TABLE IF EXISTS subscriptions ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();",
                "ALTER TABLE IF EXISTS subscriptions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();",
                "ALTER TABLE IF EXISTS payments ADD COLUMN IF NOT EXISTS plan TEXT;",
                "ALTER TABLE IF EXISTS payments ADD COLUMN IF NOT EXISTS payment_type TEXT DEFAULT 'subscription';",
                "ALTER TABLE IF EXISTS payments ADD COLUMN IF NOT EXISTS billing_cycle TEXT;",
                "ALTER TABLE IF EXISTS payments ADD COLUMN IF NOT EXISTS booster_sku TEXT;",
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
        return {"plan": "free", "billing_cycle": None, "status": "active", "expires_at": None}

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
                return {"plan": "free", "billing_cycle": None, "status": "active", "expires_at": None}

            expires_at = row.get("expires_at")
            if expires_at is not None:
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at <= datetime.now(timezone.utc):
                    return {"plan": "free", "billing_cycle": None, "status": "expired", "expires_at": expires_at}

            return {
                "plan": row.get("plan") or "free",
                "billing_cycle": row.get("billing_cycle"),
                "status": row.get("status") or "active",
                "expires_at": expires_at,
            }
    except Exception:
        logger.exception("get_subscription failed")
        return {"plan": "free", "billing_cycle": None, "status": "active", "expires_at": None}


def upsert_subscription(user_id: int, plan: str, duration_days: int, billing_cycle: str | None = None) -> Dict[str, Any]:
    """Activate or extend a subscription.

    Trust-first rule:
    - If the user already has an active subscription that hasn't expired,
      a new purchase EXTENDS from the current expiry (does not reset/shorten).
    - If the existing subscription is expired/missing, start from "now".

    This prevents accidental loss of remaining time when switching cycles
    (Monthly ↔ Yearly) or upgrading.
    """
    ensure_tables()
    eng = _get_engine()

    now = datetime.now(timezone.utc)
    base_start = now

    # If DB is available, extend from the later of (now, current expires_at).
    if eng is not None:
        try:
            with eng.begin() as conn:
                row = conn.execute(
                    text(
                        """
                        SELECT expires_at
                        FROM subscriptions
                        WHERE user_id=:user_id
                        LIMIT 1
                        """
                    ),
                    {"user_id": int(user_id)},
                ).mappings().first()
                cur_exp = row.get("expires_at") if row else None
                if cur_exp is not None:
                    if cur_exp.tzinfo is None:
                        cur_exp = cur_exp.replace(tzinfo=timezone.utc)
                    if cur_exp > now:
                        base_start = cur_exp
        except Exception:
            # Non-fatal: fall back to "now".
            logger.exception("upsert_subscription: failed to read current expiry")

    starts_at = now
    expires_at = base_start + timedelta(days=int(duration_days))

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
    razorpay_order_id: str | None = None,
    *,
    # Backward/forward compatibility:
    # - Older callers passed only a razorpay_order_id positional.
    # - Newer callers may use keyword arguments like payment_type / booster_sku.
    # - Some callers may pass order_id as a keyword.
    order_id: str | None = None,
    payment_type: str = "subscription",
    billing_cycle: str | None = None,
    booster_sku: str | None = None,
    **_ignored: object,
) -> None:
    ensure_tables()
    # Allow either param name.
    effective_order_id = (razorpay_order_id or order_id)
    if not effective_order_id:
        return
    eng = _get_engine()
    if eng is None:
        return
    try:
        with eng.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO payments(user_id, plan, payment_type, billing_cycle, booster_sku, amount_paise, currency, razorpay_order_id, status)
                    VALUES (:user_id, :plan, :payment_type, :billing_cycle, :booster_sku, :amount_paise, :currency, :order_id, 'created')
                    ON CONFLICT (razorpay_order_id) DO NOTHING
                    """
                ),
                {
                    "user_id": int(user_id),
                    "plan": plan,
                    "payment_type": (payment_type or "subscription"),
                    "billing_cycle": billing_cycle,
                    "booster_sku": booster_sku,
                    "amount_paise": int(amount_paise),
                    "currency": currency,
                    "order_id": effective_order_id,
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


# -----------------------------------------------------------------------------
# New helper: fetch order details for verification
# -----------------------------------------------------------------------------
def get_order_record(user_id: int, order_id: str) -> Optional[Dict[str, Any]]:
    """Return a single payment row for the given user and Razorpay order id.

    This is used by the payments_router.verify endpoint to cross-check the
    incoming verification request against the originally created order. It
    ensures the order exists, belongs to the current user and is still in
    a mutable state (e.g., not already marked paid). Returns None if no
    matching record is found. Never raises.
    """
    ensure_tables()
    eng = _get_engine()
    if eng is None:
        return None
    try:
        with eng.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT user_id,
                           plan,
                           billing_cycle,
                           amount_paise,
                           currency,
                           status,
                           payment_type,
                           booster_sku
                    FROM payments
                    WHERE razorpay_order_id = :order_id AND user_id = :user_id
                    LIMIT 1
                    """
                ),
                {"order_id": order_id, "user_id": int(user_id)},
            ).mappings().first()
            # Ensure that callers get a plain dict even if additional columns are added in the future.
            return dict(row) if row else None
    except Exception:
        logger.exception("get_order_record failed")
        return None


def list_payments(user_id: int, limit: int = 50) -> list[Dict[str, Any]]:
    """Return recent payment records for a user (most recent first).

    Safe for production:
    - best-effort (never raises)
    - returns an empty list if DB is unavailable
    """
    ensure_tables()
    eng = _get_engine()
    if eng is None:
        return []

    try:
        lim = int(limit or 50)
        if lim < 1:
            lim = 1
        if lim > 200:
            lim = 200

        with eng.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, plan, payment_type, billing_cycle, booster_sku,
                           amount_paise, currency,
                           razorpay_order_id, razorpay_payment_id,
                           status, created_at
                    FROM payments
                    WHERE user_id=:user_id
                    ORDER BY created_at DESC
                    LIMIT :lim
                    """
                ),
                {"user_id": int(user_id), "lim": lim},
            ).mappings().all()

        out: list[Dict[str, Any]] = []
        for r in rows or []:
            out.append(
                {
                    "id": int(r.get("id") or 0),
                    "plan": (r.get("plan") or "").lower().strip() or None,
                    "payment_type": (r.get("payment_type") or "").lower().strip() or "subscription",
                    "billing_cycle": (r.get("billing_cycle") or "").lower().strip() or None,
                    "booster_sku": r.get("booster_sku"),
                    "amount_paise": int(r.get("amount_paise") or 0),
                    "currency": (r.get("currency") or "INR").upper().strip() or "INR",
                    "razorpay_order_id": r.get("razorpay_order_id"),
                    "razorpay_payment_id": r.get("razorpay_payment_id"),
                    "status": (r.get("status") or "").lower().strip() or "created",
                    "created_at": r.get("created_at"),
                }
            )
        return out
    except Exception:
        logger.exception("list_payments failed")
        return []
