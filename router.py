from fastapi import APIRouter, HTTPException
from schemas import SolveRequest, SolveResponse
from orchestrator import solve

router = APIRouter()

@router.post("/solve", response_model=SolveResponse)
def solve_route(req: SolveRequest):
    try:
        payload = req.model_dump(by_alias=True)
        out = solve(payload)

        # Hard safety: if model gave empty answer, return safe response
        if not out.get("final_answer"):
            return SolveResponse(
                final_answer="I’m not confident enough to answer this correctly. Please rephrase or add missing conditions/details.",
                steps=[],
                assumptions=[],
                confidence=0.2,
                flags=["EMPTY_MODEL_OUTPUT"],
                safe_note="Try adding chapter/topic or any given options/conditions.",
                meta={}
            )

        return SolveResponse(
            final_answer=str(out.get("final_answer", "")).strip(),
            steps=[str(s).strip() for s in (out.get("steps") or [])][:8],
            assumptions=[str(a).strip() for a in (out.get("assumptions") or [])][:8],
            confidence=float(out.get("confidence", 0.5)),
            flags=[str(f).strip() for f in (out.get("flags") or [])][:12],
            safe_note=out.get("safe_note"),
            meta={"engine": "knoweasy-orchestrator-phase1"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Solve failed: {type(e).__name__}: {e}")
