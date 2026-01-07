# config.py
"""
Central configuration for KnowEasy Engine API.

Goal:
- Never crash on missing env vars
- Provide safe defaults
- Export a stable set of names that router/main/orchestrator can import

All values are read from environment variables (Render -> Environment).
"""

from __future__ import annotations

import os
from typing import Optional


# -------------------------
# helpers
# -------------------------
def _get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(key)
    if v is None:
        return default
    v = v.strip()
    return v if v != "" else default


def _as_bool(v: Optional[str], default: bool = False) -> bool:
    if v is None:
        return default
    s = v.strip().lower()
    if s in ("1", "true", "yes", "y", "on", "enabled"):
        return True
    if s in ("0", "false", "no", "n", "off", "disabled"):
        return False
    return default


def _as_int(v: Optional[str], default: int) -> int:
    try:
        return int(str(v).strip())
    except Exception:
        return default


# -------------------------
# basic app config
# -------------------------
APP_NAME: str = _get_env("APP_NAME", "knoweasy-engine-api") or "knoweasy-engine-api"
ENV: str = _get_env("ENV", "production") or "production"
LOG_LEVEL: str = _get_env("LOG_LEVEL", "INFO") or "INFO"

# CORS (if you use it elsewhere)
ALLOWED_ORIGINS: str = _get_env("ALLOWED_ORIGINS", "*") or "*"


# -------------------------
# AI config
# -------------------------
AI_ENABLED: bool = _as_bool(_get_env("AI_ENABLED"), default=False)
AI_MODE: str = _get_env("AI_MODE", "exam_safe") or "exam_safe"
AI_PROVIDER: str = _get_env("AI_PROVIDER", "gemini") or "gemini"
AI_TIMEOUT_SECONDS: int = _as_int(_get_env("AI_TIMEOUT_SECONDS"), default=25)

# Gemini (your env shows GEMINI_API_KEY exists)
GEMINI_API_KEY: Optional[str] = _get_env("GEMINI_API_KEY", None)


# -------------------------
# DB config (Postgres)
# -------------------------
# On Render: set DATABASE_URL (external/internal), and optionally DB_SSLMODE=require
DATABASE_URL: Optional[str] = _get_env("DATABASE_URL", None)
DB_SSLMODE: str = _get_env("DB_SSLMODE", "require") or "require"

# Optional flag if your code checks it
DB_ENABLED: bool = _as_bool(_get_env("DB_ENABLED"), default=True)


# -------------------------
# Redis config
# -------------------------
REDIS_URL: Optional[str] = _get_env("REDIS_URL", None)
REDIS_ENABLED: bool = _as_bool(_get_env("REDIS_ENABLED"), default=True)


# -------------------------
# Rate limiting config (router imports these)
# -------------------------
RATE_LIMIT_ENABLED: bool = _as_bool(_get_env("RATE_LIMIT_ENABLED"), default=True)

# Window size in seconds (required by router import)
RATE_LIMIT_WINDOW_SECONDS: int = _as_int(_get_env("RATE_LIMIT_WINDOW_SECONDS"), default=60)

# Max requests allowed per window
RATE_LIMIT_MAX_REQUESTS: int = _as_int(_get_env("RATE_LIMIT_MAX_REQUESTS"), default=30)

# Extra burst tokens allowed temporarily
RATE_LIMIT_BURST: int = _as_int(_get_env("RATE_LIMIT_BURST"), default=10)


# -------------------------
# Solve cache config (optional)
# -------------------------
SOLVE_CACHE_ENABLED: bool = _as_bool(_get_env("SOLVE_CACHE_ENABLED"), default=True)
SOLVE_CACHE_TTL_SECONDS: int = _as_int(_get_env("SOLVE_CACHE_TTL_SECONDS"), default=300)


# Make sure star-imports / explicit imports remain stable
__all__ = [
    "APP_NAME",
    "ENV",
    "LOG_LEVEL",
    "ALLOWED_ORIGINS",
    "AI_ENABLED",
    "AI_MODE",
    "AI_PROVIDER",
    "AI_TIMEOUT_SECONDS",
    "GEMINI_API_KEY",
    "DATABASE_URL",
    "DB_SSLMODE",
    "DB_ENABLED",
    "REDIS_URL",
    "REDIS_ENABLED",
    "RATE_LIMIT_ENABLED",
    "RATE_LIMIT_WINDOW_SECONDS",
    "RATE_LIMIT_MAX_REQUESTS",
    "RATE_LIMIT_BURST",
    "SOLVE_CACHE_ENABLED",
    "SOLVE_CACHE_TTL_SECONDS",
]
