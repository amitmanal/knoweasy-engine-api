"""rate_limiter.py — Redis-first rate limiting for multi-worker safety.

FIX: The old in-memory _BUCKETS dict only worked with a single worker.
With UVICORN_WORKERS=4, each worker had its own bucket → rate limits
were effectively divided by 4 (useless).

This module provides a single function `is_allowed(ip)` that:
1. Uses Redis atomically (INCR + EXPIRE) — works across all workers
2. Falls back to in-memory ONLY if Redis is completely unavailable
3. In-memory fallback is per-worker aware (divides limit by worker count)
"""

from __future__ import annotations

import os
import time
import logging
from typing import Dict, Tuple

from redis_store import incr_with_ttl as redis_incr_with_ttl

logger = logging.getLogger("knoweasy.rate_limiter")

# In-memory fallback (only used if Redis is totally dead)
_BUCKETS: Dict[str, Tuple[float, int]] = {}
_BUCKET_CLEANUP_COUNTER = 0


def _env_int(key: str, default: int) -> int:
    v = os.getenv(key)
    if v is None or str(v).strip() == "":
        return default
    try:
        return int(str(v).strip())
    except Exception:
        return default


def is_allowed(ip: str) -> bool:
    """Check if IP is within rate limit. Returns True if allowed."""
    limit = _env_int("RATE_LIMIT_PER_MINUTE", 60) + _env_int("RATE_LIMIT_BURST", 10)
    window_s = _env_int("RATE_LIMIT_WINDOW_SECONDS", 60)

    now = time.time()
    bucket = int(now // window_s)
    redis_key = f"rl:{ip}:{bucket}"

    # Try Redis first (works across all workers)
    rc = redis_incr_with_ttl(redis_key, window_s)
    if rc is not None:
        return rc <= limit

    # Fallback: in-memory (per-worker, so divide limit by worker count)
    workers = _env_int("UVICORN_WORKERS", 4)
    per_worker_limit = max(5, limit // max(1, workers))

    global _BUCKET_CLEANUP_COUNTER
    _BUCKET_CLEANUP_COUNTER += 1
    if _BUCKET_CLEANUP_COUNTER % 100 == 0:
        _cleanup_stale_buckets(now, window_s)

    start, count = _BUCKETS.get(ip, (now, 0))
    if now - start >= window_s:
        start, count = now, 0

    if count >= per_worker_limit:
        _BUCKETS[ip] = (start, count)
        return False

    _BUCKETS[ip] = (start, count + 1)
    return True


def _cleanup_stale_buckets(now: float, window_s: int) -> None:
    """Remove stale entries to prevent memory leak in fallback mode."""
    stale = [ip for ip, (start, _) in _BUCKETS.items() if now - start > window_s * 2]
    for ip in stale:
        _BUCKETS.pop(ip, None)
