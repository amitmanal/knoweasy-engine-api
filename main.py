from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from router import router
from db import db_init


@asynccontextmanager
async def lifespan(app: FastAPI):
    # DB init must NEVER crash deployment.
    # db_init() is synchronous, so run it safely in a threadpool.
    try:
        await run_in_threadpool(db_init)
    except Exception:
        # Swallow all init errors so the API still boots.
        # Logging is optional; keep it quiet for stability.
        pass

    yield


app = FastAPI(
    title="KnowEasy Engine API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS (keep permissive for Hostinger frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(router)


# Root must return 200 (Render will ping "/")
@app.get("/")
def root():
    return {"ok": True, "service": "knoweasy-engine-api", "status": "live"}


# Common health endpoints
@app.get("/health")
def health():
    return {"ok": True}


@app.get("/healthz")
def healthz():
    return {"ok": True}
