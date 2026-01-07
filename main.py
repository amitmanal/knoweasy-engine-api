# main.py
from __future__ import annotations

import asyncio
import inspect
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from router import router as api_router
from db import db_init, db_health

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("knoweasy-engine-api")


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

    # Optional: nothing required on shutdown
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
    # db_health is already defensive; keep it simple
    try:
        return db_health()
    except Exception as e:
        return {"enabled": True, "connected": False, "reason": str(e)}


# API routes (/solve etc)
app.include_router(api_router)
