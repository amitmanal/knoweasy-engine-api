from __future__ import annotations

import logging
import os
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from router import router as api_router
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
# Routes
# -----------------------------
app.include_router(api_router)

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
