"""KnowEasy Engine API — Main application (Production)"""

from __future__ import annotations

import logging
import os
import time
import uuid
import hmac
import hashlib
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ─── Routers ─────────────────────────────────────────────────────────────────
from router import router as api_router
from auth_router import router as auth_router
from phase1_router import router as phase1_router
from payments_router import router as payments_router
from billing_router import router as billing_router
from admin_router import router as admin_router
from learning_router import router as learning_router
from luma_router import router as luma_router
from study_router import router as study_router
from assets_router import router as assets_router
from syllabus_router import router as syllabus_router
from teacher_admin_router import router as teacher_admin_router

import phase1_store
from redis_store import redis_health
from db import db_health, db_init

logger = logging.getLogger("knoweasy-engine-api")

# ─── Config ──────────────────────────────────────────────────────────────────
try:
    from config import SERVICE_NAME, SERVICE_VERSION, ENV
except Exception:
    SERVICE_NAME = "knoweasy-engine-api"
    SERVICE_VERSION = "v2.0"
    ENV = os.getenv("ENV", "production")

MAX_REQUEST_BODY_BYTES = int(os.getenv("MAX_REQUEST_BODY_BYTES", "2000000"))

app = FastAPI(title=SERVICE_NAME, version=str(SERVICE_VERSION))

# ─── Middleware: Body size limit ─────────────────────────────────────────────
@app.middleware("http")
async def limit_request_body(request: Request, call_next):
    try:
        cl = request.headers.get("content-length")
        if cl and int(cl) > MAX_REQUEST_BODY_BYTES:
            return JSONResponse(status_code=413, content={
                "ok": False, "error": "PAYLOAD_TOO_LARGE",
                "max_bytes": MAX_REQUEST_BODY_BYTES,
            })
    except Exception:
        pass
    return await call_next(request)

# ─── Middleware: Request logging ─────────────────────────────────────────────
@app.middleware("http")
async def request_logger(request: Request, call_next):
    rid = str(uuid.uuid4())[:8]
    request.state.rid = rid
    start = time.time()
    path = request.url.path
    method = request.method
    try:
        response = await call_next(request)
        ms = int((time.time() - start) * 1000)
        if not path.startswith("/health"):
            logger.info(f"[{rid}] {method} {path} {response.status_code} ({ms}ms)")
        response.headers["X-Request-ID"] = rid
        return response
    except Exception as e:
        logger.exception(f"[{rid}] {method} {path} EXCEPTION: {e}")
        raise

# ─── Routes ──────────────────────────────────────────────────────────────────
app.include_router(api_router)
app.include_router(auth_router)
app.include_router(phase1_router)
app.include_router(payments_router)
app.include_router(billing_router)
app.include_router(admin_router)
app.include_router(learning_router)
app.include_router(luma_router)
app.include_router(study_router)
app.include_router(assets_router)
app.include_router(syllabus_router)
app.include_router(teacher_admin_router)

# ─── Razorpay Webhook ───────────────────────────────────────────────────────
@app.post("/webhook/razorpay")
async def razorpay_webhook(request: Request):
    try:
        body = await request.body()
    except Exception:
        body = b""
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()
    sig = request.headers.get("X-Razorpay-Signature") or request.headers.get("x-razorpay-signature")
    if secret and sig:
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, str(sig)):
            return JSONResponse(status_code=200, content={"ok": True, "warn": "BAD_SIGNATURE"})
    return {"ok": True}

# ─── CORS ────────────────────────────────────────────────────────────────────
_origins_env = os.getenv("ALLOWED_ORIGINS", "").strip()
if _origins_env:
    _origins = [o.strip() for o in _origins_env.split(",") if o.strip()]
else:
    _origins = [
        "https://knoweasylearning.com",
        "https://www.knoweasylearning.com",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ]

if "*" in _origins:
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                       allow_methods=["*"], allow_headers=["*"])
else:
    app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

# ─── Startup ─────────────────────────────────────────────────────────────────
@app.on_event("startup")
def _startup():
    for init_fn in [
        lambda: phase1_store.ensure_tables(),
        lambda: db_init(),
        lambda: __import__("payments_store").ensure_tables(),
        lambda: __import__("billing_store").ensure_tables(),
        lambda: __import__("luma_router").ensure_tables(),
        lambda: __import__("study_store").ensure_tables(),
    ]:
        try:
            init_fn()
        except Exception:
            pass

# ─── Health ──────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"ok": True, "service": SERVICE_NAME}

@app.get("/version")
def version():
    return {"ok": True, "service": SERVICE_NAME, "env": ENV, "version": str(SERVICE_VERSION)}

@app.get("/health")
def health():
    db_info = {}
    redis_info = {}
    try:
        db_info = db_health()
    except Exception as e:
        db_info = {"connected": False, "reason": str(e)}
    try:
        redis_info = redis_health()
    except Exception as e:
        redis_info = {"connected": False, "reason": str(e)}
    db_ok = bool(db_info.get("connected"))
    return {
        "ok": True,
        "ready": db_ok,
        "service": SERVICE_NAME,
        "version": str(SERVICE_VERSION),
        "env": ENV,
        "deps": {"db": db_info, "redis": redis_info},
    }
