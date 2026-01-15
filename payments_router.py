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
from payments_store import get_subscription, mark_payment_paid, record_order, upsert_subscription

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


def _plan_to_amount_paise(plan: str) -> int:
    # Safety-first defaults: ₹1 if env not set.
    plan = (plan or "").lower().strip()
    if plan == "pro":
        return _env_int("PLAN_PRO_AMOUNT_PAISE", 100)
    if plan == "max":
        return _env_int("PLAN_MAX_AMOUNT_PAISE", 100)
    raise HTTPException(status_code=400, detail="Invalid plan")


def _plan_duration_days(plan: str) -> int:
    plan = (plan or "").lower().strip()
    if plan == "pro":
        return _env_int("PLAN_PRO_DAYS", 30)
    if plan == "max":
        return _env_int("PLAN_MAX_DAYS", 30)
    raise HTTPException(status_code=400, detail="Invalid plan")


@router.get("/me")
def payments_me(user=Depends(get_current_user)):
    # Always returns something.
    sub = get_subscription(int(user["user_id"]))
    return {"ok": True, "subscription": sub}


@router.post("/create_order")
def create_order(payload: Dict[str, Any], user=Depends(get_current_user)):
    role = (user.get("role") or "").lower()
    if role != "student":
        raise HTTPException(status_code=403, detail="Only students can purchase")

    plan = (payload.get("plan") or "").lower().strip()
    amount_paise = _plan_to_amount_paise(plan)
    currency = (payload.get("currency") or "INR").upper().strip() or "INR"

    key_id, key_secret = _get_razorpay_keys()

    # Create an order in Razorpay
    # https://razorpay.com/docs/api/orders/
    order_payload = {
        "amount": int(amount_paise),
        "currency": currency,
        "receipt": f"knoweasy_{user['user_id']}_{plan}",
        "notes": {"user_id": str(user["user_id"]), "plan": plan},
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

    record_order(int(user["user_id"]), plan, int(amount_paise), currency, order_id)

    return {
        "ok": True,
        "key_id": key_id,
        "order_id": order_id,
        "amount": int(amount_paise),
        "currency": currency,
        "plan": plan,
    }


@router.post("/verify")
def verify_payment(payload: Dict[str, Any], user=Depends(get_current_user)):
    role = (user.get("role") or "").lower()
    if role != "student":
        raise HTTPException(status_code=403, detail="Only students can verify")

    plan = (payload.get("plan") or "").lower().strip()
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

    mark_payment_paid(int(user["user_id"]), razorpay_order_id, razorpay_payment_id, razorpay_signature)

    duration_days = _plan_duration_days(plan)
    sub = upsert_subscription(int(user["user_id"]), plan, duration_days)

    return {"ok": True, "subscription": sub}
