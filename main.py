from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from router import router as api_router
from auth_router import router as auth_router
from phase1_router import router as phase1_router
from payments_router import router as payments_router
from billing_router import router as billing_router
import phase1_store
from redis_store import redis_health
from db import db_health

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

# Merge env origins with defaults (env can include '*' to allow all origins).
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

    try:
        import payments_store
        import billing_store

        payments_store.ensure_tables()
        billing_store.ensure_tables()
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
    # NOTE: Must never crash. Report status even if dependencies are down.
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

    return {
        "ok": True,
        "service": SERVICE_NAME,
        "version": str(SERVICE_VERSION),
        "redis": redis_info,
        "db": db_info,
    }
