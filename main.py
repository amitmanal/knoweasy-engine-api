from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from router import router
from config import AI_ENABLED, DB_ENABLED, DATABASE_URL

# DB module should expose: db_init(), db_health()
# If DB is disabled or not configured, endpoints will still work safely.
from db import db_init, db_health


app = FastAPI(title="KnowEasy Engine API", version="Phase-1C")


# -------------------------
# CORS (Phase-1 friendly)
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Phase-1: open; later restrict to your Hostinger domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------
# Routes
# -------------------------
app.include_router(router)


# -------------------------
# Startup (ONLY ONCE)
# -------------------------
@app.on_event("startup")
async def _startup():
    # DB init should be safe/no-op if DB is disabled or missing DATABASE_URL
    await db_init()


# -------------------------
# Health / Status
# -------------------------
@app.get("/")
def root():
    # Fix: Render/monitors hitting "/" should not see 404.
    return {
        "service": "knoweasy-engine-api",
        "status": "ok",
        "endpoints": ["/health", "/health/db", "/solve"],
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "ai_enabled": bool(AI_ENABLED),
        "db_enabled": bool(DB_ENABLED and DATABASE_URL),
    }


@app.get("/health/db")
async def health_db():
    # Safe DB health: never crash the API even if DB settings are wrong.
    if not (DB_ENABLED and DATABASE_URL):
        return {"status": "disabled"}

    try:
        info = await db_health()  # should return a dict
        # Normalize output a bit
        if isinstance(info, dict):
            info.setdefault("status", "ok")
            return info
        return {"status": "ok", "detail": str(info)}
    except Exception as e:
        return {"status": "down", "error": str(e)}
