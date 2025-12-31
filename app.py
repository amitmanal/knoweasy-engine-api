# app.py
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any, Dict, Optional
import traceback

from src.subject_gate import detect_subject
from src.solver import solve_question

APP_VERSION = "v2.0.1"

app = FastAPI(title="KnowEasy Engine API", version=APP_VERSION)


class SolveRequest(BaseModel):
    question: str
    meta: Optional[Dict[str, Any]] = None


def _non_chemistry_response(q: str, reason: str) -> Dict[str, Any]:
    return {
        "answer": "This engine currently supports Chemistry only. Question deferred.",
        "confidence": 0.0,
        "flags": ["NON_CHEMISTRY", "DEFERRED"],
        "explanation_v1": {
            "title": "Not supported yet",
            "steps": [
                "Detected non-chemistry question.",
                "Chemistry engine is frozen and runs only for Chemistry.",
            ],
            "final": reason,
        },
        "decision": "DEFER",
        "meta": {
            "subject": "non-chemistry",
            "source": "engine_v2",
            "verified_chemistry": False,
        },
    }


@app.get("/")
def root():
    return {"ok": True, "service": "knoweasy-engine-api", "version": APP_VERSION}


@app.get("/health")
def health():
    return {"ok": True, "status": "healthy", "version": APP_VERSION}


@app.post("/solve")
def solve(req: SolveRequest) -> Dict[str, Any]:
    q = (req.question or "").strip()
    if not q:
        return {
            "answer": "Empty question.",
            "confidence": 0.0,
            "flags": ["EMPTY_QUESTION"],
            "explanation_v1": {"title": "Error", "steps": [], "final": "Provide a question."},
            "decision": "ERROR",
            "meta": {"subject": "unknown", "source": "engine_v2", "verified_chemistry": False},
        }

    try:
        subject = detect_subject(q)  # expects 'chemistry' or other
        if subject != "chemistry":
            return _non_chemistry_response(q, "Only Chemistry is enabled in Engine v2 right now.")

        # Chemistry path
        result = solve_question(q)
        # Ensure minimal keys exist
        if "meta" not in result:
            result["meta"] = {}
        result["meta"].setdefault("subject", "chemistry")
        result["meta"].setdefault("source", "engine_v2")

        return result

    except Exception:
        # Never crash the API; return a safe payload
        return {
            "answer": "Engine error while processing question.",
            "confidence": 0.0,
            "flags": ["INTERNAL_ERROR"],
            "explanation_v1": {
                "title": "Internal error",
                "steps": [],
                "final": "Traceback captured on server logs.",
            },
            "decision": "ERROR",
            "meta": {
                "subject": "unknown",
                "source": "engine_v2",
                "verified_chemistry": False,
                "trace": traceback.format_exc().splitlines()[-8:],  # short tail
            },
        }
