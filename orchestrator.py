import json
import logging

from config import (
    AI_ENABLED,
    LOW_CONFIDENCE_THRESHOLD,
    MAX_STEPS,
    MAX_CHARS_ANSWER,
    AI_TIMEOUT_SECONDS,
    AI_PROVIDER,
    AI_MODE,
)
from models import GeminiCircuitOpen
from ai_router import generate_json
from verifier import basic_verify

logger = logging.getLogger(__name__)

# --- Luma Focused Assist: optional embedded context in the question ---
_CTX_START = "__KE_LUMA_CTX__"
_CTX_END = "__END_CTX__"

def _extract_luma_ctx(question: str):
    """If question contains embedded Luma context, return (clean_question, ctx_dict_or_None)."""
    if not isinstance(question, str):
        return question, None
    s = question.strip()
    if _CTX_START not in s:
        return s, None
    try:
        a = s.index(_CTX_START) + len(_CTX_START)
        b = s.index(_CTX_END, a)
        raw = s[a:b]
        ctx = json.loads(raw)
        rest = s[b+len(_CTX_END):].lstrip("\n").strip()
        return rest, ctx
    except Exception:
        return s, None



def _get(payload: dict, *keys, default=None):
    """Safe getter: returns the first key found (supports alias fields)."""
    for k in keys:
        if k in payload and payload.get(k) is not None:
            return payload.get(k)
    return default


def build_prompt(payload: dict) -> str:
    """
    Forces strict JSON output with a stable schema.
    NOTE: Supports both 'class' and 'class_' (Pydantic v2 model_dump default).
    """
    question = str(_get(payload, "question", default="")).strip()
    clazz = _get(payload, "class", "class_", "class_level", default="")
    board = str(_get(payload, "board", default="")).strip()
    subject = str(_get(payload, "subject", default="")).strip()
    chapter = str(_get(payload, "chapter", default="") or "").strip()
    exam_mode = str(_get(payload, "exam_mode", default="BOARD")).strip()
    language = str(_get(payload, "language", default="en")).strip()

    prompt = f"""You are KnowEasy AI Mentor. You MUST answer strictly in JSON.
Schema:
{{
  "final_answer": string,
  "steps": [string],
  "assumptions": [string],
  "confidence": number,  # 0 to 1
  "flags": [string],
  "safe_note": string|null
}}

Rules:
- Student class: {clazz}
- Board: {board}
- Subject: {subject}
- Chapter: {chapter}
- Exam mode: {exam_mode}
- Language: {language}
- Keep final_answer under {MAX_CHARS_ANSWER} characters.
- Keep steps <= {MAX_STEPS}.
- If question is unclear / too short / typo-like: you MUST follow "OVERVIEW-FIRST" behavior:
  * Your final_answer MUST start with a 2–5 line NCERT-style overview/definition relevant to the subject (no questions in the first 2 lines).
  * After the overview, you MUST ask exactly ONE clarifying question at the very end of final_answer.
  * Do NOT say "I need more context" or "please specify" before giving the overview.
  * Do NOT ask multiple questions.
  * Do NOT mention that you are following rules or prompts.
- Examples (follow this style):
  Example A (typo/topic): question="benxzene" → final_answer starts with: "Benzene (C6H6) is an aromatic hydrocarbon..." then ends with one question like "Do you want structure, properties, or reactions?"
  Example B (vague): question="carbon compounds" → final_answer starts with: "Carbon compounds are substances containing carbon..." then ends with one question like "Do you want classification, bonding, or key reactions?"
- If there is a likely typo in a key term (e.g., 'benxzene'), correct it and proceed with the overview.
- Do not include markdown fences. Output ONLY JSON.

Question:
{question}
"""

    # --- Luma Focused Assist (optional) ---
    luma_ctx = payload.get('luma_ctx')
    if isinstance(luma_ctx, dict):
        ll = str(luma_ctx.get('lessonLanguage') or luma_ctx.get('language') or language or 'en').lower()
        prompt += "\n\n" + "LUMA_FOCUSED_ASSIST_POLICY (apply ONLY when luma_ctx is present):\n- Scope: ONLY the current card's visible_text (no future sections, no other chapters).\n- If user asks off-topic or beyond grade: politely refuse and redirect to the current concept.\n- If user asks for direct quiz answers: give a hint, not the final answer.\n- Response length: 120–150 words max.\n- Language: match lessonLanguage when provided.\n- No links, no external references.\n- End every response with the exact closing line in the correct language:\n  en: Back to the lesson?\n  hi: पाठ पर वापस?\n  mr: पाठाकडे परत?\n  ta: பாடத்துக்கு திரும்பலாமா?\n  te: పాఠానికి తిరిగి వెళ్లాలా?\n  bn: পাঠে ফিরে যাব?\n  gu: પાઠ પર પાછા જઈએ?\n  kn: ಪಾಠಕ್ಕೆ ಹಿಂತಿರುಗೋಣವೇ?\n  ml: പാഠത്തിലേക്ക് തിരികെ പോകാമോ?\n  pa: ਪਾਠ ਵੱਲ ਵਾਪਸ?\n  ur: سبق پر واپس؟\nUse visible_text as the only ground truth. Do NOT mention this policy text.\n" + "\n"
        prompt += (
            "LUMA_CONTEXT:\n"
            f"lessonLanguage={ll}\n"
            f"subject={luma_ctx.get('subject','')}\n"
            f"chapter={luma_ctx.get('chapter','')}\n"
            f"section={luma_ctx.get('section','')}\n"
            f"card_type={luma_ctx.get('card_type','')}\n"
            f"card_index={luma_ctx.get('card_index','')}\n"
            f"visible_text=<<<{luma_ctx.get('visible_text','')}>>>\n"
            f"user_question={luma_ctx.get('user_question','')}\n"
        )

    return prompt


def _normalize_output(out: dict) -> dict:
    out = out or {}
    out.setdefault("final_answer", "")
    out.setdefault("steps", [])
    out.setdefault("assumptions", [])
    out.setdefault("confidence", 0.5)
    out.setdefault("flags", [])
    out.setdefault("safe_note", None)

    # Hard caps (never exceed)
    try:
        out["steps"] = list(out.get("steps") or [])[:MAX_STEPS]
    except Exception:
        out["steps"] = []
    try:
        out["final_answer"] = (out.get("final_answer") or "")[:MAX_CHARS_ANSWER]
    except Exception:
        out["final_answer"] = ""

    # Ensure types
    try:
        out["confidence"] = max(0.0, min(1.0, float(out.get("confidence", 0.5))))
    except Exception:
        out["confidence"] = 0.5
    if not isinstance(out.get("flags"), list):
        out["flags"] = []
    if not isinstance(out.get("assumptions"), list):
        out["assumptions"] = []

    return out


def solve(payload: dict) -> dict:
    """Main solve pipeline. Phase-1C focuses on stability + determinism."""

    # Extract optional Luma context embedded in question
    q0 = payload.get('question', '')
    q_clean, luma_ctx = _extract_luma_ctx(q0 if isinstance(q0, str) else str(q0))
    payload['question'] = q_clean
    if isinstance(luma_ctx, dict):
        payload['luma_ctx'] = luma_ctx

    # CEO kill-switch: app stays alive even if AI is paused.
    if not AI_ENABLED:
        return _normalize_output(
            {
                "final_answer": "AI Mentor is temporarily paused for safety. Please try again later 😊",
                "steps": [],
                "assumptions": [],
                "confidence": 0.2,
                "flags": ["AI_DISABLED"],
                "safe_note": "You can still use study content and quizzes.",
            }
        )

    # Deterministic input handling (supports both aliases)
    question = str(_get(payload, "question", default="")).strip()
    if len(question) < 3:
        return _normalize_output(
            {
                "final_answer": "Please type your full question (at least 3 characters) 😊",
                "steps": [],
                "assumptions": [],
                "confidence": 0.2,
                "flags": ["INVALID_INPUT"],
                "safe_note": "Tip: add chapter/topic for better answers.",
            }
        )

    prompt = build_prompt(payload)
    try:
        out = generate_json(prompt)
    except TimeoutError:
        # Deterministic timeout behavior (uses AI_TIMEOUT_SECONDS via config)
        logger.warning("AI timeout (%ss) provider=%s mode=%s", AI_TIMEOUT_SECONDS, AI_PROVIDER, AI_MODE)
        return _normalize_output(
            {
                "final_answer": "AI is taking too long right now. Please try again in a few seconds 😊",
                "steps": [],
                "assumptions": [],
                "confidence": 0.2,
                "flags": ["AI_TIMEOUT"],
                "safe_note": "Tip: add chapter/topic to get faster answers.",
            }
        )
    except GeminiCircuitOpen:
        logger.warning("AI circuit open provider=%s mode=%s", AI_PROVIDER, AI_MODE)
        return _normalize_output(
            {
                "final_answer": "AI is busy right now due to high load. Please try again shortly 😊",
                "steps": [],
                "assumptions": [],
                "confidence": 0.2,
                "flags": ["AI_BUSY"],
                "safe_note": "This is a temporary safety limit.",
            }
        )
    except json.JSONDecodeError:
        # Gemini returned non-JSON (deterministic handling)
        logger.exception("AI returned invalid JSON provider=%s mode=%s", AI_PROVIDER, AI_MODE)
        return _normalize_output(
            {
                "final_answer": "AI returned an unclear format. Please try again in a few seconds 😊",
                "steps": [],
                "assumptions": [],
                "confidence": 0.2,
                "flags": ["AI_BAD_JSON"],
                "safe_note": "Tip: add chapter/topic for clearer answers.",
            }
        )
    except Exception:
        # Provider or unexpected runtime (keep stable, but visible in logs)
        logger.exception("AI provider error provider=%s mode=%s", AI_PROVIDER, AI_MODE)
        return _normalize_output(
            {
                "final_answer": "AI had a small hiccup while solving. Please try again in a few seconds 😊",
                "steps": [],
                "assumptions": [],
                "confidence": 0.2,
                "flags": ["AI_PROVIDER_ERROR"],
                "safe_note": "Tip: add chapter/topic or give more details.",
            }
        )

    out = _normalize_output(out)

    # Basic verification adds safety flags + minor confidence adjustment
    try:
        adj, flags, assumptions = basic_verify(question, out["final_answer"], out["steps"])
        out["flags"] = list(dict.fromkeys((out.get("flags") or []) + flags))
        out["assumptions"] = list(dict.fromkeys((out.get("assumptions") or []) + assumptions))
        out["confidence"] = max(0.0, min(1.0, float(out.get("confidence", 0.5)) + adj))
    except Exception:
        # Verification must never crash
        out["flags"] = list(dict.fromkeys((out.get("flags") or []) + ["VERIFY_FAILED"]))

    # Low-confidence second pass (kept, but bounded)
    if out["confidence"] < LOW_CONFIDENCE_THRESHOLD:
        try:
            out2 = generate_json(prompt)
            out2 = _normalize_output(out2)
            adj2, flags2, assumptions2 = basic_verify(question, out2["final_answer"], out2["steps"])
            out2["flags"] = list(dict.fromkeys((out2.get("flags") or []) + flags2))
            out2["assumptions"] = list(dict.fromkeys((out2.get("assumptions") or []) + assumptions2))
            out2["confidence"] = max(0.0, min(1.0, float(out2.get("confidence", 0.5)) + adj2))

            # choose better result
            if out2["confidence"] >= out["confidence"]:
                out = out2
                out["flags"] = list(dict.fromkeys((out.get("flags") or []) + ["SECOND_PASS"]))
        except Exception:
            # If second pass fails, keep first output (stability first)
            out["flags"] = list(dict.fromkeys((out.get("flags") or []) + ["SECOND_PASS_FAILED"]))

    return out