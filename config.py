# src/config.py
"""
Central configuration for KnowEasy Engine API.

Goals:
- Never crash on missing env vars (safe defaults)
- Export stable names used across app (router/main/orchestrator/db)
- Keep parsing/typing consistent
"""

from __future__ import annotations

import os
from typing import Optional


# ----------------------------
# helpers
# ----------------------------
def _env(key: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(key)
    if v is None:
        return default
    v = v.strip()
    return v if v != "" else default


def _env_bool(key: str, default: bool = False) -> bool:
    v = _env(key, None)
    if v is None:
        return default
    return v.lower() in {"1", "true", "yes", "y", "on"}


def _env_int(key: str, default: int) -> int:
    v = _env(key, None)
    if v is None:
        return default
    try:
        return int(v)
    except Exception:
        return default


# ----------------------------
# app metadata
# ----------------------------
APP_NAME: str = _env("APP_NAME", "knoweasy-engine-api") or "knoweasy-engine-api"
ENV: str = _env("ENV", _env("RENDER_ENV", "production")) or "production"
APP_VERSION: str = _env("APP_VERSION", _env("VERSION", "1.0.0")) or "1.0.0"
LOG_LEVEL: str = _env("LOG_LEVEL", "INFO") or "INFO"


# ----------------------------
# AI config
# ----------------------------
# NOTE: Your Render screenshot shows AI_* env vars exist; still keep defaults safe.
AI_ENABLED: bool = _env_bool("AI_ENABLED", False)
AI_MODE: str = _env("AI_MODE", "safe") or "safe"          # e.g. safe / pro / debug
AI_PROVIDER: str = _env("AI_PROVIDER", "gemini") or "gemini"
AI_TIMEOUT_SECONDS: int = _env_int("AI_TIMEOUT_SECONDS", 25)

# Provider keys (optional)
GEMINI_API_KEY: Optional[str] = _env("GEMINI_API_KEY", None)
OPENAI_API_KEY: Optional[str] = _env("OPENAI_API_KEY", None)


# ----------------------------
# database config (Postgres)
# ----------------------------
# Render usually provides DATABASE_URL, but you also created your own DATABASE_URL env.
DATABASE_URL: Optional[str] = _env("DATABASE_URL", _env("POSTGRES_URL", None))
DB_SSLMODE: str = _env("DB_SSLMODE", "require") or "require"

# Enable DB only if URL exists and doesn't look invalid
DB_ENABLED: bool = _env_bool("DB_ENABLED", True) and bool(DATABASE_URL)


# ----------------------------
# redis config
# ----------------------------
REDIS_URL: Optional[str] = _env("REDIS_URL", None)
REDIS_ENABLED: bool = _env_bool("REDIS_ENABLED", True) and bool(REDIS_URL)


# ----------------------------
# rate limiting config
# ----------------------------
# These names MUST exist because router.py imports them.
RATE_LIMIT_ENABLED: bool = _env_bool("RATE_LIMIT_ENABLED", True)

# Requests per minute per IP (basic token-bucket/rolling window style)
RATE_LIMIT_PER_MINUTE: int = _env_int("RATE_LIMIT_PER_MINUTE", 60)

# Burst capacity (your missing symbol)
RATE_LIMIT_BURST: int = _env_int("RATE_LIMIT_BURST", 20)

# Optional: allow local/dev bypass
RATE_LIMIT_TRUST_PROXY_HEADERS: bool = _env_bool("RATE_LIMIT_TRUST_PROXY_HEADERS", True)


# ----------------------------
# caching config (solve cache)
# ----------------------------
SOLVE_CACHE_ENABLED: bool = _env_bool("SOLVE_CACHE_ENABLED", True) and (REDIS_ENABLED or False)
SOLVE_CACHE_TTL_SECONDS: int = _env_int("SOLVE_CACHE_TTL_SECONDS", 600)


# ----------------------------
# CORS / security basics
# ----------------------------
# Comma separated list. Keep permissive default ONLY if you already handle it elsewhere.
CORS_ALLOW_ORIGINS_RAW: str = _env("CORS_ALLOW_ORIGINS", "*") or "*"
CORS_ALLOW_ORIGINS = [o.strip() for o in CORS_ALLOW_ORIGINS_RAW.split(",") if o.strip()]

# Used by some deployments / middleware
TRUST_PROXY_HEADERS: bool = _env_bool("TRUST_PROXY_HEADERS", True)


# ----------------------------
# convenience dict (optional)
# ----------------------------
def as_dict() -> dict:
    return {
        "APP_NAME": APP_NAME,
        "ENV": ENV,
        "APP_VERSION": APP_VERSION,
        "LOG_LEVEL": LOG_LEVEL,
        "AI_ENABLED": AI_ENABLED,
        "AI_MODE": AI_MODE,
        "AI_PROVIDER": AI_PROVIDER,
        "AI_TIMEOUT_SECONDS": AI_TIMEOUT_SECONDS,
        "DB_ENABLED": DB_ENABLED,
        "REDIS_ENABLED": REDIS_ENABLED,
        "RATE_LIMIT_ENABLED": RATE_LIMIT_ENABLED,
        "RATE_LIMIT_PER_MINUTE": RATE_LIMIT_PER_MINUTE,
        "RATE_LIMIT_BURST": RATE_LIMIT_BURST,
        "SOLVE_CACHE_ENABLED": SOLVE_CACHE_ENABLED,
        "SOLVE_CACHE_TTL_SECONDS": SOLVE_CACHE_TTL_SECONDS,
    }
