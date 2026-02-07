"""Luma Credit Configuration

This module defines credit costs for all AI features.
Credits are the universal currency for AI operations across KnowEasy.

Design Principles:
- Simple features cost fewer credits
- Complex features (images, PDFs) cost more
- Modes affect cost (Lite < Tutor < Mastery)
- Fair pricing based on actual AI token usage

Cost Calibration:
- Average AI cost per credit: ~₹0.50
- This ensures profitability across all plans
"""

from __future__ import annotations
from typing import Dict

# ============================================================================
# AI FEATURE CREDIT COSTS
# ============================================================================

# Base costs for text-only questions by mode
TEXT_CREDIT_COSTS: Dict[str, float] = {
    "lite": 0.5,      # Quick answer, minimal tokens
    "tutor": 1.0,     # Full Answer Blueprint
    "mastery": 2.0,   # Deep analysis, multiple methods
}

# Additional costs for special features
FEATURE_CREDIT_COSTS: Dict[str, float] = {
    "follow_up": 0.5,        # Cheaper due to cached context
    "image_analysis": 3.0,   # Vision model processing
    "pdf_processing": 5.0,   # Document parsing + OCR
    "luma_ai_simple": 0.5,   # Context-aware, short answers
}

# ============================================================================
# PLAN MONTHLY CREDIT ALLOCATIONS
# ============================================================================

PLAN_MONTHLY_CREDITS: Dict[str, int] = {
    "free": 300,   # 10 credits/day × 30 days
    "pro": 300,    # 10 credits/day average usage
    "max": 1200,   # 40 credits/day for power users
}

# Daily limits for free tier (prevents abuse)
FREE_DAILY_LIMIT: int = 10


# ============================================================================
# BOOSTER PACK DEFINITIONS
# ============================================================================

BOOSTER_PACKS: Dict[str, Dict[str, any]] = {
    "small": {
        "credits": 50,
        "price_paise": 9900,  # ₹99
        "sku": "booster_50",
    },
    "medium": {
        "credits": 150,
        "price_paise": 24900,  # ₹249
        "sku": "booster_150",
    },
    "large": {
        "credits": 500,
        "price_paise": 69900,  # ₹699
        "sku": "booster_500",
    },
}


# ============================================================================
# CREDIT CALCULATION HELPERS
# ============================================================================

def calculate_credits(
    mode: str = "tutor",
    has_image: bool = False,
    has_pdf: bool = False,
    is_follow_up: bool = False,
    is_luma_simple: bool = False,
) -> float:
    """Calculate credit cost for an AI request.
    
    Args:
        mode: Answer mode (lite/tutor/mastery)
        has_image: Whether image is attached
        has_pdf: Whether PDF is attached
        is_follow_up: Whether this is a follow-up question
        is_luma_simple: Whether this is simple Luma AI chat
        
    Returns:
        Total credits required
        
    Examples:
        >>> calculate_credits(mode="tutor")
        1.0
        >>> calculate_credits(mode="lite", has_image=True)
        3.5
        >>> calculate_credits(mode="mastery", has_pdf=True)
        7.0
    """
    # Start with base cost
    if is_luma_simple:
        cost = FEATURE_CREDIT_COSTS["luma_ai_simple"]
    elif is_follow_up:
        cost = FEATURE_CREDIT_COSTS["follow_up"]
    else:
        cost = TEXT_CREDIT_COSTS.get(mode, 1.0)
    
    # Add feature costs
    if has_image:
        cost += FEATURE_CREDIT_COSTS["image_analysis"]
    
    if has_pdf:
        cost += FEATURE_CREDIT_COSTS["pdf_processing"]
    
    return cost


def get_plan_credits(plan: str) -> int:
    """Get monthly credit allocation for a plan.
    
    Args:
        plan: Plan name (free/pro/max)
        
    Returns:
        Monthly credit allocation
    """
    return PLAN_MONTHLY_CREDITS.get(plan.lower(), 0)


def get_booster_pack(sku: str) -> Dict[str, any] | None:
    """Get booster pack details by SKU.
    
    Args:
        sku: Booster pack SKU
        
    Returns:
        Pack details or None if not found
    """
    for pack in BOOSTER_PACKS.values():
        if pack["sku"] == sku:
            return pack
    return None


# ============================================================================
# VALIDATION
# ============================================================================

def validate_mode(mode: str) -> str:
    """Validate and normalize mode string.
    
    Args:
        mode: Raw mode string
        
    Returns:
        Normalized mode (lite/tutor/mastery)
        
    Raises:
        ValueError: If mode is invalid
    """
    mode = str(mode).lower().strip()
    if mode not in TEXT_CREDIT_COSTS:
        raise ValueError(f"Invalid mode: {mode}. Must be lite/tutor/mastery")
    return mode


def validate_plan(plan: str) -> str:
    """Validate and normalize plan string.
    
    Args:
        plan: Raw plan string
        
    Returns:
        Normalized plan (free/pro/max)
        
    Raises:
        ValueError: If plan is invalid
    """
    plan = str(plan).lower().strip()
    if plan not in PLAN_MONTHLY_CREDITS:
        raise ValueError(f"Invalid plan: {plan}. Must be free/pro/max")
    return plan
