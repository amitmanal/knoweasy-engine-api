from fastapi import APIRouter
from schemas import SolveRequest, SolveResponse
from orchestrator import solve

router = APIRouter()

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
def solve_route(req: SolveRequest):
    try:
        payload = req.model_dump(by_alias=True)
        out = solve(payload)

        # Hard safety: if model gave empty answer, return safe response
        if not str(out.get("final_answer") or "").strip():
            return _safe_failure(
                "I’m not confident enough to answer this correctly. Please rephrase or add missing conditions/details.",
                "EMPTY_MODEL_OUTPUT",
            )

        return SolveResponse(
            final_answer=str(out.get("final_answer", "")).strip(),
            steps=[str(s).strip() for s in (out.get("steps") or []) if str(s).strip()][:8],
            assumptions=[str(a).strip() for a in (out.get("assumptions") or []) if str(a).strip()][:8],
            confidence=max(0.0, min(1.0, float(out.get("confidence", 0.5)))),
            flags=[str(f).strip() for f in (out.get("flags") or []) if str(f).strip()][:12],
            safe_note=out.get("safe_note"),
            meta={"engine": "knoweasy-orchestrator-phase1"},
        )

    except Exception:
        # Don't leak raw errors to the student UI; keep response stable + CORS-safe.
        return _safe_failure(
            "Luma had a small hiccup while solving. Please try again in a few seconds 😊",
            "SERVER_ERROR",
        )

# Backward-compatible alias (some older frontends may call /ask)
@router.post("/ask", response_model=SolveResponse)
def ask_route(req: SolveRequest):
    return solve_route(req)
