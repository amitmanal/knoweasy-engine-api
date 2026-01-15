"""payments_router.py

Razorpay wiring (orders + verify) + subscription activation + booster packs.

Endpoints
- POST /payments/create_order
- POST /payments/verify
- GET  /payments/me
- GET  /payments/booster_packs

Notes
- Uses Razorpay Orders API via HTTPS + Basic Auth (key_id, key_secret)
- Signature verification: HMAC_SHA256(secret, order_id + '|' + payment_id)
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
    get_payment_by_order_id,
    mark_payment_paid,
    record_order,
    upsert_subscription,
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


def _pricing_paise(plan: str, billing_cycle: str) -> int:
    """Returns full price (not upgrade difference)."""
    plan = (plan or "").lower().strip()
    bc = (billing_cycle or "monthly").lower().strip()

    if plan == "pro":
        if bc == "yearly":
            return _env_int("PLAN_PRO_AMOUNT_PAISE_YEARLY", _env_int("PLAN_PRO_AMOUNT_PAISE", 24900))
        return _env_int("PLAN_PRO_AMOUNT_PAISE", 24900)

    if plan == "max":
        if bc == "yearly":
            return _env_int("PLAN_MAX_AMOUNT_PAISE_YEARLY", _env_int("PLAN_MAX_AMOUNT_PAISE", 49900))
        return _env_int("PLAN_MAX_AMOUNT_PAISE", 49900)

    raise HTTPException(status_code=400, detail="Invalid plan")


def _create_razorpay_order(amount_paise: int, currency: str, receipt: str, notes: Dict[str, Any]) -> Dict[str, Any]:
    key_id, key_secret = _get_razorpay_keys()
    url = "https://api.razorpay.com/v1/orders"
    payload = {
        "amount": int(amount_paise),
        "currency": currency,
        "receipt": receipt,
        "notes": notes or {},
    }
    try:
        r = requests.post(url, json=payload, auth=(key_id, key_secret), timeout=20)
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Razorpay error: {r.text}")
        return r.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Payment gateway error: {e}")


@router.get("/booster_packs")
def booster_packs():
    """Returns booster SKUs/prices/credits from server config."""
    packs = billing_store.list_booster_packs()
    # keep response minimal + stable
    return {
        "packs": [
            {
                "sku": p["sku"],
                "credits": p["credits"],
                "amount_paise": p["amount_paise"],
            }
            for p in packs
        ]
    }


@router.post("/create_order")
def create_order(body: Dict[str, Any], user=Depends(get_current_user)):
    """Create a Razorpay order for subscription (pro/max) or booster packs."""
    plan = (body.get("plan") or "").lower().strip()
    billing_cycle = (body.get("billing_cycle") or "monthly").lower().strip()

    if not plan:
        raise HTTPException(status_code=400, detail="Missing plan")

    user_id = user["user_id"]
    email = user.get("email")

    # ----- Booster flow -----
    if plan.startswith("boost_"):
        packs = billing_store.list_booster_packs()
        pack = next((p for p in packs if p["sku"].lower() == plan), None)
        if not pack:
            raise HTTPException(status_code=400, detail="Invalid booster pack")

        amount_paise = int(pack["amount_paise"])
        currency = "INR"
        receipt = f"booster_{plan}_{user_id}"
        rp_order = _create_razorpay_order(
            amount_paise=amount_paise,
            currency=currency,
            receipt=receipt,
            notes={"user_id": user_id, "email": email, "payment_type": "booster", "booster_sku": plan},
        )
        record_order(
            user_id=user_id,
            plan="booster",
            amount_paise=amount_paise,
            currency=currency,
            razorpay_order_id=rp_order.get("id"),
            payment_type="booster",
            billing_cycle=None,
            booster_sku=plan,
        )
        return {
            "key_id": os.getenv("RAZORPAY_KEY_ID"),
            "order_id": rp_order.get("id"),
            "amount_paise": amount_paise,
            "currency": currency,
            "display": {"kind": "booster", "sku": plan, "credits": pack["credits"]},
        }

    # ----- Subscription flow (pro/max) -----
    if plan not in ("pro", "max"):
        raise HTTPException(status_code=400, detail="Invalid plan")

    sub = get_subscription(user_id)

    # Protect against re-paying for current plan
    current_plan = (sub.get("plan") if sub else None) or "free"
    is_active = bool(sub and sub.get("is_active"))
    if is_active:
        if current_plan == plan:
            raise HTTPException(status_code=409, detail="Already on this plan")
        if current_plan == "max" and plan == "pro":
            raise HTTPException(status_code=400, detail="Downgrade not supported")

    full_amount = _pricing_paise(plan, billing_cycle)

    # Upgrade difference: PRO -> MAX charges only the difference (same cycle).
    if is_active and current_plan == "pro" and plan == "max":
        pro_amt = _pricing_paise("pro", billing_cycle)
        diff = max(int(full_amount - pro_amt), 100)  # never 0; keep >= ₹1
        amount_paise = diff
        pay_kind = "upgrade_diff"
    else:
        amount_paise = full_amount
        pay_kind = "subscription"

    currency = "INR"
    receipt = f"sub_{plan}_{billing_cycle}_{user_id}"
    rp_order = _create_razorpay_order(
        amount_paise=amount_paise,
        currency=currency,
        receipt=receipt,
        notes={"user_id": user_id, "email": email, "payment_type": "subscription", "plan": plan, "billing_cycle": billing_cycle, "kind": pay_kind},
    )
    record_order(
        user_id=user_id,
        plan=plan,
        amount_paise=amount_paise,
        currency=currency,
        razorpay_order_id=rp_order.get("id"),
        payment_type="subscription",
        billing_cycle=billing_cycle,
        booster_sku=None,
    )
    return {
        "key_id": os.getenv("RAZORPAY_KEY_ID"),
        "order_id": rp_order.get("id"),
        "amount_paise": amount_paise,
        "currency": currency,
        "display": {"kind": pay_kind, "plan": plan, "billing_cycle": billing_cycle},
    }


@router.post("/verify")
def verify(body: Dict[str, Any], user=Depends(get_current_user)):
    razorpay_order_id = (body.get("razorpay_order_id") or "").strip()
    razorpay_payment_id = (body.get("razorpay_payment_id") or "").strip()
    razorpay_signature = (body.get("razorpay_signature") or "").strip()

    if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
        raise HTTPException(status_code=400, detail="Missing Razorpay fields")

    key_id, key_secret = _get_razorpay_keys()

    # Verify signature
    msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
    expected = hmac.new(key_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    if expected != razorpay_signature:
        raise HTTPException(status_code=400, detail="Invalid payment signature")

    user_id = user["user_id"]
    pay = get_payment_by_order_id(razorpay_order_id)
    if not pay or pay.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Order not found")

    # Mark paid
    mark_payment_paid(razorpay_order_id, razorpay_payment_id)

    payment_type = (pay.get("payment_type") or "subscription").lower()
    if payment_type == "booster":
        booster_sku = pay.get("booster_sku")
        packs = billing_store.list_booster_packs()
        pack = next((p for p in packs if p["sku"].lower() == (booster_sku or "")), None)
        if not pack:
            raise HTTPException(status_code=400, detail="Invalid booster pack")

        # Apply to current plan wallet (default free)
        sub = get_subscription(user_id)
        current_plan = (sub.get("plan") if sub else None) or "free"
        billing_store.grant_booster_credits(
            user_id=user_id,
            plan=current_plan,
            units=int(pack["credits"]),
            meta={"booster_sku": booster_sku, "payment_id": razorpay_payment_id},
        )
        wallet = billing_store.get_wallet(user_id, current_plan)
        return {"status": "paid", "payment_type": "booster", "wallet": wallet}

    # Subscription activation
    plan = (pay.get("plan") or "").lower().strip()
    billing_cycle = (pay.get("billing_cycle") or "monthly").lower().strip()
    if plan not in ("pro", "max"):
        raise HTTPException(status_code=400, detail="Invalid subscription plan")

    upsert_subscription(user_id=user_id, plan=plan, billing_cycle=billing_cycle)
    # Reset included credits for the new cycle
    billing_store.reset_cycle_for_plan(user_id=user_id, plan=plan)
    wallet = billing_store.get_wallet(user_id, plan)
    return {"status": "paid", "payment_type": "subscription", "subscription": {"plan": plan, "billing_cycle": billing_cycle}, "wallet": wallet}


@router.get("/me")
def me(user=Depends(get_current_user)):
    user_id = user["user_id"]
    sub = get_subscription(user_id)

    plan = "free"
    billing_cycle = "monthly"
    is_active = False
    cycle_end_at = None
    if sub:
        plan = sub.get("plan") or "free"
        billing_cycle = sub.get("billing_cycle") or "monthly"
        is_active = bool(sub.get("is_active"))
        cycle_end_at = sub.get("cycle_end_at")

    wallet = billing_store.get_wallet(user_id, plan)

    return {
        "plan": plan,
        "billing_cycle": billing_cycle,
        "is_active": is_active,
        "cycle_end_at": cycle_end_at,
        "credits": {
            "included_balance": wallet.get("included_balance", 0),
            "booster_balance": wallet.get("booster_balance", 0),
            "cycle_ends_at": wallet.get("cycle_ends_at"),
        },
    }
