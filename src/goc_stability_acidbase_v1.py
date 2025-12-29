# src/goc_stability_acidbase_v1.py
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional


@dataclass
class GOCResult:
    reaction: str
    product: str
    notes: str = ""


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(t: str, words: list[str]) -> bool:
    return any(w in t for w in words)


def _is_concept_question(t: str) -> bool:
    # Try to avoid hijacking pure reaction questions (those usually have reagents/arrow)
    concept_markers = [
        "order of", "arrange", "increasing", "decreasing", "compare", "which is more",
        "stability", "stabilit", "acidic strength", "acidity", "basicity", "stronger acid",
        "stronger base", "pka", "pk a", "inductive", "resonance", "hyperconjugation",
        "carbocation", "carbanion", "radical"
    ]
    if not _has_any(t, concept_markers):
        return False

    # If the prompt is clearly a reaction completion, don't trigger
    reaction_markers = ["->", "→", "gives", "product", "complete the reaction", "reagent", "h2so4", "nabh4", "lialh4"]
    if _has_any(t, reaction_markers) and not _has_any(t, ["order of", "arrange", "compare", "stability", "acidity", "basicity"]):
        return False

    return True


def _carbocation_rank_text() -> str:
    return (
        "**Carbocation stability (most → least):** "
        "benzylic > allylic > 3° > 2° > 1° > methyl. "
        "Resonance-stabilized (benzylic/allylic) usually outrank simple alkyl; "
        "hyperconjugation + +I stabilize; -I groups destabilize a carbocation."
    )


def _radical_rank_text() -> str:
    return (
        "**Free-radical stability (most → least):** "
        "benzylic > allylic > 3° > 2° > 1° > methyl. "
        "Resonance stabilizes radicals strongly; hyperconjugation also helps."
    )


def _carbanion_rank_text() -> str:
    return (
        "**Carbanion stability (most → least):** "
        "benzylic ≈ allylic (resonance-stabilized) > methyl > 1° > 2° > 3°. "
        "Alkyl groups (+I) destabilize carbanions; -I/-M groups stabilize."
    )


def _acidity_rank_text() -> str:
    return (
        "**Acidic strength (typical, most → least):** "
        "carboxylic acid > phenol > alcohol > terminal alkyne > alkene/alkane. "
        "Stronger acid = more stable conjugate base; -I/-M groups increase acidity."
    )


def _basicity_rank_text() -> str:
    return (
        "**Basic strength (typical aqueous trend):** "
        "aliphatic amines > NH3 > aniline (aryl amines). "
        "Resonance in aniline reduces lone-pair availability; +I increases basicity, -I decreases."
    )


def solve_goc_v1(text: str) -> Optional[GOCResult]:
    """
    GOC v1: deterministic concept answers for Class 11:
      - Carbocation / carbanion / radical stability orders
      - Acidity / basicity broad orders + key exam traps
    """
    t = _lc(text)
    if not _is_concept_question(t):
        return None

    # Decide primary intent
    if _has_any(t, ["carbocation", "carbo cation", "c+", "cation stability"]):
        return GOCResult(
            reaction="GOC: Carbocation stability order",
            product=_carbocation_rank_text(),
            notes="Exam trap: benzylic/allylic often more stable than 3° due to resonance.",
        )

    if _has_any(t, ["carbanion", "carbo anion", "c-", "anion stability"]):
        return GOCResult(
            reaction="GOC: Carbanion stability order",
            product=_carbanion_rank_text(),
            notes="Exam trap: alkyl groups destabilize carbanions; resonance / -I stabilizes.",
        )

    if _has_any(t, ["radical", "free radical", "•", "dot", "homolytic"]):
        return GOCResult(
            reaction="GOC: Free-radical stability order",
            product=_radical_rank_text(),
            notes="Exam trap: benzylic/allylic radicals are strongly resonance-stabilized.",
        )

    if _has_any(t, ["acidity", "acidic", "stronger acid", "pka", "pk a"]):
        # If asked “why” include the rule
        extra = ""
        if _has_any(t, ["why", "reason", "explain"]):
            extra = " Rule: stronger acid ⇔ more stable conjugate base (A⁻)."
        return GOCResult(
            reaction="GOC: Acidity order / acidity rules",
            product=_acidity_rank_text() + extra,
            notes="Common trap: do not compare acidity by just “electronegativity”; use conjugate-base stability.",
        )

    if _has_any(t, ["basicity", "stronger base", "more basic", "base strength"]):
        extra = ""
        if _has_any(t, ["why", "reason", "explain"]):
            extra = " Rule: stronger base ⇔ more available lone pair (less resonance delocalization)."
        return GOCResult(
            reaction="GOC: Basicity order / basicity rules",
            product=_basicity_rank_text() + extra,
            notes="Exam trap: aniline is less basic than aliphatic amines due to resonance.",
        )

    # If generic “stability order” without specifying species, give the 3 core orders
    if _has_any(t, ["stability", "order of stability", "arrange stability", "increasing stability"]):
        return GOCResult(
            reaction="GOC: Stability orders (quick sheet)",
            product=(
                _carbocation_rank_text()
                + "\n"
                + _radical_rank_text()
                + "\n"
                + _carbanion_rank_text()
            ),
            notes="Pick the correct species first: C+ vs radical vs C− (orders are not the same).",
        )

    # Fallback: still a concept question, so give a safe overview
    return GOCResult(
        reaction="GOC: Concept overview (stability + acidity/basicity)",
        product=(
            _carbocation_rank_text()
            + "\n"
            + _carbanion_rank_text()
            + "\n"
            + _radical_rank_text()
            + "\n"
            + _acidity_rank_text()
            + "\n"
            + _basicity_rank_text()
        ),
        notes="Use resonance first (if present), then inductive effects, then hyperconjugation.",
    )
