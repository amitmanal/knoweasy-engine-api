from __future__ import annotations

import time
from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ✅ Deterministic engine pipeline (no LLM)
from src.pipeline_v1 import run_pipeline_v1


def map_confidence(decision: str) -> str:
    d = (decision or "").upper().strip()
    if d in {"FULL", "SAFE", "HIGH", "OK"}:
        return "high"
    if d in {"PARTIAL", "MED", "MEDIUM"}:
        return "medium"
    if d in {"REFUSE", "LOW", "UNSAFE"}:
        return "low"
    return "medium"


class SolveRequest(BaseModel):
    question: str
    context: Optional[Dict[str, Any]] = None


app = FastAPI(title="KnowEasy Engine API", version="1.0")

# ✅ CORS: allow Hostinger frontend to call Render API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> Dict[str, Any]:
    return {"ok": True, "service": "KnowEasy Engine API"}


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True}


@app.post("/solve")
def solve(req: SolveRequest) -> Dict[str, Any]:
    # Context is accepted for future expansion; deterministic pipeline may ignore it.
    q = (req.question or "").strip()
    if not q:
        return {
            "answer": "",
            "confidence": "low",
            "explanation": ["Empty question."],
            "flags": ["EMPTY_QUESTION"],
            "latency_ms": 0,
        }

    start = time.time()
    result = run_pipeline_v1(q)
    latency_ms = int((time.time() - start) * 1000)

    # Pipeline shape is stable but we parse defensively.
    final = result.get("final") if isinstance(result, dict) else None
    rendered = final if isinstance(final, dict) else (result.get("rendered") if isinstance(result, dict) else {})
    rendered = rendered if isinstance(rendered, dict) else {}

    decision = rendered.get("decision", "PARTIAL")
    assumptions = rendered.get("assumptions", []) or []
    sections = rendered.get("sections", {}) or {}

    answer = sections.get("final_answer") or sections.get("final") or ""
    exam_tip = sections.get("exam_tip") or ""
    concept = sections.get("concept") or ""

    steps_raw = sections.get("steps", [])
    if isinstance(steps_raw, str):
        steps = [steps_raw] if steps_raw else []
    elif isinstance(steps_raw, list):
        steps = [str(x) for x in steps_raw if x is not None]
    else:
        steps = [str(steps_raw)] if steps_raw else []

    flags: list[str] = []
    # If pipeline surfaced an error, return it clearly.
    err = result.get("error") if isinstance(result, dict) else None
    if err:
        flags.append("ENGINE_ERROR")
        return {
            "answer": "",
            "confidence": "low",
            "explanation": [str(err)],
            "flags": flags,
            "latency_ms": latency_ms,
        }

    explanation: list[str] = []
    if concept:
        explanation.append(str(concept))
    explanation.extend(steps)
    if exam_tip:
        explanation.append(str(exam_tip))
    if assumptions:
        explanation.extend([f"Assumption: {a}" for a in assumptions])

    return {
        "answer": str(answer),
        "confidence": map_confidence(str(decision)),
        "explanation": explanation,
        "flags": flags,
        "latency_ms": latency_ms,
        # Also include raw pipeline for debugging (frontend can ignore)
        "_raw": result,
    }
