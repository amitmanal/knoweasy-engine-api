from __future__ import annotations

import os
import uuid
import hmac
import hashlib
from typing import Any, Dict

import requests
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from auth_store import session_user
from billing_store import (
    get_plan_price_inr,
    create_payment_order_row,
    mark_payment_paid,
)

def _is_simulation() -> bool:
    """Return True if payments should be simulated instead of using Razorpay.

    In simulation mode we bypass external Razorpay API calls.  This
    mode is enabled when either the environment variable
    PAYMENT_SIMULATION_MODE is set to a truthy value, or when the
    Razorpay key credentials are missing.  Simulation mode allows
    development and testing of the payment flow without real
    transactions.
    """
    flag = os.getenv("PAYMENT_SIMULATION_MODE", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return True
    # If either key_id or key_secret is missing then treat as simulation
    key_id, key_secret = _creds()
    return not (key_id and key_secret)

router = APIRouter(prefix="/billing/razorpay", tags=["billing"])


def _token_from_header(authorization: str | None) -> str:
    if not authorization:
        return ""
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return ""


def _creds() -> tuple[str, str]:
    return (os.getenv("RAZORPAY_KEY_ID", ""), os.getenv("RAZORPAY_KEY_SECRET", ""))


@router.get("/key")
def get_key():
    """Return Razorpay key information.

    When payment simulation mode is enabled (see _is_simulation()),
    this endpoint returns `enabled: False` to signal to the frontend
    that Razorpay is unavailable and a simulated payment flow should
    be used instead.  Otherwise it returns the configured key_id.
    """
    if _is_simulation():
        # In simulation mode we do not expose a key; the frontend
        # should fall back to the simulation flow.
        return {"ok": True, "enabled": False}
    key_id, _ = _creds()
    if not key_id:
        return {"ok": False, "enabled": False}
    return {"ok": True, "enabled": True, "key_id": key_id}


@router.post("/order")
def create_order(payload: Dict[str, Any], authorization: str | None = Header(default=None, alias="Authorization")):
    token = _token_from_header(authorization)
    if not token:
        return JSONResponse(status_code=401, content={"ok": False, "error": "UNAUTHORIZED", "message": "Missing session token."})
    u = session_user(token)
    if not u:
        return JSONResponse(status_code=401, content={"ok": False, "error": "UNAUTHORIZED", "message": "Invalid or expired session."})

    plan = str(payload.get("plan", "")).upper()
    if plan not in ("PRO", "MAX"):
        return JSONResponse(status_code=400, content={"ok": False, "error": "INVALID_PLAN", "message": "Plan must be PRO or MAX."})

    # Determine price and amount for the order
    price_inr = get_plan_price_inr(plan)
    if price_inr <= 0:
        return JSONResponse(status_code=400, content={"ok": False, "error": "INVALID_PRICE", "message": "Price not configured."})

    amount_paise = int(price_inr * 100)
    receipt = f"ke_{u['user_id']}_{plan}_{uuid.uuid4().hex[:12]}"

    # Simulation mode: create a fake order without contacting Razorpay
    if _is_simulation():
        order_id = f"sim_{u['user_id']}_{uuid.uuid4().hex[:10]}"
        create_payment_order_row(int(u["user_id"]), plan, amount_paise, "INR", order_id, {"receipt": receipt, "simulated": True})
        return {"ok": True, "order": {"id": order_id, "amount": amount_paise, "currency": "INR", "plan": plan, "simulated": True}}

    # Real mode: use Razorpay API
    key_id, key_secret = _creds()
    if not key_id or not key_secret:
        return JSONResponse(status_code=501, content={"ok": False, "error": "PAYMENTS_NOT_ENABLED", "message": "Razorpay is not configured yet."})

    try:
        r = requests.post(
            "https://api.razorpay.com/v1/orders",
            auth=(key_id, key_secret),
            json={
                "amount": amount_paise,
                "currency": "INR",
                "receipt": receipt,
                "notes": {
                    "user_id": str(u["user_id"]),
                    "plan": plan,
                },
            },
            timeout=15,
        )
        if r.status_code >= 300:
            return JSONResponse(status_code=502, content={"ok": False, "error": "RAZORPAY_ERROR", "message": "Failed to create order.", "detail": r.text[:300]})
        data = r.json()
        order_id = data.get("id", "")
        if not order_id:
            return JSONResponse(status_code=502, content={"ok": False, "error": "RAZORPAY_ERROR", "message": "Missing order id."})

        create_payment_order_row(int(u["user_id"]), plan, amount_paise, "INR", order_id, {"receipt": receipt})
        return {"ok": True, "order": {"id": order_id, "amount": amount_paise, "currency": "INR", "plan": plan}}
    except Exception as e:
        return JSONResponse(status_code=502, content={"ok": False, "error": "RAZORPAY_ERROR", "message": "Order creation failed.", "detail": str(e)[:200]})


@router.post("/verify")
def verify_payment(payload: Dict[str, Any], authorization: str | None = Header(default=None, alias="Authorization")):
    token = _token_from_header(authorization)
    if not token:
        return JSONResponse(status_code=401, content={"ok": False, "error": "UNAUTHORIZED", "message": "Missing session token."})
    u = session_user(token)
    if not u:
        return JSONResponse(status_code=401, content={"ok": False, "error": "UNAUTHORIZED", "message": "Invalid or expired session."})

    order_id = str(payload.get("razorpay_order_id", "")).strip()
    payment_id = str(payload.get("razorpay_payment_id", "")).strip() or "simulated"
    signature = str(payload.get("razorpay_signature", "")).strip()
    plan = str(payload.get("plan", "")).upper()

    if plan not in ("PRO", "MAX") or not order_id:
        return JSONResponse(status_code=400, content={"ok": False, "error": "BAD_REQUEST", "message": "Missing fields."})

    # Simulation mode: skip signature validation and mark payment as paid
    if _is_simulation():
        mark_payment_paid(int(u["user_id"]), plan, order_id, payment_id)
        return {"ok": True, "message": "Simulated payment verified. Subscription activated.", "plan": plan}

    # Real mode requires signature validation
    key_id, key_secret = _creds()
    if not key_id or not key_secret:
        return JSONResponse(status_code=501, content={"ok": False, "error": "PAYMENTS_NOT_ENABLED", "message": "Razorpay is not configured yet."})

    if not payment_id or not signature:
        return JSONResponse(status_code=400, content={"ok": False, "error": "BAD_REQUEST", "message": "Missing fields."})

    body = f"{order_id}|{payment_id}".encode("utf-8")
    expected = hmac.new(key_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return JSONResponse(status_code=400, content={"ok": False, "error": "INVALID_SIGNATURE", "message": "Payment signature verification failed."})

    # Mark paid + activate subscription (skeleton: 30 days)
    mark_payment_paid(int(u["user_id"]), plan, order_id, payment_id)
    return {"ok": True, "message": "Payment verified. Subscription activated.", "plan": plan}


@router.post("/webhook")
async def webhook(request: Request, x_razorpay_signature: str | None = Header(default=None, alias="X-Razorpay-Signature")):
    """Razorpay webhook receiver (production-grade).

    Requires env var RAZORPAY_WEBHOOK_SECRET.
    Verifies signature over raw request body (HMAC SHA256).
    Handles payment.captured / order.paid events idempotently.
    """
    _, key_secret = _creds()
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "") or ""
    if not webhook_secret:
        return JSONResponse(status_code=503, content={"ok": False, "error": "WEBHOOK_NOT_CONFIGURED"})

    raw = await request.body()
    sig = (x_razorpay_signature or "").strip()
    if not sig:
        return JSONResponse(status_code=400, content={"ok": False, "error": "MISSING_SIGNATURE"})

    expected = hmac.new(webhook_secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return JSONResponse(status_code=400, content={"ok": False, "error": "BAD_SIGNATURE"})

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    event = str(payload.get("event") or "").lower()

    # Try extract order_id and payment_id from common events
    order_id = None
    payment_id = None
    plan = None

    try:
        if event == "payment.captured":
            ent = payload["payload"]["payment"]["entity"]
            order_id = ent.get("order_id")
            payment_id = ent.get("id")
        elif event == "order.paid":
            ent = payload["payload"]["order"]["entity"]
            order_id = ent.get("id")
        # plan is stored in our payment_orders row; we don't trust webhook payload for plan
    except Exception:
        pass

    if not order_id:
        # acknowledge but do nothing
        return {"ok": True, "ignored": True}

    # Find order in DB to get user_id/plan_code
    try:
        from db import get_engine
        from sqlalchemy import text

        eng = get_engine()
        if eng is None:
            return {"ok": True, "ignored": True}

        with eng.begin() as conn:
            row = conn.execute(
                text("""SELECT user_id, plan_code, status FROM payment_orders WHERE razorpay_order_id=:oid"""),
                {"oid": order_id},
            ).mappings().first()

        if not row:
            return {"ok": True, "ignored": True}

        if str(row.get("status") or "") == "paid":
            return {"ok": True, "idempotent": True}

        plan = str(row.get("plan_code") or "PRO").upper()
        uid = int(row.get("user_id"))

        # If payment_id not present (order.paid), we store a placeholder.
        mark_payment_paid(uid, plan, order_id, payment_id or "webhook")
        return {"ok": True, "processed": True, "event": event, "order_id": order_id}
    except Exception:
        # Always 200 OK to avoid repeated hammering; log server-side in real production
        return {"ok": True, "processed": False}
