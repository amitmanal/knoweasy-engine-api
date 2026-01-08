# orchestrator.py — Phase-1 LOCKED (overview-first, exam-safe)

from typing import Dict
import re

OVERVIEW_PROMPT = """
You are an exam-safe chemistry tutor for Indian Class 11–12.

RULES (STRICT):
1. If the question is vague, incomplete, or a typo:
   - FIRST give a short NCERT-level overview (2–5 lines).
   - THEN ask exactly ONE clarifying question.
   - DO NOT ask multiple questions.
2. If the question is clear, answer directly with steps.
3. Do NOT refuse to answer simple topic names (e.g. "benzene").
4. Tone must be calm, academic, and student-friendly.
"""


def normalize_question(q: str) -> str:
    q = q.strip()
    q = re.sub(r"\s+", " ", q)
    return q


def build_prompt(question: str) -> str:
    q = normalize_question(question)

    return f"""{OVERVIEW_PROMPT}

Student question:
"""{q}"""

Respond accordingly.
"""


def orchestrate(question: str) -> Dict:
    prompt = build_prompt(question)

    # The model client will be called by ai_router / models layer.
    # We only prepare the prompt here.
    return {
        "prompt": prompt,
        "confidence": 0.8
    }