import time
from typing import Dict, Tuple

from fastapi import APIRouter, Request, Header
from fastapi.responses import JSONResponse

from config import RATE_LIMIT_PER_MINUTE, RATE_LIMIT_BURST, KE_API_KEY
from schemas import SolveRequest, SolveResponse
from orchestrator import solve
from db import db_log_solve

router = APIRouter()

# In-memory rate limit buckets: {ip: (window_start_epoch, count)}
# Phase-1: single-instance friendly. Later we move this to Redis/Cloudflare with same interface.
_BUCKETS: Dict[str, Tuple[float, int]] = {}

_WINDOW_S = 60.0


def _client_ip(req: Request) -> str:
    # If behind a proxy/CDN, X-Forwarded-For may exist.
    xff = req.headers.get("x-forwarded-for")
    if xff:
        # first ip in list
        return xff.split(",")[0].strip()
    if req.client:
        return req.client.host or "unknown"
    return "unknown"


def _rate_limit_ok(ip: str) -> bool:
    now = time.time()
    start, count = _BUCKETS.get(ip, (now, 0))
    if now - start >= _WINDOW_S:
        start, count = now, 0

    # Allow burst on top of base per-minute limit
    limit = RATE_LIMIT_PER_MINUTE + RATE_LIMIT_BURST
    if count >= limit:
        _BUCKETS[ip] = (start, count)
        return False

    _BUCKETS[ip] = (start, count + 1)
    return True


def _safe_failure(message: str, code: str) -> SolveResponse:
    return SolveResponse(
        final_answer=message,
        steps=[],
        assumptions=[],
        confidence=0.2,
        flags=[code],
        safe_note="Try adding chapter/topic or any given options/conditions.",
        meta={"engine": "knoweasy-orchestrator-phase1"},
    )


@router.post("/solve", response_model=SolveResponse)
def solve_route(
    req: SolveRequest,
    request: Request,
    x_ke_key: str | None = Header(default=None, alias="X-KE-KEY"),
):
    # Optional shared key guardrail (not security, but reduces random abuse).
    if KE_API_KEY:
        if not x_ke_key or x_ke_key.strip() != KE_API_KEY:
            return JSONResponse(
                status_code=401,
                content=_safe_failure(
                    "Unauthorized request. Please open the app from the official KnowEasy website.",
                    "UNAUTHORIZED",
                ).model_dump(),
            )

    ip = _client_ip(request)
    if not _rate_limit_ok(ip):
        return JSONResponse(
            status_code=429,
            content=_safe_failure(
                "Too many requests right now. Please try again in a minute 😊",
                "RATE_LIMITED",
            ).model_dump(),
        )

    try:
        t0 = time.perf_counter()
        out = solve(req.model_dump())
        latency_ms = int((time.perf_counter() - t0) * 1000)

        # Best-effort DB log (never breaks the response)
        db_log_solve(req=req, out=out, latency_ms=latency_ms, error=None)

        return SolveResponse(
            final_answer=out.get("final_answer", ""),
            steps=out.get("steps", []),
            assumptions=out.get("assumptions", []),
            confidence=float(out.get("confidence", 0.5)),
            flags=out.get("flags", []),
            safe_note=out.get("safe_note"),
            meta={"engine": "knoweasy-orchestrator-phase1"},
        )

    except Exception as e:
        # Don't leak raw errors to the student UI; keep response stable + CORS-safe.
        db_log_solve(req=req, out=None, latency_ms=None, error=str(e))
        return _safe_failure(
            "Luma had a small hiccup while solving. Please try again in a few seconds 😊",
            "SERVER_ERROR",
        )


# Backward-compatible alias (some older frontends may call /ask)
@router.post("/ask", response_model=SolveResponse)
def ask_route(
    req: SolveRequest,
    request: Request,
    x_ke_key: str | None = Header(default=None, alias="X-KE-KEY"),
):
    return solve_route(req, request, x_ke_key=x_ke_key)
