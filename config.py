# config.py
import os

def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    try:
        return int(v) if v is not None and v.strip() != "" else default
    except Exception:
        return default

def _env_float(name: str, default: float) -> float:
    v = os.getenv(name)
    try:
        return float(v) if v is not None and v.strip() != "" else default
    except Exception:
        return default

def _env_str(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return v.strip() if v is not None else default

# ----------------------------
# Security / guardrail (optional)
# ----------------------------
KE_API_KEY = _env_str("KE_API_KEY", "")

# ----------------------------
# Rate limiting (Phase-1)
# ----------------------------
RATE_LIMIT_PER_MINUTE = _env_int("RATE_LIMIT_PER_MINUTE", 30)
RATE_LIMIT_BURST = _env_int("RATE_LIMIT_BURST", 10)
RATE_LIMIT_WINDOW_SECONDS = _env_float("RATE_LIMIT_WINDOW_SECONDS", 60.0)

# ----------------------------
# Redis (optional)
# Set this in Render Environment to enable distributed rate limiting + cache
# Example: REDIS_URL=redis://default:password@host:port
# ----------------------------
REDIS_URL = _env_str("REDIS_URL", "")

# ----------------------------
# Cache controls (Phase-1)
# ----------------------------
# Cache successful /solve outputs for short time to reduce AI cost
SOLVE_CACHE_TTL_SECONDS = _env_int("SOLVE_CACHE_TTL_SECONDS", 120)

# De-dup safety (same as cache TTL; can be shorter if you want)
SOLVE_DEDUP_TTL_SECONDS = _env_int("SOLVE_DEDUP_TTL_SECONDS", 60)
