# config.py
"""
KnowEasy Engine API - runtime configuration

RULES:
- Single source of truth is Environment Variables (Render / local .env)
- This module MUST NOT raise on import (keeps deploy stable).
- All settings that other modules import MUST be defined here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


# -----------------------------
# Helpers (safe parsing)
# -----------------------------
def _getenv(key: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(key)
    if val is None:
        return default
    val = val.strip()
    return val if val != "" else default


def _to_bool(val: Optional[str], default: bool = False) -> bool:
    if val is None:
        return default
    v = val.strip().lower()
    if v in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


def _to_int(val: Optional[str], default: int) -> int:
    if val is None:
        return default
    try:
        return int(val.strip())
    except Exception:
        return default


# -----------------------------
# Public config values (imported elsewhere)
# -----------------------------
# App
APP_ENV: str = _getenv("APP_ENV", "prod") or "prod"
APP_NAME: str = _getenv("APP_NAME", "knoweasy-engine-api") or "knoweasy-engine-api"
APP_VERSION: str = _getenv("APP_VERSION", "1.0.0") or "1.0.0"

# AI
AI_ENABLED: bool = _to_bool(_getenv("AI_ENABLED", "false"), default=False)
AI_MODE: str = _getenv("AI_MODE", "prod") or "prod"          # e.g., dev/prod
AI_PROVIDER: str = _getenv("AI_PROVIDER", "gemini") or "gemini"
AI_TIMEOUT_SECONDS: int = _to_int(_getenv("AI_TIMEOUT_SECONDS", "30"), default=30)

# Secrets / Provider Keys
GEMINI_API_KEY: Optional[str] = _getenv("GEMINI_API_KEY")  # may be None if AI disabled

# Database
DATABASE_URL: Optional[str] = _getenv("DATABASE_URL")  # postgres connection string
DB_SSLMODE: str = _getenv("DB_SSLMODE", "require") or "require"

# Redis / Cache
REDIS_URL: Optional[str] = _getenv("REDIS_URL")  # rediss://... or redis://...

# Rate limiting / caching knobs (safe defaults)
RATE_LIMIT_ENABLED: bool = _to_bool(_getenv("RATE_LIMIT_ENABLED", "true"), default=True)
RATE_LIMIT_PER_MINUTE: int = _to_int(_getenv("RATE_LIMIT_PER_MINUTE", "60"), default=60)

SOLVE_CACHE_ENABLED: bool = _to_bool(_getenv("SOLVE_CACHE_ENABLED", "true"), default=True)
SOLVE_CACHE_TTL_SECONDS: int = _to_int(_getenv("SOLVE_CACHE_TTL_SECONDS", "3600"), default=3600)

# Logging / Observability
LOG_LEVEL: str = _getenv("LOG_LEVEL", "INFO") or "INFO"
REQUEST_ID_HEADER: str = _getenv("REQUEST_ID_HEADER", "X-Request-ID") or "X-Request-ID"


# -----------------------------
# Optional: structured access
# -----------------------------
@dataclass(frozen=True)
class Settings:
    app_env: str
    app_name: str
    app_version: str

    ai_enabled: bool
    ai_mode: str
    ai_provider: str
    ai_timeout_seconds: int
    gemini_api_key: Optional[str]

    database_url: Optional[str]
    db_sslmode: str

    redis_url: Optional[str]

    rate_limit_enabled: bool
    rate_limit_per_minute: int

    solve_cache_enabled: bool
    solve_cache_ttl_seconds: int

    log_level: str
    request_id_header: str


def get_settings() -> Settings:
    """Call this from code if you prefer a single object instead of globals."""
    return Settings(
        app_env=APP_ENV,
        app_name=APP_NAME,
        app_version=APP_VERSION,
        ai_enabled=AI_ENABLED,
        ai_mode=AI_MODE,
        ai_provider=AI_PROVIDER,
        ai_timeout_seconds=AI_TIMEOUT_SECONDS,
        gemini_api_key=GEMINI_API_KEY,
        database_url=DATABASE_URL,
        db_sslmode=DB_SSLMODE,
        redis_url=REDIS_URL,
        rate_limit_enabled=RATE_LIMIT_ENABLED,
        rate_limit_per_minute=RATE_LIMIT_PER_MINUTE,
        solve_cache_enabled=SOLVE_CACHE_ENABLED,
        solve_cache_ttl_seconds=SOLVE_CACHE_TTL_SECONDS,
        log_level=LOG_LEVEL,
        request_id_header=REQUEST_ID_HEADER,
    )


def config_summary_safe() -> dict:
    """
    Safe summary for /version or logs (never expose secrets).
    """
    return {
        "app_env": APP_ENV,
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "ai": {
            "enabled": AI_ENABLED,
            "mode": AI_MODE,
            "provider": AI_PROVIDER,
            "timeout_seconds": AI_TIMEOUT_SECONDS,
            "has_gemini_key": bool(GEMINI_API_KEY),
        },
        "db": {
            "configured": bool(DATABASE_URL),
            "sslmode": DB_SSLMODE,
        },
        "redis": {
            "configured": bool(REDIS_URL),
        },
        "rate_limit": {
            "enabled": RATE_LIMIT_ENABLED,
            "per_minute": RATE_LIMIT_PER_MINUTE,
        },
        "solve_cache": {
            "enabled": SOLVE_CACHE_ENABLED,
            "ttl_seconds": SOLVE_CACHE_TTL_SECONDS,
        },
        "log_level": LOG_LEVEL,
    }
