# src/aromatics_diazonium_v1.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import re


def _lc(s: str) -> str:
    return (s or "").lower().strip()


@dataclass(frozen=True)
class DiazoniumResult:
    reaction: str
    product: str
    notes: str = ""


# -------------------------------------------------
# DETECTORS
# -------------------------------------------------

def _is_aniline(text: str) -> bool:
    t = _lc(text)
    return any(x in t for x in ["aniline", "phenylamine", "c6h5nh2"])


def _has_diazotization_conditions(text: str) -> bool:
    t = _lc(text)

    has_nitrite = ("nano2" in t) or ("sodium nitrite" in t)
    has_acid = ("hcl" in t) or ("acidic" in t)

    # handle 0-5, 0–5, 0 to 5, cold, ice
    cold_ok = bool(
        re.search(r"0\s*[-–to]+\s*5", t) or
        any(x in t for x in ["cold", "ice", "0°c", "0 c"])
    )

    return has_nitrite and has_acid and cold_ok


def _sandmeyer_reagent(text: str) -> Optional[str]:
    t = _lc(text)

    # Explicit priority: Br > Cl > CN
    if "cubr" in t:
        return "Br"
    if "cucl" in t:
        return "Cl"
    if "cucn" in t or "kcn" in t:
        return "CN"
    return None


# -------------------------------------------------
# SOLVERS
# -------------------------------------------------

def solve_diazotization_v1(question: str) -> Optional[DiazoniumResult]:
    t = _lc(question)

    if not _is_aniline(t):
        return None

    if not _has_diazotization_conditions(t):
        return None

    return DiazoniumResult(
        reaction="Diazotization",
        product="Benzene diazonium chloride (C6H5N2+Cl−).",
        notes="Reaction carried out at 0–5 °C to stabilize diazonium salt.",
    )


def solve_diazonium_substitution_v1(question: str) -> Optional[DiazoniumResult]:
    t = _lc(question)

    if "diazonium" not in t and "n2+" not in t:
        return None

    # Sandmeyer reactions
    X = _sandmeyer_reagent(t)
    if X == "Cl":
        return DiazoniumResult(
            reaction="Sandmeyer reaction",
            product="Chlorobenzene.",
            notes="CuCl replaces diazonium group.",
        )

    if X == "Br":
        return DiazoniumResult(
            reaction="Sandmeyer reaction",
            product="Bromobenzene.",
            notes="CuBr replaces diazonium group.",
        )

    if X == "CN":
        return DiazoniumResult(
            reaction="Sandmeyer reaction",
            product="Benzonitrile.",
            notes="CuCN replaces diazonium group.",
        )

    # Hydrolysis
    if "water" in t or "h2o" in t or "warm" in t:
        return DiazoniumResult(
            reaction="Hydrolysis of diazonium salt",
            product="Phenol.",
            notes="Diazonium group replaced by –OH.",
        )

    # Reduction
    if "h3po2" in t or "hypophosphorous" in t:
        return DiazoniumResult(
            reaction="Reduction of diazonium salt",
            product="Benzene.",
            notes="Diazonium group replaced by hydrogen.",
        )

    return None
