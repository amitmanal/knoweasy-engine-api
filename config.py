"""Central configuration for KnowEasy Engine API.

LOCKED INTENT:
- This module must export ALL constants imported by router.py / orchestrator.py / redis_store.py / db.py.
- Missing env vars MUST NOT crash startup.
- AI auto-disables if GEMINI_API_KEY is missing.
- DB & Redis are optional.
"""

from __future__ import annotations

import os
from typing import Optional


def _env_str(name: str, default: str = "") -> str:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip()


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or str(v).strip() == "":
        return default
    try:
        return int(str(v).strip())
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    v = os.getenv(name)
    if v is None or str(v).strip() == "":
        return default
    try:
        return float(str(v).strip())
    except Exception:
        return default


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "no", "n", "off"}:
        return False
    return default


# =========================
# Service identity
# =========================
SERVICE_NAME = _env_str("SERVICE_NAME", "knoweasy-engine-api")
ENV = _env_str("ENV", _env_str("RENDER_ENV", "dev"))
LOG_LEVEL = _env_str("LOG_LEVEL", "INFO")

# =========================
# API security / auth (optional)
# =========================
# Kept for backward compatibility with older code paths.
KE_API_KEY = _env_str("KE_API_KEY", "")  # optional API auth

# =========================
# AI configuration
# =========================
AI_PROVIDER = _env_str("AI_PROVIDER", "gemini")
AI_MODE = _env_str("AI_MODE", "default")

# Primary key used by google-genai client
GEMINI_API_KEY = _env_str("GEMINI_API_KEY", "")

# NOTE: You said Gemini 2.5 Flash/Pro were working for you before.
# So defaults are set to those. You can override via Render env vars.
GEMINI_PRIMARY_MODEL = _env_str("GEMINI_PRIMARY_MODEL", "gemini-2.5-flash")
GEMINI_FALLBACK_MODEL = _env_str("GEMINI_FALLBACK_MODEL", "gemini-2.5-pro")

# Timeouts and output constraints
AI_TIMEOUT_SECONDS = _env_int("AI_TIMEOUT_SECONDS", 20)
MAX_STEPS = _env_int("MAX_STEPS", 8)
MAX_CHARS_ANSWER = _env_int("MAX_CHARS_ANSWER", 900)
LOW_CONFIDENCE_THRESHOLD = _env_float("LOW_CONFIDENCE_THRESHOLD", 0.45)

# AI is enabled only if:
# - AI_ENABLED env is true (or default true)
# - and we actually have a Gemini API key present
AI_ENABLED = _env_bool("AI_ENABLED", True) and bool(GEMINI_API_KEY)

# =========================
# Rate limit (router + optional Redis)
# =========================
RATE_LIMIT_PER_MINUTE = _env_int("RATE_LIMIT_PER_MINUTE", 20)
RATE_LIMIT_WINDOW_SECONDS = _env_int("RATE_LIMIT_WINDOW_SECONDS", 60)

# In-memory per-process safety limit (kept modest for free tier)
MAX_REQUESTS_INFLIGHT = _env_int("MAX_REQUESTS_INFLIGHT", 30)

# =========================
# Solve cache (optional Redis)
# =========================
SOLVE_CACHE_TTL_SECONDS = _env_int("SOLVE_CACHE_TTL_SECONDS", 3600)

# =========================
# Redis (optional)
# =========================
REDIS_URL = _env_str("REDIS_URL", "")  # empty => Redis disabled

# =========================
# Database (optional)
# =========================
DATABASE_URL = _env_str("DATABASE_URL", _env_str("DATABASE_URL_INTERNAL", ""))
DB_SSLMODE = _env_str("DB_SSLMODE", "require")

# =========================
# HTTP / CORS
# =========================
# Comma-separated list. "*" allows all.
CORS_ALLOW_ORIGINS = _env_str("CORS_ALLOW_ORIGINS", "*")
REQUEST_TIMEOUT_SECONDS = _env_int("REQUEST_TIMEOUT_SECONDS", 30)

# =========================
# Compatibility exports (some older names referenced in logs)
# =========================
# Aliases to avoid future ImportError if older code imports these.
SOLVE_CACHE_TTL = SOLVE_CACHE_TTL_SECONDS
REQUEST_TIMEOUT_MS = REQUEST_TIMEOUT_SECONDS * 1000
