# config.py — SINGLE SOURCE OF TRUTH (Render-safe)
# Full replacement. No missing env var should crash the app.

import os
from dotenv import load_dotenv

load_dotenv()

# -----------------------------
# helpers
# -----------------------------
def _env_str(key: str, default: str = "") -> str:
    v = os.getenv(key)
    return default if v is None else str(v).strip()

def _env_int(key: str, default: int) -> int:
    v = os.getenv(key)
    if v is None or str(v).strip() == "":
        return int(default)
    try:
        return int(str(v).strip())
    except Exception:
        return int(default)

def _env_float(key: str, default: float) -> float:
    v = os.getenv(key)
    if v is None or str(v).strip() == "":
        return float(default)
    try:
        return float(str(v).strip())
    except Exception:
        return float(default)

def _env_bool(key: str, default: bool = False) -> bool:
    v = os.getenv(key)
    if v is None or str(v).strip() == "":
        return bool(default)
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")

# -----------------------------
# service basics
# -----------------------------
SERVICE_NAME = _env_str("SERVICE_NAME", "knoweasy-engine-api")
ENV = _env_str("ENV", "production")  # "development" / "production"
LOG_LEVEL = _env_str("LOG_LEVEL", "INFO")

# request safety
MAX_REQUEST_BYTES = _env_int("MAX_REQUEST_BYTES", 200_000)

# -----------------------------
# auth / api key (optional)
# -----------------------------
KE_API_KEY = _env_str("KE_API_KEY", "")  # optional guard

# -----------------------------
# rate limiting (router imports these)
# -----------------------------
RATE_LIMIT_PER_MINUTE = _env_int("RATE_LIMIT_PER_MINUTE", 60)
RATE_LIMIT_BURST = _env_int("RATE_LIMIT_BURST", 20)
RATE_LIMIT_WINDOW_SECONDS = _env_int("RATE_LIMIT_WINDOW_SECONDS", 60)

# -----------------------------
# Redis (optional)
# -----------------------------
REDIS_URL = _env_str("REDIS_URL", "")

# Solve cache (optional)
SOLVE_CACHE_TTL_SECONDS = _env_int("SOLVE_CACHE_TTL_SECONDS", 300)

# -----------------------------
# AI settings (orchestrator/models import these)
# -----------------------------
AI_ENABLED = _env_bool("AI_ENABLED", True)
AI_PROVIDER = _env_str("AI_PROVIDER", "gemini")  # gemini
AI_MODE = _env_str("AI_MODE", "auto")            # auto / require / off
AI_TIMEOUT_SECONDS = _env_int("AI_TIMEOUT_SECONDS", 18)

MAX_STEPS = _env_int("MAX_STEPS", 6)
MAX_CHARS_ANSWER = _env_int("MAX_CHARS_ANSWER", 2500)
LOW_CONFIDENCE_THRESHOLD = _env_float("LOW_CONFIDENCE_THRESHOLD", 0.35)

# Gemini configuration
GEMINI_API_KEY = _env_str("GEMINI_API_KEY", "")
GEMINI_PRIMARY_MODEL = _env_str("GEMINI_PRIMARY_MODEL", "gemini-2.5-flash")
GEMINI_FALLBACK_MODEL = _env_str("GEMINI_FALLBACK_MODEL", "gemini-2.5-pro")

# models.py expects this name
GEMINI_TIMEOUT_S = AI_TIMEOUT_SECONDS

# Circuit breaker (models.py expects these)
CB_FAILURE_THRESHOLD = _env_int("CB_FAILURE_THRESHOLD", 3)
CB_COOLDOWN_S = _env_int("CB_COOLDOWN_S", 30)

# Auto-disable AI if key missing (LOCKED INTENT)
if not GEMINI_API_KEY:
    AI_ENABLED = False

# -----------------------------
# Database (optional)
# -----------------------------
DATABASE_URL = _env_str("DATABASE_URL", "")
DB_SSLMODE = _env_str("DB_SSLMODE", "require")

# predictable exports
__all__ = [
    "SERVICE_NAME",
    "ENV",
    "LOG_LEVEL",
    "MAX_REQUEST_BYTES",
    "KE_API_KEY",
    "RATE_LIMIT_PER_MINUTE",
    "RATE_LIMIT_BURST",
    "RATE_LIMIT_WINDOW_SECONDS",
    "REDIS_URL",
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
    "DATABASE_URL",
    "DB_SSLMODE",
]
