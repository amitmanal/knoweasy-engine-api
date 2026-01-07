# config.py
# =========================================================
# KnowEasy Engine API — Phase-1 Stable + Track-B Safe Config
# Goal: NEVER crash on missing env vars / future imports
# =========================================================

import os

def _bool(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip() == "1"

def _int(name: str, default: str) -> int:
    try:
        return int(os.getenv(name, default))
    except Exception:
        return int(default)

# =========================================================
# ENVIRONMENT / SERVICE
# =========================================================
ENV = os.getenv("ENV", "production")
SERVICE_NAME = os.getenv("SERVICE_NAME", "knoweasy-engine-api")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "phase-1-stable")

# =========================================================
# CORS (optional; your main.py may configure separately)
# =========================================================
CORS_ALLOW_ORIGINS = [
    x.strip()
    for x in os.getenv(
        "CORS_ALLOW_ORIGINS",
        "https://knoweasylearning.com,https://www.knoweasylearning.com,http://localhost:5500,http://127.0.0.1:5500",
    ).split(",")
    if x.strip()
]

# =========================================================
# API KEY GUARD (optional)
# =========================================================
KE_API_KEY = os.getenv("KE_API_KEY", "")  # if empty => guard off

# =========================================================
# AI PROVIDERS — KEYS (safe if empty)
# =========================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")

# =========================================================
# AI MODELS (safe defaults)
# =========================================================
GEMINI_PRIMARY_MODEL = os.getenv("GEMINI_PRIMARY_MODEL", "gemini-1.5-flash")
OPENAI_PRIMARY_MODEL = os.getenv("OPENAI_PRIMARY_MODEL", "gpt-4o-mini")
CLAUDE_PRIMARY_MODEL = os.getenv("CLAUDE_PRIMARY_MODEL", "claude-3-haiku")

# (Optional) routing defaults (Track-B)
AI_PROVIDER_DEFAULT = os.getenv("AI_PROVIDER_DEFAULT", "gemini")  # gemini|openai|claude
AI_PROVIDER_FALLBACKS = [
    x.strip()
    for x in os.getenv("AI_PROVIDER_FALLBACKS", "gemini,openai,claude").split(",")
    if x.strip()
]

# =========================================================
# AI ENABLE FLAGS (THIS FIXES YOUR CURRENT CRASH)
# =========================================================
# Primary flag expected by your orchestrator imports
AI_ENABLED = _bool("AI_ENABLED", "1")

# Provider-specific flags (future)
ENABLE_GEMINI = _bool("ENABLE_GEMINI", "1")
ENABLE_OPENAI = _bool("ENABLE_OPENAI", "1")
ENABLE_CLAUDE = _bool("ENABLE_CLAUDE", "1")

# Compatibility aliases (in case older code imports these)
GEMINI_ENABLED = ENABLE_GEMINI
OPENAI_ENABLED = ENABLE_OPENAI
CLAUDE_ENABLED = ENABLE_CLAUDE

# =========================================================
# AI TIMEOUTS / RETRIES
# =========================================================
AI_TIMEOUT_SECONDS = _int("AI_TIMEOUT_SECONDS", "25")
MAX_AI_RETRIES = _int("MAX_AI_RETRIES", "2")

# =========================================================
# INPUT LIMITS (abuse safety)
# =========================================================
MAX_QUESTION_CHARS = _int("MAX_QUESTION_CHARS", "3000")
MAX_CONTEXT_CHARS = _int("MAX_CONTEXT_CHARS", "6000")

# =========================================================
# RATE LIMITING (Phase-1 in-memory)
# =========================================================
RATE_LIMIT_WINDOW_SECONDS = _int("RATE_LIMIT_WINDOW_SECONDS", "60")
RATE_LIMIT_PER_MINUTE = _int("RATE_LIMIT_PER_MINUTE", "30")
RATE_LIMIT_BURST = _int("RATE_LIMIT_BURST", "10")

# Compatibility alias (some files may import this name)
RATE_LIMIT_WINDOW = RATE_LIMIT_WINDOW_SECONDS

# =========================================================
# REDIS (optional; shared rate limit / cache later)
# =========================================================
REDIS_URL = os.getenv("REDIS_URL", "")
ENABLE_REDIS_RATE_LIMIT = _bool("ENABLE_REDIS_RATE_LIMIT", "0")

# =========================================================
# SOLVE CACHE (optional; router.py expects TTL constant)
# =========================================================
ENABLE_SOLVE_CACHE = _bool("ENABLE_SOLVE_CACHE", "0")
SOLVE_CACHE_TTL_SECONDS = _int("SOLVE_CACHE_TTL_SECONDS", "900")  # 15 min

# =========================================================
# DATABASE (optional best-effort logging)
# =========================================================
DATABASE_URL = os.getenv("DATABASE_URL", "")

# =========================================================
# LOGGING
# =========================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
