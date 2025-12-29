# src/f_block_v1.py
"""
KnowEasy Engine v1 — f-Block Elements — v1 (Deterministic)

Scope (LOCKED, exam-safe):
- Lanthanides & Actinides overview
- Electronic configuration
- Oxidation states (common)
- Lanthanide contraction (cause + consequences)
- Colour & magnetic properties (qualitative)
- Actinide radioactivity basics

Design:
- Deterministic facts only
- Minimal logic
- No external dependencies
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple


LANthanides: Tuple[str, ...] = (
    "La", "Ce", "Pr", "Nd", "Pm", "Sm", "Eu",
    "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu"
)

ACTINIDES: Tuple[str, ...] = (
    "Ac", "Th", "Pa", "U", "Np", "Pu", "Am",
    "Cm", "Bk", "Cf", "Es", "Fm", "Md", "No", "Lr"
)


def lanthanides_list() -> List[str]:
    return list(LANthanides)


def actinides_list() -> List[str]:
    return list(ACTINIDES)


def f_block_general_configuration() -> str:
    """
    General electronic configuration for f-block elements.
    """
    return "(n−2)f1–14 (n−1)d0–1 ns2"


def lanthanide_common_oxidation_states() -> Dict[str, List[int]]:
    """
    Exam-safe common oxidation states.
    +3 is most common; +2 and +4 occur for some.
    """
    return {
        "La": [+3],
        "Ce": [+3, +4],
        "Pr": [+3, +4],
        "Nd": [+3],
        "Pm": [+3],
        "Sm": [+2, +3],
        "Eu": [+2, +3],
        "Gd": [+3],
        "Tb": [+3, +4],
        "Dy": [+3],
        "Ho": [+3],
        "Er": [+3],
        "Tm": [+3],
        "Yb": [+2, +3],
        "Lu": [+3],
    }


def actinide_common_oxidation_states() -> Dict[str, List[int]]:
    """
    Exam-safe oxidation states for actinides (variable).
    """
    return {
        "Ac": [+3],
        "Th": [+4],
        "Pa": [+5],
        "U": [+3, +4, +5, +6],
        "Np": [+3, +4, +5, +6, +7],
        "Pu": [+3, +4, +5, +6],
        "Am": [+3, +4, +5, +6],
        "Cm": [+3],
        "Bk": [+3, +4],
        "Cf": [+3],
        "Es": [+3],
        "Fm": [+3],
        "Md": [+3],
        "No": [+2, +3],
        "Lr": [+3],
    }


def lanthanide_contraction_cause() -> List[str]:
    """
    Cause of lanthanide contraction.
    """
    return [
        "Poor shielding effect of 4f electrons",
        "Increase in effective nuclear charge across the series",
    ]


def lanthanide_contraction_consequences() -> List[str]:
    """
    Standard exam consequences.
    """
    return [
        "Decrease in atomic and ionic radii from La to Lu",
        "Similarity between 4d and 5d transition elements",
        "Difficulty in separation of lanthanides",
        "Increase in covalent character of compounds",
    ]


def colour_property(series: str) -> str:
    """
    Colour origin summary.
    """
    s = series.strip().lower()
    if s == "lanthanides":
        return "Mostly coloured due to f–f transitions (except f0 or f14)"
    if s == "actinides":
        return "Mostly coloured due to f–f and charge transfer transitions"
    raise ValueError(f"Unsupported series for colour property: {series!r}")


def magnetic_property(series: str) -> str:
    """
    Magnetic behavior summary.
    """
    s = series.strip().lower()
    if s == "lanthanides":
        return "Generally paramagnetic due to unpaired 4f electrons"
    if s == "actinides":
        return "Paramagnetic; more complex due to actinide bonding"
    raise ValueError(f"Unsupported series for magnetic property: {series!r}")


def radioactivity_notes() -> List[str]:
    """
    Actinide radioactivity basics.
    """
    return [
        "All actinides are radioactive",
        "Radioactivity increases with atomic number",
        "Most actinides are synthetic beyond uranium",
    ]


def f_block_summary() -> Dict[str, List[str]]:
    """
    Compact summary for verification.
    """
    return {
        "lanthanides": lanthanides_list(),
        "actinides": actinides_list(),
        "key_feature": ["Lanthanide contraction", "Variable oxidation states"],
    }
