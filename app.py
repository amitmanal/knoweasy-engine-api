# KE_PATCH: 2025-12-31 v2.1.1
# Purpose: Add Pydantic request model so Swagger shows a JSON body editor for /solve.
# NOTE: Hybrid routing behavior is unchanged.

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from src.normalizer import normalize_question
from src.guard import guard_question
from src.micro_rules import try_micro_rule
from src.solver import gemini_solve
from src.verifier import gemini_verify
from src.formatter import format_for_frontend
from src.subject_gate import detect_subject

app = FastAPI(title="KnowEasy Engine v2", version="2.1.1")


class SolveRequest(BaseModel):
    question: str
    subject: Optional[str] = None


@app.get("/")
def health():
    return {"ok": True, "service": "knoweasy-engine-v2", "version": "2.1.1"}


@app.post("/solve")
async def solve(req: SolveRequest):
    raw_q = (req.question or "").strip()
    if not raw_q:
        raise HTTPException(status_code=400, detail="Missing 'question'")

    q = normalize_question(raw_q)

    # ------------------------------------------------------------
    # STEP 1: Subject gate (lightweight)
    # Optional override from caller:
    # subject can be: "chemistry" | "physics" | "math" | "bio" | ...
    # ------------------------------------------------------------
    subject_hint = (req.subject or "").strip().lower()
    is_chem = subject_hint == "chemistry" or (not subject_hint and detect_subject(q) == "chemistry")

    # ------------------------------------------------------------
    # NON-CHEMISTRY FLOW (Gemini directly; chemistry kernel skipped)
    # ------------------------------------------------------------
    if not is_chem:
        solved = gemini_solve(q)

        decision = solved.get("decision", "PARTIAL")
        answer = solved.get("answer", "Need more information")
        steps = solved.get("steps", [])
        exam_tip = solved.get("exam_tip", "")

        # Conservative confidence cap for non-chemistry until subject kernels exist
        base_conf = float(solved.get("confidence", 0.45) or 0.45)
        confidence = min(0.60, max(0.30, base_conf))

        flags = ["NON_CHEMISTRY", "GEMINI_ONLY", "UNVERIFIED"]

        return format_for_frontend(
            decision=decision,
            answer=answer,
            steps=steps,
            exam_tip=exam_tip,
            confidence=confidence,
            flags=flags,
            subject=subject_hint or "non_chemistry",
            source="gemini",
            verified_chemistry=False,
        )

    # ------------------------------------------------------------
    # CHEMISTRY FLOW (Engine v2 safety kernel FIRST, then Gemini fallback)
    # ------------------------------------------------------------

    # 0) Micro rules (ultra-safe exam rules) BEFORE any LLM
    micro = try_micro_rule(q)
    if micro:
        return format_for_frontend(
            decision=micro["decision"],
            answer=micro["answer"],
            steps=micro.get("steps", []),
            exam_tip=micro.get("exam_tip", ""),
            confidence=micro.get("confidence", 0.95),
            flags=micro.get("flags", ["MICRO_RULE"]) + ["VERIFIED_CHEMISTRY"],
            subject="chemistry",
            source="engine_v2",
            verified_chemistry=True,
        )

    # 1) Guardrail check (NEVER guess)
    guard = guard_question(q)
    if guard.get("decision") != "FULL":
        return format_for_frontend(
            decision=guard.get("decision", "PARTIAL"),
            answer=guard.get("answer", "Need more information"),
            steps=guard.get("steps", []),
            exam_tip=guard.get("exam_tip", ""),
            confidence=guard.get("confidence", 0.35),
            flags=guard.get("flags", ["NEEDS_INFO"]) + ["CHEMISTRY_GUARD"],
            subject="chemistry",
            source="engine_v2",
            verified_chemistry=True,
        )

    # 2) Solve (Gemini) – chemistry fallback only
    solved = gemini_solve(q)

    # If solver is not FULL, return safely (no verification)
    if solved.get("decision") != "FULL":
        return format_for_frontend(
            decision=solved.get("decision", "PARTIAL"),
            answer=solved.get("answer", "Need more information"),
            steps=solved.get("steps", []),
            exam_tip=solved.get("exam_tip", ""),
            confidence=float(solved.get("confidence", 0.40)),
            flags=["CHEMISTRY_FALLBACK", "GEMINI_SOLVED", "SAFE_NOT_FULL"],
            subject="chemistry",
            source="gemini",
            verified_chemistry=False,
        )

    # 3) Verify (Gemini verifier)
    verdict = gemini_verify(q, solved)

    # 4) Final decision logic
    if verdict.get("verdict") == "AGREE":
        decision = "FULL"
        confidence = min(0.98, max(0.85, float(solved.get("confidence", 0.85) or 0.85)))
        flags = ["CHEMISTRY_FALLBACK", "GEMINI_SOLVED", "VERIFIED"]
        exam_tip = solved.get("exam_tip", "")
        steps = solved.get("steps", [])
        answer = solved.get("answer", "")
    elif verdict.get("verdict") == "NEED_INFO":
        decision = "PARTIAL"
        confidence = 0.45
        flags = ["NEEDS_INFO", "VERIFIER_REQUEST"]
        answer = verdict.get("need", "Need one more condition to answer safely.")
        steps = [
            "Your question is missing a critical condition.",
            "Provide the missing condition and I will give an exam-safe final answer.",
        ]
        exam_tip = verdict.get("tip", "Specify missing condition (e.g., medium/temperature/catalyst).")
    else:
        decision = "PARTIAL"
        confidence = 0.40
        flags = ["VERIFIER_DISAGREE", "SAFE_MODE"]
        answer = "I cannot answer safely from the given info without risking a wrong answer."
        steps = [
            "Two independent checks did not agree on a single safe answer.",
            "Please add missing conditions (medium, temperature, catalyst, oxidant/reductant).",
        ]
        exam_tip = "In exams, conditions decide the product. Add conditions to proceed."

    return format_for_frontend(
        decision=decision,
        answer=answer,
        steps=steps,
        exam_tip=exam_tip,
        confidence=confidence,
        flags=flags,
        subject="chemistry",
        source="gemini",
        verified_chemistry=("VERIFIED" in flags) or ("VERIFIED_CHEMISTRY" in flags),
    )
