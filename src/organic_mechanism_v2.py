"""
Organic Chemistry v2 — Reaction Mechanism Core (Deterministic)

Scope:
- Carbocation / Carbanion / Radical stability ranking
- SN1 / SN2 / E1 / E2 preference decision (exam-safe)

No simulations. No product prediction. Ranking + decisions only.
"""

from __future__ import annotations


class OrganicMechanismError(ValueError):
    """Invalid inputs for organic mechanism helpers."""


# -------------------------
# Stability ranking helpers
# -------------------------

def carbocation_stability_rank(kind: str) -> int:
    """
    Higher return value = more stable.

    Order (NCERT/JEE):
      benzylic > allylic > 3° > 2° > 1° > methyl
    """
    order = {
        "methyl": 0,
        "primary": 1,
        "secondary": 2,
        "tertiary": 3,
        "allylic": 4,
        "benzylic": 5,
    }
    k = (kind or "").lower().strip()
    if k not in order:
        raise OrganicMechanismError(f"Unknown carbocation type: {kind}")
    return order[k]


def carbanion_stability_rank(kind: str) -> int:
    """
    Higher return value = more stable.

    Order (reverse of carbocation):
      methyl > 1° > 2° > 3°
    """
    order = {
        "tertiary": 0,
        "secondary": 1,
        "primary": 2,
        "methyl": 3,
    }
    k = (kind or "").lower().strip()
    if k not in order:
        raise OrganicMechanismError(f"Unknown carbanion type: {kind}")
    return order[k]


def radical_stability_rank(kind: str) -> int:
    """
    Higher return value = more stable.

    Order:
      benzylic > allylic > 3° > 2° > 1° > methyl
    """
    order = {
        "methyl": 0,
        "primary": 1,
        "secondary": 2,
        "tertiary": 3,
        "allylic": 4,
        "benzylic": 5,
    }
    k = (kind or "").lower().strip()
    if k not in order:
        raise OrganicMechanismError(f"Unknown radical type: {kind}")
    return order[k]


# -------------------------
# Mechanism decision logic
# -------------------------

def decide_substitution_elimination_mechanism(
    substrate_degree: str,
    nucleophile_strength: str,
    base_strength: str,
    solvent: str,
    temperature_high: bool = False,
) -> str:
    """
    Deterministic exam-safe mechanism selector.

    Returns one of:
      "SN1", "SN2", "E1", "E2"

    Rules (simplified, NCERT/JEE):
    - 3° + weak nucleophile + polar protic → SN1 / E1
    - Strong base → E2
    - 1° + strong nucleophile → SN2
    - High temperature biases elimination
    """
    sd = substrate_degree.lower()
    nu = nucleophile_strength.lower()
    bs = base_strength.lower()
    sol = solvent.lower()

    if sd not in ("primary", "secondary", "tertiary"):
        raise OrganicMechanismError("Invalid substrate_degree")

    if bs == "strong":
        return "E2"

    if sd == "tertiary":
        if temperature_high:
            return "E1"
        return "SN1"

    if sd == "primary":
        if nu == "strong":
            return "SN2"
        raise OrganicMechanismError("Primary substrate with weak nucleophile is uncommon in exams")

    # secondary (borderline)
    if sd == "secondary":
        if nu == "strong" and sol == "polar aprotic":
            return "SN2"
        if temperature_high:
            return "E1"
        return "SN1"
