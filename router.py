from __future__ import annotations

from fastapi import APIRouter

from schemas import SolveRequest, SolveResponse
from orchestrator import solve

router = APIRouter()


@router.get("/")
def root():
    return {
        "ok": True,
        "service": "knoweasy-orchestrator-phase1",
        "health": "/health",
        "docs": "/docs",
        "solve": "/solve",
    }


@router.get("/health")
def health():
    return {"ok": True, "service": "knoweasy-orchestrator-phase1"}


@router.post("/solve", response_model=SolveResponse)
def solve_api(req: SolveRequest):
    return solve(req)
