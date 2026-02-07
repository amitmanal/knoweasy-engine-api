"""payments_router.py

Razorpay wiring (orders + verify) + subscription activation.

Endpoints
- POST /payments/create_order
- POST /payments/verify
- GET  /payments/me

Notes
- Uses Razorpay Orders API via HTTPS + Basic Auth (key_id, key_secret)
- Signature verification: HMAC_SHA256(secret, order_id + '|' + payment_id)
- Duration defaults: PRO=30 days, MAX=30 days (adjust later)
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Any, Dict, Optional
from datetime import datetime, timezone

import requests
from fastapi import APIRouter, Depends, HTTPException

from phase1_router import get_current_user
import billing_store
from payments_store import (
    get_subscription,
    mark_payment_paid,
    record_order,
    upsert_subscription,
    get_order_record,
    list_payments,
)

logger = logging.getLogger("knoweasy-engine-api.payments")

router = APIRouter(prefix="/payments", tags=["payments"])


def _plan_rank(plan: str) -> int:
    p = (plan or "free").lower().strip() or "free"
    if p == "max":
        return 2
    if p == "pro":
        return 1
    return 0


def _is_active_sub(sub: Dict[str, Any]) -> bool:
    try:
        status = str(sub.get("status") or "").lower().strip()
        exp = sub.get("expires_at")
        if not exp:
            return False
        dt = None
        if isinstance(exp, datetime):
            dt = exp
        else:
            dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return status == "active" and dt.timestamp() > datetime.now(timezone.utc).timestamp()
    except Exception:
        return False


def _env_int(name: str, default: int) -> int:
    try:
        v = os.getenv(name)
        if v is None or str(v).strip() == "":
            return int(default)
        return int(str(v).strip())
    except Exception:
        return int(default)


def _get_razorpay_keys() -> tuple[str, str]:
    key_id = (os.getenv("RAZORPAY_KEY_ID") or "").strip()
    key_secret = (os.getenv("RAZORPAY_KEY_SECRET") or "").strip()
    if not key_id or not key_secret:
        raise HTTPException(status_code=503, detail="Payments not enabled")
    return key_id, key_secret


def _plan_to_amount_paise(plan: str, billing_cycle: str) -> int:
    # Safety-first defaults: ₹1 if env not set.
    plan = (plan or "").lower().strip()
    bc = (billing_cycle or "monthly").lower().strip()
    if plan == "pro":
        if bc == "yearly":
            return _env_int("PLAN_PRO_AMOUNT_PAISE_YEARLY", _env_int("PLAN_PRO_AMOUNT_PAISE", 100))
        return _env_int("PLAN_PRO_AMOUNT_PAISE_MONTHLY", _env_int("PLAN_PRO_AMOUNT_PAISE", 100))
    if plan == "max":
        if bc == "yearly":
            return _env_int("PLAN_MAX_AMOUNT_PAISE_YEARLY", _env_int("PLAN_MAX_AMOUNT_PAISE", 100))
        return _env_int("PLAN_MAX_AMOUNT_PAISE_MONTHLY", _env_int("PLAN_MAX_AMOUNT_PAISE", 100))
    raise HTTPException(status_code=400, detail="Invalid plan")


def _plan_duration_days(plan: str, billing_cycle: str) -> int:
    plan = (plan or "").lower().strip()
    bc = (billing_cycle or "monthly").lower().strip()
    if plan == "pro":
        if bc == "yearly":
            return _env_int("PLAN_PRO_DAYS_YEARLY", 365)
        return _env_int("PLAN_PRO_DAYS_MONTHLY", 30)
    if plan == "max":
        if bc == "yearly":
            return _env_int("PLAN_MAX_DAYS_YEARLY", 365)
        return _env_int("PLAN_MAX_DAYS_MONTHLY", 30)
    raise HTTPException(status_code=400, detail="Invalid plan")


@router.get("/me")
def payments_me(user=Depends(get_current_user)):
    uid = int(user["user_id"])
    sub = get_subscription(uid)
    plan = (sub.get("plan") or "free").lower().strip() or "free"
    wallet = billing_store.get_wallet(uid, plan)
    return {"ok": True, "subscription": sub, "wallet": wallet}


@router.get("/history")
def payments_history(limit: int = 50, user=Depends(get_current_user)):
    """Student-only: list recent payment attempts (paid/pending/failed).

    This powers the frontend Payment History page.
    If a user has an active subscription but no payment rows (legacy/manual
    activation), we also include a single synthetic entry so the UI doesn't
    look broken.
    """
    role = (user.get("role") or "").lower()
    if role != "student":
        raise HTTPException(status_code=403, detail="Only students can view payment history")

    uid = int(user["user_id"])
    limit = max(1, min(int(limit or 50), 100))

    rows = list_payments(uid, limit=limit)

    # --- TRUST POLISH (display-only cleanup) ---
    # Goal: keep history confidence-building without changing payment logic.
    # Rules:
    # - Always show PAID
    # - Show PENDING only if created < 60 minutes ago
    # - Hide legacy/test ₹1 subscription rows (sandbox artifacts)
    # - Normalize status strings to: PAID | PENDING | FAILED
    now_utc = datetime.now(timezone.utc)
    cleaned: list[dict[str, Any]] = []
    for r in rows:
        # Normalize created_at to datetime for filtering
        ca_dt: Optional[datetime] = None
        ca = r.get("created_at")
        if isinstance(ca, datetime):
            ca_dt = ca
        elif isinstance(ca, str) and ca.strip():
            try:
                ca_dt = datetime.fromisoformat(ca.replace("Z", "+00:00"))
            except Exception:
                ca_dt = None
        if ca_dt and ca_dt.tzinfo is None:
            ca_dt = ca_dt.replace(tzinfo=timezone.utc)

        # Normalize status to a small set
        raw_status = str(r.get("status") or "").lower().strip()
        if raw_status in ("paid", "captured", "success", "succeeded"):
            norm_status = "PAID"
        elif raw_status in ("created", "pending", "authorized"):
            norm_status = "PENDING"
        else:
            norm_status = "FAILED"
        r["status"] = norm_status

        # Mark ₹1 subscription rows as TEST instead of hiding (trust: never show empty history after payment)
        pay_type = str(r.get("payment_type") or "").lower().strip()
        amt = r.get("amount_paise")
        try:
            amt_i = int(amt) if amt is not None else None
        except Exception:
            amt_i = None
        if pay_type == "subscription" and (amt_i is not None and amt_i <= 100):
            # Keep it visible, but clearly label it as a test/sandbox price.
            r["is_test_payment"] = True
            existing_note = str(r.get("note") or "").strip()
            r["note"] = (existing_note + (" | " if existing_note else "") + "Test / sandbox price").strip()

        # Hide old pending rows (>60 minutes)
        if norm_status == "PENDING" and ca_dt is not None:
            age_sec = (now_utc - ca_dt.astimezone(timezone.utc)).total_seconds()
            if age_sec > 60 * 60:
                continue

        cleaned.append(r)

    rows = cleaned

    # Normalize datetimes to ISO for JSON
    for r in rows:
        ca = r.get("created_at")
        if isinstance(ca, datetime):
            r["created_at"] = ca.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    # Legacy fallback: if subscription exists but no payment rows
    if not rows:
        sub = get_subscription(uid)
        if sub and (sub.get("plan") or "free").lower() != "free":
            expires_at = sub.get("expires_at")
            created_at = sub.get("created_at")
            if isinstance(expires_at, datetime):
                expires_at = expires_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            if isinstance(created_at, datetime):
                created_at = created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            rows = [
                {
                    "created_at": created_at,
                    "plan": sub.get("plan"),
                    "payment_type": "subscription",
                    "billing_cycle": sub.get("billing_cycle"),
                    "booster_sku": None,
                    "amount_paise": None,
                    "currency": "INR",
                    "status": "ACTIVE",
                    "razorpay_order_id": None,
                    "razorpay_payment_id": None,
                    "note": "Active subscription (legacy activation)",
                    "expires_at": expires_at,
                }
            ]

    return {"ok": True, "items": rows}


@router.post("/create_order")
def create_order(payload: Dict[str, Any], user=Depends(get_current_user)):
    role = (user.get("role") or "").lower()
    if role != "student":
        raise HTTPException(status_code=403, detail="Only students can purchase")

    uid = int(user["user_id"])

    plan = (payload.get("plan") or "").lower().strip()
    billing_cycle = (payload.get("billing_cycle") or "monthly").lower().strip() or "monthly"
    if billing_cycle not in ("monthly", "yearly"):
        billing_cycle = "monthly"
    # Phase 1 (trust rules): one active plan at a time.
    # - No cycle-switch payments while a plan is active (avoids double-payment confusion).
    # - Allow upgrades (Free->Pro/Max, Pro->Max) only.
    # - Block "buy same plan again" while active (no stacking).
    # - Block downgrades while active.
    cur = get_subscription(uid)
    cur_plan = (cur.get("plan") or "free").lower().strip() or "free"
    cur_cycle = (cur.get("billing_cycle") or "").lower().strip() or ""

    if _is_active_sub(cur):
        if cur_cycle and billing_cycle != cur_cycle:
            raise HTTPException(
                status_code=409,
                detail="Billing cycle change applies at next renewal. To avoid double payments, your current cycle is locked for now.",
            )
        if _plan_rank(plan) < _plan_rank(cur_plan):
            raise HTTPException(status_code=409, detail="Downgrade is not available while your plan is active.")
        if _plan_rank(plan) == _plan_rank(cur_plan):
            raise HTTPException(status_code=409, detail="You already have this plan active. No need to buy it again.")

    amount_paise = _plan_to_amount_paise(plan, billing_cycle)
    currency = (payload.get("currency") or "INR").upper().strip() or "INR"

    key_id, key_secret = _get_razorpay_keys()

    # Create an order in Razorpay
    # https://razorpay.com/docs/api/orders/
    order_payload = {
        "amount": int(amount_paise),
        "currency": currency,
        "receipt": f"knoweasy_{user['user_id']}_{plan}",
        "notes": {"user_id": str(user["user_id"]), "plan": plan, "billing_cycle": billing_cycle, "type": "subscription"},
    }

    try:
        resp = requests.post(
            "https://api.razorpay.com/v1/orders",
            auth=(key_id, key_secret),
            json=order_payload,
            timeout=20,
        )
    except Exception as e:
        logger.exception("Razorpay order create failed")
        raise HTTPException(status_code=502, detail="Razorpay request failed") from e

    if resp.status_code >= 400:
        logger.error("Razorpay create order error: %s %s", resp.status_code, resp.text)
        raise HTTPException(status_code=502, detail="Razorpay error")

    data = resp.json() if resp.content else {}
    order_id = data.get("id")
    if not order_id:
        raise HTTPException(status_code=502, detail="Razorpay order id missing")

    record_order(uid, plan, int(amount_paise), currency, order_id, payment_type="subscription", billing_cycle=billing_cycle)

    return {
        "ok": True,
        "key_id": key_id,
        "order_id": order_id,
        "amount": int(amount_paise),
        "amount_paise": int(amount_paise),
        "currency": currency,
        "plan": plan,
        "billing_cycle": billing_cycle,
    }


@router.post("/verify")
def verify_payment(payload: Dict[str, Any], user=Depends(get_current_user)):
    role = (user.get("role") or "").lower()
    if role != "student":
        raise HTTPException(status_code=403, detail="Only students can verify")

    plan = (payload.get("plan") or "").lower().strip()
    billing_cycle = (payload.get("billing_cycle") or "monthly").lower().strip() or "monthly"
    if billing_cycle not in ("monthly", "yearly"):
        billing_cycle = "monthly"
    razorpay_order_id = (payload.get("razorpay_order_id") or "").strip()
    razorpay_payment_id = (payload.get("razorpay_payment_id") or "").strip()
    razorpay_signature = (payload.get("razorpay_signature") or "").strip()

    if not (plan and razorpay_order_id and razorpay_payment_id and razorpay_signature):
        raise HTTPException(status_code=400, detail="Missing fields")

    _, key_secret = _get_razorpay_keys()

    # Verify signature
    msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
    expected = hmac.new(key_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, razorpay_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    # ---------------------------------------------------------------------
    # Additional server-side verification beyond the Razorpay signature.
    # Fetch the previously recorded order and ensure it matches the user,
    # plan, billing cycle and amount. Without this, a malicious client
    # could tamper with the payload or pay a different amount.
    # ---------------------------------------------------------------------
    order = get_order_record(int(user["user_id"]), razorpay_order_id)
    if not order:
        raise HTTPException(status_code=400, detail="Order not found or does not belong to user")

    # Idempotency / retries:
    # If the client retries verification (network glitches, double-click, refresh),
    # do NOT throw a scary error. If the order is already marked paid, simply
    # return the current subscription state.
    status = str(order.get("status") or "").lower().strip()
    if status and status != "created":
        if status == "paid":
            sub = get_subscription(int(user["user_id"]))
            return {"ok": True, "subscription": sub, "note": "already_verified"}
        raise HTTPException(status_code=400, detail="Order already processed")

    # Verify plan and billing cycle match what was originally requested
    orig_plan = str(order.get("plan") or "").lower().strip()
    orig_bc = str(order.get("billing_cycle") or "monthly").lower().strip() or "monthly"
    if orig_plan != plan or orig_bc != billing_cycle:
        raise HTTPException(status_code=400, detail="Plan or billing cycle mismatch")

    # Verify the amount charged matches the configured price for the plan
    expected_amount = _plan_to_amount_paise(plan, billing_cycle)
    try:
        orig_amount = int(order.get("amount_paise") or 0)
    except Exception:
        orig_amount = 0
    if orig_amount != expected_amount:
        raise HTTPException(status_code=400, detail="Payment amount mismatch")

    # Finally mark the order as paid and activate the subscription
    mark_payment_paid(int(user["user_id"]), razorpay_order_id, razorpay_payment_id, razorpay_signature)

    duration_days = _plan_duration_days(plan, billing_cycle)
    sub = upsert_subscription(int(user["user_id"]), plan, duration_days, billing_cycle=billing_cycle)
    # reset wallet included credits on activation
    try:
        billing_store.reset_included_credits(int(user["user_id"]), plan, reason=f"subscription_{billing_cycle}")
    except Exception:
        pass

    return {"ok": True, "subscription": sub}