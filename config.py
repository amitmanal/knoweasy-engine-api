"""
knoweasy-engine-api: config.py

Goal:
- Single source of truth for environment variables + safe defaults
- Export ALL constants used by router.py / orchestrator.py / main.py
- Never crash on missing env vars (unless you explicitly want to enforce)
"""

from __future__ import annotations

import os
from typing import List
from dotenv import load_dotenv

# Load .env locally (Render will ignore if not present; it uses Dashboard env vars)
load_dotenv()


# -----------------------------
# Helpers
# -----------------------------
def _get_str(key: str, default: str = "") -> str:
    v = os.getenv(key)
    return default if v is None else str(v).strip()


def _get_int(key: str, default: int) -> int:
    v = os.getenv(key)
    if v is None or str(v).strip() == "":
        return default
    try:
        return int(str(v).strip())
    except Exception:
        return default


def _get_float(key: str, default: float) -> float:
    v = os.getenv(key)
    if v is None or str(v).strip() == "":
        return default
    try:
        return float(str(v).strip())
    except Exception:
        return default


def _get_bool(key: str, default: bool = False) -> bool:
    v = os.getenv(key)
    if v is None:
        return default
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off"):
        return False
    return default


def _get_csv_list(key: str, default: List[str]) -> List[str]:
    v = os.getenv(key)
    if v is None or str(v).strip() == "":
        return default
    return [x.strip() for x in str(v).split(",") if x.strip()]


# -----------------------------
# Environment / app identity
# -----------------------------
ENV = _get_str("ENV", "production")
APP_NAME = _get_str("APP_NAME", "knoweasy-engine-api")
LOG_LEVEL = _get_str("LOG_LEVEL", "INFO")


# -----------------------------
# API keys (Engine access control + Gemini)
# -----------------------------
# Your frontend should send this as x-api-key (or whatever your code expects).
KE_API_KEY = _get_str("KE_API_KEY", "")

# Gemini / Google GenAI
GEMINI_API_KEY = _get_str("GEMINI_API_KEY", _get_str("GOOGLE_API_KEY", ""))

# Model settings
GEMINI_MODEL = _get_str("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_TEMPERATURE = _get_float("GEMINI_TEMPERATURE", 0.2)
GEMINI_MAX_OUTPUT_TOKENS = _get_int("GEMINI_MAX_OUTPUT_TOKENS", 1200)


# -----------------------------
# Rate limiting (safe defaults)
# -----------------------------
# These were failing in Render logs because router.py imports them.
RATE_LIMIT_PER_MINUTE = _get_int("RATE_LIMIT_PER_MINUTE", 60)
RATE_LIMIT_WINDOW_SECONDS = _get_int("RATE_LIMIT_WINDOW_SECONDS", 60)
RATE_LIMIT_BURST = _get_int("RATE_LIMIT_BURST", 30)


# -----------------------------
# Confidence / safety thresholds
# -----------------------------
# This was failing latest: orchestrator imports it.
LOW_CONFIDENCE_THRESHOLD = _get_float("LOW_CONFIDENCE_THRESHOLD", 0.55)


# -----------------------------
# CORS
# -----------------------------
# If your app uses CORS, keep it open-safe for now. Lock later.
ALLOW_ORIGINS = _get_csv_list(
    "ALLOW_ORIGINS",
    default=[
        "https://knoweasylearning.com",
        "https://www.knoweasylearning.com",
        "http://localhost",
        "http://localhost:3000",
        "http://127.0.0.1:5500",
    ],
)
ALLOW_CREDENTIALS = _get_bool("ALLOW_CREDENTIALS", True)
ALLOW_METHODS = _get_csv_list("ALLOW_METHODS", ["*"])
ALLOW_HEADERS = _get_csv_list("ALLOW_HEADERS", ["*"])


# -----------------------------
# Database / Redis toggles
# -----------------------------
DATABASE_URL = _get_str("DATABASE_URL", "")
DB_ENABLED = _get_bool("DB_ENABLED", bool(DATABASE_URL))

REDIS_URL = _get_str("REDIS_URL", "")
REDIS_ENABLED = _get_bool("REDIS_ENABLED", bool(REDIS_URL))


# -----------------------------
# Misc operational defaults
# -----------------------------
REQUEST_TIMEOUT_SECONDS = _get_int("REQUEST_TIMEOUT_SECONDS", 40)
MAX_REQUEST_CHARS = _get_int("MAX_REQUEST_CHARS", 5000)

# If you want to hard-enforce KE_API_KEY in production later:
# ENFORCE_API_KEY = _get_bool("ENFORCE_API_KEY", ENV.lower() == "production")
ENFORCE_API_KEY = _get_bool("ENFORCE_API_KEY", False)
