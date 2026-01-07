"""
KnowEasy Engine API — configuration (superset, backward-compatible)

Goals:
- Define every config symbol that any module might import from `config`.
- Never crash at import-time if env vars are missing.
- Keep Gemini as primary now; make OpenAI/Claude easy to add later via env vars.
"""

from __future__ import annotations

import os
from typing import List, Optional


# -----------------------------
# helpers
# -----------------------------
def _env(key: str, default: str = "") -> str:
    v = os.getenv(key)
    return default if v is None else str(v).strip()


def _env_bool(key: str, default: bool = False) -> bool:
    v = os.getenv(key)
    if v is None or str(v).strip() == "":
        return default
    s = str(v).strip().lower()
    return s in {"1", "true", "yes", "y", "on"}


def _env_int(key: str, default: int) -> int:
    v = os.getenv(key)
    if v is None or str(v).strip() == "":
        return default
    try:
        return int(str(v).strip())
    except Exception:
        return default


def _env_float(key: str, default: float) -> float:
    v = os.getenv(key)
    if v is None or str(v).strip() == "":
        return default
    try:
        return float(str(v).strip())
    except Exception:
        return default


def _env_list(key: str, default: Optional[List[str]] = None, sep: str = ",") -> List[str]:
    if default is None:
        default = []
    v = os.getenv(key)
    if v is None or str(v).strip() == "":
        return list(default)
    return [s.strip() for s in str(v).split(sep) if s.strip()]


# -----------------------------
# Environment / mode
# -----------------------------
ENV: str = _env("ENV", _env("APP_ENV", "production"))
DEBUG: bool = _env_bool("DEBUG", False)
LOG_LEVEL: str = _env("LOG_LEVEL", "INFO")

# CORS
ALLOWED_ORIGINS: List[str] = _env_list("ALLOWED_ORIGINS", default=["*"])
ALLOW_CREDENTIALS: bool = _env_bool("ALLOW_CREDENTIALS", False)
ALLOWED_METHODS: List[str] = _env_list("ALLOWED_METHODS", default=["*"])
ALLOWED_HEADERS: List[str] = _env_list("ALLOWED_HEADERS", default=["*"])

# Render / uvicorn
HOST: str = _env("HOST", "0.0.0.0")
PORT: int = _env_int("PORT", 10000)  # Render supplies PORT; default is safe
UVICORN_WORKERS: int = _env_int("UVICORN_WORKERS", 1)

# Security / API keys
API_KEY: str = _env("API_KEY", "")  # optional: if you gate endpoints later

# -----------------------------
# AI Provider keys (Gemini primary)
# -----------------------------
# Gemini
GEMINI_API_KEY: str = _env("GEMINI_API_KEY", _env("GOOGLE_API_KEY", ""))
GEMINI_PRIMARY_MODEL: str = _env("GEMINI_PRIMARY_MODEL", _env("GEMINI_MODEL", "gemini-2.0-flash"))
GEMINI_FALLBACK_MODELS: List[str] = _env_list(
    "GEMINI_FALLBACK_MODELS", default=["gemini-2.0-flash", "gemini-1.5-flash"]
)
GEMINI_TEMPERATURE: float = _env_float("GEMINI_TEMPERATURE", 0.2)
GEMINI_MAX_OUTPUT_TOKENS: int = _env_int("GEMINI_MAX_OUTPUT_TOKENS", 1024)
GEMINI_TIMEOUT_SECONDS: int = _env_int("GEMINI_TIMEOUT_SECONDS", 40)

# OpenAI (future)
OPENAI_API_KEY: str = _env("OPENAI_API_KEY", "")
OPENAI_ORG_ID: str = _env("OPENAI_ORG_ID", "")
OPENAI_PRIMARY_MODEL: str = _env("OPENAI_PRIMARY_MODEL", "gpt-4o-mini")  # unused unless enabled
OPENAI_TEMPERATURE: float = _env_float("OPENAI_TEMPERATURE", 0.2)
OPENAI_TIMEOUT_SECONDS: int = _env_int("OPENAI_TIMEOUT_SECONDS", 40)

# Claude (Anthropic, future)
CLAUDE_API_KEY: str = _env("CLAUDE_API_KEY", _env("ANTHROPIC_API_KEY", ""))
CLAUDE_PRIMARY_MODEL: str = _env("CLAUDE_PRIMARY_MODEL", "claude-3-5-sonnet-latest")
CLAUDE_TEMPERATURE: float = _env_float("CLAUDE_TEMPERATURE", 0.2)
CLAUDE_TIMEOUT_SECONDS: int = _env_int("CLAUDE_TIMEOUT_SECONDS", 40)

# AI toggle
AI_ENABLED: bool = _env_bool("AI_ENABLED", True)

# Provider routing (Track‑B later; safe to exist now)
AI_PROVIDER_PRIMARY: str = _env("AI_PROVIDER_PRIMARY", "gemini")  # gemini|openai|claude
AI_PROVIDER_FALLBACKS: List[str] = _env_list("AI_PROVIDER_FALLBACKS", default=["gemini"])
AI_PROVIDER_STRICT: bool = _env_bool("AI_PROVIDER_STRICT", False)  # if True, no fallback

# -----------------------------
# Rate limiting / abuse protection
# -----------------------------
RATE_LIMIT_ENABLED: bool = _env_bool("RATE_LIMIT_ENABLED", True)
RATE_LIMIT_REQUESTS: int = _env_int("RATE_LIMIT_REQUESTS", 60)
RATE_LIMIT_WINDOW_SECONDS: int = _env_int("RATE_LIMIT_WINDOW_SECONDS", 60)
RATE_LIMIT_TRUST_PROXY_HEADERS: bool = _env_bool("RATE_LIMIT_TRUST_PROXY_HEADERS", True)

# -----------------------------
# Caching (in-memory / optional external later)
# -----------------------------
SOLVE_CACHE_ENABLED: bool = _env_bool("SOLVE_CACHE_ENABLED", True)
SOLVE_CACHE_TTL_SECONDS: int = _env_int("SOLVE_CACHE_TTL_SECONDS", 3600)
SOLVE_CACHE_MAX_ITEMS: int = _env_int("SOLVE_CACHE_MAX_ITEMS", 500)

# -----------------------------
# Database logging (must never crash app if DB missing)
# -----------------------------
DATABASE_URL: str = _env("DATABASE_URL", "")
DB_LOGGING_ENABLED: bool = _env_bool("DB_LOGGING_ENABLED", False)
DB_CONNECT_TIMEOUT_SECONDS: int = _env_int("DB_CONNECT_TIMEOUT_SECONDS", 5)
DB_STATEMENT_TIMEOUT_MS: int = _env_int("DB_STATEMENT_TIMEOUT_MS", 5000)

# Backward-compat aliases (older names that might exist in code)
DB_URL: str = DATABASE_URL
ENABLE_DB_LOGGING: bool = DB_LOGGING_ENABLED

# -----------------------------
# Request handling / timeouts
# -----------------------------
REQUEST_TIMEOUT_SECONDS: int = _env_int("REQUEST_TIMEOUT_SECONDS", 60)
MAX_REQUEST_BODY_BYTES: int = _env_int("MAX_REQUEST_BODY_BYTES", 2_000_000)

# -----------------------------
# Misc feature flags (safe placeholders)
# -----------------------------
ENABLE_METRICS: bool = _env_bool("ENABLE_METRICS", False)
ENABLE_TRACING: bool = _env_bool("ENABLE_TRACING", False)


def summarize_config_for_logs() -> dict:
    """Return a safe summary (no secrets) that can be printed at startup."""

    def _mask(s: str) -> str:
        if not s:
            return ""
        if len(s) <= 6:
            return "***"
        return s[:3] + "***" + s[-2:]

    return {
        "ENV": ENV,
        "DEBUG": DEBUG,
        "LOG_LEVEL": LOG_LEVEL,
        "AI_ENABLED": AI_ENABLED,
        "AI_PROVIDER_PRIMARY": AI_PROVIDER_PRIMARY,
        "GEMINI_PRIMARY_MODEL": GEMINI_PRIMARY_MODEL,
        "OPENAI_PRIMARY_MODEL": OPENAI_PRIMARY_MODEL,
        "CLAUDE_PRIMARY_MODEL": CLAUDE_PRIMARY_MODEL,
        "GEMINI_API_KEY": _mask(GEMINI_API_KEY),
        "OPENAI_API_KEY": _mask(OPENAI_API_KEY),
        "CLAUDE_API_KEY": _mask(CLAUDE_API_KEY),
        "RATE_LIMIT_ENABLED": RATE_LIMIT_ENABLED,
        "RATE_LIMIT_REQUESTS": RATE_LIMIT_REQUESTS,
        "RATE_LIMIT_WINDOW_SECONDS": RATE_LIMIT_WINDOW_SECONDS,
        "SOLVE_CACHE_ENABLED": SOLVE_CACHE_ENABLED,
        "SOLVE_CACHE_TTL_SECONDS": SOLVE_CACHE_TTL_SECONDS,
        "DB_LOGGING_ENABLED": DB_LOGGING_ENABLED,
        "DATABASE_URL_SET": bool(DATABASE_URL),
    }
