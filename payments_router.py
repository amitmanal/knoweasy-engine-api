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
)

logger = logging.getLogger("knoweasy-engine-api.payments")

router = APIRouter(prefix="/payments", tags=["payments"])


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


@router.post("/create_order")
def create_order(payload: Dict[str, Any], user=Depends(get_current_user)):
    role = (user.get("role") or "").lower()
    if role != "student":
        raise HTTPException(status_code=403, detail="Only students can purchase")

    plan = (payload.get("plan") or "").lower().strip()
    billing_cycle = (payload.get("billing_cycle") or "monthly").lower().strip() or "monthly"
    if billing_cycle not in ("monthly", "yearly"):
        billing_cycle = "monthly"
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

    record_order(int(user["user_id"]), plan, int(amount_paise), currency, order_id, payment_type="subscription", billing_cycle=billing_cycle)

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