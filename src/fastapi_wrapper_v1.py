"""
fastapi_wrapper_v1.py

FastAPI wrapper for KnowEasy Engine v1
WITH CORS ENABLED (LOCKED)
"""

from __future__ import annotations
import os
import time
import uuid
from typing import Any, Callable, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


ENGINE_VERSION = "fastapi_wrapper_v1"
DEFAULT_IMPORT_PATH_ENV = "KNOWEASY_ENGINE_ENTRYPOINT"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _load_solver() -> Callable:
    import_path = os.environ.get(DEFAULT_IMPORT_PATH_ENV)
    if not import_path or ":" not in import_path:
        raise RuntimeError("KNOWEASY_ENGINE_ENTRYPOINT not set correctly")

    module_path, fn_name = import_path.split(":")
    mod = __import__(module_path, fromlist=[fn_name])
    fn = getattr(mod, fn_name)
    return fn


class SolveRequest(BaseModel):
    question: str
    context: Dict[str, Any] = {}
    options: Dict[str, Any] = {}


class SolveResponse(BaseModel):
    request_id: str
    ok: bool
    engine: str
    elapsed_ms: int
    result: Dict[str, Any] = {}
    error: Optional[Dict[str, Any]] = None


class BatchSolveRequest(BaseModel):
    items: list[SolveRequest]


class BatchSolveResponse(BaseModel):
    request_id: str
    ok: bool
    engine: str
    elapsed_ms: int
    results: list[Dict[str, Any]]
    errors: Optional[list[Dict[str, Any]]] = None


def create_app(solver_callable: Optional[Callable] = None) -> FastAPI:
    app = FastAPI(title="KnowEasy Engine API", version=ENGINE_VERSION)

    # ✅ ADD CORS (THIS IS THE IMPORTANT PART)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # later we can restrict to your domain
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if solver_callable is None:
        try:
            solver_callable = _load_solver()
        except Exception:
            # Fallback: use the v1 engine's adapter solve function when the
            # environment variable is not set.  This allows tests to call
            # create_app() without configuring KNOWEASY_ENGINE_ENTRYPOINT.
            from src.engine_entrypoint_adapter_v1 import solve as default_solve
            solver_callable = default_solve

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request.state.request_id = str(uuid.uuid4())
        start = _now_ms()
        response = await call_next(request)
        response.headers["x-request-id"] = request.state.request_id
        response.headers["x-elapsed-ms"] = str(_now_ms() - start)
        return response

    @app.get("/health")
    async def health():
        return {"ok": True, "engine": ENGINE_VERSION, "ts_ms": _now_ms()}

    @app.post("/solve", response_model=SolveResponse)
    async def solve(req: SolveRequest, request: Request):
        try:
            start = _now_ms()
            result = solver_callable(req.question, req.context, req.options)
            return SolveResponse(
                request_id=request.state.request_id,
                ok=True,
                engine=ENGINE_VERSION,
                elapsed_ms=_now_ms() - start,
                result=result,
                error=None,
            )
        except Exception as e:
            return SolveResponse(
                request_id=request.state.request_id,
                ok=False,
                engine=ENGINE_VERSION,
                elapsed_ms=0,
                result={},
                error={"type": "solver_error", "detail": str(e)},
            )

    @app.post("/batch_solve", response_model=BatchSolveResponse)
    async def batch_solve(req: BatchSolveRequest, request: Request):
        results, errors = [], []
        for i, item in enumerate(req.items):
            try:
                results.append(solver_callable(item.question, item.context, item.options))
                errors.append({})
            except Exception as e:
                results.append({})
                errors.append({"index": i, "detail": str(e)})

        ok = all(not e for e in errors)
        return BatchSolveResponse(
            request_id=request.state.request_id,
            ok=ok,
            engine=ENGINE_VERSION,
            elapsed_ms=0,
            results=results,
            errors=None if ok else errors,
        )

    return app
