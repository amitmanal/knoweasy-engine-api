# src/carbonyl_hydride_reduction_v1.py
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional


@dataclass
class HydrideReductionResult:
    reaction: str
    product: str
    notes: str = ""


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(t: str, words: list[str]) -> bool:
    return any(w in t for w in words)


def _is_nabh4(t: str) -> bool:
    return _has_any(t, ["nabh4", "na bh4", "sodium borohydride", "borohydride"])


def _is_lialh4(t: str) -> bool:
    return _has_any(t, ["lialh4", "li alh4", "lialh₄", "lithium aluminium hydride", "lithium aluminum hydride", "lah"])


def _has_acidic_workup(t: str) -> bool:
    return _has_any(t, ["h3o", "h₃o", "h+", "workup", "hydrolysis", "dil. hcl", "dilute hcl"])


def _substrate_key(t: str) -> Optional[str]:
    # very exam-common explicit names/formula
    if re.search(r"\bbenzaldehyde\b|\bc6h5cho\b|\bphcho\b", t):
        return "benzaldehyde"
    if re.search(r"\bacetone\b|\bpropanone\b|\bch3coch3\b", t):
        return "acetone"
    if re.search(r"\bethanal\b|\bacetaldehyde\b|\bch3cho\b", t):
        return "ethanal"
    if re.search(r"\best(er|ers)\b|\bethyl acetate\b|\bch3cooc2h5\b", t):
        return "ester"
    if re.search(r"\bcarboxylic acid\b|\bacid\b|\bacetic acid\b|\bch3cooh\b", t):
        return "acid"
    if re.search(r"\bamide\b", t):
        return "amide"
    return None


def solve_hydride_reduction_v1(text: str) -> Optional[HydrideReductionResult]:
    """
    Hydride reduction (exam-safe):
      - NaBH4: reduces aldehydes/ketones -> alcohols (generally not esters/acids/amides).
      - LiAlH4 (LAH): strong; reduces aldehydes/ketones/esters/acids/amides -> alcohols (amines from amides),
        but we keep v1 scope exam-focused.
    """
    t = _lc(text)

    has_bh4 = _is_nabh4(t)
    has_lah = _is_lialh4(t)

    if not (has_bh4 or has_lah):
        return None

    sub = _substrate_key(t)

    # Deterministic workup string: include ASCII
    workup = "then H3O+ (acidic workup)"
    if _has_acidic_workup(t):
        workup = "then acidic workup (H3O+)"

    # =========================
    # NaBH4 (mild)
    # =========================
    if has_bh4 and not has_lah:
        if sub in ["benzaldehyde", "ethanal"]:
            return HydrideReductionResult(
                reaction="NaBH4 reduction (aldehyde → 1° alcohol)",
                product=f"Aldehyde + NaBH4 → alkoxide → {workup} → **1° alcohol** (RCH2OH).",
                notes="Exam trap: NaBH4 reduces aldehydes/ketones; generally NOT esters/acids/amides.",
            )
        if sub == "acetone":
            return HydrideReductionResult(
                reaction="NaBH4 reduction (ketone → 2° alcohol)",
                product=f"Ketone + NaBH4 → alkoxide → {workup} → **2° alcohol** (R2CHOH).",
                notes="NaBH4 is mild; typically for aldehydes/ketones.",
            )
        if sub in ["ester", "acid", "amide"]:
            return HydrideReductionResult(
                reaction="NaBH4 selectivity (exam convention)",
                product="NaBH4 **does not typically reduce** esters/carboxylic acids/amides under normal conditions (exam convention).",
                notes="Use LiAlH4 for stronger reductions of esters/acids/amides.",
            )

        return HydrideReductionResult(
            reaction="NaBH4 reduction (selective)",
            product=f"NaBH4 reduces **aldehydes/ketones → alcohols** with {workup}.",
            notes="Exam trap: NaBH4 is mild (selective) vs LAH (strong).",
        )

    # =========================
    # LiAlH4 (strong)
    # =========================
    # If both appear, treat as LAH (stronger) for exam safety.
    if has_lah:
        if sub in ["benzaldehyde", "ethanal"]:
            return HydrideReductionResult(
                reaction="LiAlH4 reduction (aldehyde → 1° alcohol)",
                product=f"Aldehyde + LiAlH4 → alkoxide → {workup} → **1° alcohol** (RCH2OH).",
                notes="LAH is strong; moisture-sensitive; needs dry ether then workup.",
            )
        if sub == "acetone":
            return HydrideReductionResult(
                reaction="LiAlH4 reduction (ketone → 2° alcohol)",
                product=f"Ketone + LiAlH4 → alkoxide → {workup} → **2° alcohol** (R2CHOH).",
                notes="LAH reduces aldehydes/ketones easily.",
            )
        if sub == "ester":
            return HydrideReductionResult(
                reaction="LiAlH4 reduction (ester → 1° alcohols)",
                product=f"Ester + LiAlH4 → {workup} → **two alcohols** (RCH2OH + R'OH).",
                notes="Exam key: esters reduce to primary alcohols (and the alkoxy part becomes alcohol).",
            )
        if sub == "acid":
            return HydrideReductionResult(
                reaction="LiAlH4 reduction (carboxylic acid → 1° alcohol)",
                product=f"RCOOH + LiAlH4 → {workup} → **RCH2OH (1° alcohol)**.",
                notes="LAH reduces acids strongly; NaBH4 usually does not (exam convention).",
            )
        if sub == "amide":
            return HydrideReductionResult(
                reaction="LiAlH4 reduction (amide → amine)",
                product=f"Amide + LiAlH4 → {workup} → **amine** (RCH2NH2 / substituted amine).",
                notes="Exam trap: amide reduces to amine (not alcohol).",
            )

        return HydrideReductionResult(
            reaction="LiAlH4 reduction (strong hydride)",
            product=f"LAH (LiAlH4) reduces aldehydes/ketones → alcohols; esters/acids → 1° alcohols; amides → amines, followed by {workup}.",
            notes="Use dry ether; LAH is destroyed by water.",
        )

    return None
