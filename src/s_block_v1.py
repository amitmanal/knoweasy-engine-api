"""
Inorganic Chemistry v1 — s-Block Elements (Deterministic)

Scope (LOCKED):
- Alkali metals (Group 1): Li, Na, K, Rb, Cs
- Alkaline earth metals (Group 2): Be, Mg, Ca, Sr, Ba
- Deterministic helpers:
  1) Identify group (1 or 2)
  2) Flame test colors (exam-safe lookup)
  3) Reactivity with water (qualitative: none/slow/fast/violent)
  4) Oxides formed with oxygen (typical exam products)
  5) Simple trend comparisons within group (reactivity increases down)

Notes:
- Be and Mg are special (slow/no reaction with cold water).
- Li shows some anomalous behavior; we keep rules exam-safe.
- This module is NOT a full inorganic database; it encodes standard NCERT/JEE facts.
"""

from __future__ import annotations


class SBlockError(ValueError):
    """Invalid inputs for s-block helpers."""


_ALKALI = ["LI", "NA", "K", "RB", "CS"]
_ALKALINE_EARTH = ["BE", "MG", "CA", "SR", "BA"]

# Flame test colors (standard exam-safe)
_FLAME_COLORS = {
    "LI": "crimson_red",
    "NA": "golden_yellow",
    "K": "lilac",
    "RB": "red_violet",
    "CS": "blue",
    "CA": "brick_red",
    "SR": "crimson_red",
    "BA": "apple_green",
    # Mg/Be typically no characteristic flame color in basic tests
}

def _norm(elem: str) -> str:
    e = (elem or "").strip().upper()
    if len(e) == 0:
        raise SBlockError("Element symbol is required.")
    return e


def is_s_block_element(elem: str) -> bool:
    e = _norm(elem)
    return e in _ALKALI or e in _ALKALINE_EARTH


def group_of_s_block(elem: str) -> int:
    e = _norm(elem)
    if e in _ALKALI:
        return 1
    if e in _ALKALINE_EARTH:
        return 2
    raise SBlockError("Element is not supported in s-block v1.")


def flame_test_color(elem: str) -> str:
    """
    Returns a deterministic token string for flame color.

    Raises if element has no standard flame color in this v1 table.
    """
    e = _norm(elem)
    if e not in _FLAME_COLORS:
        raise SBlockError("No standard flame test color in v1 for this element.")
    return _FLAME_COLORS[e]


def reactivity_with_water(elem: str, water_temp: str = "cold") -> str:
    """
    Qualitative reactivity with water:
    Returns one of:
      "no_reaction", "very_slow", "slow", "fast", "violent"

    water_temp: "cold" or "hot" (steam is not modeled separately in v1)
    """
    e = _norm(elem)
    wt = (water_temp or "").strip().lower()
    if wt not in ("cold", "hot"):
        raise SBlockError("water_temp must be 'cold' or 'hot'.")

    # Group 1: generally vigorous, increases down
    if e in _ALKALI:
        if e == "LI":
            return "slow"
        if e == "NA":
            return "fast"
        # K, Rb, Cs
        return "violent"

    # Group 2: Be none, Mg slow (hot water faster), Ca/Sr/Ba react
    if e == "BE":
        return "no_reaction"
    if e == "MG":
        return "very_slow" if wt == "cold" else "slow"
    if e == "CA":
        return "slow" if wt == "cold" else "fast"
    if e == "SR":
        return "fast"
    if e == "BA":
        return "violent"

    raise SBlockError("Element is not supported in s-block v1.")


def oxide_formed_in_oxygen(elem: str) -> str:
    """
    Typical oxide products in oxygen (exam-safe, simplified):
    Group 1:
      Li -> normal oxide (Li2O)
      Na -> peroxide (Na2O2) (often emphasized)
      K/Rb/Cs -> superoxide (MO2)
    Group 2:
      Mainly normal oxides (MO), BeO, MgO, CaO, SrO, BaO
    Returns token:
      "normal_oxide", "peroxide", "superoxide"
    """
    e = _norm(elem)

    if e in _ALKALI:
        if e == "LI":
            return "normal_oxide"
        if e == "NA":
            return "peroxide"
        return "superoxide"

    if e in _ALKALINE_EARTH:
        return "normal_oxide"

    raise SBlockError("Element is not supported in s-block v1.")


def is_more_reactive_down_group(elem_upper: str, elem_lower: str) -> bool:
    """
    Returns True if elem_lower is below elem_upper in the SAME s-block group,
    hence generally more reactive (basic trend rule).
    """
    e1 = _norm(elem_upper)
    e2 = _norm(elem_lower)

    g1 = group_of_s_block(e1)
    g2 = group_of_s_block(e2)
    if g1 != g2:
        raise SBlockError("Elements must be from the same s-block group for comparison.")

    seq = _ALKALI if g1 == 1 else _ALKALINE_EARTH
    i1 = seq.index(e1)
    i2 = seq.index(e2)
    return i2 > i1
