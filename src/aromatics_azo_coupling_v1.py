# src/aromatics_azo_coupling_v1.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import re


def _lc(s: str) -> str:
    return (s or "").lower().strip()


@dataclass(frozen=True)
class AzoCouplingResult:
    reaction: str
    product: str
    notes: str = ""


# -------------------------
# DETECTION HELPERS
# -------------------------

_DIAZO_HINT = re.compile(r"(diazonium|n2\+|benzenediazonium|aryl\s*diazonium)", re.IGNORECASE)
_COUPLING_HINT = re.compile(r"(coupling|azo\s*dye|azo)", re.IGNORECASE)

_PHENOL_HINT = re.compile(r"(phenol|c6h5oh)", re.IGNORECASE)
_ANILINE_HINT = re.compile(r"(aniline|c6h5nh2|phenylamine)", re.IGNORECASE)

_BASIC_HINT = re.compile(r"(naoh|koh|alkaline|basic|oh\-)", re.IGNORECASE)
_COLD_HINT = re.compile(r"(0\s*[-–to]+\s*5|cold|ice)", re.IGNORECASE)


def detect_azo_coupling_v1(text: str) -> bool:
    t = _lc(text)
    if not _DIAZO_HINT.search(t):
        return False
    # coupling keyword or azo-dye keyword is typical
    if not _COUPLING_HINT.search(t):
        # allow if clearly diazonium + phenol/aniline is mentioned
        if not (_PHENOL_HINT.search(t) or _ANILINE_HINT.search(t)):
            return False
    return True


# -------------------------
# SOLVER
# -------------------------

def solve_azo_coupling_v1(question: str) -> Optional[AzoCouplingResult]:
    t = _lc(question)
    if not detect_azo_coupling_v1(t):
        return None

    # Exam-safe: coupling is done cold; phenol requires alkaline medium (phenoxide).
    cold_ok = bool(_COLD_HINT.search(t)) or True  # allow if not stated (exam convention)

    # Phenol coupling (alkaline)
    if _PHENOL_HINT.search(t):
        if _BASIC_HINT.search(t) or ("naoh" in t) or ("koh" in t):
            return AzoCouplingResult(
                reaction="Azo coupling (phenol, alkaline)",
                product="p-Hydroxyazobenzene (para major; ortho minor).",
                notes="Phenoxide activates ring; coupling occurs mainly at para position.",
            )
        # If phenol mentioned but base not mentioned: exam-safe assumption that alkaline medium is used
        return AzoCouplingResult(
            reaction="Azo coupling (phenol)",
            product="p-Hydroxyazobenzene (para major; ortho minor).",
            notes="Assume alkaline medium (NaOH) for phenol coupling; cold conditions preferred.",
        )

    # Aniline coupling (typically weakly acidic/neutral; exam-safe)
    if _ANILINE_HINT.search(t):
        return AzoCouplingResult(
            reaction="Azo coupling (aniline)",
            product="p-Aminoazobenzene (para major; ortho minor).",
            notes="Amino group activates ring; coupling mainly at para position.",
        )

    # Generic fallback
    return AzoCouplingResult(
        reaction="Azo coupling",
        product="Azo dye (para major).",
        notes="Coupling of aryl diazonium salt with activated aromatic ring (phenol/aniline).",
    )
