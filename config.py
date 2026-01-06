import os
from dotenv import load_dotenv

load_dotenv()

def env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    return v if v not in (None, "") else default

APP_ENV = env("APP_ENV", "prod")
GEMINI_API_KEY = env("GEMINI_API_KEY")

# CORS: comma-separated list of allowed origins.
# Example:
# CORS_ALLOW_ORIGINS=https://knoweasy.in,https://www.knoweasy.in,http://localhost:5500
CORS_ALLOW_ORIGINS = env("CORS_ALLOW_ORIGINS", "*")
