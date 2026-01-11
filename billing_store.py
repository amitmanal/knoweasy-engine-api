
"""Subscription & Credits store (Phase-2 skeleton)

Goals:
- Minimal, stable DB tables for plans/subscriptions/credit ledger
- Default everyone to FREE with daily credits
- Enforce credits for AI actions (e.g., /solve)

This is intentionally simple and additive.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, date, timedelta
from typing import Any, Dict, Optional, List

from sqlalchemy import text

from db import _get_engine

# --- Plan defaults (can later be moved to DB migrations/admin panel) ---
DEFAULT_PLANS = [
    {
        "code": "FREE",
        "daily_credits": 8,
        "monthly_credits": 0,
        "features_json": {"ai": True, "downloads": False, "parent_dashboard": False},
        "is_active": True,
    },
    {
        "code": "PRO",
        "daily_credits": 0,
        "monthly_credits": 800,
        "features_json": {"ai": True, "downloads": False, "parent_dashboard": True},
        "is_active": True,
    },
    {
        "code": "MAX",
        "daily_credits": 0,
        "monthly_credits": 2000,
        "features_json": {"ai": True, "downloads": True, "parent_dashboard": True},
        "is_active": True,
    },
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_tables() -> None:
    eng = _get_engine()
    if eng is None:
        return
    with eng.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS plans (
              id SERIAL PRIMARY KEY,
              code TEXT UNIQUE NOT NULL,
              daily_credits INTEGER NOT NULL DEFAULT 0,
              monthly_credits INTEGER NOT NULL DEFAULT 0,
              features_json JSONB NOT NULL DEFAULT '{}'::jsonb,
              is_active BOOLEAN NOT NULL DEFAULT TRUE,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        ))
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS subscriptions (
              user_id INTEGER PRIMARY KEY,
              plan_code TEXT NOT NULL DEFAULT 'FREE',
              status TEXT NOT NULL DEFAULT 'active',
              started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              expires_at TIMESTAMPTZ NULL,
              credits_balance INTEGER NOT NULL DEFAULT 0,
              last_refill_at DATE NULL,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        ))
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS credit_ledger (
              id BIGSERIAL PRIMARY KEY,
              user_id INTEGER NOT NULL,
              action TEXT NOT NULL,
              credits_used INTEGER NOT NULL,
              balance_after INTEGER NOT NULL,
              meta_json JSONB NOT NULL DEFAULT '{}'::jsonb,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        ))

        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS payment_orders (
              id BIGSERIAL PRIMARY KEY,
              user_id INTEGER NOT NULL,
              plan_code TEXT NOT NULL,
              amount_paise INTEGER NOT NULL,
              currency TEXT NOT NULL DEFAULT 'INR',
              razorpay_order_id TEXT UNIQUE NOT NULL,
              razorpay_payment_id TEXT NULL,
              status TEXT NOT NULL DEFAULT 'created',  -- created|paid|failed
              meta_json JSONB NOT NULL DEFAULT '{}'::jsonb,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              paid_at TIMESTAMPTZ NULL
            );
            """
        ))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_payment_orders_user_id ON payment_orders(user_id);"))


    seed_plans()


def seed_plans() -> None:
    eng = _get_engine()
    if eng is None:
        return
    with eng.begin() as conn:
        for p in DEFAULT_PLANS:
            conn.execute(
                text(
                    """
                    INSERT INTO plans (code, daily_credits, monthly_credits, features_json, is_active)
                    VALUES (:code, :daily_credits, :monthly_credits, :features_json::jsonb, :is_active)
                    ON CONFLICT (code) DO UPDATE SET
                      daily_credits = EXCLUDED.daily_credits,
                      monthly_credits = EXCLUDED.monthly_credits,
                      features_json = EXCLUDED.features_json,
                      is_active = EXCLUDED.is_active,
                      updated_at = NOW();
                    """
                ),
                {
                    "code": p["code"],
                    "daily_credits": int(p["daily_credits"]),
                    "monthly_credits": int(p["monthly_credits"]),
                    "features_json": json_dumps(p["features_json"]),
                    "is_active": bool(p["is_active"]),
                },
            )


def json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)


def get_plans() -> List[Dict[str, Any]]:
    ensure_tables()
    eng = _get_engine()
    if eng is None:
        return []
    with eng.begin() as conn:
        rows = conn.execute(text("""SELECT code, daily_credits, monthly_credits, features_json, is_active FROM plans ORDER BY id""")).mappings().all()
        return [dict(r) for r in rows]


def _get_plan(conn, plan_code: str) -> Dict[str, Any]:
    row = conn.execute(
        text("""SELECT code, daily_credits, monthly_credits, features_json, is_active FROM plans WHERE code=:code"""),
        {"code": plan_code},
    ).mappings().first()
    if row:
        return dict(row)
    # fallback to FREE default
    return {"code": "FREE", "daily_credits": 8, "monthly_credits": 0, "features_json": {}, "is_active": True}


def get_or_create_subscription(user_id: int) -> Dict[str, Any]:
    ensure_tables()
    eng = _get_engine()
    if eng is None:
        return {"plan_code": "FREE", "status": "active", "credits_balance": 0, "expires_at": None, "last_refill_at": None}
    with eng.begin() as conn:
        sub = conn.execute(
            text("""SELECT user_id, plan_code, status, started_at, expires_at, credits_balance, last_refill_at FROM subscriptions WHERE user_id=:uid"""),
            {"uid": user_id},
        ).mappings().first()

        if not sub:
            # Create FREE subscription
            plan = _get_plan(conn, "FREE")
            today = _utc_now().date()
            credits = int(plan.get("daily_credits") or 0)
            conn.execute(
                text("""INSERT INTO subscriptions (user_id, plan_code, status, started_at, expires_at, credits_balance, last_refill_at, updated_at)
                         VALUES (:uid, 'FREE', 'active', NOW(), NULL, :credits, :today, NOW())"""),
                {"uid": user_id, "credits": credits, "today": today},
            )
            sub = conn.execute(
                text("""SELECT user_id, plan_code, status, started_at, expires_at, credits_balance, last_refill_at FROM subscriptions WHERE user_id=:uid"""),
                {"uid": user_id},
            ).mappings().first()

        # Refill if needed
        sub = dict(sub)
        sub = _refill_if_needed(conn, sub)
        return sub


def _refill_if_needed(conn, sub: Dict[str, Any]) -> Dict[str, Any]:
    now = _utc_now()
    plan_code = str(sub.get("plan_code") or "FREE").upper()
    status = str(sub.get("status") or "active")
    expires_at = sub.get("expires_at")
    if expires_at and isinstance(expires_at, datetime) and now > expires_at:
        # Expired subscription => downgrade to FREE
        plan_code = "FREE"
        status = "active"
        expires_at = None

    plan = _get_plan(conn, plan_code)
    today = now.date()
    last_refill = sub.get("last_refill_at")

    # FREE: daily refill
    if plan_code == "FREE":
        if last_refill != today:
            credits = int(plan.get("daily_credits") or 0)
            conn.execute(
                text("""UPDATE subscriptions SET plan_code='FREE', status='active', expires_at=NULL, credits_balance=:credits, last_refill_at=:today, updated_at=NOW()
                         WHERE user_id=:uid"""),
                {"uid": sub["user_id"], "credits": credits, "today": today},
            )
            sub["plan_code"] = "FREE"
            sub["status"] = "active"
            sub["expires_at"] = None
            sub["credits_balance"] = credits
            sub["last_refill_at"] = today
        return sub

    # PRO/MAX: monthly refill on first access after last_refill changes month, if active
    if status != "active":
        return sub

    if last_refill is None or (hasattr(last_refill, "month") and hasattr(last_refill, "year") and (last_refill.month != today.month or last_refill.year != today.year)):
        credits = int(plan.get("monthly_credits") or 0)
        conn.execute(
            text("""UPDATE subscriptions SET credits_balance=:credits, last_refill_at=:today, updated_at=NOW()
                     WHERE user_id=:uid"""),
            {"uid": sub["user_id"], "credits": credits, "today": today},
        )
        sub["credits_balance"] = credits
        sub["last_refill_at"] = today

    # Keep plan/status normalized if we downgraded due to expiry
    if sub.get("plan_code") != plan_code or sub.get("status") != status or sub.get("expires_at") != expires_at:
        conn.execute(
            text("""UPDATE subscriptions SET plan_code=:plan_code, status=:status, expires_at=:expires_at, updated_at=NOW()
                     WHERE user_id=:uid"""),
            {"uid": sub["user_id"], "plan_code": plan_code, "status": status, "expires_at": expires_at},
        )
        sub["plan_code"] = plan_code
        sub["status"] = status
        sub["expires_at"] = expires_at

    return sub


def get_billing_summary(user_id: int) -> Dict[str, Any]:
    ensure_tables()
    eng = _get_engine()
    if eng is None:
        return {"plan": {"code": "FREE"}, "subscription": {}, "credits": {"balance": 0}}
    with eng.begin() as conn:
        sub = get_or_create_subscription(user_id)
        plan = _get_plan(conn, str(sub.get("plan_code") or "FREE").upper())
        return {
            "plan": {
                "code": plan["code"],
                "daily_credits": int(plan.get("daily_credits") or 0),
                "monthly_credits": int(plan.get("monthly_credits") or 0),
                "features": plan.get("features_json") or {},
            },
            "subscription": {
                "status": sub.get("status"),
                "started_at": sub.get("started_at"),
                "expires_at": sub.get("expires_at"),
                "last_refill_at": sub.get("last_refill_at"),
            },
            "credits": {"balance": int(sub.get("credits_balance") or 0)},
        }


def consume_credits(user_id: int, action: str, cost: int, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Consume credits atomically. Raises ValueError('INSUFFICIENT_CREDITS') if not enough."""
    ensure_tables()
    eng = _get_engine()
    if eng is None:
        raise ValueError("CREDITS_NOT_CONFIGURED")

    action = str(action or "solve").lower()
    cost = int(cost or 0)
    if cost <= 0:
        return {"ok": True, "balance": 0}

    with eng.begin() as conn:
        sub = get_or_create_subscription(user_id)
        sub = dict(sub)
        sub = _refill_if_needed(conn, sub)
        bal = int(sub.get("credits_balance") or 0)
        if bal < cost:
            raise ValueError("INSUFFICIENT_CREDITS")

        new_bal = bal - cost
        conn.execute(
            text("""UPDATE subscriptions SET credits_balance=:bal, updated_at=NOW() WHERE user_id=:uid"""),
            {"uid": user_id, "bal": new_bal},
        )
        conn.execute(
            text("""INSERT INTO credit_ledger (user_id, action, credits_used, balance_after, meta_json)
                     VALUES (:uid, :action, :used, :after, :meta::jsonb)"""),
            {"uid": user_id, "action": action, "used": cost, "after": new_bal, "meta": json_dumps(meta or {})},
        )
        return {"ok": True, "balance": new_bal}


# -----------------------------
# Razorpay pricing (skeleton)
# -----------------------------
def get_plan_price_inr(plan_code: str) -> int:
    """Return plan price in INR for Razorpay checkout (skeleton, editable via env).
    Payments are not enabled unless RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are set.
    """
    import os
    plan_code = (plan_code or "").upper()
    if plan_code == "PRO":
        return int(os.getenv("RAZORPAY_PRICE_PRO_INR", "199"))
    if plan_code == "MAX":
        return int(os.getenv("RAZORPAY_PRICE_MAX_INR", "399"))
    return 0


def create_payment_order_row(user_id: int, plan_code: str, amount_paise: int, currency: str, razorpay_order_id: str, meta: dict) -> None:
    eng = _get_engine()
    if eng is None:
        return
    with eng.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO payment_orders (user_id, plan_code, amount_paise, currency, razorpay_order_id, status, meta_json)
                VALUES (:user_id, :plan_code, :amount_paise, :currency, :razorpay_order_id, 'created', :meta_json::jsonb)
                ON CONFLICT (razorpay_order_id) DO NOTHING
                """
            ),
            {
                "user_id": user_id,
                "plan_code": plan_code,
                "amount_paise": amount_paise,
                "currency": currency,
                "razorpay_order_id": razorpay_order_id,
                "meta_json": json.dumps(meta or {}),
            },
        )


def mark_payment_paid(user_id: int, plan_code: str, razorpay_order_id: str, razorpay_payment_id: str) -> None:
    """Mark a payment order as paid and activate/renew subscription.

    Production-grade behaviors:
    - Idempotent: if order already marked paid, do nothing.
    - Renewal: extends from max(current_expires, now) + 30 days.
    - Credit refill: sets credits_balance to plan monthly_credits immediately and records a ledger row.
    """
    ensure_tables()
    eng = _get_engine()
    if eng is None:
        return

    plan_code = (plan_code or "").upper()
    if plan_code not in ("PRO", "MAX"):
        plan_code = "PRO"

    now = _now_utc()
    today = now.date()

    with eng.begin() as conn:
        # 1) Update payment order row (idempotent)
        row = conn.execute(
            text("""SELECT status, user_id, plan_code FROM payment_orders WHERE razorpay_order_id=:oid"""),
            {"oid": razorpay_order_id},
        ).mappings().first()

        if row and str(row.get("status") or "") == "paid":
            # Already processed
            return

        conn.execute(
            text(
                """
                UPDATE payment_orders
                   SET status='paid',
                       razorpay_payment_id=:pid,
                       updated_at=NOW()
                 WHERE razorpay_order_id=:oid
                """
            ),
            {"pid": razorpay_payment_id, "oid": razorpay_order_id},
        )

        # 2) Compute new expiry (renewal)
        sub = conn.execute(
            text("""SELECT expires_at FROM subscriptions WHERE user_id=:uid"""),
            {"uid": user_id},
        ).mappings().first()
        current_expires = sub.get("expires_at") if sub else None
        base = current_expires if isinstance(current_expires, datetime) and current_expires > now else now
        expires = base + timedelta(days=30)

        # 3) Set credits immediately to monthly_credits for plan
        plan = _get_plan(conn, plan_code)
        refill_credits = int(plan.get("monthly_credits") or 0)

        conn.execute(
            text(
                """
                INSERT INTO subscriptions (user_id, plan_code, status, started_at, expires_at, credits_balance, last_refill_at, updated_at)
                VALUES (:uid, :plan_code, 'active', NOW(), :expires_at, :credits, :today, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                  plan_code=EXCLUDED.plan_code,
                  status='active',
                  expires_at=:expires_at,
                  credits_balance=:credits,
                  last_refill_at=:today,
                  updated_at=NOW()
                """
            ),
            {"uid": user_id, "plan_code": plan_code, "expires_at": expires, "credits": refill_credits, "today": today},
        )

        # 4) Ledger entry for refill (audit trail)
        conn.execute(
            text(
                """INSERT INTO credit_ledger (user_id, action, credits_used, balance_after, meta_json)
                   VALUES (:uid, :action, :used, :after, :meta::jsonb)"""
            ),
            {
                "uid": user_id,
                "action": "refill",
                "used": 0,
                "after": refill_credits,
                "meta": json_dumps(
                    {
                        "reason": "payment_activation_or_renewal",
                        "plan": plan_code,
                        "razorpay_order_id": razorpay_order_id,
                        "razorpay_payment_id": razorpay_payment_id,
                    }
                ),
            },
        )
