# redis_store.py
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Tuple

from config import REDIS_URL

logger = logging.getLogger("knoweasy-engine-api")

_redis_client = None


def get_redis():
    """
    Lazy Redis client creation.
    If REDIS_URL is not set, returns None (feature disabled).
    """
    global _redis_client
    if not REDIS_URL:
        return None

    if _redis_client is not None:
        return _redis_client

    try:
        import redis  # type: ignore
        _redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        return _redis_client
    except Exception as e:
        logger.warning("Redis init failed (disabled): %s", e)
        _redis_client = None
        return None


def redis_health() -> Dict[str, Any]:
    r = get_redis()
    if not r:
        return {"enabled": False, "connected": False}

    try:
        pong = r.ping()
        return {"enabled": True, "connected": bool(pong)}
    except Exception as e:
        return {"enabled": True, "connected": False, "reason": str(e)}


def get_json(key: str) -> Optional[Dict[str, Any]]:
    r = get_redis()
    if not r:
        return None
    try:
        raw = r.get(key)
        if not raw:
            return None
        return json.loads(raw)
    except Exception as e:
        logger.warning("Redis get_json failed: %s", e)
        return None


def setex_json(key: str, ttl_seconds: int, value: Dict[str, Any]) -> bool:
    r = get_redis()
    if not r:
        return False
    try:
        r.setex(key, int(ttl_seconds), json.dumps(value, ensure_ascii=False))
        return True
    except Exception as e:
        logger.warning("Redis setex_json failed: %s", e)
        return False


def setnx_ex(key: str, ttl_seconds: int, value: str = "1") -> bool:
    """SET key value NX EX ttl_seconds.

    Returns True if the key was set (lock acquired), False otherwise.
    Best-effort: returns False if Redis is disabled/fails.
    """
    r = get_redis()
    if not r:
        return False
    try:
        ok = r.set(key, value, nx=True, ex=int(ttl_seconds))
        return bool(ok)
    except Exception as e:
        logger.warning("Redis setnx_ex failed: %s", e)
        return False


def incr_with_ttl(key: str, ttl_seconds: int) -> Optional[int]:
    """
    Atomic-ish counter with TTL:
    - INCR key
    - if value becomes 1, set EXPIRE ttl_seconds
    Returns current count or None if Redis disabled/fails.
    """
    r = get_redis()
    if not r:
        return None
    try:
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.ttl(key)
        count, current_ttl = pipe.execute()

        # If key is new or has no expiry, set expiry
        if current_ttl is None or current_ttl < 0:
            r.expire(key, int(ttl_seconds))

        return int(count)
    except Exception as e:
        logger.warning("Redis incr_with_ttl failed: %s", e)
        return None
