# src/aromatics_etard_v1.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


def _lc(s: str) -> str:
    return (s or "").lower().strip()


@dataclass(frozen=True)
class EtardResult:
    reaction: str
    product: str
    notes: str = ""


def detect_etard_v1(text: str) -> bool:
    t = _lc(text)
    # Key reagent: chromyl chloride (CrO2Cl2)
    has_chromyl = ("cro2cl2" in t) or ("chromyl chloride" in t)
    # Typical substrate: toluene / alkylbenzene with benzylic H
    has_toluene = ("toluene" in t) or ("c6h5ch3" in t)
    return has_chromyl and has_toluene


def solve_etard_v1(question: str) -> Optional[EtardResult]:
    t = _lc(question)
    if not detect_etard_v1(t):
        return None

    return EtardResult(
        reaction="Etard oxidation",
        product="Benzaldehyde (C6H5CHO).",
        notes="CrO2Cl2 oxidizes benzylic methyl group to aldehyde (controlled oxidation).",
    )
