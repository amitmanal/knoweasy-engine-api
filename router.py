from fastapi import APIRouter, Request, HTTPException
from schemas import SolveRequest, SolveResponse
from orchestrator import solve
from guards import enforce_body_limit, rate_limit

router = APIRouter()

@router.get("/health")
def health():
    return {"ok": True, "service": "knoweasy-orchestrator-phase1"}

@router.post("/solve", response_model=SolveResponse)
async def solve_api(req: SolveRequest, request: Request):
    try:
        enforce_body_limit(req.question)
        # Simple rate limit by IP (later: Redis)
        ip = request.client.host if request.client else "unknown"
        rate_limit(ip)
        return await solve(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {e}")
