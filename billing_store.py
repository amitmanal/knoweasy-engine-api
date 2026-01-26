"""
KnowEasy Premium - Credit Billing Store v2.1.0
CEO Fix: Correct credit allocations and booster packs

Changes from v2.0.0:
- Fixed FREE tier credits: 1000 (was 300) - allows ~12 basic questions
- Fixed PRO tier credits: 6000 (was 4500) - matches marketing ~75 questions
- Fixed MAX tier credits: 18000 (was 12000) - matches marketing ~225 questions  
- Added FAMILY tier: 25000 credits
- Fixed booster packs to match frontend pricing
- Added carry-forward logic for unused included credits (Pro/Max only)

Author: KnowEasy AI Architecture Team
Version: 2.1.0 (CEO Audit Fix)
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List
from enum import Enum

logger = logging.getLogger("knoweasy.billing")


# ============================================================================
# CONFIGURATION - CEO APPROVED PRICING
# ============================================================================

class SubscriptionPlan(Enum):
    FREE = "free"
    PRO = "pro"
    MAX = "max"
    FAMILY = "family"


# Credit allocations per plan (MUST MATCH FRONTEND DISPLAY)
# CEO Decision: Credits should allow meaningful usage
# - Average question costs 80-180 credits depending on AI strategy
# - FREE: ~12 basic questions (Gemini only)
# - PRO: ~75 basic questions or ~33 triple-AI questions  
# - MAX: ~225 basic questions or ~100 triple-AI questions
# - FAMILY: ~312 basic questions or ~139 triple-AI questions

_DEFAULT_INCLUDED_CREDITS = {
    "free": int(os.getenv("CREDITS_FREE_INCLUDED", "1000")),
    "pro": int(os.getenv("CREDITS_PRO_INCLUDED", "6000")),
    "max": int(os.getenv("CREDITS_MAX_INCLUDED", "18000")),
    "family": int(os.getenv("CREDITS_FAMILY_INCLUDED", "25000")),
}

# Booster pack definitions (MUST MATCH FRONTEND upgrade.html)
# Format: (sku, credits, price_paise)
BOOSTER_PACKS = {
    "BOOST_MINI": {
        "credits": 500,
        "price_paise": 4900,  # ₹49
        "display_name": "Mini Boost",
        "description": "500 AI Credits - Good for quick revision"
    },
    "BOOST_SMART": {
        "credits": 1500,
        "price_paise": 9900,  # ₹99
        "display_name": "Smart Boost", 
        "description": "1,500 AI Credits - Best value for regular study"
    },
    "BOOST_PRO": {
        "credits": 4000,
        "price_paise": 19900,  # ₹199
        "display_name": "Pro Boost",
        "description": "4,000 AI Credits - For serious exam prep"
    },
    "BOOST_POWER": {
        "credits": 7500,
        "price_paise": 34900,  # ₹349
        "display_name": "Power Boost",
        "description": "7,500 AI Credits - Maximum preparation"
    },
}

# Credit costs per AI strategy (from orchestrator.py)
CREDIT_COSTS = {
    "gemini_only": 80,
    "gemini_simple": 80,
    "gemini_gpt": 120,
    "triple_ai": 180,
    "claude_deep": 150,
    "gpt_math": 100,
    "fallback": 80,
    "image_solve": 200,  # NEW: For image-based doubt solving
    "tts_generate": 30,   # NEW: For text-to-speech
    "image_gen": 150,     # NEW: For diagram generation
}


# ============================================================================
# WALLET MANAGER
# ============================================================================

class CreditWallet:
    """
    Manages user credit wallet with included + booster credits.
    
    Design:
    - included_credits: Monthly allocation from subscription (resets each cycle)
    - booster_credits: Purchased credits (never expire, used after included)
    - Deduction order: included first, then booster
    - Pro/Max users can carry forward up to 20% unused included credits
    """
    
    def __init__(self, db_pool):
        self.db = db_pool
    
    async def ensure_tables(self):
        """Create billing tables if not exist"""
        async with self.db.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS credit_wallets (
                    user_id TEXT PRIMARY KEY,
                    plan TEXT DEFAULT 'free',
                    included_credits INTEGER DEFAULT 1000,
                    booster_credits INTEGER DEFAULT 0,
                    cycle_start TIMESTAMP DEFAULT NOW(),
                    cycle_end TIMESTAMP DEFAULT (NOW() + INTERVAL '30 days'),
                    total_used_this_cycle INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS credit_transactions (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    balance_after INTEGER NOT NULL,
                    transaction_type TEXT NOT NULL,
                    description TEXT,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS booster_purchases (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    sku TEXT NOT NULL,
                    credits INTEGER NOT NULL,
                    amount_paise INTEGER NOT NULL,
                    razorpay_order_id TEXT,
                    razorpay_payment_id TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_credit_txn_user 
                ON credit_transactions(user_id, created_at DESC)
            """)
            
            logger.info("✅ Billing tables ensured")
    
    async def get_or_create_wallet(self, user_id: str) -> Dict[str, Any]:
        """Get user's wallet, creating if needed"""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM credit_wallets WHERE user_id = $1",
                user_id
            )
            
            if row:
                wallet = dict(row)
                # Check if cycle needs reset
                if wallet['cycle_end'] and datetime.now() > wallet['cycle_end']:
                    wallet = await self._reset_cycle(user_id, wallet)
                return wallet
            
            # Create new wallet for free user
            plan = "free"
            included = _DEFAULT_INCLUDED_CREDITS[plan]
            cycle_end = datetime.now() + timedelta(days=30)
            
            await conn.execute("""
                INSERT INTO credit_wallets 
                (user_id, plan, included_credits, booster_credits, cycle_start, cycle_end)
                VALUES ($1, $2, $3, 0, NOW(), $4)
            """, user_id, plan, included, cycle_end)
            
            logger.info(f"Created wallet for {user_id}: {plan}, {included} credits")
            
            return {
                "user_id": user_id,
                "plan": plan,
                "included_credits": included,
                "booster_credits": 0,
                "cycle_start": datetime.now(),
                "cycle_end": cycle_end,
                "total_used_this_cycle": 0
            }
    
    async def _reset_cycle(self, user_id: str, wallet: Dict) -> Dict:
        """Reset monthly cycle with carry-forward for paid plans"""
        plan = wallet['plan']
        included = _DEFAULT_INCLUDED_CREDITS.get(plan, 1000)
        
        # Carry forward up to 20% for Pro/Max users
        carry_forward = 0
        if plan in ('pro', 'max', 'family'):
            unused = wallet.get('included_credits', 0)
            max_carry = int(included * 0.2)  # 20% of monthly allocation
            carry_forward = min(unused, max_carry)
        
        new_included = included + carry_forward
        cycle_end = datetime.now() + timedelta(days=30)
        
        async with self.db.acquire() as conn:
            await conn.execute("""
                UPDATE credit_wallets 
                SET included_credits = $2,
                    cycle_start = NOW(),
                    cycle_end = $3,
                    total_used_this_cycle = 0,
                    updated_at = NOW()
                WHERE user_id = $1
            """, user_id, new_included, cycle_end)
            
            # Log the reset
            await conn.execute("""
                INSERT INTO credit_transactions 
                (user_id, amount, balance_after, transaction_type, description)
                VALUES ($1, $2, $3, 'cycle_reset', $4)
            """, user_id, new_included, new_included + wallet.get('booster_credits', 0),
                f"Monthly reset: {included} + {carry_forward} carried forward")
        
        logger.info(f"Cycle reset for {user_id}: {new_included} credits (carried {carry_forward})")
        
        wallet['included_credits'] = new_included
        wallet['cycle_start'] = datetime.now()
        wallet['cycle_end'] = cycle_end
        wallet['total_used_this_cycle'] = 0
        
        return wallet
    
    async def get_balance(self, user_id: str) -> Dict[str, Any]:
        """Get current credit balance"""
        wallet = await self.get_or_create_wallet(user_id)
        
        included = wallet.get('included_credits', 0)
        booster = wallet.get('booster_credits', 0)
        
        return {
            "total": included + booster,
            "included": included,
            "booster": booster,
            "plan": wallet.get('plan', 'free'),
            "cycle_end": wallet.get('cycle_end'),
            "used_this_cycle": wallet.get('total_used_this_cycle', 0)
        }
    
    async def deduct_credits(
        self, 
        user_id: str, 
        amount: int, 
        reason: str = "ai_query",
        metadata: Dict = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Deduct credits from wallet.
        Returns (success, result_dict)
        """
        wallet = await self.get_or_create_wallet(user_id)
        
        included = wallet.get('included_credits', 0)
        booster = wallet.get('booster_credits', 0)
        total = included + booster
        
        if total < amount:
            return False, {
                "error": "insufficient_credits",
                "required": amount,
                "available": total,
                "message": f"Need {amount} credits but only have {total}"
            }
        
        # Deduct from included first, then booster
        deduct_included = min(amount, included)
        deduct_booster = amount - deduct_included
        
        new_included = included - deduct_included
        new_booster = booster - deduct_booster
        new_total = new_included + new_booster
        
        async with self.db.acquire() as conn:
            await conn.execute("""
                UPDATE credit_wallets 
                SET included_credits = $2,
                    booster_credits = $3,
                    total_used_this_cycle = total_used_this_cycle + $4,
                    updated_at = NOW()
                WHERE user_id = $1
            """, user_id, new_included, new_booster, amount)
            
            # Log transaction
            await conn.execute("""
                INSERT INTO credit_transactions 
                (user_id, amount, balance_after, transaction_type, description, metadata)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, user_id, -amount, new_total, reason, 
                f"Deducted {amount} credits for {reason}",
                metadata or {})
        
        logger.info(f"Deducted {amount} credits from {user_id}: {total} → {new_total}")
        
        return True, {
            "deducted": amount,
            "from_included": deduct_included,
            "from_booster": deduct_booster,
            "remaining_total": new_total,
            "remaining_included": new_included,
            "remaining_booster": new_booster
        }
    
    async def add_booster_credits(
        self, 
        user_id: str, 
        credits: int,
        sku: str,
        payment_id: str = None
    ) -> Dict[str, Any]:
        """Add booster credits after purchase"""
        wallet = await self.get_or_create_wallet(user_id)
        
        new_booster = wallet.get('booster_credits', 0) + credits
        new_total = wallet.get('included_credits', 0) + new_booster
        
        async with self.db.acquire() as conn:
            await conn.execute("""
                UPDATE credit_wallets 
                SET booster_credits = $2, updated_at = NOW()
                WHERE user_id = $1
            """, user_id, new_booster)
            
            # Log transaction
            await conn.execute("""
                INSERT INTO credit_transactions 
                (user_id, amount, balance_after, transaction_type, description, metadata)
                VALUES ($1, $2, $3, 'booster_purchase', $4, $5)
            """, user_id, credits, new_total,
                f"Purchased {sku}: +{credits} credits",
                {"sku": sku, "payment_id": payment_id})
        
        logger.info(f"Added {credits} booster credits to {user_id} via {sku}")
        
        return {
            "credits_added": credits,
            "new_booster_balance": new_booster,
            "new_total_balance": new_total
        }
    
    async def upgrade_plan(
        self, 
        user_id: str, 
        new_plan: str,
        payment_id: str = None
    ) -> Dict[str, Any]:
        """Upgrade user's subscription plan"""
        if new_plan not in _DEFAULT_INCLUDED_CREDITS:
            return {"error": f"Invalid plan: {new_plan}"}
        
        wallet = await self.get_or_create_wallet(user_id)
        old_plan = wallet.get('plan', 'free')
        
        # Get new credit allocation
        new_included = _DEFAULT_INCLUDED_CREDITS[new_plan]
        
        # Prorate: add difference if upgrading mid-cycle
        current_included = wallet.get('included_credits', 0)
        old_allocation = _DEFAULT_INCLUDED_CREDITS.get(old_plan, 1000)
        
        # Calculate prorated addition
        if new_included > old_allocation:
            # Add the difference in allocation
            credit_boost = new_included - old_allocation
            final_included = current_included + credit_boost
        else:
            final_included = new_included
        
        cycle_end = datetime.now() + timedelta(days=30)
        
        async with self.db.acquire() as conn:
            await conn.execute("""
                UPDATE credit_wallets 
                SET plan = $2,
                    included_credits = $3,
                    cycle_start = NOW(),
                    cycle_end = $4,
                    updated_at = NOW()
                WHERE user_id = $1
            """, user_id, new_plan, final_included, cycle_end)
            
            # Log transaction
            await conn.execute("""
                INSERT INTO credit_transactions 
                (user_id, amount, balance_after, transaction_type, description, metadata)
                VALUES ($1, $2, $3, 'plan_upgrade', $4, $5)
            """, user_id, final_included, final_included + wallet.get('booster_credits', 0),
                f"Upgraded from {old_plan} to {new_plan}",
                {"old_plan": old_plan, "new_plan": new_plan, "payment_id": payment_id})
        
        logger.info(f"Upgraded {user_id}: {old_plan} → {new_plan}, {final_included} credits")
        
        return {
            "old_plan": old_plan,
            "new_plan": new_plan,
            "new_included_credits": final_included,
            "cycle_end": cycle_end.isoformat()
        }
    
    async def get_transaction_history(
        self, 
        user_id: str, 
        limit: int = 50
    ) -> List[Dict]:
        """Get recent credit transactions"""
        async with self.db.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM credit_transactions 
                WHERE user_id = $1 
                ORDER BY created_at DESC 
                LIMIT $2
            """, user_id, limit)
            
            return [dict(r) for r in rows]
    
    async def check_can_use(self, user_id: str, required_credits: int) -> Dict[str, Any]:
        """Check if user can afford an operation"""
        balance = await self.get_balance(user_id)
        
        can_use = balance['total'] >= required_credits
        
        return {
            "can_use": can_use,
            "required": required_credits,
            "available": balance['total'],
            "shortfall": max(0, required_credits - balance['total']),
            "plan": balance['plan']
        }


# ============================================================================
# BOOSTER STORE
# ============================================================================

class BoosterStore:
    """Manage booster pack purchases"""
    
    def __init__(self, db_pool):
        self.db = db_pool
    
    def get_all_packs(self) -> Dict[str, Dict]:
        """Get all available booster packs"""
        return BOOSTER_PACKS
    
    def get_pack(self, sku: str) -> Optional[Dict]:
        """Get specific booster pack details"""
        return BOOSTER_PACKS.get(sku)
    
    async def create_purchase(
        self, 
        user_id: str, 
        sku: str, 
        razorpay_order_id: str
    ) -> Dict[str, Any]:
        """Record pending booster purchase"""
        pack = self.get_pack(sku)
        if not pack:
            return {"error": f"Unknown SKU: {sku}"}
        
        async with self.db.acquire() as conn:
            result = await conn.fetchrow("""
                INSERT INTO booster_purchases 
                (user_id, sku, credits, amount_paise, razorpay_order_id, status)
                VALUES ($1, $2, $3, $4, $5, 'pending')
                RETURNING id
            """, user_id, sku, pack['credits'], pack['price_paise'], razorpay_order_id)
            
            return {
                "purchase_id": result['id'],
                "sku": sku,
                "credits": pack['credits'],
                "amount_paise": pack['price_paise'],
                "status": "pending"
            }
    
    async def complete_purchase(
        self, 
        razorpay_order_id: str, 
        razorpay_payment_id: str
    ) -> Optional[Dict[str, Any]]:
        """Mark purchase as complete and return details"""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("""
                UPDATE booster_purchases 
                SET status = 'completed', razorpay_payment_id = $2
                WHERE razorpay_order_id = $1 AND status = 'pending'
                RETURNING *
            """, razorpay_order_id, razorpay_payment_id)
            
            if row:
                return dict(row)
            return None


# ============================================================================
# INITIALIZATION
# ============================================================================

async def init_billing_store(db_pool) -> Tuple[CreditWallet, BoosterStore]:
    """Initialize billing stores"""
    wallet = CreditWallet(db_pool)
    booster = BoosterStore(db_pool)
    
    await wallet.ensure_tables()
    
    logger.info("✅ Billing store initialized")
    logger.info(f"   Credit allocations: {_DEFAULT_INCLUDED_CREDITS}")
    logger.info(f"   Booster packs: {list(BOOSTER_PACKS.keys())}")
    
    return wallet, booster
