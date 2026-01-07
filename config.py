from __future__ import annotations

import os
from typing import List
from dotenv import load_dotenv

load_dotenv()


# -----------------------------
# Helpers
# -----------------------------
def _get_str(key: str, default: str = "") -> str:
    v = os.getenv(key)
    return default if v is None else str(v).strip()


def _get_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, default))
    except Exception:
        return default


def _get_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, default))
    except Exception:
        return default


def _get_bool(key: str, default: bool = False) -> bool:
    v = os.getenv(key)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _get_csv(key: str, default: List[str]) -> List[str]:
    v = os.getenv(key)
    if not v:
        return default
    return [x.strip() for x in v.split(",") if x.strip()]


# -----------------------------
# App identity
# -----------------------------
ENV = _get_str("ENV", "production")
APP_NAME = "knoweasy-engine-api"


# -----------------------------
# AI control (Phase-1C)
# -----------------------------
AI_ENABLED = _get_bool("AI_ENABLED", True)
AI_MODE = _get_str("AI_MODE", "production")
AI_PROVIDER = _get_str("AI_PROVIDER", "gemini")
AI_TIMEOUT_SECONDS = _get_int("AI_TIMEOUT_SECONDS", 25)


# -----------------------------
# API / security
# -----------------------------
KE_API_KEY = _get_str("KE_API_KEY", "")


# -----------------------------
# Gemini config
# -----------------------------
GEMINI_API_KEY = _get_str("GEMINI_API_KEY", "")
GEMINI_MODEL = _get_str("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_TEMPERATURE = _get_float("GEMINI_TEMPERATURE", 0.2)
GEMINI_MAX_OUTPUT_TOKENS = _get_int("GEMINI_MAX_OUTPUT_TOKENS", 1200)

# --- Future providers (Phase-2 ready): OpenAI + Claude ---
# Keep installed-code minimal: we use HTTPS calls via stdlib urllib. Just add keys to enable.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "").strip()
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20240620").strip()



# -----------------------------
# Solver behavior (THIS FIXES THE CRASH)
# -----------------------------
MAX_STEPS = _get_int("MAX_STEPS", 8)
MAX_CHARS_ANSWER = int(os.getenv("MAX_CHARS_ANSWER", "3500"))
LOW_CONFIDENCE_THRESHOLD = _get_float("LOW_CONFIDENCE_THRESHOLD", 0.55)


# -----------------------------
# Rate limiting
# -----------------------------
RATE_LIMIT_PER_MINUTE = _get_int("RATE_LIMIT_PER_MINUTE", 60)
RATE_LIMIT_WINDOW_SECONDS = _get_int("RATE_LIMIT_WINDOW_SECONDS", 60)
RATE_LIMIT_BURST = _get_int("RATE_LIMIT_BURST", 30)


# -----------------------------
# Cache
# -----------------------------
SOLVE_CACHE_ENABLED = _get_bool("SOLVE_CACHE_ENABLED", True)
SOLVE_CACHE_TTL_SECONDS = _get_int("SOLVE_CACHE_TTL_SECONDS", 300)


# -----------------------------
# Database / Redis
# -----------------------------
DATABASE_URL = _get_str("DATABASE_URL", "")
DB_ENABLED = bool(DATABASE_URL)

REDIS_URL = _get_str("REDIS_URL", "")
REDIS_ENABLED = bool(REDIS_URL)


# -----------------------------
# CORS
# -----------------------------
ALLOW_ORIGINS = _get_csv(
    "ALLOW_ORIGINS",
    [
        "https://knoweasylearning.com",
        "https://www.knoweasylearning.com",
        "http://localhost",
        "http://localhost:3000",
    ],
)
ALLOW_METHODS = ["*"]
ALLOW_HEADERS = ["*"]
ALLOW_CREDENTIALS = True