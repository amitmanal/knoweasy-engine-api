# config.py
# =========================================================
# KnowEasy Engine API — Phase-1 Stable Configuration
# Silicon-valley grade: safe defaults, future-proof
# =========================================================

import os

# =========================================================
# ENVIRONMENT
# =========================================================
ENV = os.getenv("ENV", "production")

SERVICE_NAME = "knoweasy-engine-api"
SERVICE_VERSION = "phase-1-stable"

# =========================================================
# AI PROVIDERS — API KEYS
# (Safe even if not set)
# =========================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")

# =========================================================
# AI MODELS (DEFAULTS)
# =========================================================
GEMINI_PRIMARY_MODEL = os.getenv(
    "GEMINI_PRIMARY_MODEL", "gemini-1.5-flash"
)

OPENAI_PRIMARY_MODEL = os.getenv(
    "OPENAI_PRIMARY_MODEL", "gpt-4o-mini"
)

CLAUDE_PRIMARY_MODEL = os.getenv(
    "CLAUDE_PRIMARY_MODEL", "claude-3-haiku"
)

# =========================================================
# AI TIMEOUTS & SAFETY
# =========================================================
AI_TIMEOUT_SECONDS = int(
    os.getenv("AI_TIMEOUT_SECONDS", "25")
)

MAX_AI_RETRIES = int(
    os.getenv("MAX_AI_RETRIES", "2")
)

# =========================================================
# RATE LIMITING (IN-MEMORY — PHASE-1)
# =========================================================
RATE_LIMIT_PER_MINUTE = int(
    os.getenv("RATE_LIMIT_PER_MINUTE", "30")
)

RATE_LIMIT_BURST = int(
    os.getenv("RATE_LIMIT_BURST", "10")
)

RATE_LIMIT_WINDOW_SECONDS = int(
    os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")
)

# =========================================================
# SECURITY
# =========================================================
# Optional shared key (Phase-1)
KE_API_KEY = os.getenv("KE_API_KEY", "")

# =========================================================
# DATABASE (OPTIONAL / BEST-EFFORT)
# =========================================================
DATABASE_URL = os.getenv("DATABASE_URL", "")

# =========================================================
# FEATURE FLAGS (FUTURE SAFE)
# =========================================================
ENABLE_GEMINI = True
ENABLE_OPENAI = True
ENABLE_CLAUDE = True

# =========================================================
# LOGGING
# =========================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# =========================================================
# END OF FILE — DO NOT ADD LOGIC HERE
# =========================================================
