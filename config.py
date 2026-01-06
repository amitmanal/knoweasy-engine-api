import os

def env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    return v if v not in (None, "") else default

APP_ENV = env("APP_ENV", "prod")

# Gemini API key: keep both names for convenience
GEMINI_API_KEY = env("GEMINI_API_KEY") or env("GOOGLE_API_KEY")

# Default Gemini model (stable, fast)
GENAI_MODEL = env("GENAI_MODEL", "gemini-2.5-flash")

# CORS
ALLOWED_ORIGINS = env("ALLOWED_ORIGINS", "*")

# Basic rate limiting (soft guard)
RATE_LIMIT_RPM = int(env("RATE_LIMIT_RPM", "60") or "60")
