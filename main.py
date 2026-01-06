from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os

from config import MAX_REQUEST_BYTES
from router import router
from db import db_init, db_health

app = FastAPI(title="KnowEasy Orchestrator API", version="0.2.0-phase1")

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
if env_origins:
    allow_origins = [o.strip() for o in env_origins.split(",") if o.strip()]
else:
    allow_origins = default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,  # keep FALSE unless you are using cookies/sessions
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=86400,
)

# ---- Request size guard (anti-abuse) ----
@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    # Fast path: Content-Length
    cl = request.headers.get("content-length")
    if cl:
        try:
            if int(cl) > MAX_REQUEST_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={
                        "final_answer": "Request too large. Please shorten your question 😊",
                        "steps": [],
                        "assumptions": [],
                        "confidence": 0.2,
                        "flags": ["PAYLOAD_TOO_LARGE"],
                        "safe_note": "Tip: remove extra text and keep only the question.",
                        "meta": {"engine": "knoweasy-orchestrator-phase1"},
                    },
                )
        except Exception:
            pass

    # If content-length missing, we still proceed (most browsers send it).
    return await call_next(request)

@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "knoweasy-orchestrator-phase1",
        "version": "0.3.0",
        "db": db_health(),
    }


@app.on_event("startup")
def _startup():
    # DB is optional; init is safe even when DATABASE_URL is missing.
    db_init()

app.include_router(router)


@app.on_event("startup")
def _startup():
    # Safe DB init (no-op if DATABASE_URL not provided)
    db_init()
