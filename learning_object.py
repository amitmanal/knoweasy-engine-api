"""learning_object.py

Defines the **AnswerObject** schema used across KnowEasy Learning.

NON‑NEGOTIABLE PRODUCT RULES (locked):
- No raw chat text as a final product response.
- Every response must be a structured AnswerObject (Learning Object).
- 3 modes only: lite / tutor / mastery (age & syllabus safe).
- Visuals are thinking tools (diagram/graph/map/timeline) when helpful.

This module is deterministic and stable. It does not call external providers.
External AI calls happen only in orchestrator.py / ai_router.py.

"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
import re


# -----------------------------
# Schema
# -----------------------------

@dataclass
class ExplanationBlock:
    title: str
    content: str


@dataclass
class VisualSpec:
    """A lightweight visual spec that frontend can render.

    Supported fields:
      - type: diagram | graph | map | timeline | table | formula
      - title: short title
      - format: mermaid | text
      - code: mermaid code or text fallback
    """
    type: str
    title: str
    format: str = "text"
    code: str = ""


@dataclass
class AnswerObject:
    title: str
    why_this_matters: str
    explanation_blocks: List[ExplanationBlock]
    visuals: List[VisualSpec] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    common_mistakes: List[str] = field(default_factory=list)
    exam_relevance_footer: str = ""
    follow_up_chips: List[str] = field(default_factory=list)
    language: str = "en"
    mode: str = "tutor"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "why_this_matters": self.why_this_matters,
            "explanation_blocks": [
                {"title": b.title, "content": b.content} for b in (self.explanation_blocks or [])
            ],
            "visuals": [
                {"type": v.type, "title": v.title, "format": v.format, "code": v.code} for v in (self.visuals or [])
            ],
            "examples": list(self.examples or []),
            "common_mistakes": list(self.common_mistakes or []),
            "exam_relevance_footer": self.exam_relevance_footer or "",
            "follow_up_chips": list(self.follow_up_chips or []),
            "language": self.language or "en",
            "mode": self.mode or "tutor",
        }


# -----------------------------
# Helpers (deterministic)
# -----------------------------

def _clean(s: Any) -> str:
    t = "" if s is None else str(s)
    t = t.replace("\r", " ").strip()
    # Keep newlines in content blocks; normalize spacing in titles
    return t


def _short_title_from_question(q: str) -> str:
    q = _clean(q)
    q = re.sub(r"\s+", " ", q).strip()
    if not q:
        return "Answer"
    if len(q) <= 96:
        return q
    return q[:96].rsplit(" ", 1)[0] + "…"


def _exam_footer(board: str, class_level: str, subject: str, exam_mode: str) -> str:
    bits: List[str] = []
    if board:
        bits.append(board.upper())
    if class_level:
        bits.append(f"Class {class_level}")
    if subject:
        bits.append(subject)
    ctx = " • ".join([b for b in bits if b])
    # Never fabricate past-year claims.
    if exam_mode:
        return f"Exam relevance (for you): {('Important for ' + exam_mode) if exam_mode else ''}{(' — ' + ctx) if ctx else ''}".strip()
    return f"Exam relevance (for you): Important concept — {ctx}".strip() if ctx else "Exam relevance (for you): Important concept"


def _default_followups(question: str) -> List[str]:
    q = _clean(question)
    # Keep calm + actionable
    return [
        "Give me a 2-line recap",
        "Show 2 practice questions",
        "Explain with a simple diagram",
        "What are common mistakes here?",
    ]


def _common_mistakes(subject: str) -> List[str]:
    s = (subject or "").lower()
    if "math" in s:
        return [
            "Skipping units/conditions while simplifying.",
            "Not checking the final answer with the original equation.",
        ]
    if "chem" in s:
        return [
            "Mixing up reagents/conditions (acidic vs basic).",
            "Writing products without checking mechanism/major product rule.",
        ]
    if "phys" in s:
        return [
            "Forgetting sign conventions or units.",
            "Using a formula without checking assumptions (constant a, no friction, etc.).",
        ]
    if "bio" in s:
        return [
            "Confusing similar terms (e.g., diffusion vs osmosis).",
            "Skipping key labels in diagrams.",
        ]
    return [
        "Learning words without understanding the core idea.",
        "Not connecting the concept to an example problem.",
    ]


def _visual_for_question(question: str, subject: str) -> List[VisualSpec]:
    q = (question or "").lower()
    s = (subject or "").lower()

    # Biology: photosynthesis / respiration etc.
    if any(k in q for k in ["photosynthesis", "respiration", "cell", "chloroplast"]) or "bio" in s:
        code = """flowchart LR
A[Sunlight] --> B[Chloroplast]
B --> C[Light reactions]
C --> D[ATP + NADPH]
D --> E[Calvin cycle]
E --> F[Glucose]
"""
        return [VisualSpec(type="diagram", title="Concept flow (simplified)", format="mermaid", code=code)]

    # Chemistry: reaction mechanism (very simplified)
    if "chem" in s or any(k in q for k in ["tollens", "aldol", "sn1", "sn2", "oxidation", "reduction"]):
        code = """flowchart LR
A[Reactant] -->|Reagent / Condition| B[Intermediate]
B --> C[Major product]
"""
        return [VisualSpec(type="diagram", title="Reaction roadmap (template)", format="mermaid", code=code)]

    # Physics: graph template
    if "phys" in s or any(k in q for k in ["velocity", "acceleration", "graph", "force", "motion"]):
        code = """flowchart LR
A[Given] --> B[Choose formula]
B --> C[Substitute values]
C --> D[Compute + check units]
"""
        return [VisualSpec(type="diagram", title="Problem-solving roadmap", format="mermaid", code=code)]

    # History/Geo timeline/map placeholders
    if any(k in s for k in ["history", "geography", "civics"]) or any(k in q for k in ["timeline", "map", "river", "empire"]):
        return [VisualSpec(type="timeline", title="Timeline (template)", format="text", code="• Event 1 → Event 2 → Event 3")]

    return []


def _split_to_steps(raw_answer: str) -> List[str]:
    """Convert a raw answer into bullet-ish steps (deterministic)."""
    a = _clean(raw_answer)
    if not a:
        return []
    # Split by blank lines or sentences (light)
    parts = [p.strip() for p in re.split(r"\n\s*\n", a) if p.strip()]
    if len(parts) >= 2:
        return parts[:6]
    # Sentence split
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", a) if s.strip()]
    return sents[:6]


# -----------------------------
# Public builder
# -----------------------------

def build_answer_object(
    *,
    question: str,
    raw_answer: str,
    language: str = "en",
    mode: str = "tutor",
    board: str = "",
    class_level: str = "",
    subject: str = "",
    exam_mode: str = "",
    study_mode: str = "chat",
) -> AnswerObject:
    """Build a syllabus-safe AnswerObject.

    This is used as the final, stable contract returned to frontend.
    It can wrap a provider answer OR a fallback answer.
    """
    q = _clean(question)
    ans = _clean(raw_answer)

    m = (mode or "tutor").lower().strip()
    if m not in {"lite", "tutor", "mastery"}:
        m = "tutor"

    # Luma is tutor-first and concise by feel:
    if (study_mode or "").lower().strip() == "luma" and m == "mastery":
        # Allow mastery if user selects it, but keep blocks tighter by content
        pass

    title = _short_title_from_question(q)
    why = "This helps you understand the concept clearly and apply it in exam-style questions."

    steps = _split_to_steps(ans)

    blocks: List[ExplanationBlock] = []

    if m == "lite":
        # 2 blocks, fast clarity
        one_line = steps[0] if steps else (ans[:220].rsplit(" ", 1)[0] + "…") if len(ans) > 240 else ans
        blocks = [
            ExplanationBlock("In one line", one_line or "Here’s the core idea in one line."),
            ExplanationBlock("Key idea", steps[1] if len(steps) > 1 else "Focus on the definition + one example."),
        ]
    elif m == "tutor":
        blocks = [
            ExplanationBlock("Simple definition", steps[0] if steps else ans or "Let’s define it simply."),
            ExplanationBlock("Step-by-step", "\n".join(f"• {s}" for s in steps[1:4]) if len(steps) > 1 else "• Step 1: Identify what is asked\n• Step 2: Recall the definition/formula\n• Step 3: Apply carefully"),
            ExplanationBlock("Why it works", steps[4] if len(steps) > 4 else "Because it follows from the basic rule/definition for this topic."),
        ]
    else:  # mastery
        blocks = [
            ExplanationBlock("Concept (exam-safe)", steps[0] if steps else ans or "Concept summary."),
            ExplanationBlock("Reasoning / working", "\n".join(f"• {s}" for s in steps[1:5]) if len(steps) > 1 else "• Break the problem into parts\n• Apply the correct rule\n• Check assumptions + units"),
            ExplanationBlock("Common mistakes", "\n".join(f"• {m}" for m in _common_mistakes(subject)[:3])),
            ExplanationBlock("How exam questions are asked", "• Definition / MCQ\n• Assertion-Reason\n• Numerical / short notes (depending on subject)"),
            ExplanationBlock("Practice now", "1) Write the definition in 2 lines\n2) Solve 2 similar questions\n3) Explain the concept to a friend in 30 seconds"),
        ]

    visuals = _visual_for_question(q, subject)

    examples: List[str] = []
    if m != "lite":
        examples = [
            "Example: apply the definition to a simple real-life situation.",
            "Example: solve a short exam-style question using the steps above.",
        ]
    if m == "mastery":
        examples.append("Quick check: can you explain the same idea in 2 lines without looking?")

    footer = _exam_footer(board or "", class_level or "", subject or "", (exam_mode or "").upper().strip() or "")

    ao = AnswerObject(
        title=title,
        why_this_matters=why,
        explanation_blocks=blocks,
        visuals=visuals,
        examples=examples,
        common_mistakes=_common_mistakes(subject),
        exam_relevance_footer=footer,
        follow_up_chips=_default_followups(q),
        language=(language or "en").lower().strip() or "en",
        mode=m,
    )
    return ao


def ensure_answer_object_dict(obj: Any) -> Dict[str, Any]:
    """Validate minimal schema and return a safe dict.

    This is a strict guardrail so frontend never receives raw text-only answers.
    """
    if isinstance(obj, AnswerObject):
        return obj.to_dict()
    if isinstance(obj, dict):
        # Required keys
        required = {"title", "why_this_matters", "explanation_blocks", "visuals", "examples", "common_mistakes", "exam_relevance_footer", "follow_up_chips", "language", "mode"}
        if required.issubset(set(obj.keys())) and isinstance(obj.get("explanation_blocks"), list):
            return obj
    # Fallback minimal
    ao = build_answer_object(
        question=str(getattr(obj, "question", "") or "Answer"),
        raw_answer=str(obj) if obj is not None else "",
        mode="tutor",
    )
    return ao.to_dict()
