from __future__ import annotations

"""
KnowEasy Engine API - Central Configuration (Single Source of Truth)

LOCKED INTENT:
- Missing ENV vars must NOT crash app.
- AI must auto-disable if the AI key is missing.
- DB & Redis are optional (handled in their own modules).
- Rate limiting & cache must have safe defaults.

This module MUST export every constant imported by router.py, orchestrator.py, models.py.
"""

import os
from typing import Optional


# -----------------------------
# Safe env getters (never crash)
# -----------------------------
def _env_str(key: str, default: str = "") -> str:
    v = os.getenv(key)
    if v is None:
        return default
    return str(v).strip()


def _env_int(key: str, default: int) -> int:
    try:
        return int(str(os.getenv(key, "")).strip() or default)
    except Exception:
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(str(os.getenv(key, "")).strip() or default)
    except Exception:
        return default


def _env_bool(key: str, default: bool) -> bool:
    v = os.getenv(key)
    if v is None:
        return default
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off"):
        return False
    return default


# ------------------------------------
# Frontend/API auth (optional soft-gate)
# ------------------------------------
# If set, /solve expects header: X-KE-KEY == KE_API_KEY
KE_API_KEY: str = _env_str("KE_API_KEY", "")

# -----------------------------
# Rate limiting (router.py)
# -----------------------------
# Default: allow normal traffic on Render free tier without being too strict.
RATE_LIMIT_PER_MINUTE: int = _env_int("RATE_LIMIT_PER_MINUTE", 60)  # steady rate
RATE_LIMIT_BURST: int = _env_int("RATE_LIMIT_BURST", 20)            # short burst
RATE_LIMIT_WINDOW_SECONDS: int = _env_int("RATE_LIMIT_WINDOW_SECONDS", 60)

# -----------------------------
# Solve caching (router.py)
# -----------------------------
# If Redis is enabled, router will use it; otherwise it may fall back to in-memory.
# TTL in seconds
SOLVE_CACHE_TTL_SECONDS: int = _env_int("SOLVE_CACHE_TTL_SECONDS", 300)

# -----------------------------
# AI Orchestrator controls
# -----------------------------
# Provider/mode are currently used for logging + future compatibility.
AI_PROVIDER: str = _env_str("AI_PROVIDER", "gemini").lower()
AI_MODE: str = _env_str("AI_MODE", "mentor").lower()

# Timeout used by orchestrator/models (seconds)
AI_TIMEOUT_SECONDS: int = _env_int("AI_TIMEOUT_SECONDS", 20)

# Response shaping / guardrails
MAX_STEPS: int = _env_int("MAX_STEPS", 8)
MAX_CHARS_ANSWER: int = _env_int("MAX_CHARS_ANSWER", 1800)
LOW_CONFIDENCE_THRESHOLD: float = _env_float("LOW_CONFIDENCE_THRESHOLD", 0.45)

# -----------------------------
# Gemini client config (models.py)
# -----------------------------
# Accept common env key aliases safely (no crash if missing).
# Primary expected key is GEMINI_API_KEY.
GEMINI_API_KEY: str = (
    _env_str("GEMINI_API_KEY", "")
    or _env_str("GOOGLE_API_KEY", "")
    or _env_str("GOOGLE_GENAI_API_KEY", "")
)

GEMINI_PRIMARY_MODEL: str = _env_str("GEMINI_PRIMARY_MODEL", "gemini-2.0-flash")
GEMINI_FALLBACK_MODEL: str = _env_str("GEMINI_FALLBACK_MODEL", "gemini-1.5-flash")

# models.py expects GEMINI_TIMEOUT_S; keep aligned with orchestrator timeout
GEMINI_TIMEOUT_S: int = _env_int("GEMINI_TIMEOUT_S", AI_TIMEOUT_SECONDS)

# Simple circuit breaker defaults
CB_FAILURE_THRESHOLD: int = _env_int("CB_FAILURE_THRESHOLD", 3)
CB_COOLDOWN_S: int = _env_int("CB_COOLDOWN_S", 30)

# -----------------------------
# AI enabled (auto-disable if key missing)
# -----------------------------
# User can force disable via AI_ENABLED=false.
# Even if AI_ENABLED=true, we auto-disable if Gemini key missing.
_ai_enabled_flag: bool = _env_bool("AI_ENABLED", True)
AI_ENABLED: bool = bool(_ai_enabled_flag and GEMINI_API_KEY)

# Optional: if provider is not gemini, disable (safety: avoid half-configured modes)
if AI_PROVIDER not in ("gemini", "google-genai", "google_genai"):
    AI_ENABLED = False


# --------------------------------
# Explicit export list (stability)
# --------------------------------
__all__ = [
    "KE_API_KEY",
    "RATE_LIMIT_PER_MINUTE",
    "RATE_LIMIT_BURST",
    "RATE_LIMIT_WINDOW_SECONDS",
    "SOLVE_CACHE_TTL_SECONDS",
    "AI_ENABLED",
    "AI_PROVIDER",
    "AI_MODE",
    "AI_TIMEOUT_SECONDS",
    "MAX_STEPS",
    "MAX_CHARS_ANSWER",
    "LOW_CONFIDENCE_THRESHOLD",
    "GEMINI_API_KEY",
    "GEMINI_PRIMARY_MODEL",
    "GEMINI_FALLBACK_MODEL",
    "GEMINI_TIMEOUT_S",
    "CB_FAILURE_THRESHOLD",
    "CB_COOLDOWN_S",
]
