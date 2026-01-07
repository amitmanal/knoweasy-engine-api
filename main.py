# main.py
from __future__ import annotations

import inspect
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from db import db_health, db_init
from router import router as api_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("knoweasy-engine-api")

_START_MONO = time.monotonic()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_version() -> str:
    # Try common env names (Render + generic CI)
    return (
        os.getenv("RENDER_GIT_COMMIT")
        or os.getenv("GIT_SHA")
        or os.getenv("BUILD_SHA")
        or os.getenv("COMMIT_SHA")
        or "unknown"
    )


def _new_req_id() -> str:
    # Short, log-friendly id
    return uuid.uuid4().hex[:12]


async def _maybe_await(value: Any) -> Any:
    """If value is awaitable (coroutine/future), await it; otherwise return as-is."""
    if inspect.isawaitable(value):
        return await value
    return value


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Safe DB init (works for both sync and async db_init)
    try:
        res = await _maybe_await(db_init())
        logger.info("DB init result: %s", res)
    except Exception as e:
        # Never crash startup due to DB
        logger.warning("DB init failed (ignored): %s", e)

    yield

    logger.info("Shutdown complete")


app = FastAPI(title="KnowEasy Engine API", version="1.0.0", lifespan=lifespan)

# CORS (keep permissive for now; tighten later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- C-4: Request ID middleware (adds X-Request-Id for every response) ---
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("x-request-id") or request.headers.get("X-Request-Id")
    rid = (rid or "").strip() or _new_req_id()

    request.state.req_id = rid

    t0 = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as e:
        # Still log with req_id for traceability, then re-raise
        logger.error(
            json.dumps(
                {
                    "event": "unhandled_exception",
                    "req_id": rid,
                    "path": str(request.url.path),
                    "method": request.method,
                    "error_type": type(e).__name__,
                    "ts_utc": _utc_now_iso(),
                },
                ensure_ascii=False,
            )
        )
        raise

    # Attach request id + basic timing
    response.headers["X-Request-Id"] = rid
    response.headers["X-Response-Time-Ms"] = str(int((time.perf_counter() - t0) * 1000))
    return response


# ---- REQUIRED FOR RENDER HEALTH ----
# Explicitly support BOTH GET and HEAD on "/"
@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
def root() -> Dict[str, Any]:
    return {"ok": True, "service": "knoweasy-engine-api"}


@app.get("/health", include_in_schema=False)
def health() -> Dict[str, Any]:
    return {"ok": True}


@app.get("/health/db", include_in_schema=False)
def health_db() -> Dict[str, Any]:
    try:
        return db_health()
    except Exception as e:
        return {"enabled": True, "connected": False, "reason": str(e)}


# --- C-4: version endpoint (debugging + deploy verification) ---
@app.api_route("/version", methods=["GET", "HEAD"], include_in_schema=False)
def version() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "knoweasy-engine-api",
        "version": _get_version(),
        "time_utc": _utc_now_iso(),
        "uptime_seconds": int(time.monotonic() - _START_MONO),
    }


# API routes (/solve etc)
app.include_router(api_router)
