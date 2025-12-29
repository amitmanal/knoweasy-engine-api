# src/p_block_group18_v1.py
"""
KnowEasy Engine v1 — p-Block Group 18 (Noble Gases) — v1 (Deterministic)

Scope (exam-safe, deterministic):
- Configuration (ns2 np6; He is 1s2)
- Inertness reasons (high IE, ~zero EA, stable config)
- Reactivity trend down the group
- Major noble gas compounds (mainly Xe; some Kr)
- Oxidation states (0 common; Xe: +2,+4,+6,+8; Kr: +2 limited; Rn: +2)
- Clathrates (concept)
- Common uses (short list)

Design:
- Minimal stable functions returning canonical facts
- No refactors, no dependencies
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


NOBLE_GASES: Tuple[str, ...] = ("He", "Ne", "Ar", "Kr", "Xe", "Rn")


def group18_general_configuration() -> str:
    """
    General valence shell configuration for Group 18 (except He):
    ns2 np6
    """
    return "ns2 np6"


def helium_configuration() -> str:
    """Helium configuration (anomalous compared to ns2 np6 pattern)."""
    return "1s2"


def noble_gases_list() -> List[str]:
    return list(NOBLE_GASES)


def inertness_reasons() -> List[str]:
    """
    Deterministic bullet points for inertness.
    """
    return [
        "Completely filled valence shell (stable electronic configuration)",
        "Very high ionization enthalpy (difficult to remove electron)",
        "Nearly zero electron affinity (little tendency to gain electron)",
        "Monoatomic, weak intermolecular forces (low reactivity, low boiling points)",
    ]


def reactivity_trend_down_group() -> List[str]:
    """
    Reactivity increases down the group due to decreasing ionization enthalpy and increasing size/polarizability.
    Standard exam emphasis: Xe > Kr > Ar ~ Ne ~ He (very low).
    """
    return ["He (least)", "Ne", "Ar", "Kr", "Xe", "Rn (most among listed)"]


def common_oxidation_states(element: str) -> List[int]:
    """
    Exam-safe oxidation states.
    - All noble gases: 0 common
    - Xe: +2, +4, +6, +8 (in compounds like XeF2, XeF4, XeF6, XeO4 etc.)
    - Kr: +2 (rare; e.g., KrF2)
    - Rn: +2 (rare; radon fluorides conceptually)
    """
    e = element.strip().capitalize()
    if e not in NOBLE_GASES:
        raise ValueError(f"Unsupported noble gas for Group 18 v1: {element!r}")

    if e == "Xe":
        return [0, +2, +4, +6, +8]
    if e == "Kr":
        return [0, +2]
    if e == "Rn":
        return [0, +2]
    return [0]


@dataclass(frozen=True)
class NobleCompound:
    formula: str
    noble_gas: str
    oxidation_state: int
    family: str  # "fluoride" / "oxide" / "oxyfluoride" / "other"


def xe_compounds_catalog() -> List[NobleCompound]:
    """
    Canonical, exam-safe Xenon compounds list.
    Not exhaustive; includes the most common ones seen in JEE/NEET.
    """
    return [
        NobleCompound(formula="XeF2", noble_gas="Xe", oxidation_state=+2, family="fluoride"),
        NobleCompound(formula="XeF4", noble_gas="Xe", oxidation_state=+4, family="fluoride"),
        NobleCompound(formula="XeF6", noble_gas="Xe", oxidation_state=+6, family="fluoride"),
        NobleCompound(formula="XeO3", noble_gas="Xe", oxidation_state=+6, family="oxide"),
        NobleCompound(formula="XeO4", noble_gas="Xe", oxidation_state=+8, family="oxide"),
        NobleCompound(formula="XeOF4", noble_gas="Xe", oxidation_state=+6, family="oxyfluoride"),
        NobleCompound(formula="XeO2F2", noble_gas="Xe", oxidation_state=+6, family="oxyfluoride"),
    ]


def kr_compounds_catalog() -> List[NobleCompound]:
    """
    Canonical Krypton compounds (limited).
    """
    return [
        NobleCompound(formula="KrF2", noble_gas="Kr", oxidation_state=+2, family="fluoride"),
    ]


def stable_compound_families(element: str) -> List[str]:
    """
    Which compound families are commonly discussed for a given noble gas (exam-safe).
    """
    e = element.strip().capitalize()
    if e not in NOBLE_GASES:
        raise ValueError(f"Unsupported noble gas: {element!r}")

    if e == "Xe":
        return ["fluoride", "oxide", "oxyfluoride"]
    if e == "Kr":
        return ["fluoride"]
    if e == "Rn":
        return ["fluoride"]  # conceptual/rare; keep exam-safe
    return []


def can_form_fluoride(element: str) -> bool:
    """
    Exam-safe: Xe and Kr can form fluorides; Rn can (rare); He/Ne/Ar generally do not.
    """
    e = element.strip().capitalize()
    if e not in NOBLE_GASES:
        raise ValueError(f"Unsupported noble gas: {element!r}")
    return e in ("Kr", "Xe", "Rn")


def most_reactive_noble_gas_among_common() -> str:
    """
    Typical school-level answer is Xenon among commonly discussed stable-compound-forming noble gases.
    (Rn is radioactive and less emphasized.)
    """
    return "Xe"


def clathrate_concept_points() -> List[str]:
    """
    Deterministic clathrate points (no deep thermodynamics).
    """
    return [
        "Clathrates are inclusion compounds where noble gas atoms are trapped in cavities of host lattices (e.g., water/quinol)",
        "They are physical entrapments (no strong chemical bonding)",
        "Formation favored at low temperature and high pressure (conceptual trend)",
    ]


def common_uses() -> Dict[str, List[str]]:
    """
    Short, exam-safe uses list.
    """
    return {
        "He": ["Balloons/airships", "Cryogenics (liquid He)"],
        "Ne": ["Neon sign lamps"],
        "Ar": ["Filling incandescent bulbs", "Shielding gas in welding"],
        "Kr": ["High-intensity lamps (limited)"],
        "Xe": ["Xenon arc lamps/flash lamps", "Anesthetic use (concept)"],
        "Rn": ["Radiotherapy concept (historical/limited due to radioactivity)"],
    }


def boiling_point_trend() -> List[str]:
    """
    Boiling points generally increase down the group due to increasing size and dispersion forces.
    """
    return ["He < Ne < Ar < Kr < Xe < Rn"]


def group18_trends_summary() -> Dict[str, List[str]]:
    """
    Compact summary of main trends for quick checking.
    """
    return {
        "reactivity_trend": reactivity_trend_down_group(),
        "boiling_point_trend": boiling_point_trend(),
        "fluoride_formers": ["Kr", "Xe", "Rn"],
    }
