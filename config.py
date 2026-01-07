# config.py
# =========================================================
# KnowEasy Engine API — Phase-1 Stable + Track-B Safe Config
# Goal: NEVER crash on missing env vars / future imports
# =========================================================

import os

# =========================================================
# ENVIRONMENT / SERVICE
# =========================================================
ENV = os.getenv("ENV", "production")
SERVICE_NAME = os.getenv("SERVICE_NAME", "knoweasy-engine-api")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "phase-1-stable")

# =========================================================
# CORS (optional; your main.py may configure separately)
# Keep as string list split for convenience.
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
KE_API_KEY = os.getenv("KE_API_KEY", "")  # if empty, guard is effectively off

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

# (Optional) “engine routing” defaults (Track-B)
AI_PROVIDER_DEFAULT = os.getenv("AI_PROVIDER_DEFAULT", "gemini")  # gemini|openai|claude
AI_PROVIDER_FALLBACKS = [
    x.strip()
    for x in os.getenv("AI_PROVIDER_FALLBACKS", "gemini,openai,claude").split(",")
    if x.strip()
]

# =========================================================
# AI TIMEOUTS / RETRIES
# =========================================================
AI_TIMEOUT_SECONDS = int(os.getenv("AI_TIMEOUT_SECONDS", "25"))
MAX_AI_RETRIES = int(os.getenv("MAX_AI_RETRIES", "2"))

# =========================================================
# INPUT LIMITS (safety against abuse)
# =========================================================
MAX_QUESTION_CHARS = int(os.getenv("MAX_QUESTION_CHARS", "3000"))
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "6000"))

# =========================================================
# RATE LIMITING (Phase-1 in-memory)
# =========================================================
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
RATE_LIMIT_BURST = int(os.getenv("RATE_LIMIT_BURST", "10"))

# =========================================================
# REDIS (optional; used for shared rate limit / cache later)
# =========================================================
REDIS_URL = os.getenv("REDIS_URL", "")  # Render Redis will provide this if enabled
ENABLE_REDIS_RATE_LIMIT = os.getenv("ENABLE_REDIS_RATE_LIMIT", "0") == "1"

# =========================================================
# SOLVE CACHE (optional; router.py expects TTL constant)
# =========================================================
ENABLE_SOLVE_CACHE = os.getenv("ENABLE_SOLVE_CACHE", "0") == "1"
SOLVE_CACHE_TTL_SECONDS = int(os.getenv("SOLVE_CACHE_TTL_SECONDS", "900"))  # 15 min default

# =========================================================
# DATABASE (optional / best-effort logging)
# =========================================================
DATABASE_URL = os.getenv("DATABASE_URL", "")

# =========================================================
# FEATURE FLAGS (future-proof; do not crash if unused)
# =========================================================
ENABLE_GEMINI = os.getenv("ENABLE_GEMINI", "1") == "1"
ENABLE_OPENAI = os.getenv("ENABLE_OPENAI", "1") == "1"
ENABLE_CLAUDE = os.getenv("ENABLE_CLAUDE", "1") == "1"

# =========================================================
# LOGGING
# =========================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
