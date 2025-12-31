from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class OxTestResult:
    matched: bool
    reagent: str = ""
    substrate: str = ""
    product: str = ""
    observation: str = ""
    notes: str = ""


def _clean(s: str) -> str:
    return (s or "").strip().lower()


def _detect_substrate(text: str) -> str:
    t = _clean(text)

    # common aldehydes in tests
    if "benzaldehyde" in t or "c6h5cho" in t:
        return "benzaldehyde (C6H5CHO)"
    if "ethanal" in t or "acetaldehyde" in t or "ch3cho" in t:
        return "ethanal (CH3CHO)"
    if "formaldehyde" in t or "hcho" in t:
        return "formaldehyde (HCHO)"

    # generic aldehyde cue
    if "aldehyde" in t or "-cho" in t or "cho" in t:
        return "an aldehyde"

    return ""


def solve_oxidation_tests_v1(normalized: Dict[str, Any]) -> OxTestResult:
    """
    Handles aldehyde oxidation tests:
    - Tollens reagent: silver mirror, aldehyde -> carboxylate/acid
    - Fehling solution: brick-red Cu2O ppt (aliphatic aldehydes), aldehyde -> carboxylate

    Returns matched=False if not a Tollens/Fehling-type question.
    """
    # Prefer ``cleaned_text`` introduced in normalizer v1; fall back to ``cleaned_question``
    # (legacy), then to ``raw_question``.  This ensures reagent detection works regardless
    # of key name used by the normalizer.
    text = _clean(
        normalized.get("cleaned_text")
        or normalized.get("cleaned_question")
        or normalized.get("raw_question")
        or ""
    )
    if not text:
        return OxTestResult(matched=False)

    # Recognise Tollens reagent via a variety of synonyms and descriptors
    has_tollens = any(
        k in text
        for k in (
            "tollens", "tollen's", "tollens reagent", "silver mirror", "silver mirror test", "ag(nh3)", "[ag(nh3)2]", "ammoniacal ag"
        )
    )
    # Recognise Fehling solution via synonyms and typical observations
    has_fehling = any(
        k in text
        for k in (
            "fehling", "fehling solution", "red precipitate", "brick-red", "cu2o", "cu2+", "fehling's"
        )
    )

    if not (has_tollens or has_fehling):
        return OxTestResult(matched=False)

    substrate = _detect_substrate(text) or "an aldehyde"

    if has_tollens:
        # aldehyde -> carboxylate (often written as acid after workup)
        product = "corresponding carboxylate (RCOO−) / carboxylic acid (RCOOH)"
        # specific common ones
        if "benzaldehyde" in substrate:
            product = "benzoate / benzoic acid (C6H5COO− / C6H5COOH)"
        elif "ethanal" in substrate:
            product = "acetate / acetic acid (CH3COO− / CH3COOH)"
        elif "formaldehyde" in substrate:
            product = "formate / formic acid (HCOO− / HCOOH)"

        return OxTestResult(
            matched=True,
            reagent="Tollens reagent",
            substrate=substrate,
            product=product,
            observation="silver mirror / grey Ag precipitate",
            notes="Tollens oxidizes aldehydes; ketones generally do not respond."
        )

    # Fehling
    product = "corresponding carboxylate (RCOO−) (after oxidation)"
    if "ethanal" in substrate:
        product = "acetate (CH3COO−) (after oxidation)"
    if "formaldehyde" in substrate:
        product = "formate (HCOO−) (after oxidation)"

    return OxTestResult(
        matched=True,
        reagent="Fehling solution",
        substrate=substrate,
        product=product,
        observation="brick-red precipitate of Cu2O",
        notes="Fehling is positive mainly for aliphatic aldehydes; aromatic aldehydes are often negative/weak."
    )
