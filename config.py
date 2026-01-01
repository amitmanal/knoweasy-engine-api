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
