"""
Inorganic Chemistry v1 — Periodic Trends (Deterministic)

Scope (LOCKED):
- Directional trend helpers for:
    * Atomic radius
    * Ionic radius (basic)
    * Ionization enthalpy
    * Electron gain enthalpy (electron affinity)
    * Electronegativity
    * Metallic character / Non-metallic character

- Simple comparison based on (period, group) position for main-group elements (s,p block),
  using general NCERT trends (exam-safe).

This module DOES NOT attempt to encode full periodic table data.
It provides rule-based comparisons and monotonicity directions.

Coordinate system:
- period: 1..7
- group: 1..18

Assumptions:
- For trends "across period": left -> right
- For trends "down group": top -> bottom

Returns:
- Strings describing relative direction or comparison result
"""

from __future__ import annotations


class PeriodicTrendsError(ValueError):
    """Invalid inputs for periodic trend helpers."""


def _validate_period_group(period: int, group: int) -> None:
    if not isinstance(period, int) or not isinstance(group, int):
        raise PeriodicTrendsError("period and group must be integers.")
    if period < 1 or period > 7:
        raise PeriodicTrendsError("period must be in 1..7.")
    if group < 1 or group > 18:
        raise PeriodicTrendsError("group must be in 1..18.")


def trend_direction_atomic_radius() -> dict:
    """
    Atomic radius:
    - Across a period: decreases left -> right
    - Down a group: increases top -> bottom
    """
    return {"across_period": "decreases", "down_group": "increases"}


def trend_direction_ionization_enthalpy() -> dict:
    """
    Ionization enthalpy:
    - Across a period: increases left -> right (general)
    - Down a group: decreases top -> bottom (general)
    """
    return {"across_period": "increases", "down_group": "decreases"}


def trend_direction_electronegativity() -> dict:
    """
    Electronegativity:
    - Across a period: increases left -> right (general)
    - Down a group: decreases top -> bottom (general)
    """
    return {"across_period": "increases", "down_group": "decreases"}


def trend_direction_electron_gain_enthalpy() -> dict:
    """
    Electron gain enthalpy (electron affinity, qualitative):
    - Across a period: generally becomes more negative left -> right
    - Down a group: generally becomes less negative down the group
    """
    return {"across_period": "more_negative", "down_group": "less_negative"}


def trend_direction_metallic_character() -> dict:
    """
    Metallic character:
    - Across a period: decreases left -> right
    - Down a group: increases top -> bottom
    """
    return {"across_period": "decreases", "down_group": "increases"}


def compare_atomic_radius(pos1: tuple[int, int], pos2: tuple[int, int]) -> str:
    """
    Compare atomic radius using general trend rules.

    pos = (period, group)

    Returns:
      "pos1_greater" / "pos2_greater" / "approximately_equal"

    Heuristic:
    - Lower group number in same period => larger (more left)
    - Higher period number in same group => larger (more down)
    - If both differ, decide by weighted score:
        radius_score = + (period * 10) - group
      Higher score => larger radius
    """
    p1, g1 = pos1
    p2, g2 = pos2
    _validate_period_group(p1, g1)
    _validate_period_group(p2, g2)

    if p1 == p2 and g1 == g2:
        return "approximately_equal"

    if p1 == p2:
        # same period: left larger
        return "pos1_greater" if g1 < g2 else "pos2_greater"

    if g1 == g2:
        # same group: down larger
        return "pos1_greater" if p1 > p2 else "pos2_greater"

    s1 = p1 * 10 - g1
    s2 = p2 * 10 - g2
    if s1 > s2:
        return "pos1_greater"
    if s2 > s1:
        return "pos2_greater"
    return "approximately_equal"


def compare_ionization_enthalpy(pos1: tuple[int, int], pos2: tuple[int, int]) -> str:
    """
    Compare ionization enthalpy using general trend rules.

    Heuristic:
    - Across a period: increases left -> right
    - Down a group: decreases top -> bottom

    Score:
      ie_score = + group - (period * 10)
      Higher score => higher IE
    """
    p1, g1 = pos1
    p2, g2 = pos2
    _validate_period_group(p1, g1)
    _validate_period_group(p2, g2)

    if p1 == p2 and g1 == g2:
        return "approximately_equal"

    if p1 == p2:
        return "pos1_greater" if g1 > g2 else "pos2_greater"

    if g1 == g2:
        return "pos1_greater" if p1 < p2 else "pos2_greater"

    s1 = g1 - (p1 * 10)
    s2 = g2 - (p2 * 10)
    if s1 > s2:
        return "pos1_greater"
    if s2 > s1:
        return "pos2_greater"
    return "approximately_equal"


def compare_electronegativity(pos1: tuple[int, int], pos2: tuple[int, int]) -> str:
    """
    Compare electronegativity using general trend rules.

    Heuristic:
    - Across period: increases left -> right
    - Down group: decreases down

    Score:
      en_score = + group - (period * 10)
      Higher score => higher EN
    """
    # Same directional heuristic as IE in basic NCERT trends
    return compare_ionization_enthalpy(pos1, pos2)


def compare_metallic_character(pos1: tuple[int, int], pos2: tuple[int, int]) -> str:
    """
    Compare metallic character.

    Heuristic:
    - Across period: decreases left -> right
    - Down group: increases down

    Score:
      metal_score = + (period * 10) - group
      Higher score => more metallic
    """
    return compare_atomic_radius(pos1, pos2)
