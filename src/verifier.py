import json
from src.gemini_client import gemini_generate, VERIFIER_MODEL

def gemini_verify(question: str, solved: dict) -> dict:
    proposed = solved.get("answer", "")
    steps = solved.get("steps", [])

    prompt = f"""
You are KnowEasy Verifier for exam-safety.
Task: judge if the proposed answer is chemically correct and safe to write in JEE/NEET given the question.

STRICT RULES:
- Output ONLY valid JSON. No markdown.
Return JSON keys:
verdict: "AGREE" | "DISAGREE" | "NEED_INFO"
reason: short string
need: (if NEED_INFO) one missing condition question
tip: (optional) exam tip

QUESTION: {question}

PROPOSED ANSWER: {proposed}
PROPOSED STEPS: {steps}
"""
    text = gemini_generate(VERIFIER_MODEL, prompt).strip()
    try:
        obj = json.loads(text)
        obj.setdefault("verdict", "DISAGREE")
        obj.setdefault("reason", "")
        return obj
    except Exception:
        return {"verdict": "DISAGREE", "reason": "Verifier output parse failed."}
