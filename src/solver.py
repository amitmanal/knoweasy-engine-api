import json
import re
from src.gemini_client import gemini_generate, SOLVER_MODEL


def _extract_json_object(text: str) -> str | None:
    """
    Tries to extract the first JSON object from a messy model output.
    This handles cases like:
      - ```json { ... } ```
      - extra commentary before/after JSON
    """
    if not text:
        return None

    # Remove code fences if present
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)

    # Find first {...} block (non-greedy, but robust enough for our size)
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return None
    return m.group(0)


def gemini_solve(question: str) -> dict:
    prompt = f"""
You are KnowEasy Chemistry Solver (Class 11-12, JEE/NEET).
STRICT RULES:
- Output ONLY valid JSON. No markdown. No extra text.
- If the question lacks conditions that can flip the answer, set decision="PARTIAL" and ask for ONE missing condition.
- Never guess. If unsure, use decision="BLOCKED".
Return JSON with keys:
decision (FULL|PARTIAL|BLOCKED),
answer (string),
steps (array of strings, exam-relevant),
exam_tip (string),
assumptions (array),
missing_info (array),
confidence (number 0..1)

QUESTION: {question}
""".strip()

    raw = gemini_generate(SOLVER_MODEL, prompt).strip()

    json_text = _extract_json_object(raw)
    if not json_text:
        return {
            "decision": "PARTIAL",
            "answer": "I need one more detail to answer safely (conditions/medium/temperature).",
            "steps": ["Your question could not be parsed into a safe structured response."],
            "exam_tip": "Add missing conditions like medium/temperature/catalyst.",
            "assumptions": [],
            "missing_info": ["conditions"],
            "confidence": 0.40
        }

    try:
        obj = json.loads(json_text)

        # Normalize defaults
        decision = str(obj.get("decision", "PARTIAL")).upper().strip()
        if decision not in ("FULL", "PARTIAL", "BLOCKED"):
            decision = "PARTIAL"

        answer = str(obj.get("answer", "")).strip()
        steps = obj.get("steps", [])
        if not isinstance(steps, list):
            steps = [str(steps)]

        exam_tip = str(obj.get("exam_tip", "")).strip()
        assumptions = obj.get("assumptions", [])
        if not isinstance(assumptions, list):
            assumptions = [str(assumptions)]

        missing_info = obj.get("missing_info", [])
        if not isinstance(missing_info, list):
            missing_info = [str(missing_info)]

        confidence = obj.get("confidence", 0.6)
        try:
            confidence = float(confidence)
        except Exception:
            confidence = 0.6
        confidence = max(0.0, min(1.0, confidence))

        # If FULL but empty answer, downgrade safely
        if decision == "FULL" and not answer:
            decision = "PARTIAL"
            missing_info = missing_info or ["clarify question / missing condition"]
            confidence = min(confidence, 0.45)

        return {
            "decision": decision,
            "answer": answer,
            "steps": steps,
            "exam_tip": exam_tip,
            "assumptions": assumptions,
            "missing_info": missing_info,
            "confidence": confidence
        }

    except Exception:
        return {
            "decision": "PARTIAL",
            "answer": "I need one more detail to answer safely (conditions/medium/temperature).",
            "steps": ["The solver output could not be parsed safely."],
            "exam_tip": "Add missing conditions like medium/temperature/catalyst.",
            "assumptions": [],
            "missing_info": ["conditions"],
            "confidence": 0.40
        }
