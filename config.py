# config.py
# Centralized runtime configuration for KnowEasy Engine API
from __future__ import annotations

import os
from typing import List, Optional


def _get_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    try:
        return int(v)
    except Exception:
        return default


def _get_float(name: str, default: float) -> float:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    try:
        return float(v)
    except Exception:
        return default


def _get_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


# --- Service identity ---
SERVICE_NAME: str = os.getenv("SERVICE_NAME", "knoweasy-engine-api")
ENV: str = os.getenv("ENV", os.getenv("RENDER_ENV", "prod"))

# --- Security (optional shared key) ---
KE_API_KEY: Optional[str] = os.getenv("KE_API_KEY")  # if set, require X-KE-KEY header

# --- CORS (keep permissive in code for Phase-1; can be tightened later) ---
# If you later want strict origins, you can use this list in main.py.
ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS: List[str] = ["*"] if ALLOWED_ORIGINS_RAW.strip() == "*" else [
    s.strip() for s in ALLOWED_ORIGINS_RAW.split(",") if s.strip()
]

# --- Rate limiting (router.py expects these names) ---
RATE_LIMIT_PER_MINUTE: int = _get_int("RATE_LIMIT_PER_MINUTE", 30)
RATE_LIMIT_BURST: int = _get_int("RATE_LIMIT_BURST", 10)

# --- AI core knobs (orchestrator.py expects these names) ---
AI_ENABLED: bool = _get_bool("AI_ENABLED", True)
AI_PROVIDER: str = os.getenv("AI_PROVIDER", "gemini")  # future: openai / anthropic
AI_MODE: str = os.getenv("AI_MODE", "exam_safe")
AI_TIMEOUT_SECONDS: int = _get_int("AI_TIMEOUT_SECONDS", 25)

# Output shaping
LOW_CONFIDENCE_THRESHOLD: float = _get_float("LOW_CONFIDENCE_THRESHOLD", 0.45)
MAX_STEPS: int = _get_int("MAX_STEPS", 8)
MAX_CHARS_ANSWER: int = _get_int("MAX_CHARS_ANSWER", 6000)

# --- Gemini provider settings (models.py expects these names) ---
# Accept either GEMINI_API_KEY (preferred) or legacy GENAI_API_KEY
GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY") or os.getenv("GENAI_API_KEY")

# Provide safe defaults. These are *model ids*; you can override in Render env.
GEMINI_PRIMARY_MODEL: str = os.getenv("GEMINI_PRIMARY_MODEL", "gemini-2.5-flash")
GEMINI_FALLBACK_MODEL: str = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-pro")

# Backward-compat name some code may use
GEMINI_TIMEOUT_S: int = _get_int("GEMINI_TIMEOUT_S", AI_TIMEOUT_SECONDS)

# Circuit breaker (models.py expects these names)
CB_FAILURE_THRESHOLD: int = _get_int("CB_FAILURE_THRESHOLD", 3)
CB_COOLDOWN_S: int = _get_int("CB_COOLDOWN_S", 60)

# --- Persistence / cache (optional) ---
DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")
DB_SSLMODE: str = os.getenv("DB_SSLMODE", "require")
REDIS_URL: Optional[str] = os.getenv("REDIS_URL")
