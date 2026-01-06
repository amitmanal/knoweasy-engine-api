import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# Default models (can be swapped anytime)
GEMINI_PRIMARY_MODEL = os.getenv("GEMINI_PRIMARY_MODEL", "gemini-2.5-flash").strip()
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-pro").strip()

# When confidence is below this, we do a second pass
LOW_CONFIDENCE_THRESHOLD = float(os.getenv("LOW_CONFIDENCE_THRESHOLD", "0.70"))

# Hard cap to keep responses fast & cheap
MAX_STEPS = int(os.getenv("MAX_STEPS", "8"))
MAX_CHARS_ANSWER = int(os.getenv("MAX_CHARS_ANSWER", "2500"))
# --- Backend safety rails (dev on free; production-ready by design) ---
# Hard timeout for a single model call (seconds)
MODEL_TIMEOUT_SEC = float(os.getenv("KE_MODEL_TIMEOUT_SEC", "20"))

# Per-IP burst control (requests per window)
RATE_LIMIT_WINDOW_SEC = int(os.getenv("KE_RATE_LIMIT_WINDOW_SEC", "60"))
RATE_LIMIT_PER_WINDOW = int(os.getenv("KE_RATE_LIMIT_PER_WINDOW", "30"))

# Daily quota for solve endpoints (per IP; later swap to per-user)
DAILY_SOLVE_LIMIT = int(os.getenv("KE_DAILY_SOLVE_LIMIT", "80"))

# Request size limit (bytes). Keeps bots from sending huge payloads.
MAX_REQUEST_BYTES = int(os.getenv("KE_MAX_REQUEST_BYTES", "50000"))

# Kill switch: if set to 0/false, AI solving will be disabled (app still responds safely)
AI_ENABLED = os.getenv("KE_AI_ENABLED", "1").strip().lower() not in ("0", "false", "no")
