import time
from typing import Dict, Tuple

# Very small in-memory guards (Phase-1).
# For large scale, we'll move to Redis/Upstash later.

_MAX_BODY_CHARS = 12000
_RATE_WINDOW_SEC = 60
_RATE_MAX_REQ = 30

_hits: Dict[str, Tuple[int, float]] = {}

def enforce_body_limit(question: str) -> None:
    if len(question or "") > _MAX_BODY_CHARS:
        raise ValueError(f"Question too large (>{_MAX_BODY_CHARS} chars).")

def rate_limit(key: str) -> None:
    now = time.time()
    count, start = _hits.get(key, (0, now))
    if now - start > _RATE_WINDOW_SEC:
        count, start = 0, now
    count += 1
    _hits[key] = (count, start)
    if count > _RATE_MAX_REQ:
        raise RuntimeError("Too many requests. Please try again in a minute.")
