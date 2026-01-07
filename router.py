# router.py
import json
import time
from typing import Dict, Tuple

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from config import KE_API_KEY, RATE_LIMIT_BURST, RATE_LIMIT_PER_MINUTE
from db import db_log_solve
from orchestrator import solve
from schemas import SolveRequest, SolveResponse

router = APIRouter()

# In-memory rate limit buckets: {ip: (window_start_epoch, count)}
# Phase-1: single-instance friendly. Later we move this to Redis/Cloudflare with same interface.
_BUCKETS: Dict[str, Tuple[float, int]] = {}
_WINDOW_S = 60.0


def _req_id(request: Request) -> str:
    rid = getattr(request.state, "req_id", None)
    return rid or "unknown"


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


def _safe_failure(message: str, code: str, rid: str) -> SolveResponse:
    return SolveResponse(
        final_answer=message,
        steps=[],
        assumptions=[],
        confidence=0.2,
        flags=[code],
        safe_note="Try adding chapter/topic or any given options/conditions.",
        meta={"engine": "knoweasy-orchestrator-phase1", "req_id": rid, "outcome": "error"},
    )


def _classify_outcome(flags: list) -> str:
    # Keep very defensive + minimal; we only log it.
    s = set(str(f) for f in (flags or []))
    if "AI_TIMEOUT" in s or "TIMEOUT" in s:
        return "ai_timeout"
    if "AI_ERROR" in s:
        return "ai_error"
    if "UNAUTHORIZED" in s:
        return "unauthorized"
    if "RATE_LIMITED" in s:
        return "rate_limited"
    if "BAD_INPUT" in s or "VALIDATION_ERROR" in s:
        return "bad_input"
    return "ok"


@router.post("/solve", response_model=SolveResponse)
def solve_route(
    req: SolveRequest,
    request: Request,
    x_ke_key: str | None = Header(default=None, alias="X-KE-KEY"),
):
    rid = _req_id(request)

    # Optional shared key guardrail (not security, but reduces random abuse).
    if KE_API_KEY:
        if not x_ke_key or x_ke_key.strip() != KE_API_KEY:
            payload = _safe_failure(
                "Unauthorized request. Please open the app from the official KnowEasy website.",
                "UNAUTHORIZED",
                rid,
            )

            # Log (structured, single-line)
            print(
                json.dumps(
                    {
                        "event": "solve",
                        "req_id": rid,
                        "outcome": "unauthorized",
                        "ip": _client_ip(request),
                        "board": getattr(req, "board", None),
                        "class_level": getattr(req, "class_level", None),
                        "subject": getattr(req, "subject", None),
                        "input_len": len((req.question or "").strip()) if getattr(req, "question", None) else 0,
                        "latency_ms": 0,
                    },
                    ensure_ascii=False,
                )
            )

            return JSONResponse(status_code=401, content=payload.model_dump())

    ip = _client_ip(request)
    if not _rate_limit_ok(ip):
        payload = _safe_failure(
            "Too many requests right now. Please try again in a minute 😊",
            "RATE_LIMITED",
            rid,
        )

        print(
            json.dumps(
                {
                    "event": "solve",
                    "req_id": rid,
                    "outcome": "rate_limited",
                    "ip": ip,
                    "board": getattr(req, "board", None),
                    "class_level": getattr(req, "class_level", None),
                    "subject": getattr(req, "subject", None),
                    "input_len": len((req.question or "").strip()) if getattr(req, "question", None) else 0,
                    "latency_ms": 0,
                },
                ensure_ascii=False,
            )
        )

        return JSONResponse(status_code=429, content=payload.model_dump())

    t0 = time.perf_counter()
    try:
        out = solve(req.model_dump())
        latency_ms = int((time.perf_counter() - t0) * 1000)

        flags = out.get("flags", []) if isinstance(out, dict) else []
        outcome = _classify_outcome(flags)

        # Best-effort DB log (never breaks the response)
        db_log_solve(req=req, out=out, latency_ms=latency_ms, error=None)

        # Structured log line (Render-friendly)
        print(
            json.dumps(
                {
                    "event": "solve",
                    "req_id": rid,
                    "outcome": outcome,
                    "ip": ip,
                    "board": getattr(req, "board", None),
                    "class_level": getattr(req, "class_level", None),
                    "subject": getattr(req, "subject", None),
                    "input_len": len((req.question or "").strip()) if getattr(req, "question", None) else 0,
                    "latency_ms": latency_ms,
                    "flags": flags,
                },
                ensure_ascii=False,
            )
        )

        return SolveResponse(
            final_answer=out.get("final_answer", ""),
            steps=out.get("steps", []),
            assumptions=out.get("assumptions", []),
            confidence=float(out.get("confidence", 0.5)),
            flags=flags,
            safe_note=out.get("safe_note"),
            meta={
                "engine": "knoweasy-orchestrator-phase1",
                "req_id": rid,
                "latency_ms": latency_ms,
                "outcome": outcome,
            },
        )

    except Exception as e:
        latency_ms = int((time.perf_counter() - t0) * 1000)

        # Don't leak raw errors to the student UI; keep response stable + CORS-safe.
        db_log_solve(req=req, out=None, latency_ms=latency_ms, error=str(e))

        # Structured log line
        print(
            json.dumps(
                {
                    "event": "solve",
                    "req_id": rid,
                    "outcome": "server_error",
                    "ip": ip,
                    "board": getattr(req, "board", None),
                    "class_level": getattr(req, "class_level", None),
                    "subject": getattr(req, "subject", None),
                    "input_len": len((req.question or "").strip()) if getattr(req, "question", None) else 0,
                    "latency_ms": latency_ms,
                    "error_type": type(e).__name__,
                },
                ensure_ascii=False,
            )
        )

        return _safe_failure(
            "Luma had a small hiccup while solving. Please try again in a few seconds 😊",
            "SERVER_ERROR",
            rid,
        )


# Backward-compatible alias (some older frontends may call /ask)
@router.post("/ask", response_model=SolveResponse)
def ask_route(
    req: SolveRequest,
    request: Request,
    x_ke_key: str | None = Header(default=None, alias="X-KE-KEY"),
):
    return solve_route(req, request, x_ke_key=x_ke_key)
