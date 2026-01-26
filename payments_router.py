"""
KnowEasy Premium - Payments Router v2.1.0
CEO Fix: Correct pricing defaults - NO MORE ₹1 SUBSCRIPTIONS!

Changes from v2.0.0:
- CRITICAL: Changed default pricing from ₹1 to actual prices
- Added Family plan support (₹599/mo, ₹5999/yr)
- Fixed Pro pricing: ₹249/mo, ₹2499/yr
- Fixed Max pricing: ₹399/mo, ₹3999/yr
- Added price validation to prevent accidental ₹1 orders
- Improved logging for payment debugging

Author: KnowEasy AI Architecture Team
Version: 2.1.0 (CEO Audit Fix)
"""

import os
import hmac
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, validator
import razorpay

logger = logging.getLogger("knoweasy.payments")

router = APIRouter(prefix="/api/payments", tags=["payments"])


# ============================================================================
# CONFIGURATION - CEO APPROVED PRICING (IN PAISE)
# ============================================================================

# CRITICAL: These are the REAL prices, not test prices!
# 100 paise = ₹1, so 24900 paise = ₹249

PLAN_PRICING = {
    "pro": {
        "monthly": int(os.getenv("PLAN_PRO_AMOUNT_PAISE_MONTHLY", "24900")),   # ₹249
        "yearly": int(os.getenv("PLAN_PRO_AMOUNT_PAISE_YEARLY", "249900")),    # ₹2499
    },
    "max": {
        "monthly": int(os.getenv("PLAN_MAX_AMOUNT_PAISE_MONTHLY", "39900")),   # ₹399
        "yearly": int(os.getenv("PLAN_MAX_AMOUNT_PAISE_YEARLY", "399900")),    # ₹3999
    },
    "family": {
        "monthly": int(os.getenv("PLAN_FAMILY_AMOUNT_PAISE_MONTHLY", "59900")), # ₹599
        "yearly": int(os.getenv("PLAN_FAMILY_AMOUNT_PAISE_YEARLY", "599900")),  # ₹5999
    },
}

# Minimum valid price (to catch configuration errors)
MIN_VALID_PRICE_PAISE = 4900  # ₹49 minimum

# Razorpay configuration
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

# Initialize Razorpay client
razorpay_client = None
if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    logger.info(f"✅ Razorpay initialized with key: {RAZORPAY_KEY_ID[:12]}...")
else:
    logger.warning("⚠️ Razorpay not configured - payments will fail")


# ============================================================================
# MODELS
# ============================================================================

class CreateOrderRequest(BaseModel):
    plan: str
    billing_cycle: str = "monthly"
    
    @validator('plan')
    def validate_plan(cls, v):
        v = v.lower().strip()
        if v not in PLAN_PRICING:
            raise ValueError(f"Invalid plan: {v}. Must be one of: {list(PLAN_PRICING.keys())}")
        return v
    
    @validator('billing_cycle')
    def validate_cycle(cls, v):
        v = v.lower().strip()
        if v not in ('monthly', 'yearly'):
            raise ValueError(f"Invalid billing_cycle: {v}. Must be 'monthly' or 'yearly'")
        return v


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class CreateBoosterOrderRequest(BaseModel):
    sku: str
    
    @validator('sku')
    def validate_sku(cls, v):
        valid_skus = ['BOOST_MINI', 'BOOST_SMART', 'BOOST_PRO', 'BOOST_POWER']
        if v not in valid_skus:
            raise ValueError(f"Invalid SKU: {v}. Must be one of: {valid_skus}")
        return v


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get_plan_amount_paise(plan: str, billing_cycle: str) -> int:
    """
    Get the price in paise for a plan.
    CRITICAL: No more ₹1 defaults! Uses actual prices.
    """
    plan = plan.lower().strip()
    cycle = billing_cycle.lower().strip()
    
    if plan not in PLAN_PRICING:
        logger.error(f"❌ Invalid plan requested: {plan}")
        raise ValueError(f"Invalid plan: {plan}")
    
    if cycle not in PLAN_PRICING[plan]:
        logger.error(f"❌ Invalid cycle for {plan}: {cycle}")
        raise ValueError(f"Invalid billing cycle: {cycle}")
    
    amount = PLAN_PRICING[plan][cycle]
    
    # SAFETY CHECK: Reject suspiciously low prices
    if amount < MIN_VALID_PRICE_PAISE:
        logger.error(f"❌ PRICE TOO LOW! {plan}/{cycle} = {amount} paise (₹{amount/100})")
        logger.error("   This is likely a configuration error. Check environment variables!")
        raise ValueError(f"Configuration error: Price {amount} paise is below minimum {MIN_VALID_PRICE_PAISE}")
    
    logger.info(f"💰 Price for {plan}/{cycle}: ₹{amount/100} ({amount} paise)")
    return amount


def _verify_razorpay_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Verify Razorpay payment signature using HMAC-SHA256"""
    if not RAZORPAY_KEY_SECRET:
        logger.error("❌ Cannot verify signature: RAZORPAY_KEY_SECRET not set")
        return False
    
    message = f"{order_id}|{payment_id}"
    expected_signature = hmac.new(
        RAZORPAY_KEY_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    is_valid = hmac.compare_digest(signature, expected_signature)
    
    if not is_valid:
        logger.warning(f"⚠️ Signature mismatch for order {order_id}")
    
    return is_valid


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/create-order")
async def create_order(request: CreateOrderRequest, req: Request):
    """
    Create a Razorpay order for subscription purchase.
    Returns order_id to be used with Razorpay checkout.
    """
    if not razorpay_client:
        raise HTTPException(status_code=503, detail="Payment service not configured")
    
    # Get user from auth (you'll need to inject this)
    user_id = getattr(req.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        amount_paise = _get_plan_amount_paise(request.plan, request.billing_cycle)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Create Razorpay order
    try:
        order_data = {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": f"ke_{user_id[:8]}_{int(datetime.now().timestamp())}",
            "notes": {
                "user_id": user_id,
                "plan": request.plan,
                "billing_cycle": request.billing_cycle,
                "product": "knoweasy_subscription"
            }
        }
        
        order = razorpay_client.order.create(data=order_data)
        
        logger.info(f"✅ Created order {order['id']} for {user_id}: {request.plan}/{request.billing_cycle} = ₹{amount_paise/100}")
        
        return {
            "success": True,
            "order_id": order['id'],
            "amount": amount_paise,
            "amount_inr": amount_paise / 100,
            "currency": "INR",
            "plan": request.plan,
            "billing_cycle": request.billing_cycle,
            "key_id": RAZORPAY_KEY_ID  # Frontend needs this for checkout
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to create order: {e}")
        raise HTTPException(status_code=500, detail="Failed to create payment order")


@router.post("/verify-payment")
async def verify_payment(request: VerifyPaymentRequest, req: Request):
    """
    Verify Razorpay payment and activate subscription.
    Called after successful Razorpay checkout.
    """
    if not razorpay_client:
        raise HTTPException(status_code=503, detail="Payment service not configured")
    
    user_id = getattr(req.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Verify signature
    if not _verify_razorpay_signature(
        request.razorpay_order_id,
        request.razorpay_payment_id,
        request.razorpay_signature
    ):
        logger.warning(f"⚠️ Invalid signature for payment {request.razorpay_payment_id}")
        raise HTTPException(status_code=400, detail="Payment verification failed")
    
    # Fetch order to get plan details
    try:
        order = razorpay_client.order.fetch(request.razorpay_order_id)
        notes = order.get('notes', {})
        plan = notes.get('plan', 'pro')
        billing_cycle = notes.get('billing_cycle', 'monthly')
        
        # Verify order belongs to this user
        if notes.get('user_id') != user_id:
            logger.warning(f"⚠️ User mismatch: order for {notes.get('user_id')}, claimed by {user_id}")
            raise HTTPException(status_code=403, detail="Order does not belong to this user")
        
    except razorpay.errors.BadRequestError:
        raise HTTPException(status_code=400, detail="Invalid order ID")
    
    # Activate subscription (you'll implement this based on your billing_store)
    # For now, return success response
    logger.info(f"✅ Payment verified for {user_id}: {plan}/{billing_cycle}")
    
    return {
        "success": True,
        "message": "Payment verified successfully",
        "plan": plan,
        "billing_cycle": billing_cycle,
        "payment_id": request.razorpay_payment_id,
        "order_id": request.razorpay_order_id
    }


@router.post("/create-booster-order")
async def create_booster_order(request: CreateBoosterOrderRequest, req: Request):
    """Create order for booster pack purchase"""
    if not razorpay_client:
        raise HTTPException(status_code=503, detail="Payment service not configured")
    
    user_id = getattr(req.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Import booster packs from billing_store
    from billing_store import BOOSTER_PACKS
    
    pack = BOOSTER_PACKS.get(request.sku)
    if not pack:
        raise HTTPException(status_code=400, detail=f"Unknown booster pack: {request.sku}")
    
    try:
        order_data = {
            "amount": pack['price_paise'],
            "currency": "INR",
            "receipt": f"boost_{user_id[:8]}_{int(datetime.now().timestamp())}",
            "notes": {
                "user_id": user_id,
                "sku": request.sku,
                "credits": pack['credits'],
                "product": "knoweasy_booster"
            }
        }
        
        order = razorpay_client.order.create(data=order_data)
        
        logger.info(f"✅ Created booster order {order['id']} for {user_id}: {request.sku} = ₹{pack['price_paise']/100}")
        
        return {
            "success": True,
            "order_id": order['id'],
            "amount": pack['price_paise'],
            "amount_inr": pack['price_paise'] / 100,
            "currency": "INR",
            "sku": request.sku,
            "credits": pack['credits'],
            "key_id": RAZORPAY_KEY_ID
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to create booster order: {e}")
        raise HTTPException(status_code=500, detail="Failed to create payment order")


@router.get("/pricing")
async def get_pricing():
    """
    Get current pricing for all plans and boosters.
    Frontend should use this to display prices.
    """
    from billing_store import BOOSTER_PACKS
    
    return {
        "plans": {
            plan: {
                "monthly_paise": prices["monthly"],
                "monthly_inr": prices["monthly"] / 100,
                "yearly_paise": prices["yearly"],
                "yearly_inr": prices["yearly"] / 100,
                "yearly_monthly_equivalent": round(prices["yearly"] / 12 / 100, 2)
            }
            for plan, prices in PLAN_PRICING.items()
        },
        "boosters": {
            sku: {
                "credits": pack["credits"],
                "price_paise": pack["price_paise"],
                "price_inr": pack["price_paise"] / 100,
                "display_name": pack["display_name"],
                "description": pack["description"]
            }
            for sku, pack in BOOSTER_PACKS.items()
        },
        "currency": "INR"
    }


@router.get("/health")
async def payments_health():
    """Health check for payments service"""
    return {
        "status": "healthy" if razorpay_client else "degraded",
        "razorpay_configured": bool(razorpay_client),
        "pricing_loaded": bool(PLAN_PRICING),
        "plans_available": list(PLAN_PRICING.keys())
    }


# ============================================================================
# WEBHOOK HANDLER (for main.py to use)
# ============================================================================

async def handle_razorpay_webhook(request: Request, db_pool) -> Dict[str, Any]:
    """
    Handle Razorpay webhook events.
    This should be called from main.py's webhook endpoint.
    """
    # Verify webhook signature
    webhook_signature = request.headers.get('X-Razorpay-Signature', '')
    body = await request.body()
    
    if RAZORPAY_WEBHOOK_SECRET:
        expected_signature = hmac.new(
            RAZORPAY_WEBHOOK_SECRET.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(webhook_signature, expected_signature):
            logger.warning("⚠️ Invalid webhook signature")
            raise HTTPException(status_code=400, detail="Invalid webhook signature")
    
    import json
    payload = json.loads(body)
    event = payload.get('event', '')
    
    logger.info(f"📨 Webhook received: {event}")
    
    if event == 'payment.captured':
        # Payment successful - activate subscription
        payment_entity = payload.get('payload', {}).get('payment', {}).get('entity', {})
        order_id = payment_entity.get('order_id')
        payment_id = payment_entity.get('id')
        
        logger.info(f"✅ Payment captured: {payment_id} for order {order_id}")
        
        # TODO: Activate subscription in database
        # This would call billing_store.upgrade_plan() or similar
        
        return {"status": "processed", "event": event}
    
    elif event == 'payment.failed':
        payment_entity = payload.get('payload', {}).get('payment', {}).get('entity', {})
        logger.warning(f"❌ Payment failed: {payment_entity.get('id')}")
        return {"status": "processed", "event": event}
    
    else:
        logger.info(f"ℹ️ Ignoring webhook event: {event}")
        return {"status": "ignored", "event": event}
