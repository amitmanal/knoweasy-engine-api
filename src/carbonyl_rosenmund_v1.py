# src/carbonyl_rosenmund_v1.py
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional


@dataclass
class RosenmundResult:
    reaction: str
    product: str
    notes: str = ""


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(t: str, words: list[str]) -> bool:
    return any(w in t for w in words)


def _is_acid_chloride_present(t: str) -> bool:
    # name-based + formula-based patterns
    if _has_any(t, ["acid chloride", "acyl chloride", "alkanoyl chloride", "aroyl chloride"]):
        return True
    if _has_any(t, ["cocl", "co cl", "co-cl", "co–cl", "co—cl"]):
        return True
    if re.search(r"\bch3cocl\b|\bethanoyl chloride\b|\bacetyl chloride\b", t):
        return True
    if re.search(r"\bc6h5cocl\b|\bbenzoyl chloride\b", t):
        return True
    if re.search(r"\bc2h5cocl\b|\bpropanoyl chloride\b|\bpropionyl chloride\b", t):
        return True
    return False


def _is_rosenmund_reagents(t: str) -> bool:
    # Key: H2 / Pd-BaSO4 (poisoned), sometimes "quinoline", "sulfur"
    has_h2 = _has_any(t, ["h2", "hydrogen"])
    has_pd = _has_any(t, ["pd", "palladium"])
    has_baso4 = _has_any(t, ["baso4", "ba so4", "ba-so4", "barium sulfate", "barium sulphate"])
    has_poison_hint = _has_any(t, ["poisoned", "quinoline", "s", "sulphur", "sulfur"])

    if has_h2 and has_pd and (has_baso4 or has_poison_hint):
        return True

    if "rosenmund" in t:
        return True

    return False


def _substrate_key(t: str) -> Optional[str]:
    if re.search(r"\bacetyl chloride\b|\bethanoyl chloride\b|\bch3cocl\b", t):
        return "acetyl_chloride"
    if re.search(r"\bbenzoyl chloride\b|\bc6h5cocl\b", t):
        return "benzoyl_chloride"
    if re.search(r"\bpropanoyl chloride\b|\bpropionyl chloride\b|\bc2h5cocl\b", t):
        return "propanoyl_chloride"
    return None


def solve_rosenmund_v1(text: str) -> Optional[RosenmundResult]:
    """
    Rosenmund reduction:
      R–COCl + H2 / Pd–BaSO4 (poisoned) -> R–CHO
    Deterministic, exam-safe. Returns None if not detected.
    """
    t = _lc(text)

    # Trigger: either explicit Rosenmund OR (reagents + acid chloride)
    if not (_is_rosenmund_reagents(t) and _is_acid_chloride_present(t)) and ("rosenmund" not in t):
        return None

    # If Rosenmund mentioned but substrate isn't acid chloride, give scope-safe answer
    if not _is_acid_chloride_present(t):
        return RosenmundResult(
            reaction="Rosenmund reduction",
            product="Converts **acid chlorides (R–COCl)** to **aldehydes (R–CHO)** using H₂ / Pd–BaSO₄ (poisoned).",
            notes=(
                "Scope trap: Rosenmund is for **acid chlorides**, not carboxylic acids/esters/amides. "
                "Poisoned catalyst prevents over-reduction."
            ),
        )

    key = _substrate_key(t)

    if key == "acetyl_chloride":
        # Include ASCII + name so tests and exam outputs are robust.
        return RosenmundResult(
            reaction="Rosenmund reduction (acid chloride → aldehyde)",
            product="CH3COCl (acetyl chloride) → CH3CHO / CH₃CHO (**ethanal**).",
            notes="Reagent: H₂ / Pd–BaSO₄ (poisoned). Stops at aldehyde (exam point).",
        )

    if key == "benzoyl_chloride":
        return RosenmundResult(
            reaction="Rosenmund reduction (acid chloride → aldehyde)",
            product="C6H5COCl / C₆H₅COCl (benzoyl chloride) → C6H5CHO / C₆H₅CHO (**benzaldehyde**).",
            notes="Use poisoned Pd–BaSO₄ (often with quinoline) to avoid over-reduction.",
        )

    if key == "propanoyl_chloride":
        return RosenmundResult(
            reaction="Rosenmund reduction (acid chloride → aldehyde)",
            product="C2H5COCl (propanoyl chloride) → C2H5CHO (**propanal**).",
            notes="Acid chloride is reduced selectively to aldehyde.",
        )

    return RosenmundResult(
        reaction="Rosenmund reduction (acid chloride → aldehyde)",
        product="General: R–COCl + H₂ / Pd–BaSO₄ (poisoned) → R–CHO (aldehyde).",
        notes=(
            "Exam traps: (1) needs **poisoned catalyst** (Pd–BaSO₄, often quinoline), "
            "(2) applies to **acid chlorides**, (3) product is **aldehyde**, not alcohol."
        ),
    )
