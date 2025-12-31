from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import os

# Engine v2 modules
from src.normalizer import normalize_question
from src.micro_rules import try_micro_rules
from src.solver import gemini_solve  # chemistry-only LLM path in your repo

app = FastAPI(title="KnowEasy Engine API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SolveRequest(BaseModel):
    question: str

def _non_chemistry_response(q: str, reason: str):
    return {
        "answer": "This question is currently not supported by the deterministic chemistry kernel.",
        "confidence": 0.0,
        "flags": ["NON_CHEMISTRY", "DEFERRED"],
        "explanation_v1": {
            "title": "Not supported yet",
            "steps": [reason],
            "final": "Ask a Chemistry question (Class 11–12) for full support."
        },
        "decision": "DEFER",
        "meta": {"subject": "non_chemistry", "source": "engine_v2"}
    }

@app.get("/")
def root():
    return {"ok": True, "service": "knoweasy-engine-api", "version": "2.0"}

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/solve")
def solve(req: SolveRequest):
    q = (req.question or "").strip()
    if not q:
        return _non_chemistry_response(q, "Empty question.")

    # 1) Normalize
    normalized = normalize_question(q)
    cleaned = normalized.get("cleaned_text") or normalized.get("cleaned_question") or q

    # 2) Try deterministic chemistry micro-rules first
    rule_out = try_micro_rules(cleaned)
    if rule_out is not None:
        # rule_out is already in final output format in your v2
        return rule_out

    # 3) If no micro-rule matched, ONLY call Gemini if key exists.
    # Otherwise return a clean response (no 500).
    if not os.getenv("GEMINI_API_KEY"):
        return _non_chemistry_response(
            q,
            "No chemistry micro-rule matched and GEMINI_API_KEY is not set on the server, so AI fallback is disabled."
        )

    # 4) Gemini fallback (for chemistry / broader questions)
    try:
        out = gemini_solve(cleaned)
        # Ensure schema safety
        if not isinstance(out, dict):
            return _non_chemistry_response(q, "AI fallback returned invalid format.")
        return out
    except Exception as e:
        # Never crash the API
        return _non_chemistry_response(q, f"AI fallback failed: {type(e).__name__}")
