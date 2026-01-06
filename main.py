from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import CORS_ALLOW_ORIGINS
from router import router

app = FastAPI(title="KnowEasy Engine API", version="phase1-clean")

# CORS
if CORS_ALLOW_ORIGINS == "*" or not CORS_ALLOW_ORIGINS:
    allow_origins = ["*"]
else:
    allow_origins = [o.strip() for o in CORS_ALLOW_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
