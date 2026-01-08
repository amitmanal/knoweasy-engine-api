# router.py — Phase-1 LOCKED (safe routing)

from fastapi import APIRouter, HTTPException
from schemas import SolveRequest, SolveResponse
from orchestrator import orchestrate
from ai_router import run_ai

router = APIRouter()


@router.post("/solve", response_model=SolveResponse)
async def solve(req: SolveRequest):
    try:
        data = orchestrate(req.question)
        answer = await run_ai(data["prompt"])
        return {
            "answer": answer,
            "confidence": data.get("confidence", 0.7)
        }
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="High traffic or temporary AI issue. Please try again."
        )