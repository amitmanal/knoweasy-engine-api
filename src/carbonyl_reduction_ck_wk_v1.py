# src/carbonyl_reduction_ck_wk_v1.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


def _lc(s: str) -> str:
    return (s or "").lower().strip()


@dataclass(frozen=True)
class CKWKResult:
    reaction: str
    product: str
    notes: str = ""


def _is_benzaldehyde(t: str) -> bool:
    return ("benzaldehyde" in t) or ("c6h5cho" in t)


def _is_acetophenone(t: str) -> bool:
    return ("acetophenone" in t) or ("c6h5coch3" in t)


def detect_ck_wk_v1(text: str) -> bool:
    t = _lc(text)

    clemmensen = ("zn" in t and "hg" in t) and ("hcl" in t)
    wolff = ("nh2nh2" in t or "hydrazine" in t) and ("koh" in t or "naoh" in t) and ("heat" in t or "Δ" in t or "delta" in t)

    if "clemmensen" in t or "wolff" in t or "kishner" in t:
        return True

    # common exam: carbonyl + these reagent sets
    return clemmensen or wolff


def solve_ck_wk_v1(question: str) -> Optional[CKWKResult]:
    t = _lc(question)
    if not detect_ck_wk_v1(t):
        return None

    clemmensen = ("zn" in t and "hg" in t) and ("hcl" in t)
    wolff = ("nh2nh2" in t or "hydrazine" in t) and ("koh" in t or "naoh" in t) and ("heat" in t or "Δ" in t or "delta" in t)

    # benzaldehyde -> toluene
    if _is_benzaldehyde(t):
        if clemmensen:
            return CKWKResult(
                reaction="Clemmensen reduction",
                product="Toluene (C6H5CH3).",
                notes="Zn(Hg)/HCl reduces –CHO to –CH3 under acidic conditions.",
            )
        if wolff:
            return CKWKResult(
                reaction="Wolff–Kishner reduction",
                product="Toluene (C6H5CH3).",
                notes="NH2NH2/KOH, heat reduces –CHO to –CH3 under basic conditions.",
            )
        return CKWKResult(
            reaction="Carbonyl reduction",
            product="Alkylbenzene (–CHO reduced to –CH3).",
            notes="Clemmensen is acidic; Wolff–Kishner is basic.",
        )

    # acetophenone -> ethylbenzene
    if _is_acetophenone(t):
        if clemmensen:
            return CKWKResult(
                reaction="Clemmensen reduction",
                product="Ethylbenzene (C6H5CH2CH3).",
                notes="Zn(Hg)/HCl reduces ketone C=O to CH2 (acidic).",
            )
        if wolff:
            return CKWKResult(
                reaction="Wolff–Kishner reduction",
                product="Ethylbenzene (C6H5CH2CH3).",
                notes="NH2NH2/KOH, heat reduces ketone C=O to CH2 (basic).",
            )
        return CKWKResult(
            reaction="Carbonyl reduction",
            product="Alkylbenzene (ketone reduced to CH2).",
            notes="Clemmensen is acidic; Wolff–Kishner is basic.",
        )

    # generic
    if clemmensen:
        return CKWKResult(
            reaction="Clemmensen reduction",
            product="Carbonyl → alkane (C=O replaced by CH2).",
            notes="Acidic conditions: Zn(Hg)/HCl.",
        )
    if wolff:
        return CKWKResult(
            reaction="Wolff–Kishner reduction",
            product="Carbonyl → alkane (C=O replaced by CH2).",
            notes="Basic conditions: NH2NH2/KOH, heat.",
        )

    return None
