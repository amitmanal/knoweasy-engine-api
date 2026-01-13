"""Auth helpers: hashing, token generation, email validation.

Design goals:
- Simple, secure enough for Phase-2.1
- No external deps
- No impact on /solve
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
from typing import Tuple

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

def normalize_email(email: str) -> str:
    return (email or "").strip().lower()

def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(normalize_email(email)))

def _secret_bytes() -> bytes:
    # Required for stable hashing across processes/deploys.
    s = os.getenv("AUTH_SECRET_KEY", "").strip()
    return s.encode("utf-8") if s else b""

def auth_is_configured() -> bool:
    return bool(_secret_bytes())

def hash_value(value: str) -> str:
    """HMAC-SHA256 hash using AUTH_SECRET_KEY."""
    secret = _secret_bytes()
    if not secret:
        # No secret configured -> return empty to signal "disabled"
        return ""
    mac = hmac.new(secret, value.encode("utf-8"), hashlib.sha256).hexdigest()
    return mac

def constant_time_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))

def new_otp_code() -> Tuple[str, str]:
    """Return (otp_plain, otp_hash)."""
    otp = f"{secrets.randbelow(1_000_000):06d}"
    return otp, hash_value(otp)

def new_session_token() -> Tuple[str, str]:
    """Return (token_plain, token_hash)."""
    raw = secrets.token_bytes(32)
    token = base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")
    return token, hash_value(token)
