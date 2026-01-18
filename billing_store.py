"""billing_store.py

Subscription + AI credits engine for KnowEasy.

This module is designed for production stability:
- No migrations; we use CREATE TABLE IF NOT EXISTS.
- Best-effort: if DATABASE_URL is missing/unavailable, functions return safe defaults.
- Atomic credit consumption via SELECT ... FOR UPDATE inside a transaction.

Terminology
-----------
- "included" credits: credits that reset every cycle (monthly) as part of a plan.
- "booster" credits: add-on credits purchased via booster packs, carry forward.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import text

import payments_store

logger = logging.getLogger("knoweasy-engine-api.billing")


# -----------------------------
# Plan credit allowances (v1)
# -----------------------------

# NOTE: These are deliberately conservative. You can tune later via env.
_DEFAULT_INCLUDED_CREDITS = {
    "free": 300,
    "pro": 4500,
    "max": 12000,
}


def _env_int(name: str, default: int) -> int:
    try:
        v = (os.getenv(name) or "").strip()
        if not v:
            return int(default)
        return int(v)
    except Exception:
        return int(default)


def _included_allowance(plan: str) -> int:
    p = (plan or "free").lower().strip()
    if p not in ("free", "pro", "max"):
        p = "free"
    if p == "free":
        return _env_int("CREDITS_FREE_INCLUDED", _DEFAULT_INCLUDED_CREDITS["free"])
    if p == "pro":
        return _env_int("CREDITS_PRO_INCLUDED", _DEFAULT_INCLUDED_CREDITS["pro"])
    return _env_int("CREDITS_MAX_INCLUDED", _DEFAULT_INCLUDED_CREDITS["max"])


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _cycle_length_days() -> int:
    return _env_int("CREDITS_CYCLE_DAYS", 30)


def ensure_tables() -> None:
    """Ensure billing tables exist (best-effort)."""
    eng = payments_store.get_engine_safe()
    if eng is None:
        return

    ddl = [
        """
        CREATE TABLE IF NOT EXISTS credit_wallets (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL UNIQUE,
            included_credits_balance INT NOT NULL DEFAULT 0,
            booster_credits_balance INT NOT NULL DEFAULT 0,
            cycle_start_at TIMESTAMPTZ,
            cycle_end_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS credit_ledger (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL,
            event_type TEXT NOT NULL,
            source TEXT NOT NULL,
            units INT NOT NULL,
            included_after INT NOT NULL,
            booster_after INT NOT NULL,
            meta_json TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_credit_ledger_user_created ON credit_ledger(user_id, created_at DESC);",
        """
        CREATE TABLE IF NOT EXISTS booster_packs (
            id SERIAL PRIMARY KEY,
            sku TEXT NOT NULL UNIQUE,
            credits_units INT NOT NULL,
            price_paise INT NOT NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_booster_packs_active ON booster_packs(active);",
    ]

    repairs = [
        "ALTER TABLE IF EXISTS credit_wallets ADD COLUMN IF NOT EXISTS included_credits_balance INT NOT NULL DEFAULT 0;",
        "ALTER TABLE IF EXISTS credit_wallets ADD COLUMN IF NOT EXISTS booster_credits_balance INT NOT NULL DEFAULT 0;",
        "ALTER TABLE IF EXISTS credit_wallets ADD COLUMN IF NOT EXISTS cycle_start_at TIMESTAMPTZ;",
        "ALTER TABLE IF EXISTS credit_wallets ADD COLUMN IF NOT EXISTS cycle_end_at TIMESTAMPTZ;",
        "ALTER TABLE IF EXISTS credit_wallets ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();",
        "ALTER TABLE IF EXISTS credit_ledger ADD COLUMN IF NOT EXISTS meta_json TEXT;",
        "ALTER TABLE IF EXISTS booster_packs ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE;",
    ]

    # IMPORTANT: In Postgres, *any* SQL error aborts the whole transaction until ROLLBACK.
    # This function is best-effort and must never poison the connection/transaction.
    # Therefore, we isolate each statement in a SAVEPOINT via begin_nested().
    try:
        with eng.begin() as conn:
            for stmt in ddl:
                try:
                    with conn.begin_nested():
                        conn.execute(text(stmt))
                except Exception:
                    logger.exception("billing_store DDL failed (non-fatal)")

            for stmt in repairs:
                try:
                    with conn.begin_nested():
                        conn.execute(text(stmt))
                except Exception:
                    logger.debug("billing_store schema repair skipped: %s", stmt, exc_info=True)

            # Seed booster packs (idempotent)
            seeds = [
                ("BOOST_MINI", 500, 4900),
                ("BOOST_SMART", 2000, 14900),
                ("BOOST_POWER", 5000, 29900),
            ]
            for sku, units, price in seeds:
                try:
                    with conn.begin_nested():
                        conn.execute(
                            text(
                                """
                                INSERT INTO booster_packs (sku, credits_units, price_paise, active)
                                VALUES (:sku, :units, :price, TRUE)
                                ON CONFLICT (sku) DO UPDATE SET
                                    credits_units=EXCLUDED.credits_units,
                                    price_paise=EXCLUDED.price_paise,
                                    active=TRUE
                                """
                            ),
                            {"sku": sku, "units": int(units), "price": int(price)},
                        )
                except Exception:
                    logger.exception("billing_store booster seed failed (non-fatal)")
    except Exception:
        logger.exception("billing_store.ensure_tables failed (non-fatal)")


def get_wallet(user_id: int, plan: str) -> Dict[str, Any]:
    """Return wallet; auto-create and auto-reset cycle if needed."""
    ensure_tables()
    eng = payments_store.get_engine_safe()

    def _wallet_payload(included_balance: int, booster_balance: int, cycle_start, cycle_end, allowance: int) -> Dict[str, Any]:
        """Return a backward+forward compatible wallet payload.

        Frontend compatibility:
        - Newer UI reads *_credits_balance + cycle_* fields.
        - Older UI expects included_total / included_remaining / booster_remaining / resets_on.
        We return both so we can evolve the UI without breaking production.
        """
        return {
            # Canonical v1 fields
            "included_credits_balance": int(included_balance),
            "booster_credits_balance": int(booster_balance),
            "cycle_start_at": cycle_start,
            "cycle_end_at": cycle_end,

            # Back-compat convenience fields
            "included_total": int(allowance),
            "included_remaining": int(included_balance),
            "booster_remaining": int(booster_balance),
            "resets_on": cycle_end,
        }
    if eng is None:
        # safe defaults when DB missing
        allowance = _included_allowance(plan)
        cs = _now_utc()
        ce = cs + timedelta(days=_cycle_length_days())
        return _wallet_payload(allowance, 0, cs, ce, allowance)

    now = _now_utc()
    cycle_days = _cycle_length_days()
    allowance = _included_allowance(plan)

    try:
        with eng.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT user_id, included_credits_balance, booster_credits_balance, cycle_start_at, cycle_end_at
                    FROM credit_wallets
                    WHERE user_id=:user_id
                    LIMIT 1
                    """
                ),
                {"user_id": int(user_id)},
            ).mappings().first()

            if not row:
                cycle_start = now
                cycle_end = now + timedelta(days=cycle_days)
                conn.execute(
                    text(
                        """
                        INSERT INTO credit_wallets (user_id, included_credits_balance, booster_credits_balance, cycle_start_at, cycle_end_at, updated_at)
                        VALUES (:user_id, :included, 0, :cs, :ce, NOW())
                        ON CONFLICT (user_id) DO NOTHING
                        """
                    ),
                    {"user_id": int(user_id), "included": int(allowance), "cs": cycle_start, "ce": cycle_end},
                )
                _append_ledger(conn, user_id, "reset", "plan", int(allowance), int(allowance), 0, {"reason": "wallet_created"})
                return _wallet_payload(int(allowance), 0, cycle_start, cycle_end, allowance)

            included = int(row.get("included_credits_balance") or 0)
            booster = int(row.get("booster_credits_balance") or 0)
            cs = row.get("cycle_start_at")
            ce = row.get("cycle_end_at")

            # Normalize tz
            if cs and cs.tzinfo is None:
                cs = cs.replace(tzinfo=timezone.utc)
            if ce and ce.tzinfo is None:
                ce = ce.replace(tzinfo=timezone.utc)

            # If cycle missing or ended, reset included credits
            if (not cs) or (not ce) or (ce <= now):
                cycle_start = now
                cycle_end = now + timedelta(days=cycle_days)
                included = int(allowance)
                conn.execute(
                    text(
                        """
                        UPDATE credit_wallets
                        SET included_credits_balance=:included,
                            cycle_start_at=:cs,
                            cycle_end_at=:ce,
                            updated_at=NOW()
                        WHERE user_id=:user_id
                        """
                    ),
                    {"user_id": int(user_id), "included": int(included), "cs": cycle_start, "ce": cycle_end},
                )
                _append_ledger(conn, user_id, "reset", "plan", int(included), int(included), int(booster), {"reason": "cycle_reset"})
                return _wallet_payload(int(included), int(booster), cycle_start, cycle_end, allowance)

            return _wallet_payload(int(included), int(booster), cs, ce, allowance)

    except Exception:
        logger.exception("get_wallet failed")
        cs = now
        ce = now + timedelta(days=cycle_days)
        return _wallet_payload(allowance, 0, cs, ce, allowance)


def consume_credits(user_id: int, plan: str, units: int, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Atomically consume credits. Returns balances; raises ValueError on insufficient credits."""
    ensure_tables()
    eng = payments_store.get_engine_safe()
    if units <= 0:
        return {"ok": True, "consumed": 0, **get_wallet(user_id, plan)}

    if eng is None:
        # DB missing: allow but don't track
        w = get_wallet(user_id, plan)
        return {"ok": True, "consumed": int(units), **w}

    meta = meta or {}
    now = _now_utc()

    try:
        with eng.begin() as conn:
            # Ensure wallet exists and cycle is current
            _ = get_wallet(user_id, plan)

            row = conn.execute(
                text(
                    """
                    SELECT included_credits_balance, booster_credits_balance
                    FROM credit_wallets
                    WHERE user_id=:user_id
                    FOR UPDATE
                    """
                ),
                {"user_id": int(user_id)},
            ).mappings().first()

            if not row:
                raise ValueError("WALLET_MISSING")

            included = int(row.get("included_credits_balance") or 0)
            booster = int(row.get("booster_credits_balance") or 0)
            total = included + booster

            if total < int(units):
                raise ValueError("INSUFFICIENT_CREDITS")

            consume_from_included = min(included, int(units))
            remaining = int(units) - consume_from_included
            consume_from_booster = remaining

            included_after = included - consume_from_included
            booster_after = booster - consume_from_booster

            conn.execute(
                text(
                    """
                    UPDATE credit_wallets
                    SET included_credits_balance=:included,
                        booster_credits_balance=:booster,
                        updated_at=NOW()
                    WHERE user_id=:user_id
                    """
                ),
                {"user_id": int(user_id), "included": int(included_after), "booster": int(booster_after)},
            )

            meta2 = {**meta, "ts": now.isoformat(), "units": int(units), "from_included": int(consume_from_included), "from_booster": int(consume_from_booster)}
            _append_ledger(conn, user_id, "consume", "ai", -int(units), int(included_after), int(booster_after), meta2)

            # fetch cycle fields
            cycle = conn.execute(
                text("SELECT cycle_start_at, cycle_end_at FROM credit_wallets WHERE user_id=:user_id"),
                {"user_id": int(user_id)},
            ).mappings().first() or {}

            return {
                "ok": True,
                "consumed": int(units),
                "included_credits_balance": int(included_after),
                "booster_credits_balance": int(booster_after),
                "cycle_start_at": cycle.get("cycle_start_at"),
                "cycle_end_at": cycle.get("cycle_end_at"),
            }
    except ValueError:
        raise
    except Exception:
        logger.exception("consume_credits failed")
        # Fail-safe: do not block learning due to DB issue
        w = get_wallet(user_id, plan)
        return {"ok": True, "consumed": int(units), **w}


def grant_booster_credits(user_id: int, plan: str, units: int, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    ensure_tables()
    eng = payments_store.get_engine_safe()
    if units <= 0:
        return {"ok": True, **get_wallet(user_id, plan)}
    if eng is None:
        return {"ok": True, **get_wallet(user_id, plan)}

    meta = meta or {}
    try:
        with eng.begin() as conn:
            _ = get_wallet(user_id, plan)
            row = conn.execute(
                text(
                    """
                    SELECT included_credits_balance, booster_credits_balance
                    FROM credit_wallets
                    WHERE user_id=:user_id
                    FOR UPDATE
                    """
                ),
                {"user_id": int(user_id)},
            ).mappings().first()
            if not row:
                raise ValueError("WALLET_MISSING")
            included = int(row.get("included_credits_balance") or 0)
            booster = int(row.get("booster_credits_balance") or 0)
            booster_after = booster + int(units)
            conn.execute(
                text(
                    """
                    UPDATE credit_wallets
                    SET booster_credits_balance=:booster, updated_at=NOW()
                    WHERE user_id=:user_id
                    """
                ),
                {"user_id": int(user_id), "booster": int(booster_after)},
            )
            _append_ledger(conn, user_id, "grant", "booster", int(units), int(included), int(booster_after), meta)
            cycle = conn.execute(
                text("SELECT cycle_start_at, cycle_end_at FROM credit_wallets WHERE user_id=:user_id"),
                {"user_id": int(user_id)},
            ).mappings().first() or {}
            return {
                "ok": True,
                "included_credits_balance": int(included),
                "booster_credits_balance": int(booster_after),
                "cycle_start_at": cycle.get("cycle_start_at"),
                "cycle_end_at": cycle.get("cycle_end_at"),
            }
    except Exception:
        logger.exception("grant_booster_credits failed")
        return {"ok": True, **get_wallet(user_id, plan)}


def reset_included_credits(user_id: int, plan: str, reason: str = "plan_change") -> Dict[str, Any]:
    """Force-reset included credits to the current plan allowance and restart cycle.

    Called after subscription activation/upgrade.
    """
    ensure_tables()
    eng = payments_store.get_engine_safe()
    allowance = _included_allowance(plan)
    now = _now_utc()
    cycle_days = _cycle_length_days()

    if eng is None:
        return {
            "included_credits_balance": int(allowance),
            "booster_credits_balance": 0,
            "cycle_start_at": now,
            "cycle_end_at": now + timedelta(days=cycle_days),
        }

    try:
        with eng.begin() as conn:
            # ensure exists
            _ = get_wallet(user_id, plan)

            # lock row
            row = conn.execute(
                text(
                    """
                    SELECT included_credits_balance, booster_credits_balance
                    FROM credit_wallets
                    WHERE user_id=:user_id
                    FOR UPDATE
                    """
                ),
                {"user_id": int(user_id)},
            ).mappings().first()

            booster = int((row or {}).get("booster_credits_balance") or 0)

            cs = now
            ce = now + timedelta(days=cycle_days)
            conn.execute(
                text(
                    """
                    UPDATE credit_wallets
                    SET included_credits_balance=:included,
                        cycle_start_at=:cs,
                        cycle_end_at=:ce,
                        updated_at=NOW()
                    WHERE user_id=:user_id
                    """
                ),
                {"user_id": int(user_id), "included": int(allowance), "cs": cs, "ce": ce},
            )
            _append_ledger(conn, user_id, "reset", "plan", int(allowance), int(allowance), int(booster), {"reason": reason})

            return {
                "included_credits_balance": int(allowance),
                "booster_credits_balance": int(booster),
                "cycle_start_at": cs,
                "cycle_end_at": ce,
            }
    except Exception:
        logger.exception("reset_included_credits failed")
        return get_wallet(user_id, plan)


def list_booster_packs() -> list[Dict[str, Any]]:
    ensure_tables()
    eng = payments_store.get_engine_safe()
    if eng is None:
        return [
            {"sku": "BOOST_MINI", "credits_units": 500, "price_paise": 4900, "active": True},
            {"sku": "BOOST_SMART", "credits_units": 2000, "price_paise": 14900, "active": True},
            {"sku": "BOOST_POWER", "credits_units": 5000, "price_paise": 29900, "active": True},
        ]
    try:
        with eng.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT sku, credits_units, price_paise, active
                    FROM booster_packs
                    WHERE active=TRUE
                    ORDER BY price_paise ASC
                    """
                )
            ).mappings().all()
            return [dict(r) for r in rows]
    except Exception:
        logger.exception("list_booster_packs failed")
        return []


def get_booster_pack(sku: str) -> Optional[Dict[str, Any]]:
    """
    Return a single active booster pack by SKU.

    The lookup is case-insensitive. Returns None if the SKU is not found or
    the booster pack is inactive. This helper is used by the billing router
    to validate the canonical price and units of a booster purchase on the
    server side.
    """
    if not sku:
        return None
    sku_norm = str(sku).strip().upper()
    try:
        packs = list_booster_packs()
        for pack in packs:
            if str(pack.get("sku") or "").strip().upper() == sku_norm:
                return pack
        return None
    except Exception:
        # Safe fallback: no pack found
        return None


def _append_ledger(conn, user_id: int, event_type: str, source: str, units: int, included_after: int, booster_after: int, meta: Dict[str, Any]) -> None:
    """Best-effort credit ledger write.

    Important: If the INSERT fails (schema drift, missing table/column, etc.) Postgres
    marks the *whole* transaction as aborted. We must isolate this write in a SAVEPOINT
    so booster/plan flows don't get broken by a non-critical ledger failure.
    """
    try:
        # begin_nested() creates a SAVEPOINT on Postgres.
        # If the ledger insert fails, only the savepoint is rolled back.
        with conn.begin_nested():
            conn.execute(
                text(
                    """
                    INSERT INTO credit_ledger(user_id, event_type, source, units, included_after, booster_after, meta_json)
                    VALUES (:user_id, :event_type, :source, :units, :included_after, :booster_after, :meta_json)
                    """
                ),
                {
                    "user_id": int(user_id),
                    "event_type": str(event_type),
                    "source": str(source),
                    "units": int(units),
                    "included_after": int(included_after),
                    "booster_after": int(booster_after),
                    "meta_json": json.dumps(meta or {}, ensure_ascii=False),
                },
            )
    except Exception:
        # ledger must never break business flow
        logger.debug("credit ledger append failed (ignored)", exc_info=True)
