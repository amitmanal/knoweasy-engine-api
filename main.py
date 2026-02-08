"""KnowEasy Engine API — Main application (Production v2.1)"""

from __future__ import annotations
import logging, os, time, uuid, hmac, hashlib
from typing import Any, Dict
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from router import router as api_router
from auth_router import router as auth_router
from phase1_router import router as phase1_router
from payments_router import router as payments_router
from billing_router import router as billing_router
from admin_router import router as admin_router
from learning_router import router as learning_router
from study_router import router as study_router
from syllabus_router import router as syllabus_router
from assets_router import router as assets_router
from teacher_admin_router import router as teacher_admin_router
from luma_router import router as luma_router

import phase1_store
from redis_store import redis_health
from db import db_health, db_init

logger = logging.getLogger("knoweasy-engine-api")

try:
    from config import ENV, AI_ENABLED, AI_PROVIDER
except Exception:
    ENV = os.getenv("ENV", "production")
    AI_ENABLED = True
    AI_PROVIDER = "gemini"

SERVICE_NAME = "knoweasy-engine-api"
SERVICE_VERSION = "v2.1"
MAX_REQUEST_BODY_BYTES = int(os.getenv("MAX_REQUEST_BODY_BYTES", "10000000"))

app = FastAPI(title=SERVICE_NAME, version=SERVICE_VERSION)

@app.middleware("http")
async def limit_request_body(request: Request, call_next):
    try:
        cl = request.headers.get("content-length")
        if cl and int(cl) > MAX_REQUEST_BODY_BYTES:
            return JSONResponse(status_code=413, content={"ok": False, "error": "PAYLOAD_TOO_LARGE", "max_bytes": MAX_REQUEST_BODY_BYTES})
    except Exception:
        pass
    return await call_next(request)

@app.middleware("http")
async def request_logger(request: Request, call_next):
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
        ms = int((time.time() - start) * 1000)
        try:
            logger.info(f"[RID:{rid}] <-- {method} {path} {response.status_code} ({ms}ms)")
        except Exception:
            pass
        try:
            response.headers["X-Request-ID"] = rid
        except Exception:
            pass
        return response
    except Exception as e:
        logger.exception(f"[RID:{rid}] !! {method} {path}: {e}")
        raise

# ─── Routes ──────────────────────────────────────────────────────────────────
app.include_router(api_router)
app.include_router(auth_router)
app.include_router(phase1_router)
app.include_router(payments_router)
app.include_router(billing_router)
app.include_router(admin_router)
app.include_router(learning_router)
app.include_router(study_router)
app.include_router(syllabus_router)
app.include_router(assets_router)
app.include_router(teacher_admin_router)
app.include_router(luma_router)

@app.post("/webhook/razorpay")
async def razorpay_webhook(request: Request):
    try:
        body = await request.body()
    except Exception:
        body = b""
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()
    sig = request.headers.get("X-Razorpay-Signature") or request.headers.get("x-razorpay-signature")
    if secret:
        if not sig:
            return JSONResponse(status_code=200, content={"ok": True, "warn": "MISSING_SIGNATURE"})
        expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, str(sig)):
            return JSONResponse(status_code=200, content={"ok": True, "warn": "BAD_SIGNATURE"})
    return {"ok": True}

# ─── CORS (SINGLE middleware) ────────────────────────────────────────────────
_origins_env = os.getenv("ALLOWED_ORIGINS", "").strip()
if _origins_env:
    _origins = [o.strip() for o in _origins_env.split(",") if o.strip()]
else:
    _origins = ["https://knoweasylearning.com", "https://www.knoweasylearning.com",
                "http://localhost", "http://127.0.0.1", "http://localhost:5500", "http://127.0.0.1:5500"]

if any(o == "*" for o in _origins):
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
else:
    app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def _startup():
    for label, fn in [
        ("phase1", lambda: phase1_store.ensure_tables()),
        ("db_init", lambda: db_init()),
        ("payments", lambda: __import__("payments_store").ensure_tables()),
        ("billing", lambda: __import__("billing_store").ensure_tables()),
        ("study", lambda: __import__("study_store").ensure_tables()),
    ]:
        try:
            fn()
        except Exception as e:
            logger.warning(f"Startup {label}: {e}")

@app.get("/")
def root():
    return {"ok": True, "service": SERVICE_NAME}

@app.get("/version")
def version():
    return {"ok": True, "service": SERVICE_NAME, "env": ENV, "version": SERVICE_VERSION}

@app.get("/health")
def health():
    redis_info = {}
    db_info = {}
    try:
        redis_info = redis_health()
    except Exception as e:
        redis_info = {"connected": False, "reason": str(e)}
    try:
        db_info = db_health()
    except Exception as e:
        db_info = {"connected": False, "reason": str(e)}
    auth_cfg = email_cfg = False
    try:
        from auth_utils import auth_is_configured
        auth_cfg = bool(auth_is_configured())
    except Exception:
        pass
    try:
        from email_service import email_is_configured
        email_cfg = bool(email_is_configured())
    except Exception:
        pass
    r2_cfg = bool((os.getenv("R2_ENDPOINT") or "").strip() and (os.getenv("R2_ACCESS_KEY_ID") or "").strip())
    payments_cfg = bool((os.getenv("RAZORPAY_KEY_ID") or "").strip() and (os.getenv("RAZORPAY_KEY_SECRET") or "").strip())
    db_ready = (not bool(db_info.get("enabled"))) or bool(db_info.get("connected"))
    return {
        "ok": True, "ready": db_ready and auth_cfg and email_cfg,
        "service": SERVICE_NAME, "version": SERVICE_VERSION, "env": ENV,
        "deps": {"redis": redis_info, "db": db_info},
        "subsystems": {
            "auth": {"configured": auth_cfg, "email_configured": email_cfg},
            "payments": {"enabled": payments_cfg},
            "ai": {"enabled": bool(AI_ENABLED), "provider": str(AI_PROVIDER)},
            "r2": {"configured": r2_cfg},
        },
    }
