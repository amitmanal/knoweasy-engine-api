from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import hmac
import hashlib

from router import router as api_router
from auth_router import router as auth_router
from phase1_router import router as phase1_router
from payments_router import router as payments_router
from billing_router import router as billing_router
from admin_router import router as admin_router
from learning_router import router as learning_router
from luma_router import router as luma_router
import phase1_store
from redis_store import redis_health
from db import db_health, db_init

logger = logging.getLogger("knoweasy-engine-api")

# -----------------------------
# Config (safe imports)
# -----------------------------
try:
    from config import SERVICE_NAME, SERVICE_VERSION, ENV  # type: ignore
except Exception:
    SERVICE_NAME = "knoweasy-engine-api"
    SERVICE_VERSION = "phase-1"
    ENV = os.getenv("ENV", "production")

try:
    from config import ALLOWED_ORIGINS  # type: ignore
except Exception:
    ALLOWED_ORIGINS = ["*"]

try:
    from config import MAX_REQUEST_BODY_BYTES  # type: ignore
except Exception:
    # Default: 2MB (enough for text questions; blocks huge payload abuse)
    MAX_REQUEST_BODY_BYTES = 2_000_000

app = FastAPI(title=SERVICE_NAME, version=str(SERVICE_VERSION))

# -----------------------------
# CORS (required for Hostinger frontend)
# -----------------------------
# Keep permissive for Phase-1 stability; tighten later.

# -----------------------------
# Request body size cap (stability + abuse protection)
# -----------------------------
@app.middleware("http")
async def limit_request_body_size(request: Request, call_next):
    try:
        cl = request.headers.get("content-length")
        if cl:
            n = int(cl)
            if n > int(MAX_REQUEST_BODY_BYTES):
                return JSONResponse(
                    status_code=413,
                    content={
                        "ok": False,
                        "error": "PAYLOAD_TOO_LARGE",
                        "message": "Request too large. Please send a shorter question.",
                        "max_bytes": int(MAX_REQUEST_BODY_BYTES),
                    },
                )
    except Exception:
        # Never crash middleware
        pass

    return await call_next(request)

# -----------------------------
# Request logging (critical for debugging production issues)
# -----------------------------
@app.middleware("http")
async def request_logger(request: Request, call_next):
    """Log every request and attach a short request id.

    This is intentionally lightweight and NEVER crashes the app.
    """
    rid = str(uuid.uuid4())[:8]
    request.state.rid = rid
    start = time.time()
    path = request.url.path
    method = request.method
    try:
        logger.info(f"[RID:{rid}] --> {method} {path}")
    except Exception:
        pass

    try:
        response = await call_next(request)
        try:
            ms = int((time.time() - start) * 1000)
            logger.info(f"[RID:{rid}] <-- {method} {path} {response.status_code} ({ms}ms)")
        except Exception:
            pass
        try:
            response.headers["X-Request-ID"] = rid
        except Exception:
            pass
        return response
    except Exception as e:
        try:
            ms = int((time.time() - start) * 1000)
            logger.exception(f"[RID:{rid}] !! EXCEPTION on {method} {path} after {ms}ms: {e}")
        except Exception:
            pass
        raise

# -----------------------------
# Routes
# -----------------------------
app.include_router(api_router)
app.include_router(auth_router)
app.include_router(phase1_router)
app.include_router(payments_router)
app.include_router(billing_router)
app.include_router(admin_router)
app.include_router(learning_router)
app.include_router(luma_router)

# -----------------------------
# Razorpay webhook (optional)
# -----------------------------
# Razorpay may send webhooks (if enabled in dashboard). We ACK them safely so
# production logs don't fill with 404s. Later we can use this to auto-activate
# plans/boosters server-side.

@app.post("/webhook/razorpay")
async def razorpay_webhook(request: Request):
    try:
        body = await request.body()
    except Exception:
        body = b""

    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()
    sig = request.headers.get("X-Razorpay-Signature") or request.headers.get("x-razorpay-signature")

    # If secret is configured, verify signature.
    if secret:
        if not sig:
            logger.warning("Razorpay webhook: missing signature header")
            return JSONResponse(status_code=200, content={"ok": True, "warn": "MISSING_SIGNATURE"})
        expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, str(sig)):
            logger.warning("Razorpay webhook: bad signature (check RAZORPAY_WEBHOOK_SECRET)")
            return JSONResponse(status_code=200, content={"ok": True, "warn": "BAD_SIGNATURE"})

    # For now: accept and ignore. (Verification/activation handled by client verify endpoint.)
    return {"ok": True}

# -----------------------------
# CORS (required for Hostinger frontend + parent dashboard)
# -----------------------------
# IMPORTANT: Keep this middleware OUTERMOST so even error responses include CORS headers.
ALLOWED_ORIGINS_EFFECTIVE = os.getenv('ALLOWED_ORIGINS', '').strip()
if ALLOWED_ORIGINS_EFFECTIVE:
    allow_origins = [o.strip() for o in ALLOWED_ORIGINS_EFFECTIVE.split(',') if o.strip()]
elif isinstance(ALLOWED_ORIGINS, list) and ALLOWED_ORIGINS:
    allow_origins = ALLOWED_ORIGINS
else:
    allow_origins = [
        'https://knoweasylearning.com',
        'https://www.knoweasylearning.com',
        'http://localhost:8000',
        'http://127.0.0.1:8000',
    ]

# CORS: allow our Hostinger domains + local dev by default. Use ALLOWED_ORIGINS env to override.
default_origins = [
    'https://knoweasylearning.com',
    'https://www.knoweasylearning.com',
    'http://localhost',
    'http://127.0.0.1',
    'http://localhost:5500',
    'http://127.0.0.1:5500',
]

# If ALLOWED_ORIGINS env is set, we use it EXACTLY (production-safe).
# If not set, we merge a small default allowlist for Hostinger + local dev.
if ALLOWED_ORIGINS_EFFECTIVE:
    origins = allow_origins
else:
    origins = list(dict.fromkeys((allow_origins or []) + default_origins))

if any(o == '*' for o in origins):
    # Wildcard mode (no credentials).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_credentials=False,
        allow_methods=['*'],
        allow_headers=['*'],
    )
else:
    # Normal mode (supports Authorization header).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )

@app.on_event("startup")
def _startup() -> None:
    """Create Phase-1 tables early so the first parent/student call never fails."""
    try:
        phase1_store.ensure_tables()
    except Exception:
        # Never crash boot. Health endpoint will still show DB status.
        pass

    # Phase-4A: ensure telemetry tables exist (best-effort)
    try:
        db_init()
    except Exception:
        pass

    try:
        import payments_store
        import billing_store

        payments_store.ensure_tables()
        billing_store.ensure_tables()
    except Exception:
        pass

    # Luma tables (best-effort)
    try:
        import luma_store
        luma_store.ensure_tables()
    except Exception:
        pass

# -----------------------------
# Health & version endpoints (Render + monitoring)
# -----------------------------
@app.get("/")
def root():
    return {"ok": True, "service": SERVICE_NAME}

@app.get("/version")
def version():
    return {
        "ok": True,
        "service": SERVICE_NAME,
        "env": ENV,
        "version": str(SERVICE_VERSION),
        "git_sha": os.getenv("GIT_SHA", "")[:12],
    }

@app.get("/health")
def health():
    """Health + readiness diagnostics.

    - Must never crash.
    - Never returns secrets.
    - Helps us quickly see which subsystems are configured in production.
    """
    redis_info: Dict[str, Any] = {}
    db_info: Dict[str, Any] = {}

    try:
        redis_info = redis_health()
    except Exception as e:
        redis_info = {"enabled": True, "connected": False, "reason": str(e)}

    try:
        db_info = db_health()
    except Exception as e:
        db_info = {"enabled": True, "connected": False, "reason": str(e)}

    # Auth readiness (AUTH_SECRET_KEY + email provider)
    auth_cfg = False
    email_cfg = False
    email_diag: Dict[str, Any] = {}
    try:
        from auth_utils import auth_is_configured  # local import: never crash app startup
        auth_cfg = bool(auth_is_configured())
    except Exception:
        auth_cfg = False
    try:
        from email_service import email_is_configured, email_provider_debug  # local import
        email_cfg = bool(email_is_configured())
        email_diag = dict(email_provider_debug() or {})
        # remove any accidental sensitive keys
        for k in list(email_diag.keys()):
            if "key" in k.lower() or "secret" in k.lower() or "token" in k.lower():
                email_diag.pop(k, None)
    except Exception:
        email_cfg = False
        email_diag = {}

    # Payments readiness (Razorpay keys present)
    payments_cfg = bool((os.getenv("RAZORPAY_KEY_ID") or "").strip() and (os.getenv("RAZORPAY_KEY_SECRET") or "").strip())

    # AI readiness (provider key present if AI enabled)
    try:
        from config import AI_ENABLED, AI_PROVIDER, AI_MODE, GEMINI_PRIMARY_MODEL, OPENAI_MODEL, CLAUDE_MODEL  # type: ignore
    except Exception:
        AI_ENABLED = True
        AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini")
        AI_MODE = os.getenv("AI_MODE", "balanced")
        GEMINI_PRIMARY_MODEL = os.getenv("GEMINI_PRIMARY_MODEL", "")
        OPENAI_MODEL = os.getenv("OPENAI_MODEL", "")
        CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "")

    provider = (AI_PROVIDER or "gemini").strip().lower()
    gem_ok = bool((os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip())
    oai_ok = bool((os.getenv("OPENAI_API_KEY") or "").strip())
    cla_ok = bool((os.getenv("ANTHROPIC_API_KEY") or "").strip())
    if provider == "openai":
        ai_cfg = oai_ok
    elif provider == "claude":
        ai_cfg = cla_ok
    else:
        ai_cfg = gem_ok

    # CORS summary (no secrets)
    cors_effective = os.getenv("ALLOWED_ORIGINS", "").strip()
    cors_mode = "env" if cors_effective else "default"
    cors_wildcard = bool(cors_effective and "*" in [o.strip() for o in cors_effective.split(",") if o.strip()])

    # Readiness rules:
    # - DB: if enabled, must be connected; else OK (Phase-1 supports DB-less mode but we prefer DB in prod)
    # - Auth: requires AUTH_SECRET_KEY AND email configured (so OTP can actually send)
    # - AI: if AI enabled, provider key must exist
    db_ready = (not bool(db_info.get("enabled"))) or bool(db_info.get("connected"))
    auth_ready = bool(auth_cfg) and bool(email_cfg)
    ai_ready = (not bool(AI_ENABLED)) or bool(ai_cfg)

    overall_ready = bool(db_ready and auth_ready and ai_ready)

    return {
        "ok": True,
        "ready": overall_ready,
        "service": SERVICE_NAME,
        "version": str(SERVICE_VERSION),
        "env": ENV,
        "deps": {
            "redis": redis_info,
            "db": db_info,
        },
        "subsystems": {
            "auth": {
                "configured": auth_cfg,
                "email_configured": email_cfg,
                "email_provider": (email_diag.get("provider") if isinstance(email_diag, dict) else None),
            },
            "payments": {
                "enabled": payments_cfg,
            },
            "ai": {
                "enabled": bool(AI_ENABLED),
                "provider": provider,
                "mode": str(AI_MODE),
                "configured": bool(ai_cfg),
                "model": (
                    str(OPENAI_MODEL) if provider == "openai"
                    else str(CLAUDE_MODEL) if provider == "claude"
                    else str(GEMINI_PRIMARY_MODEL)
                ),
            },
        },
        "cors": {
            "mode": cors_mode,
            "wildcard": cors_wildcard,
        },
    }
