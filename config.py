from __future__ import annotations

"""KnowEasy Engine API - Central Configuration (Single Source of Truth)

PHASE-1 STABLE RULES (LOCKED):
- Missing ENV vars must NOT crash the app.
- AI must auto-disable if the selected provider key is missing.
- DB & Redis are optional (handled in their own modules).
- Rate limiting & cache must have safe defaults.

This module MUST export every constant imported by:
- router.py
- orchestrator.py
- models.py
- ai_router.py (Track-B)
- redis_store.py

Provider strategy:
- Today: Gemini only in production.
- Future: add OpenAI/Claude by only setting env keys + AI_PROVIDER.
"""

import os


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
# Redis (redis_store.py)
# -----------------------------
# Optional. If empty, redis features auto-disable.
# Render usually provides REDIS_URL if you attach a Redis service.
REDIS_URL: str = _env_str("REDIS_URL", "")


# -----------------------------
# Rate limiting (router.py)
# -----------------------------
RATE_LIMIT_PER_MINUTE: int = _env_int("RATE_LIMIT_PER_MINUTE", 60)
RATE_LIMIT_BURST: int = _env_int("RATE_LIMIT_BURST", 20)
RATE_LIMIT_WINDOW_SECONDS: int = _env_int("RATE_LIMIT_WINDOW_SECONDS", 60)


# -----------------------------
# Solve caching (router.py)
# -----------------------------
SOLVE_CACHE_TTL_SECONDS: int = _env_int("SOLVE_CACHE_TTL_SECONDS", 300)


# -----------------------------
# AI Orchestrator controls
# -----------------------------
# provider values supported (case-insensitive):
#   - gemini / google-genai / google_genai
#   - openai / chatgpt
#   - claude / anthropic
AI_PROVIDER: str = _env_str("AI_PROVIDER", "gemini").strip().lower()
AI_MODE: str = _env_str("AI_MODE", "mentor").strip().lower()
AI_TIMEOUT_SECONDS: int = _env_int("AI_TIMEOUT_SECONDS", 20)

MAX_STEPS: int = _env_int("MAX_STEPS", 8)
MAX_CHARS_ANSWER: int = _env_int("MAX_CHARS_ANSWER", 1800)
LOW_CONFIDENCE_THRESHOLD: float = _env_float("LOW_CONFIDENCE_THRESHOLD", 0.45)


# -----------------------------
# Gemini config (models.py)
# -----------------------------
GEMINI_API_KEY: str = (
    _env_str("GEMINI_API_KEY", "")
    or _env_str("GOOGLE_API_KEY", "")
    or _env_str("GOOGLE_GENAI_API_KEY", "")
)

GEMINI_PRIMARY_MODEL: str = _env_str("GEMINI_PRIMARY_MODEL", "gemini-2.0-flash")
GEMINI_FALLBACK_MODEL: str = _env_str("GEMINI_FALLBACK_MODEL", "gemini-1.5-flash")

# Keep legacy name used in some modules
GEMINI_TIMEOUT_S: int = _env_int("GEMINI_TIMEOUT_S", AI_TIMEOUT_SECONDS)

CB_FAILURE_THRESHOLD: int = _env_int("CB_FAILURE_THRESHOLD", 3)
CB_COOLDOWN_S: int = _env_int("CB_COOLDOWN_S", 30)


# -----------------------------
# OpenAI config (ai_router.py / future)
# -----------------------------
OPENAI_API_KEY: str = (
    _env_str("OPENAI_API_KEY", "")
    or _env_str("CHATGPT_API_KEY", "")
)
OPENAI_MODEL: str = _env_str("OPENAI_MODEL", "gpt-4o-mini")


# -----------------------------
# Anthropic/Claude config (ai_router.py / future)
# -----------------------------
ANTHROPIC_API_KEY: str = (
    _env_str("ANTHROPIC_API_KEY", "")
    or _env_str("CLAUDE_API_KEY", "")
)
ANTHROPIC_MODEL: str = _env_str("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")


# -----------------------------
# AI enabled (auto-disable if key missing)
# -----------------------------
_ai_enabled_flag: bool = _env_bool("AI_ENABLED", True)

# Normalize provider aliases
if AI_PROVIDER in ("google-genai", "google_genai"):
    AI_PROVIDER = "gemini"
elif AI_PROVIDER in ("chatgpt",):
    AI_PROVIDER = "openai"
elif AI_PROVIDER in ("anthropic",):
    AI_PROVIDER = "claude"

# Provider-aware enablement
if AI_PROVIDER == "gemini":
    AI_ENABLED: bool = bool(_ai_enabled_flag and GEMINI_API_KEY)
elif AI_PROVIDER == "openai":
    AI_ENABLED = bool(_ai_enabled_flag and OPENAI_API_KEY)
elif AI_PROVIDER == "claude":
    AI_ENABLED = bool(_ai_enabled_flag and ANTHROPIC_API_KEY)
else:
    # Safety: unknown provider => AI off
    AI_ENABLED = False


__all__ = [
    # auth
    "KE_API_KEY",
    # redis
    "REDIS_URL",
    # rate limit
    "RATE_LIMIT_PER_MINUTE",
    "RATE_LIMIT_BURST",
    "RATE_LIMIT_WINDOW_SECONDS",
    # cache
    "SOLVE_CACHE_TTL_SECONDS",
    # ai controls
    "AI_ENABLED",
    "AI_PROVIDER",
    "AI_MODE",
    "AI_TIMEOUT_SECONDS",
    "MAX_STEPS",
    "MAX_CHARS_ANSWER",
    "LOW_CONFIDENCE_THRESHOLD",
    # gemini
    "GEMINI_API_KEY",
    "GEMINI_PRIMARY_MODEL",
    "GEMINI_FALLBACK_MODEL",
    "GEMINI_TIMEOUT_S",
    "CB_FAILURE_THRESHOLD",
    "CB_COOLDOWN_S",
    # openai
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    # anthropic
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
]
