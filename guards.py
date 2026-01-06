import os
import time
import hmac
from typing import Dict, Tuple
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

def _now() -> float:
    return time.time()

def _get_ip(request: Request) -> str:
    # If behind a proxy/CDN, you may set KE_TRUST_X_FORWARDED_FOR=1 and ensure the proxy sets X-Forwarded-For safely.
    trust = os.getenv("KE_TRUST_X_FORWARDED_FOR", "").strip() in ("1", "true", "TRUE", "yes", "YES")
    if trust:
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            return xff.split(",")[0].strip() or "unknown"
    client = request.client
    return (client.host if client else "unknown") or "unknown"

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_bytes: int):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl:
            try:
                if int(cl) > self.max_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"ok": False, "error": "PAYLOAD_TOO_LARGE"},
                    )
            except Exception:
                # Ignore malformed content-length; still allow but the body may be rejected later by validation.
                pass
        return await call_next(request)

class ClientKeyMiddleware(BaseHTTPMiddleware):
    """Lightweight protection against random direct hits to your API.
    This is NOT a replacement for Cloudflare/WAF or proper auth."""

    def __init__(self, app, header_name: str = "x-ke-client-key"):
        super().__init__(app)
        self.header_name = header_name.lower()

    async def dispatch(self, request: Request, call_next):
        expected = os.getenv("KE_CLIENT_KEY", "").strip()
        if not expected:
            # If not configured, do not block (dev-friendly).
            return await call_next(request)

        provided = (request.headers.get(self.header_name) or request.headers.get(self.header_name.title()) or "").strip()
        if not provided:
            return JSONResponse(status_code=401, content={"ok": False, "error": "MISSING_CLIENT_KEY"})

        if not hmac.compare_digest(provided, expected):
            return JSONResponse(status_code=401, content={"ok": False, "error": "INVALID_CLIENT_KEY"})

        return await call_next(request)

class InMemoryRateLimiter:
    """Simple sliding-window limiter for dev and single-instance.
    For multi-instance production, move counters to Redis/Upstash later."""

    def __init__(self):
        self._buckets: Dict[str, Tuple[float, int]] = {}

    def allow(self, key: str, window_sec: int, limit: int) -> bool:
        now = _now()
        ts, count = self._buckets.get(key, (now, 0))
        if now - ts >= window_sec:
            self._buckets[key] = (now, 1)
            return True
        if count >= limit:
            return False
        self._buckets[key] = (ts, count + 1)
        return True

_rate_limiter = InMemoryRateLimiter()

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, window_sec: int, limit: int, path_prefixes=None):
        super().__init__(app)
        self.window_sec = window_sec
        self.limit = limit
        self.path_prefixes = tuple(path_prefixes or ("/solve", "/ask"))

    async def dispatch(self, request: Request, call_next):
        path = request.url.path or ""
        if not path.startswith(self.path_prefixes):
            return await call_next(request)

        ip = _get_ip(request)
        key = f"ip:{ip}:{path}"
        if not _rate_limiter.allow(key, self.window_sec, self.limit):
            return JSONResponse(status_code=429, content={"ok": False, "error": "RATE_LIMITED"})
        return await call_next(request)

class DailyQuotaMiddleware(BaseHTTPMiddleware):
    """Basic daily quota to prevent runaway AI spend during virality.
    Counts per IP by default. When you add login, switch to per-user_id."""

    def __init__(self, app, limit_per_day: int, path_prefixes=None):
        super().__init__(app)
        self.limit_per_day = limit_per_day
        self.path_prefixes = tuple(path_prefixes or ("/solve", "/ask"))
        self._day_key = None
        self._counts: Dict[str, int] = {}

    def _current_day(self) -> str:
        return time.strftime("%Y-%m-%d", time.gmtime())

    async def dispatch(self, request: Request, call_next):
        path = request.url.path or ""
        if not path.startswith(self.path_prefixes):
            return await call_next(request)

        day = self._current_day()
        if day != self._day_key:
            self._day_key = day
            self._counts = {}

        ip = _get_ip(request)
        user_hint = (request.headers.get("x-ke-user-id") or "").strip()
        k = f"user:{user_hint}" if user_hint else f"ip:{ip}"

        c = self._counts.get(k, 0)
        if c >= self.limit_per_day:
            return JSONResponse(
                status_code=429,
                content={"ok": False, "error": "DAILY_QUOTA_REACHED", "day": day, "limit": self.limit_per_day},
            )
        self._counts[k] = c + 1
        return await call_next(request)
