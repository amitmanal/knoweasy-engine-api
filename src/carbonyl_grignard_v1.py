# src/carbonyl_grignard_v1.py
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional


@dataclass
class GrignardResult:
    reaction: str
    product: str
    notes: str = ""


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(t: str, words: list[str]) -> bool:
    return any(w in t for w in words)


def _is_grignard_reagent(t: str) -> bool:
    if _has_any(t, ["grignard", "rmgx", "rm gx", "r-mgx", "mgx", "alkylmagnesium", "arylmagne", "magnesium halide"]):
        return True
    if re.search(r"\bch3mgbr\b|\bc2h5mgbr\b|\bphmgbr\b|\bch3mgcl\b|\bphmgcl\b", t):
        return True
    return False


def _has_acidic_workup(t: str) -> bool:
    return _has_any(t, ["h3o", "h₃o", "h+", "acidic workup", "hydrolysis", "dil. hcl", "dilute hcl", "h2o/acid"])


def _substrate_key(t: str) -> Optional[str]:
    if _has_any(t, ["co2", "co₂", "dry ice", "carbon dioxide"]):
        return "co2"
    if re.search(r"\bformaldehyde\b|\bhcho\b|\bmethanal\b", t):
        return "hcho"
    if re.search(r"\bacetaldehyde\b|\bethanal\b|\bch3cho\b", t):
        return "ch3cho"
    if re.search(r"\bacetone\b|\bpropanone\b|\bch3coch3\b", t):
        return "acetone"
    return None


def solve_grignard_v1(text: str) -> Optional[GrignardResult]:
    """
    Grignard addition:
      Carbonyl + RMgX -> alkoxide -> (H3O+) alcohol
      CO2 + RMgX -> carboxylic acid (after H3O+)
    """
    t = _lc(text)
    if not _is_grignard_reagent(t):
        return None

    key = _substrate_key(t)

    # CO2 / dry ice -> carboxylic acid after workup
    if key == "co2":
        return GrignardResult(
            reaction="Grignard carboxylation (CO2 / CO₂ + RMgX)",
            product="CO2 / CO₂ + RMgX → RCOO⁻MgX → (H3O+ / H₃O⁺) **RCOOH (carboxylic acid)**.",
            notes="Exam trap: CO2 gives carboxylic acid after acidic workup (not alcohol).",
        )

    workup_note = "Needs acidic workup (H3O+) to give alcohol from alkoxide."

    if key == "hcho":
        return GrignardResult(
            reaction="Grignard addition to formaldehyde (gives 1° alcohol)",
            product="HCHO + RMgX → RCH2O⁻MgX → (H3O+ / H₃O⁺) **RCH2OH (1° alcohol)**.",
            notes=workup_note,
        )

    if key == "ch3cho":
        return GrignardResult(
            reaction="Grignard addition to aldehyde (gives 2° alcohol)",
            product="CH3CHO + RMgX → CH3CH(OMgX)R → (H3O+ / H₃O⁺) **CH3CH(OH)R (2° alcohol)**.",
            notes=workup_note,
        )

    if key == "acetone":
        return GrignardResult(
            reaction="Grignard addition to ketone (gives 3° alcohol)",
            product="(CH3)2CO + RMgX → (CH3)2C(OMgX)R → (H3O+ / H₃O⁺) **(CH3)2C(OH)R (3° alcohol)**.",
            notes=workup_note,
        )

    generic = (
        "General: HCHO + RMgX → (H3O+) 1° alcohol; "
        "Aldehyde + RMgX → (H3O+) 2° alcohol; "
        "Ketone + RMgX → (H3O+) 3° alcohol; "
        "CO2 + RMgX → (H3O+) carboxylic acid."
    )
    if not _has_acidic_workup(t):
        generic += " (Acidic workup is required.)"

    return GrignardResult(
        reaction="Grignard reaction (carbonyl addition)",
        product=generic,
        notes="Grignard reagents are destroyed by water/alcohol/acids; use dry ether/THF.",
    )
