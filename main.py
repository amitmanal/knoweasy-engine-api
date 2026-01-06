from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from router import router
from config import (
    MAX_REQUEST_BYTES,
    RATE_LIMIT_WINDOW_SEC,
    RATE_LIMIT_PER_WINDOW,
    DAILY_SOLVE_LIMIT,
)
from guards import (
    RequestSizeLimitMiddleware,
    ClientKeyMiddleware,
    RateLimitMiddleware,
    DailyQuotaMiddleware,
)

app = FastAPI(title="KnowEasy Orchestrator API", version="0.2.0")

# ---- CORS (production-safe) ----
# Comma-separated list in env: KE_ALLOWED_ORIGINS="https://knoweasylearning.com,https://www.knoweasylearning.com"
default_origins = [
    "https://knoweasylearning.com",
    "https://www.knoweasylearning.com",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
env_origins = os.getenv("KE_ALLOWED_ORIGINS", "").strip()
allow_origins = [o.strip() for o in env_origins.split(",") if o.strip()] or default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,  # keep FALSE unless you are using cookies/sessions
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=86400,
)

# ---- Safety rails (works on FREE now; production-ready by design) ----
# 1) Prevent huge payloads (cheap DoS)
app.add_middleware(RequestSizeLimitMiddleware, max_bytes=MAX_REQUEST_BYTES)

# 2) Optional lightweight client key (set KE_CLIENT_KEY in env when ready)
app.add_middleware(ClientKeyMiddleware)

# 3) Burst rate limiting (per IP)
app.add_middleware(RateLimitMiddleware, window_sec=RATE_LIMIT_WINDOW_SEC, limit=RATE_LIMIT_PER_WINDOW)

# 4) Daily quota (per IP; later swap to per-user when login is added)
app.add_middleware(DailyQuotaMiddleware, limit_per_day=DAILY_SOLVE_LIMIT)

@app.get("/health")
def health():
    return {"ok": True, "service": "knoweasy-orchestrator-phase1"}

app.include_router(router)
