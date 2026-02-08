"""billing_router.py

Billing endpoints: subscription status + credit wallets + booster packs.

This router is additive (does not break existing /payments endpoints).

Endpoints
- GET  /billing/me
- POST /billing/consume
- GET  /billing/booster/packs

Booster purchase flow (Razorpay):
- POST /billing/booster/create_order
- POST /billing/booster/verify
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Any, Dict

import requests
from fastapi import APIRouter, Depends, HTTPException

from phase1_router import get_current_user

import billing_store
from payments_store import get_subscription, mark_payment_paid, record_order, get_order_record

logger = logging.getLogger("knoweasy-engine-api.billing")

router = APIRouter(prefix="/billing", tags=["billing"])


def _get_razorpay_keys() -> tuple[str, str]:
    key_id = (os.getenv("RAZORPAY_KEY_ID") or "").strip()
    key_secret = (os.getenv("RAZORPAY_KEY_SECRET") or "").strip()
    if not key_id or not key_secret:
        raise HTTPException(status_code=503, detail="Payments not enabled")
    return key_id, key_secret


@router.get("/me")
def billing_me(user=Depends(get_current_user)):
    """Return subscription + wallet + booster catalog."""
    uid = int(user["user_id"])
    sub = get_subscription(uid)
    plan = (sub.get("plan") or "free").lower().strip() or "free"
    wallet = billing_store.get_wallet(uid, plan)
    packs = billing_store.list_booster_packs()
    return {"ok": True, "subscription": sub, "wallet": wallet, "booster_packs": packs}


@router.get("/wallet")
@router.get("/wallet/me")
def billing_wallet(user=Depends(get_current_user)):
    """Backward-compatible wallet endpoint for older frontend builds.

    Returns: { ok, subscription, wallet }
    """
    uid = int(user["user_id"])
    sub = get_subscription(uid)
    plan = (sub.get("plan") or "free").lower().strip() or "free"
    wallet = billing_store.get_wallet(uid, plan)
    return {"ok": True, "subscription": sub, "wallet": wallet}


@router.post("/consume")
def billing_consume(payload: Dict[str, Any], user=Depends(get_current_user)):
    """Consume credits for an action.

    Payload: { units:int, meta:dict }
    """
    uid = int(user["user_id"])
    sub = get_subscription(uid)
    plan = (sub.get("plan") or "free").lower().strip() or "free"
    units = int(payload.get("units") or 0)
    meta = payload.get("meta") or {}
    try:
        out = billing_store.consume_credits(uid, plan, units, meta=meta)
        return {"ok": True, **out}
    except ValueError:
        raise HTTPException(status_code=402, detail="OUT_OF_CREDITS")


@router.get("/booster/packs")
def booster_packs():
    return {"ok": True, "packs": billing_store.list_booster_packs()}


@router.post("/booster/create_order")
def booster_create_order(payload: Dict[str, Any], user=Depends(get_current_user)):
    role = (user.get("role") or "").lower()
    if role != "student":
        raise HTTPException(status_code=403, detail="Only students can purchase")

    uid = int(user["user_id"])
    sub = get_subscription(uid)
    plan = (sub.get("plan") or "free").lower().strip() or "free"
    if plan == "free":
        raise HTTPException(status_code=403, detail="Upgrade required for booster")

    sku = (payload.get("sku") or "").strip().upper()
    packs = {p["sku"].upper(): p for p in billing_store.list_booster_packs()}
    if sku not in packs:
        raise HTTPException(status_code=400, detail="Invalid booster sku")

    pack = packs[sku]
    amount_paise = int(pack["price_paise"])
    currency = "INR"

    key_id, key_secret = _get_razorpay_keys()

    order_payload = {
        "amount": int(amount_paise),
        "currency": currency,
        "receipt": f"knoweasy_{uid}_booster_{sku}",
        "notes": {"user_id": str(uid), "type": "booster", "sku": sku},
    }

    try:
        resp = requests.post(
            "https://api.razorpay.com/v1/orders",
            auth=(key_id, key_secret),
            json=order_payload,
            timeout=20,
        )
    except Exception as e:
        logger.exception("Razorpay booster order create failed")
        raise HTTPException(status_code=502, detail="Razorpay request failed") from e

    if resp.status_code >= 400:
        logger.error("Razorpay create booster order error: %s %s", resp.status_code, resp.text)
        raise HTTPException(status_code=502, detail="Razorpay error")

    data = resp.json() if resp.content else {}
    order_id = data.get("id")
    if not order_id:
        raise HTTPException(status_code=502, detail="Razorpay order id missing")

    # record order using existing audit table
    record_order(uid, plan, int(amount_paise), currency, order_id, payment_type="booster", booster_sku=sku)

    return {
        "ok": True,
        "key_id": key_id,
        "order_id": order_id,
        "amount": int(amount_paise),
        "amount_paise": int(amount_paise),
        "currency": currency,
        "sku": sku,
        "credits_units": int(pack["credits_units"]),
    }


@router.post("/booster/verify")
def booster_verify(payload: Dict[str, Any], user=Depends(get_current_user)):
    role = (user.get("role") or "").lower()
    if role != "student":
        raise HTTPException(status_code=403, detail="Only students can verify")

    uid = int(user["user_id"])
    sub = get_subscription(uid)
    plan = (sub.get("plan") or "free").lower().strip() or "free"

    sku = (payload.get("sku") or "").strip().upper()
    razorpay_order_id = (payload.get("razorpay_order_id") or "").strip()
    razorpay_payment_id = (payload.get("razorpay_payment_id") or "").strip()
    razorpay_signature = (payload.get("razorpay_signature") or "").strip()

    if not (sku and razorpay_order_id and razorpay_payment_id and razorpay_signature):
        raise HTTPException(status_code=400, detail="Missing fields")

    # Canonical booster pack lookup (case-insensitive).
    pack = billing_store.get_booster_pack(sku)
    if not pack:
        raise HTTPException(status_code=400, detail="Invalid booster sku")

    # Verify the Razorpay signature.
    _, key_secret = _get_razorpay_keys()
    msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
    expected = hmac.new(key_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, razorpay_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Additional server-side verification: fetch the recorded order and validate it.
    order = get_order_record(uid, razorpay_order_id)
    if not order:
        raise HTTPException(status_code=400, detail="Order not found or does not belong to user")

    # Extract recorded fields.
    payment_type = str(order.get("payment_type") or "").lower().strip()
    recorded_sku = (order.get("booster_sku") or "").strip().upper()
    status = str(order.get("status") or "").lower().strip()
    try:
        recorded_amount = int(order.get("amount_paise")) if order.get("amount_paise") is not None else None
    except Exception:
        recorded_amount = None
    canonical_amount = int(pack.get("price_paise"))

    # If payment_type exists and is not booster, treat as mismatch.
    if payment_type and payment_type != "booster" and recorded_sku != sku:
        raise HTTPException(status_code=400, detail="Order type mismatch")
    if recorded_sku and recorded_sku != sku:
        raise HTTPException(status_code=400, detail="Booster SKU mismatch")
    if recorded_amount is not None and recorded_amount != canonical_amount:
        raise HTTPException(status_code=400, detail="Booster amount mismatch")

    # If already paid, do not grant credits again (idempotent). Return current wallet.
    if status and status != "created":
        wallet = billing_store.get_wallet(uid, plan)
        return {"ok": True, "wallet": wallet, "granted": 0, "sku": sku}

    # Mark payment paid and grant credits exactly once.
    mark_payment_paid(uid, razorpay_order_id, razorpay_payment_id, razorpay_signature)
    units = int(pack.get("credits_units") or 0)
    wallet = billing_store.grant_booster_credits(uid, plan, units, meta={"sku": sku, "order": razorpay_order_id})
    return {"ok": True, "wallet": wallet, "granted": units, "sku": sku}
