# src/carbonyl_perkin_v1.py
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional


@dataclass
class PerkinResult:
    reaction: str
    product: str
    notes: str = ""


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(t: str, words: list[str]) -> bool:
    return any(w in t for w in words)


def _is_aromatic_aldehyde(t: str) -> bool:
    # exam-common aromatic aldehydes
    if re.search(r"\bbenzaldehyde\b|\bc6h5cho\b|\bc₆h₅cho\b", t):
        return True
    if re.search(r"\baryl aldehyde\b|\baromatic aldehyde\b", t):
        return True
    # "PhCHO" shorthand
    if re.search(r"\bphcho\b|\bph-cho\b|\bph cho\b", t):
        return True
    return False


def _is_perkin_reagents(t: str) -> bool:
    # Perkin: acid anhydride + acetate base (NaOAc / KOAc)
    has_anhydride = _has_any(t, ["anhydride", "(ch3co)2o", "acetic anhydride", "acid anhydride"])
    has_acetate_base = _has_any(t, ["naoac", "koac", "sodium acetate", "potassium acetate", "acetate"])

    if "perkin" in t:
        return True

    # reagent-based trigger (tight to avoid false positives)
    if has_anhydride and has_acetate_base:
        return True

    return False


def _substrate_key(t: str) -> Optional[str]:
    if re.search(r"\bbenzaldehyde\b|\bc6h5cho\b|\bc₆h₅cho\b|\bphcho\b", t):
        return "benzaldehyde"
    return None


def solve_perkin_v1(text: str) -> Optional[PerkinResult]:
    """
    Perkin reaction:
      Aromatic aldehyde + acid anhydride + acetate base -> alpha,beta-unsaturated acid (after hydrolysis)
    Deterministic, exam-safe.
    """
    t = _lc(text)

    # trigger: explicit Perkin OR (aromatic aldehyde + anhydride + acetate base)
    if not ("perkin" in t or (_is_aromatic_aldehyde(t) and _is_perkin_reagents(t))):
        return None

    # If Perkin is mentioned but aromatic aldehyde not clear: give scope-safe answer
    if not _is_aromatic_aldehyde(t):
        return PerkinResult(
            reaction="Perkin reaction",
            product="Gives **α,β-unsaturated carboxylic acid** from an **aromatic aldehyde** using **acid anhydride + acetate base (NaOAc/KOAc)**.",
            notes=(
                "Scope trap: Perkin is classically for **aromatic aldehydes** (e.g., benzaldehyde). "
                "Product is an unsaturated acid (after hydrolysis), not an aldol product."
            ),
        )

    key = _substrate_key(t)

    # Deterministic core reagent string (ASCII included)
    reag = "acetic anhydride ((CH3CO)2O) + NaOAc (acetate base), then hydrolysis"

    if key == "benzaldehyde":
        return PerkinResult(
            reaction="Perkin reaction (aromatic aldehyde → cinnamic acid type)",
            product=f"C6H5CHO (benzaldehyde) → C6H5CH=CHCOOH (**cinnamic acid**) using {reag}.",
            notes="Exam key: product is α,β-unsaturated carboxylic acid (cinnamic acid type).",
        )

    # generic aromatic aldehyde
    return PerkinResult(
        reaction="Perkin reaction",
        product=f"General: Ar–CHO + (CH3CO)2O + NaOAc → Ar–CH=CH–COOH (after hydrolysis).",
        notes=(
            "Exam traps: (1) needs aromatic aldehyde, (2) acetate base is typical, "
            "(3) final product is α,β-unsaturated acid (not aldehyde/ketone)."
        ),
    )
