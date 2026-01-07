from __future__ import annotations

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from router import router as api_router

logger = logging.getLogger("knoweasy-engine-api")

app = FastAPI(title="KnowEasy Engine API", version="1.0.0")

# -----------------------------
# CORS (required for Hostinger frontend)
# -----------------------------
# Without this, browser requests from https://knoweasylearning.com will be blocked.
ALLOWED_ORIGINS = [
    "https://knoweasylearning.com",
    "https://www.knoweasylearning.com",
    "http://localhost",
    "http://localhost:5500",
    "http://127.0.0.1",
    "http://127.0.0.1:5500",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Routes
# -----------------------------
app.include_router(api_router)

# -----------------------------
# Basic health
# -----------------------------
@app.get("/")
def root():
    return {"ok": True, "service": "knoweasy-engine-api"}
