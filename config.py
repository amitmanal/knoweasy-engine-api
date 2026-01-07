import os
from dotenv import load_dotenv

load_dotenv()

# =========================
# Core AI configuration
# =========================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# Default models (can be swapped anytime)
GEMINI_PRIMARY_MODEL = os.getenv("GEMINI_PRIMARY_MODEL", "gemini-2.5-flash").strip()
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-pro").strip()

# Feature flag / emergency stop (CEO kill-switch)
AI_ENABLED = os.getenv("AI_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")

# Optional (kept for roadmap / logging)
AI_MODE = os.getenv("AI_MODE", "production").strip()
AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").strip()

# Single source of truth timeout (Render env)
# If not set, fallback to legacy GEMINI_TIMEOUT_S, then 18.
AI_TIMEOUT_SECONDS = float(
    (os.getenv("AI_TIMEOUT_SECONDS") or os.getenv("GEMINI_TIMEOUT_S") or "18").strip()
)

# Backward-compatible alias (models.py still imports GEMINI_TIMEOUT_S)
GEMINI_TIMEOUT_S = AI_TIMEOUT_SECONDS

# When confidence is below this, we do a second pass
LOW_CONFIDENCE_THRESHOLD = float(os.getenv("LOW_CONFIDENCE_THRESHOLD", "0.70"))

# Hard cap to keep responses fast & cheap
MAX_STEPS = int(os.getenv("MAX_STEPS", "8"))
MAX_CHARS_ANSWER = int(os.getenv("MAX_CHARS_ANSWER", "2500"))

# =========================
# Stability / anti-crash knobs
# =========================
# Max request body size (bytes) - protects against abuse / accidental huge payloads
MAX_REQUEST_BYTES = int(os.getenv("MAX_REQUEST_BYTES", str(64 * 1024)))  # 64KB default

# Circuit breaker: if Gemini fails too often, pause calls temporarily (auto self-protection)
CB_FAILURE_THRESHOLD = int(os.getenv("CB_FAILURE_THRESHOLD", "6"))
CB_COOLDOWN_S = int(os.getenv("CB_COOLDOWN_S", "60"))

# In-memory per-IP rate limits (good enough for Phase-1 / free tier).
# Later we'll replace with Redis/Cloudflare rate limiting (no rewrites needed).
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
RATE_LIMIT_BURST = int(os.getenv("RATE_LIMIT_BURST", "10"))

# Optional shared secret to reduce random abuse (NOT true security, but a helpful guardrail).
# If empty -> disabled.
KE_API_KEY = os.getenv("KE_API_KEY", "").strip()

# =========================
# Database (optional)
# =========================
# If DATABASE_URL is not set, DB logging/features are disabled.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or None

# Render Postgres often needs sslmode=require for external URLs.
DB_SSLMODE = os.getenv("DB_SSLMODE", "require").strip() or "require"

# A switch to hard-disable DB usage (even if DATABASE_URL is present)
DB_ENABLED = os.getenv("DB_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")
