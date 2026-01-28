"""
learning_object.py
------------------

This module defines dataclasses and helper functions for building
a structured AnswerObject used by the KnowEasy AI backend.  The
AnswerObject is inspired by the product requirements from the CEO,
containing clearly defined sections that improve learning outcomes.

This file does not make any outbound network calls.  It simply
converts raw AI responses into a richer structure.  In the absence
of a real AI response (for example, when the AI backend cannot
access external models due to network restrictions during local
development), we populate the fields using basic heuristics based
on the user's question.  These placeholders can later be removed
when integrating with real AI providers.

Author: KnowEasy AI Architecture Team
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
import re


@dataclass
class ExplanationBlock:
    """A single explanatory block of content.

    For now this simply wraps text, but could be extended to
    include headings, subpoints, and inline LaTeX or HTML.
    """
    text: str


@dataclass
class AnswerObject:
    """Structured answer returned by the AI.

    The keys mirror the product specification: a title summarising
    the answer, a one-line explanation of why the topic matters,
    an ordered list of explanation blocks, optional visuals and
    examples, common mistakes, an exam relevance footer, clickable
    follow-up chips, the language code, and the answer mode.
    """
    title: str
    why_this_matters: str
    explanation_blocks: List[ExplanationBlock]
    visuals: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    common_mistakes: List[str] = field(default_factory=list)
    exam_relevance_footer: str = ""
    follow_up_chips: List[str] = field(default_factory=list)
    language: str = "en"
    mode: str = "lite"

    def to_dict(self) -> Dict:
        """Serialize the AnswerObject to a plain dict for JSON response."""
        return {
            "title": self.title,
            "why_this_matters": self.why_this_matters,
            "explanation_blocks": [block.text for block in self.explanation_blocks],
            "visuals": self.visuals,
            "examples": self.examples,
            "common_mistakes": self.common_mistakes,
            "exam_relevance_footer": self.exam_relevance_footer,
            "follow_up_chips": self.follow_up_chips,
            "language": self.language,
            "mode": self.mode,
        }


def build_answer_object(
    question: str,
    raw_answer: str,
    *,
    language: str = "en",
    mode: str = "lite",
    board: Optional[str] = None,
    class_level: Optional[str] = None,
) -> AnswerObject:
    """Construct an AnswerObject from a raw answer string using heuristics.

    This helper attempts to populate all fields of the AnswerObject
    specification, including examples, common mistakes, visuals, and
    exam relevance.  The implementation relies on simple heuristics
    based on the question content because the environment may not
    have access to real AI providers.  When integrated with actual
    AI models, these heuristics can be replaced with AI-generated
    values.

    Args:
        question: The user question to contextualise the answer.
        raw_answer: The plain text answer from an AI model or fallback.
        language: Two-letter language code (default "en").
        mode: The answer mode (lite, tutor, mastery).
        board: Optional educational board for exam relevance (e.g., "CBSE").
        class_level: Optional class level (e.g., "10").

    Returns:
        AnswerObject populated with heuristic fields.
    """
    # --- Title and introductory statement ---
    # Use the first sentence of the answer as the title, or fallback to the question
    title = raw_answer.strip().split(".")[0].strip()
    if not title:
        title = question.strip().capitalize() if question else "Answer"

    # A generic one-line explanation of why the topic matters
    why = (
        "Understanding this concept builds a strong foundation for your studies."
    )

    # --- Explanation blocks ---
    # Split the raw answer into paragraphs for separate explanation blocks
    paragraphs = [p.strip() for p in raw_answer.split("\n") if p.strip()]
    if not paragraphs:
        paragraphs = [raw_answer.strip()] if raw_answer.strip() else ["No answer available."]
    blocks: List[ExplanationBlock] = [ExplanationBlock(text=p) for p in paragraphs]

    # --- Examples ---
    # Provide at least one example based on the question keywords.
    examples: List[str] = []
    tokens = [t.lower() for t in re.findall(r"\b\w+\b", question)] if question else []
    if tokens:
        concept = tokens[0]
        examples.append(
            f"For example, consider the concept of {concept}. Applying {concept} in a real-world situation helps illustrate the idea."
        )
        if len(paragraphs) > 1:
            examples.append(
                f"Another example: when studying {concept}, try to relate it to everyday activities."
            )

    # --- Common mistakes ---
    common_mistakes: List[str] = []
    if tokens:
        concept = tokens[0]
        common_mistakes.append(
            f"A common mistake is to confuse the key ideas of {concept} with unrelated topics."
        )
        common_mistakes.append(
            f"Students often forget to review the basic definitions when working with {concept}."
        )

    # --- Exam relevance ---
    if board and class_level:
        exam_footer = (
            f"Important for {board.upper()} Class {class_level} syllabus and exam preparation."
        )
    else:
        exam_footer = "Important for your syllabus and exam preparation."

    # --- Visuals ---
    visuals: List[Dict] = []
    try:
        if mode and mode.lower() in {"tutor", "mastery"}:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            from io import BytesIO
            import base64

            categories = ["Basics", "Intermediate", "Advanced"]
            q_len = len(question or "")
            values = [max(1, q_len % 5 + 3), max(1, (q_len // 2) % 5 + 2), max(1, (q_len // 3) % 5 + 1)]
            plt.figure(figsize=(4, 2.5))
            bars = plt.bar(categories, values, color=["#4f8dff", "#a855f7", "#34d399"])
            plt.title("Concept Depth Overview")
            plt.ylabel("Relative importance")
            plt.ylim(0, max(values) + 2)
            for idx, bar in enumerate(bars):
                plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3, str(values[idx]), ha='center', va='bottom')
            plt.tight_layout()
            buffer = BytesIO()
            plt.savefig(buffer, format='png', bbox_inches='tight')
            plt.close()
            encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
            visuals.append({
                "src": f"data:image/png;base64,{encoded}",
                "title": "Concept Depth Overview"
            })
    except Exception:
        pass

    # --- Follow-up chips ---
    chips: List[str] = []
    if tokens:
        unique_tokens: List[str] = []
        for t in tokens:
            if t not in unique_tokens and len(unique_tokens) < 3:
                unique_tokens.append(t)
        chips = [f"Learn about {t}" for t in unique_tokens]

    return AnswerObject(
        title=title,
        why_this_matters=why,
        explanation_blocks=blocks,
        visuals=visuals,
        examples=examples,
        common_mistakes=common_mistakes,
        exam_relevance_footer=exam_footer,
        follow_up_chips=chips,
        language=language,
        mode=mode,
    )