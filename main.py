from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from router import router

app = FastAPI(title="KnowEasy Orchestrator API", version="0.1.1")

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
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=86400,
)

@app.get("/health")
def health():
    return {"ok": True, "service": "knoweasy-orchestrator-phase1"}

app.include_router(router)
