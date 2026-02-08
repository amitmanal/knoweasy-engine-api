"""KnowEasy Engine API — Superset config (anti-ImportError)

This file intentionally defines *all* names that other modules import from `config`,
with safe defaults so Render never crash-loops due to missing env vars.

Gemini-only execution is the default. OpenAI/Claude are future-ready via env keys.
"""

from __future__ import annotations

import os
import logging
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
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}

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
# logging (must exist for imports)
# -----------------------------
LOG_LEVEL = _env("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger("knoweasy-engine-api")


# -----------------------------
# core app env
# -----------------------------
ENV = _env("ENV", _env("APP_ENV", "production"))
DEBUG = _env_bool("DEBUG", False)

HOST = _env("HOST", "0.0.0.0")
PORT = _env_int("PORT", 10000)
UVICORN_WORKERS = _env_int("UVICORN_WORKERS", 4)

# Optional API key to protect endpoints later
KE_API_KEY = _env("KE_API_KEY", _env("API_KEY", ""))


# -----------------------------
# AI control (names expected by repo)
# -----------------------------
AI_ENABLED = _env_bool("AI_ENABLED", True)

# Keep both names to avoid breaking older imports
AI_PROVIDER = _env("AI_PROVIDER", _env("AI_PROVIDER_PRIMARY", "gemini"))   # gemini|openai|claude
AI_MODE = _env("AI_MODE", "stable")  # placeholder: stable|debug|strict etc
AI_TIMEOUT_SECONDS = _env_int("AI_TIMEOUT_SECONDS", _env_int("REQUEST_TIMEOUT_SECONDS", 90))

# Gemini
GEMINI_API_KEY = _env("GEMINI_API_KEY", _env("GOOGLE_API_KEY", ""))
GEMINI_PRIMARY_MODEL = _env("GEMINI_PRIMARY_MODEL", _env("GEMINI_MODEL", "gemini-2.5-flash"))

# Optional fallback models (comma-separated). Used if primary model is unavailable.
GEMINI_FALLBACK_MODELS = [m.strip() for m in _env("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash,gemini-2.5-pro,gemini-2.5-flash-lite").split(",") if m.strip()]
GEMINI_FALLBACK_MODEL = _env("GEMINI_FALLBACK_MODEL", "gemini-1.5-flash")
GEMINI_TIMEOUT_S = _env_int("GEMINI_TIMEOUT_S", _env_int("GEMINI_TIMEOUT_SECONDS", 40))

# OpenAI (future)
OPENAI_API_KEY = _env("OPENAI_API_KEY", "")
OPENAI_MODEL = _env("OPENAI_MODEL", _env("OPENAI_PRIMARY_MODEL", "gpt-4o-mini"))
OPENAI_VERIFIER_MODEL = _env("OPENAI_VERIFIER_MODEL", _env("OPENAI_CHECKER_MODEL", "o3-mini"))

# Claude (future)
CLAUDE_API_KEY = _env("CLAUDE_API_KEY", _env("ANTHROPIC_API_KEY", ""))
CLAUDE_MODEL = _env("CLAUDE_MODEL", _env("CLAUDE_PRIMARY_MODEL", "claude-3-5-sonnet-latest"))
CLAUDE_WRITER_MODEL = _env("CLAUDE_WRITER_MODEL", _env("CLAUDE_DEEP_MODEL", CLAUDE_MODEL))

# Confidence / output shaping (safe defaults)
LOW_CONFIDENCE_THRESHOLD = _env_float("LOW_CONFIDENCE_THRESHOLD", 0.35)
MAX_STEPS = _env_int("MAX_STEPS", 12)
MAX_CHARS_ANSWER = _env_int("MAX_CHARS_ANSWER", 6000)


# -----------------------------
# rate limiting (names expected by repo)
# -----------------------------
RATE_LIMIT_WINDOW_SECONDS = _env_int("RATE_LIMIT_WINDOW_SECONDS", 60)
RATE_LIMIT_PER_MINUTE = _env_int("RATE_LIMIT_PER_MINUTE", 60)
RATE_LIMIT_BURST = _env_int("RATE_LIMIT_BURST", 10)


# -----------------------------
# cache / redis (names expected by repo)
# -----------------------------
SOLVE_CACHE_TTL_SECONDS = _env_int("SOLVE_CACHE_TTL_SECONDS", 3600)
REDIS_URL = _env("REDIS_URL", _env("REDIS_TLS_URL", ""))


# -----------------------------
# circuit breaker (names expected by repo)
# -----------------------------
CB_FAILURE_THRESHOLD = _env_int("CB_FAILURE_THRESHOLD", 3)
CB_COOLDOWN_S = _env_int("CB_COOLDOWN_S", 20)


# -----------------------------
# backwards-compatible extras (safe)
# -----------------------------
# Security/trust default:
# - In production, prefer known web origins unless explicitly overridden.
# - In dev/staging, allow "*" unless ALLOWED_ORIGINS is set.
_origins_env = os.getenv("ALLOWED_ORIGINS")
if _origins_env is None or str(_origins_env).strip() == "":
    if str(ENV).lower().strip() == "production":
        ALLOWED_ORIGINS = [
            "https://knoweasylearning.com",
            "https://www.knoweasylearning.com",
        ]
    else:
        ALLOWED_ORIGINS = ["*"]
else:
    ALLOWED_ORIGINS = _env_list("ALLOWED_ORIGINS", default=[])