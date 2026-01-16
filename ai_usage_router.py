"""ai_usage_router.py

Phase-6: AI usage transparency (trust layer)

Additive, read-only endpoints so students (and later parents) can see:
- credits remaining
- last AI usage time
- credits used today / this cycle

Non-negotiable stability:
- Never breaks existing billing, auth, or solve flows.
- Never mutates balances.
- Returns safe defaults on DB issues.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from phase1_router import get_current_user
from payments_store import get_subscription
import billing_store


router = APIRouter(prefix="/ai", tags=["ai-usage"])


@router.get("/usage/me")
def ai_usage_me(user=Depends(get_current_user)):
    uid = int(user["user_id"])
    sub = get_subscription(uid)
    plan = (sub.get("plan") or "free").lower().strip() or "free"
    out = billing_store.get_ai_usage_summary(uid, plan)
    # Include subscription context for the frontend (read-only).
    out["subscription"] = sub
    return out
