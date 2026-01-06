import json
from config import LOW_CONFIDENCE_THRESHOLD, MAX_STEPS, MAX_CHARS_ANSWER
from models import GeminiClient
from verifier import basic_verify

def build_prompt(payload: dict) -> str:
    """
    Forces strict JSON output with a stable schema.
    """
    question = payload["question"]
    clazz = payload["class"]
    board = payload["board"]
    subject = payload["subject"]
    chapter = payload.get("chapter") or ""
    exam_mode = payload.get("exam_mode", "BOARD")
    language = payload.get("language", "en")
    answer_mode = payload.get("answer_mode", "step_by_step")

    # Output schema demanded from model
    schema = {
        "final_answer": "string",
        "steps": ["string"],
        "assumptions": ["string"],
        "confidence": "number 0..1",
        "flags": ["string"],
        "safe_note": "string|null"
    }

    return f"""
You are KnowEasy AI, a syllabus-aligned tutor for India.
You MUST output ONLY valid JSON (no markdown, no backticks, no extra text).

Context:
- Class: {clazz}
- Board: {board}
- Subject: {subject}
- Chapter: {chapter}
- Exam mode overlay: {exam_mode}
- Language: {language}
- Answer mode: {answer_mode}

Rules:
1) If question is ambiguous or missing conditions, do NOT guess confidently.
   Add a flag and put the assumption clearly.
2) For CBSE/BOARD: keep the explanation simple, correct, and exam-appropriate.
3) Keep steps concise (max {MAX_STEPS} bullets).
4) final_answer must be short and direct (max {MAX_CHARS_ANSWER} chars).
5) Provide confidence from 0 to 1.

Return JSON in this schema:
{json.dumps(schema)}

Question:
{question}
""".strip()

def solve(payload: dict) -> dict:
    client = GeminiClient()

    prompt = build_prompt(payload)
    out = client.generate_json(prompt)

    # Normalize missing keys defensively
    out.setdefault("final_answer", "")
    out.setdefault("steps", [])
    out.setdefault("assumptions", [])
    out.setdefault("confidence", 0.5)
    out.setdefault("flags", [])
    out.setdefault("safe_note", None)

    # Basic verification adjustments
    adj, flags2, assumptions2 = basic_verify(payload["question"], out["final_answer"], out["steps"])
    out["flags"] = list(dict.fromkeys(out["flags"] + flags2))
    out["assumptions"] = list(dict.fromkeys(out["assumptions"] + assumptions2))
    out["confidence"] = max(0.0, min(1.0, float(out["confidence"]) + adj))

    # Second pass if low confidence
    if out["confidence"] < LOW_CONFIDENCE_THRESHOLD:
        repair_prompt = build_prompt(payload) + "\n\nYou gave a low-confidence answer earlier. Re-check carefully and improve correctness. Output ONLY JSON."
        out2 = client.generate_json(repair_prompt)
        # choose better of the two by confidence (still bounded)
        try:
            c2 = float(out2.get("confidence", 0.0))
        except Exception:
            c2 = 0.0

        if c2 > out["confidence"]:
            out = out2
            out.setdefault("final_answer", "")
            out.setdefault("steps", [])
            out.setdefault("assumptions", [])
            out.setdefault("confidence", 0.5)
            out.setdefault("flags", [])
            out.setdefault("safe_note", None)

            adj, flags2, assumptions2 = basic_verify(payload["question"], out["final_answer"], out["steps"])
            out["flags"] = list(dict.fromkeys(out["flags"] + flags2))
            out["assumptions"] = list(dict.fromkeys(out["assumptions"] + assumptions2))
            out["confidence"] = max(0.0, min(1.0, float(out["confidence"]) + adj))

    return out
