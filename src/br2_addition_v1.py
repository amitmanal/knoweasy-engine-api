"""
Solver for bromine addition to alkenes under different solvent conditions.

This module distinguishes between bromination in inert solvents (CCl₄) and
halohydrin formation in aqueous media.  For a few common substrates such
as propene it returns the named product; otherwise it asks the user to
specify the solvent if ambiguous.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Br2AdditionResult:
    reaction: str
    product: str
    notes: str = ""


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(t: str, kws: list[str]) -> bool:
    return any(k in t for k in kws)


def solve_br2_addition_v1(text: str) -> Optional[Br2AdditionResult]:
    """
    Determine the product of bromination of alkenes given solvent conditions.

    Parameters
    ----------
    text : str
        The user question text.

    Returns
    -------
    Optional[Br2AdditionResult]
        If a recognised alkene + Br2 combination is detected, returns the product
        based on solvent; otherwise returns an informative prompt to specify the medium.
    """
    t = _lc(text)
    # Trigger only if bromine is mentioned along with an alkene
    if not (("br2" in t or "bromine" in t) and _has_any(t, ["alkene", "propene", "propylene", "c3h6"])):
        return None

    # Determine solvent conditions
    ccl4 = _has_any(t, ["ccl4", "carbon tetrachloride", "ccl₄"])
    water = _has_any(t, ["h2o", "water"])

    # Specific substrate: propene
    if _has_any(t, ["propene", "propylene", "ch3ch=ch2", "c3h6"]):
        if ccl4 and not water:
            return Br2AdditionResult(
                reaction="Addition of Br2 to propene in CCl4",
                product="1,2-dibromopropane",
                notes="In inert solvent (CCl4) bromine adds across the double bond forming vicinal dibromide.",
            )
        if water and not ccl4:
            return Br2AdditionResult(
                reaction="Bromohydrin formation from propene",
                product="1-bromopropan-2-ol",
                notes="In aqueous medium, bromonium ion opening by water gives halohydrin (bromo alcohol).",
            )

    # General alkene: if solvent specified
    if ccl4 and not water:
        return Br2AdditionResult(
            reaction="Addition of Br2 to alkene in CCl4",
            product="Vicinal dibromide",
            notes="Bromine adds anti across C=C in inert solvent.",
        )
    if water and not ccl4:
        return Br2AdditionResult(
            reaction="Formation of bromohydrin from alkene",
            product="Bromoalcohol (halohydrin)",
            notes="In aqueous medium, halonium intermediate is attacked by water, giving halohydrin.",
        )

    # Ambiguous conditions: ask to specify solvent
    return Br2AdditionResult(
        reaction="Bromination of alkene (conditions unspecified)",
        product="Please specify solvent/medium: in CCl4 → vicinal dibromide; in H2O → halohydrin.",
        notes="Exam tip: product depends on solvent (inert vs aqueous).",
    )