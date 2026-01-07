# config.py
# ============================================================
# KnowEasy Engine API — FINAL STABLE CONFIG (Phase-1 + Track-B)
# Superset config: NEVER crashes on missing imports
# ============================================================

import os

# ------------------------------------------------------------
# ENV / SERVICE
# ------------------------------------------------------------
ENV = os.getenv("ENV", "production")
SERVICE_NAME = "knoweasy-engine-api"
SERVICE_VERSION = "phase-1-stable"

# ------------------------------------------------------------
# CORE FLAGS (legacy + new compatibility)
# ------------------------------------------------------------
AI_ENABLED = os.getenv("AI_ENABLED", "1") == "1"
AI_MODE = os.getenv("AI_MODE", "prod")               # prod | dev
AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini")     # gemini | openai | claude

# ------------------------------------------------------------
# API KEYS (SAFE IF EMPTY)
# ------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")

# ------------------------------------------------------------
# MODEL NAMES
# ------------------------------------------------------------
GEMINI_PRIMARY_MODEL = os.getenv("GEMINI_PRIMARY_MODEL", "gemini-1.5-flash")
OPENAI_PRIMARY_MODEL = os.getenv("OPENAI_PRIMARY_MODEL", "gpt-4o-mini")
CLAUDE_PRIMARY_MODEL = os.getenv("CLAUDE_PRIMARY_MODEL", "claude-3-haiku")

# ------------------------------------------------------------
# PROVIDER ROUTING (Track-B ready)
# ------------------------------------------------------------
AI_PROVIDER_DEFAULT = os.getenv("AI_PROVIDER_DEFAULT", "gemini")
AI_PROVIDER_FALLBACKS = [
    x.strip()
    for x in os.getenv("AI_PROVIDER_FALLBACKS", "gemini,openai,claude").split(",")
    if x.strip()
]

ENABLE_GEMINI = True
ENABLE_OPENAI = True
ENABLE_CLAUDE = True

# ------------------------------------------------------------
# TIMEOUTS / RETRIES
# ------------------------------------------------------------
AI_TIMEOUT_SECONDS = int(os.getenv("AI_TIMEOUT_SECONDS", "25"))
MAX_AI_RETRIES = int(os.getenv("MAX_AI_RETRIES", "2"))

# ------------------------------------------------------------
# RATE LIMITING (Phase-1 in-memory)
# ------------------------------------------------------------
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
RATE_LIMIT_BURST = int(os.getenv("RATE_LIMIT_BURST", "10"))

# ------------------------------------------------------------
# CACHE (router.py expects this)
# ------------------------------------------------------------
ENABLE_SOLVE_CACHE = os.getenv("ENABLE_SOLVE_CACHE", "0") == "1"
SOLVE_CACHE_TTL_SECONDS = int(os.getenv("SOLVE_CACHE_TTL_SECONDS", "900"))

# ------------------------------------------------------------
# REDIS (future)
# ------------------------------------------------------------
REDIS_URL = os.getenv("REDIS_URL", "")
ENABLE_REDIS_RATE_LIMIT = os.getenv("ENABLE_REDIS_RATE_LIMIT", "0") == "1"

# ------------------------------------------------------------
# INPUT SAFETY
# ------------------------------------------------------------
MAX_QUESTION_CHARS = int(os.getenv("MAX_QUESTION_CHARS", "3000"))
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "6000"))

# ------------------------------------------------------------
# API KEY GUARD (optional)
# ------------------------------------------------------------
KE_API_KEY = os.getenv("KE_API_KEY", "")

# ------------------------------------------------------------
# DATABASE (optional logging)
# ------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "")

# ------------------------------------------------------------
# CORS
# ------------------------------------------------------------
CORS_ALLOW_ORIGINS = [
    x.strip()
    for x in os.getenv(
        "CORS_ALLOW_ORIGINS",
        "https://knoweasylearning.com,https://www.knoweasylearning.com,http://localhost:5500",
    ).split(",")
    if x.strip()
]

# ------------------------------------------------------------
# LOGGING
# ------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
