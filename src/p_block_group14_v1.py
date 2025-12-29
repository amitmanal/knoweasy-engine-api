"""
Inorganic Chemistry v1 — p-Block Group 14 (Carbon family), Deterministic

Group 14 elements (focus):
  C, Si, Ge, Sn, Pb

Scope (LOCKED, exam-safe):
- General outer electronic configuration token
- Oxidation states (+4, +2) and inert pair effect trend token
- Dominant oxidation state token logic (down-group +2 becomes more stable)
- Catenation trend (C >> Si > Ge > Sn > Pb)
- Hydride stability trend (CH4 > SiH4 > GeH4 > SnH4 > PbH4)
- Halide stability trend (MCl4 stability decreases down group; MCl2 stability increases)
- Oxides behavior tokens:
    * CO: neutral oxide (reducing nature token)
    * CO2: acidic oxide
    * SiO2: acidic, network solid token
    * SnO/SnO2 and PbO/PbO2 amphoteric tendency token (coarse)

This module is not a full database; it encodes standard NCERT/JEE facts.
"""

from __future__ import annotations


class PBlockGroup14Error(ValueError):
    """Invalid inputs for Group 14 helpers."""


_GROUP14 = ["C", "SI", "GE", "SN", "PB"]


def _norm(elem: str) -> str:
    e = (elem or "").strip().upper()
    if not e:
        raise PBlockGroup14Error("Element symbol required.")
    return e


def is_group14(elem: str) -> bool:
    e = _norm(elem)
    return e in _GROUP14


def group14_outer_configuration_token() -> str:
    """
    General outer electronic configuration:
      ns^2 np^2
    """
    return "ns2_np2"


def common_oxidation_states(elem: str) -> list[int]:
    """
    Deterministic oxidation states (exam-safe):
    - All show +4
    - Heavier members show +2 due to inert pair effect
    """
    e = _norm(elem)
    if e not in _GROUP14:
        raise PBlockGroup14Error("Element not supported in Group 14 v1.")

    if e == "C":
        return [4]
    if e in ("SI", "GE"):
        return [4, 2]  # +2 less common but possible
    return [4, 2]      # Sn, Pb: both common; +2 more stable down group


def inert_pair_effect_trend_token() -> str:
    return "inert_pair_effect_increases_down_group"


def dominant_oxidation_state(elem: str) -> int:
    """
    Dominant oxidation state:
    - C, Si, Ge: +4 dominant
    - Sn, Pb: +2 increasingly dominant (Pb strongly +2)
    """
    e = _norm(elem)
    if e not in _GROUP14:
        raise PBlockGroup14Error("Element not supported in Group 14 v1.")
    if e in ("SN", "PB"):
        return 2
    return 4


def catenation_order() -> list[str]:
    """
    Catenation tendency:
      C >> Si > Ge > Sn > Pb
    """
    return ["C", "SI", "GE", "SN", "PB"]


def is_more_catenation(elem1: str, elem2: str) -> str:
    """
    Returns:
      "elem1_more" / "elem2_more" / "equal"
    Higher in the catenation_order list => more catenation.
    """
    e1 = _norm(elem1)
    e2 = _norm(elem2)
    order = catenation_order()
    if e1 not in order or e2 not in order:
        raise PBlockGroup14Error("Elements must be C/Si/Ge/Sn/Pb.")
    i1 = order.index(e1)
    i2 = order.index(e2)
    if i1 < i2:
        return "elem1_more"
    if i2 < i1:
        return "elem2_more"
    return "equal"


def hydride_stability_order() -> list[str]:
    """
    Stability of hydrides:
      CH4 > SiH4 > GeH4 > SnH4 > PbH4
    """
    return ["CH4", "SIH4", "GEH4", "SNH4", "PBH4"]


def is_more_stable_hydride(h1: str, h2: str) -> str:
    """
    Compare hydride stability in the above order.
    Returns:
      "h1_more_stable" / "h2_more_stable" / "equal"
    """
    order = hydride_stability_order()
    a = (h1 or "").strip().upper()
    b = (h2 or "").strip().upper()
    if a not in order or b not in order:
        raise PBlockGroup14Error("Hydrides must be one of CH4, SiH4, GeH4, SnH4, PbH4.")
    i1 = order.index(a)
    i2 = order.index(b)
    if i1 < i2:
        return "h1_more_stable"
    if i2 < i1:
        return "h2_more_stable"
    return "equal"


def tetrachloride_stability_trend_token() -> str:
    """
    MCl4 stability decreases down the group due to inert pair effect.
    """
    return "mcl4_stability_decreases_down_group"


def dichloride_stability_trend_token() -> str:
    """
    MCl2 stability increases down the group.
    """
    return "mcl2_stability_increases_down_group"


def oxide_behavior_token(oxide: str) -> str:
    """
    Coarse oxide behavior tokens:
    - CO: neutral_oxide_reducing
    - CO2: acidic_oxide
    - SiO2: acidic_network_solid
    - SnO/SnO2: amphoteric (token)
    - PbO/PbO2: amphoteric (token)

    Returns stable token string.
    """
    o = (oxide or "").strip().upper()
    if not o:
        raise PBlockGroup14Error("oxide is required.")

    if o == "CO":
        return "neutral_oxide_reducing"
    if o == "CO2":
        return "acidic_oxide"
    if o == "SIO2":
        return "acidic_network_solid"
    if o in ("SNO", "SNO2"):
        return "amphoteric_oxide"
    if o in ("PBO", "PBO2"):
        return "amphoteric_oxide"

    raise PBlockGroup14Error("Unsupported oxide token for Group 14 v1.")
