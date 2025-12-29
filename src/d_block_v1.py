# src/d_block_v1.py
"""
KnowEasy Engine v1 — d-Block Elements — v1 (Deterministic)

Scope (LOCKED):
- General electronic configuration
- Oxidation state trends
- Colour of compounds
- Magnetic behaviour
- Catalytic properties
- Variable valency
- First transition series overview (Sc → Zn)

Design:
- Deterministic facts only
- Exam-safe abstractions
- No external dependencies
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple


FIRST_TRANSITION_SERIES: Tuple[str, ...] = (
    "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn"
)


def d_block_general_configuration() -> str:
    """
    General electronic configuration of d-block elements.
    """
    return "(n−1)d1–10 ns1–2"


def first_transition_series_elements() -> List[str]:
    return list(FIRST_TRANSITION_SERIES)


def common_oxidation_states(element: str) -> List[int]:
    """
    Exam-safe common oxidation states for first transition series.
    """
    e = element.strip().capitalize()
    table = {
        "Sc": [+3],
        "Ti": [+2, +3, +4],
        "V": [+2, +3, +4, +5],
        "Cr": [+2, +3, +6],
        "Mn": [+2, +4, +7],
        "Fe": [+2, +3],
        "Co": [+2, +3],
        "Ni": [+2],
        "Cu": [+1, +2],
        "Zn": [+2],
    }
    if e not in table:
        raise ValueError(f"Unsupported d-block element: {element!r}")
    return table[e]


def colored_ions(element: str) -> bool:
    """
    Whether compounds of the element are generally coloured.
    Rule:
    - d0 and d10 → colourless
    - partially filled d → coloured
    """
    e = element.strip().capitalize()
    if e in ("Sc", "Zn"):
        return False
    if e in FIRST_TRANSITION_SERIES:
        return True
    raise ValueError(f"Unsupported d-block element: {element!r}")


def magnetic_behavior(element: str) -> str:
    """
    Returns magnetic behaviour: paramagnetic or diamagnetic (simplified).
    """
    e = element.strip().capitalize()
    if e in ("Sc", "Zn"):
        return "diamagnetic"
    if e in FIRST_TRANSITION_SERIES:
        return "paramagnetic"
    raise ValueError(f"Unsupported d-block element: {element!r}")


def shows_variable_valency(element: str) -> bool:
    """
    Variable valency is a characteristic feature of most d-block elements.
    Exceptions (exam-safe simplification): Sc, Zn.
    """
    e = element.strip().capitalize()
    if e in ("Sc", "Zn"):
        return False
    if e in FIRST_TRANSITION_SERIES:
        return True
    raise ValueError(f"Unsupported d-block element: {element!r}")


def catalytic_activity_examples() -> Dict[str, List[str]]:
    """
    Canonical catalytic examples (exam-safe).
    """
    return {
        "Fe": ["Haber process (N2 + H2 → NH3)"],
        "V2O5": ["Contact process (SO2 → SO3)"],
        "Ni": ["Hydrogenation of alkenes"],
        "Pt": ["Catalytic converters"],
        "Pd": ["Hydrogenation reactions"],
    }


def reasons_for_catalytic_activity() -> List[str]:
    """
    Deterministic reasons for catalytic nature of d-block elements.
    """
    return [
        "Variable oxidation states",
        "Ability to form complexes",
        "Presence of vacant or partially filled d-orbitals",
        "Ability to adsorb reactant molecules on surface",
    ]


def general_trends_summary() -> Dict[str, List[str]]:
    """
    Compact trends summary for fast verification.
    """
    return {
        "oxidation_state_trend": [
            "Increase to Mn, then decrease towards Zn"
        ],
        "atomic_size_trend": [
            "Gradual decrease from Sc to Cu, slight increase at Zn"
        ],
        "melting_point_trend": [
            "Generally high due to strong metallic bonding"
        ],
    }
