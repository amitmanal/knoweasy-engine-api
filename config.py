"""Central configuration for KnowEasy Engine API (Phase-1 Stable).

Design goals:
- Export ALL constants used across the codebase (router/orchestrator/models/redis_store/db).
- Never crash on missing environment variables.
- Keep Gemini-only working now, but keep the shape ready for multi-provider later.
"""

from __future__ import annotations

import os
from typing import Optional


# ----------------------------
# helpers
# ----------------------------
def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip()
    return v if v != "" else default


def _env_bool(name: str, default: bool = False) -> bool:
    v = _env(name)
    if v is None:
        return default
    return v.lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    v = _env(name)
    if v is None:
        return default
    try:
        return int(v)
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    v = _env(name)
    if v is None:
        return default
    try:
        return float(v)
    except Exception:
        return default


# ----------------------------
# service identity
# ----------------------------
SERVICE_NAME: str = _env("SERVICE_NAME", "knoweasy-engine-api") or "knoweasy-engine-api"
API_PUBLIC_BASE_URL: str = _env("API_PUBLIC_BASE_URL", "") or ""


# ----------------------------
# AI settings (Gemini now)
# ----------------------------
GEMINI_API_KEY: Optional[str] = _env("GEMINI_API_KEY")

# Provider/mode are strings so later we can route: gemini / openai / anthropic
AI_PROVIDER: str = (_env("AI_PROVIDER", "gemini") or "gemini").lower()
AI_MODE: str = (_env("AI_MODE", "fast") or "fast").lower()

# Unified timeout for any provider (seconds)
AI_TIMEOUT_SECONDS: int = _env_int("AI_TIMEOUT_SECONDS", 20)

# Backward-compatible alias (some modules import GEMINI_TIMEOUT_S)
GEMINI_TIMEOUT_S: int = AI_TIMEOUT_SECONDS

# Model names (Gemini)
GEMINI_PRIMARY_MODEL: str = _env("GEMINI_PRIMARY_MODEL", "gemini-2.5-flash") or "gemini-2.5-flash"
GEMINI_FALLBACK_MODEL: str = _env("GEMINI_FALLBACK_MODEL", "gemini-2.5-pro") or "gemini-2.5-pro"

# Enable flag: if AI_ENABLED env var is set, respect it.
# Otherwise, auto-enable when API key exists.
_ai_enabled_env = _env("AI_ENABLED")
if _ai_enabled_env is None:
    AI_ENABLED: bool = bool(GEMINI_API_KEY)
else:
    AI_ENABLED = _ai_enabled_env.lower() in {"1", "true", "yes", "y", "on"}

# Orchestrator output shaping / safety thresholds
MAX_STEPS: int = _env_int("MAX_STEPS", 8)
MAX_CHARS_ANSWER: int = _env_int("MAX_CHARS_ANSWER", 6000)
LOW_CONFIDENCE_THRESHOLD: float = _env_float("LOW_CONFIDENCE_THRESHOLD", 0.35)

# Simple circuit breaker defaults (used by models.py if implemented)
CB_FAILURE_THRESHOLD: int = _env_int("CB_FAILURE_THRESHOLD", 3)
CB_COOLDOWN_S: int = _env_int("CB_COOLDOWN_S", 30)


# ----------------------------
# rate limiting + caching
# ----------------------------
RATE_LIMIT_WINDOW_SECONDS: int = _env_int("RATE_LIMIT_WINDOW_SECONDS", 60)
RATE_LIMIT_PER_MINUTE: int = _env_int("RATE_LIMIT_PER_MINUTE", 30)
RATE_LIMIT_BURST: int = _env_int("RATE_LIMIT_BURST", 10)

# Optional solve cache (Redis-backed if REDIS_URL is set)
SOLVE_CACHE_TTL_SECONDS: int = _env_int("SOLVE_CACHE_TTL_SECONDS", 3600)


# ----------------------------
# optional shared key (basic protection)
# ----------------------------
KE_API_KEY: Optional[str] = _env("KE_API_KEY")


# ----------------------------
# DB / Redis (optional)
# ----------------------------
DATABASE_URL: Optional[str] = _env("DATABASE_URL")
DB_SSLMODE: Optional[str] = _env("DB_SSLMODE", "require" if DATABASE_URL else None)

REDIS_URL: Optional[str] = _env("REDIS_URL")


__all__ = [
    # identity
    "SERVICE_NAME",
    "API_PUBLIC_BASE_URL",
    # ai
    "AI_ENABLED",
    "AI_PROVIDER",
    "AI_MODE",
    "AI_TIMEOUT_SECONDS",
    "MAX_STEPS",
    "MAX_CHARS_ANSWER",
    "LOW_CONFIDENCE_THRESHOLD",
    "GEMINI_TIMEOUT_S",
    "GEMINI_API_KEY",
    "GEMINI_PRIMARY_MODEL",
    "GEMINI_FALLBACK_MODEL",
    "CB_FAILURE_THRESHOLD",
    "CB_COOLDOWN_S",
    # rate limit / cache
    "RATE_LIMIT_WINDOW_SECONDS",
    "RATE_LIMIT_PER_MINUTE",
    "RATE_LIMIT_BURST",
    "SOLVE_CACHE_TTL_SECONDS",
    # auth-ish
    "KE_API_KEY",
    # db/redis
    "DATABASE_URL",
    "DB_SSLMODE",
    "REDIS_URL",
]
