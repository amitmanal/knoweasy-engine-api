"""
Inorganic Chemistry v1 — p-Block Group 15 (Nitrogen family), Deterministic

Group 15 elements (focus):
  N, P, As, Sb, Bi

Scope (LOCKED, exam-safe):
- General outer electronic configuration token
- Common oxidation states (+5, +3, -3) and inert pair effect trend token
- Dominant oxidation state trend (heavier elements favor +3)
- Anomalous behavior token for nitrogen
- Hydrides:
    * stability order (NH3 > PH3 > AsH3 > SbH3 > BiH3)
    * basicity order (NH3 > PH3 > AsH3 > SbH3 > BiH3)
- Oxides acidity tokens:
    * N2O3: acidic_oxide (forms HNO2)
    * N2O5: acidic_oxide (forms HNO3)
    * P4O6: acidic_oxide (forms H3PO3)
    * P4O10: acidic_oxide (forms H3PO4)
- Oxyacids key tokens (nitrogen & phosphorus)
- Allotropy token for phosphorus (white/red/black)

This module is not a full database; it encodes standard NCERT/JEE facts.
"""

from __future__ import annotations


class PBlockGroup15Error(ValueError):
    """Invalid inputs for Group 15 helpers."""


_GROUP15 = ["N", "P", "AS", "SB", "BI"]


def _norm(elem: str) -> str:
    e = (elem or "").strip().upper()
    if not e:
        raise PBlockGroup15Error("Element symbol required.")
    return e


def is_group15(elem: str) -> bool:
    e = _norm(elem)
    return e in _GROUP15


def group15_outer_configuration_token() -> str:
    """
    General outer electronic configuration:
      ns^2 np^3
    """
    return "ns2_np3"


def inert_pair_effect_trend_token() -> str:
    return "inert_pair_effect_increases_down_group"


def common_oxidation_states(elem: str) -> list[int]:
    """
    Exam-safe oxidation states:
    - -3 (especially N, P in hydrides)
    - +3, +5 common
    """
    e = _norm(elem)
    if e not in _GROUP15:
        raise PBlockGroup15Error("Element not supported in Group 15 v1.")
    # All can show +3, +5; -3 more common for N, P, As
    if e in ("N", "P", "AS"):
        return [-3, 3, 5]
    return [3, 5, -3]  # include -3 token for completeness


def dominant_positive_oxidation_state(elem: str) -> int:
    """
    Deterministic dominant positive oxidation state trend:
    - N, P: +5 common
    - As, Sb: +3 and +5 (often +3 more stable down)
    - Bi: +3 dominant (inert pair effect)
    """
    e = _norm(elem)
    if e not in _GROUP15:
        raise PBlockGroup15Error("Element not supported in Group 15 v1.")
    if e == "BI":
        return 3
    if e in ("AS", "SB"):
        return 3
    return 5


def nitrogen_anomalous_behavior_token() -> str:
    """
    Nitrogen shows anomalous behavior due to:
    - small size
    - high electronegativity
    - absence of d-orbitals in valence shell
    """
    return "nitrogen_anomalous_small_size_high_en_no_d_orbitals"


def hydride_stability_order() -> list[str]:
    """
    Stability of hydrides:
      NH3 > PH3 > AsH3 > SbH3 > BiH3
    """
    return ["NH3", "PH3", "ASH3", "SBH3", "BIH3"]


def hydride_basicity_order() -> list[str]:
    """
    Basicity of hydrides generally decreases down the group:
      NH3 > PH3 > AsH3 > SbH3 > BiH3
    """
    return ["NH3", "PH3", "ASH3", "SBH3", "BIH3"]


def compare_hydride_order(h1: str, h2: str, *, kind: str = "stability") -> str:
    """
    kind: "stability" or "basicity"
    Returns:
      "h1_greater" / "h2_greater" / "equal"
    Earlier in list => greater (more stable / more basic).
    """
    k = (kind or "").strip().lower()
    if k not in ("stability", "basicity"):
        raise PBlockGroup15Error("kind must be stability/basicity.")
    order = hydride_stability_order() if k == "stability" else hydride_basicity_order()
    a = (h1 or "").strip().upper()
    b = (h2 or "").strip().upper()
    if a not in order or b not in order:
        raise PBlockGroup15Error("Hydrides must be one of NH3, PH3, AsH3, SbH3, BiH3.")
    i1 = order.index(a)
    i2 = order.index(b)
    if i1 < i2:
        return "h1_greater"
    if i2 < i1:
        return "h2_greater"
    return "equal"


def oxide_acidity_token(oxide: str) -> str:
    """
    Deterministic oxide acidity tokens (common):
    - N2O3, N2O5, P4O6, P4O10 are acidic oxides.
    """
    o = (oxide or "").strip().upper()
    if not o:
        raise PBlockGroup15Error("oxide is required.")
    if o in ("N2O3", "N2O5", "P4O6", "P4O10"):
        return "acidic_oxide"
    raise PBlockGroup15Error("Unsupported oxide token for Group 15 v1.")


def oxyacid_fact_tokens() -> list[str]:
    """
    Key oxyacids tokens for nitrogen & phosphorus:
    """
    return [
        "hno2_is_nitrous_acid_from_n2o3",
        "hno3_is_nitric_acid_from_n2o5",
        "h3po3_is_phosphorous_acid_from_p4o6",
        "h3po4_is_phosphoric_acid_from_p4o10",
        "h3po3_is_dibasic_due_to_two_oh_groups",
        "h3po4_is_tribasic_due_to_three_oh_groups",
    ]


def phosphorus_allotropy_token() -> str:
    """
    Phosphorus exists in allotropes: white, red, black.
    """
    return "phosphorus_allotropes_white_red_black"
