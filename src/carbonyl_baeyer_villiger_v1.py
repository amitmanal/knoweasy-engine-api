# src/carbonyl_baeyer_villiger_v1.py
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional


@dataclass
class BVResult:
    reaction: str
    product: str
    notes: str = ""


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(t: str, words: list[str]) -> bool:
    return any(w in t for w in words)


def _is_bv_reagents(t: str) -> bool:
    # Typical: peracids (mCPBA), RCO3H, peroxyacid, peracid, perbenzoic acid
    if _has_any(t, ["baeyer", "villiger", "baeyer–villiger", "baeyer-villiger", "bv oxidation"]):
        return True
    if _has_any(t, ["mcpba", "peracid", "peroxyacid", "peroxy acid", "rco3h", "perbenzoic", "peracetic"]):
        return True
    return False


def _has_carbonyl_substrate(t: str) -> bool:
    # ketone/aldehyde hints
    if _has_any(t, ["ketone", "aldehyde"]):
        return True
    if _has_any(t, ["-cho", " cho", "c=o", "carbonyl"]):
        return True
    # common named substrates
    if re.search(r"\bacetophenone\b|\bcyclohexanone\b|\bcyclopentanone\b|\bbenzaldehyde\b", t):
        return True
    return False


def _substrate_key(t: str) -> Optional[str]:
    if re.search(r"\bacetophenone\b|\b1-phenylethanone\b|\bc6h5coch3\b|\bphcoch3\b", t):
        return "acetophenone"
    if re.search(r"\bcyclohexanone\b", t):
        return "cyclohexanone"
    if re.search(r"\bcyclopentanone\b", t):
        return "cyclopentanone"
    if re.search(r"\bbenzaldehyde\b|\bc6h5cho\b|\bphcho\b", t):
        return "benzaldehyde"
    return None


def solve_baeyer_villiger_v1(text: str) -> Optional[BVResult]:
    """
    Baeyer–Villiger oxidation:
      ketone + peracid -> ester (group migration)
      cyclic ketone -> lactone (ring expansion by 1)
      aldehyde + peracid -> carboxylic acid
    Deterministic, exam-safe.
    """
    t = _lc(text)
    if not (_is_bv_reagents(t) and _has_carbonyl_substrate(t)) and ("baeyer" not in t and "villiger" not in t):
        return None

    key = _substrate_key(t)

    # Deterministic exam line for migratory aptitude
    mig = "Migratory aptitude (exam): tert > sec > primary > methyl; aryl/benzyl usually migrate well."

    if key == "acetophenone":
        # phenyl migrates over methyl → phenyl acetate
        return BVResult(
            reaction="Baeyer–Villiger oxidation (ketone → ester)",
            product="Acetophenone (PhCOCH3) + peracid (mCPBA) → **phenyl acetate** (PhOCOCH3).",
            notes="Key trap: phenyl migrates preferentially over methyl. " + mig,
        )

    if key == "cyclohexanone":
        return BVResult(
            reaction="Baeyer–Villiger oxidation (cyclic ketone → lactone)",
            product="Cyclohexanone + peracid (mCPBA) → **ε-caprolactone** (ring expansion by 1).",
            notes="Cyclic ketone gives lactone (one-carbon ring expansion). " + mig,
        )

    if key == "cyclopentanone":
        return BVResult(
            reaction="Baeyer–Villiger oxidation (cyclic ketone → lactone)",
            product="Cyclopentanone + peracid (mCPBA) → **δ-valerolactone** (ring expansion by 1).",
            notes="Cyclic ketone gives lactone (one-carbon ring expansion). " + mig,
        )

    if key == "benzaldehyde":
        return BVResult(
            reaction="Baeyer–Villiger oxidation (aldehyde → acid)",
            product="Benzaldehyde (PhCHO) + peracid → **benzoic acid** (PhCOOH).",
            notes="Aldehydes are oxidized to carboxylic acids under peracid BV conditions.",
        )

    # If BV mentioned but substrate unclear: give scope-safe rule
    if not _has_carbonyl_substrate(t):
        return BVResult(
            reaction="Baeyer–Villiger oxidation",
            product="Ketone + peracid → **ester**; cyclic ketone → **lactone**; aldehyde → **carboxylic acid**.",
            notes=mig,
        )

    return BVResult(
        reaction="Baeyer–Villiger oxidation",
        product="General: R-CO-R' + peracid (mCPBA / RCO3H) → ester (one group migrates to O). Cyclic ketone → lactone.",
        notes="Exam traps: apply migratory aptitude; do not confuse with ozonolysis/epoxidation. " + mig,
    )
