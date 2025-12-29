"""
Inorganic Chemistry v1 — p-Block Group 16 (Oxygen family), Deterministic

Group 16 elements (focus):
  O, S, Se, Te, Po

Scope (LOCKED, exam-safe):
- General outer electronic configuration token
- Common oxidation states tokens
- Anomalous behavior token for oxygen
- Hydrides (H2O -> H2Po) trends:
    * acidity increases down group
    * thermal stability decreases down group
- Oxides behavior trend token (acidic character increases left->right; within group basicity increases down)
  (We provide a simple within-group "more acidic / more basic" token helper)
- Ozone (O3): structure/oxidizing token
- Sulfur allotropy tokens (rhombic/monoclinic)
- Oxyacids tokens for sulfur: H2SO3 (sulfurous) / H2SO4 (sulfuric)

This module is not a full DB; it encodes standard NCERT/JEE facts.
"""

from __future__ import annotations


class PBlockGroup16Error(ValueError):
    """Invalid inputs for Group 16 helpers."""


_GROUP16 = ["O", "S", "SE", "TE", "PO"]


def _norm(elem: str) -> str:
    e = (elem or "").strip().upper()
    if not e:
        raise PBlockGroup16Error("Element symbol required.")
    return e


def is_group16(elem: str) -> bool:
    e = _norm(elem)
    return e in _GROUP16


def group16_outer_configuration_token() -> str:
    """
    General outer electronic configuration:
      ns^2 np^4
    """
    return "ns2_np4"


def common_oxidation_states(elem: str) -> list[int]:
    """
    Exam-safe oxidation states:
    - -2 most common
    - +4 and +6 common for S, Se, Te
    Oxygen shows -2, -1 (peroxides), +2 (OF2) in special cases (tokenized here as +2 possibility)
    """
    e = _norm(elem)
    if e not in _GROUP16:
        raise PBlockGroup16Error("Element not supported in Group 16 v1.")

    if e == "O":
        return [-2, -1, 2]
    if e == "S":
        return [-2, 4, 6]
    if e == "SE":
        return [-2, 4, 6]
    if e == "TE":
        return [-2, 4, 6]
    # Po commonly +2, +4 too; keep exam-safe
    return [-2, 2, 4]


def oxygen_anomalous_behavior_token() -> str:
    """
    Oxygen anomalous behavior due to:
    - small size
    - high electronegativity
    - absence of d-orbitals
    -> strong H-bonding, O=O multiple bonding behavior differences vs sulfur, etc.
    """
    return "oxygen_anomalous_small_size_high_en_no_d_orbitals"


def hydride_acidity_order() -> list[str]:
    """
    Acidic strength of hydrides increases down group:
      H2O < H2S < H2Se < H2Te < H2Po
    """
    return ["H2O", "H2S", "H2SE", "H2TE", "H2PO"]


def hydride_thermal_stability_order() -> list[str]:
    """
    Thermal stability decreases down group:
      H2O > H2S > H2Se > H2Te > H2Po
    """
    return ["H2O", "H2S", "H2SE", "H2TE", "H2PO"]


def compare_hydride_order(h1: str, h2: str, *, kind: str = "acidity") -> str:
    """
    kind: "acidity" or "thermal_stability"
    Returns:
      "h1_greater" / "h2_greater" / "equal"

    For acidity: later in list is stronger acid.
    For thermal_stability: earlier in list is more stable.
    """
    k = (kind or "").strip().lower()
    if k not in ("acidity", "thermal_stability"):
        raise PBlockGroup16Error("kind must be acidity/thermal_stability.")
    order = hydride_acidity_order() if k == "acidity" else hydride_thermal_stability_order()
    a = (h1 or "").strip().upper()
    b = (h2 or "").strip().upper()
    if a not in order or b not in order:
        raise PBlockGroup16Error("Hydrides must be one of H2O, H2S, H2Se, H2Te, H2Po.")
    i1 = order.index(a)
    i2 = order.index(b)

    if k == "acidity":
        if i1 > i2:
            return "h1_greater"
        if i2 > i1:
            return "h2_greater"
        return "equal"

    # thermal stability: smaller index is greater stability
    if i1 < i2:
        return "h1_greater"
    if i2 < i1:
        return "h2_greater"
    return "equal"


def oxide_trend_token_within_group() -> str:
    """
    Within the group, metallic character increases down,
    so oxides become less acidic / more basic down the group (coarse trend).
    """
    return "oxides_become_more_basic_down_group16"


def ozone_fact_tokens() -> list[str]:
    """
    Ozone (O3) key tokens:
    - bent structure
    - resonance
    - strong oxidizing agent
    """
    return [
        "ozone_is_bent",
        "ozone_has_resonance_structures",
        "ozone_is_strong_oxidizing_agent",
    ]


def sulfur_allotropy_tokens() -> list[str]:
    """
    Sulfur allotropes: rhombic and monoclinic (common Class 11).
    """
    return [
        "sulfur_allotrope_rhombic",
        "sulfur_allotrope_monoclinic",
    ]


def sulfur_oxyacid_tokens() -> list[str]:
    """
    Key oxyacids tokens:
    - H2SO3: sulfurous acid (from SO2)
    - H2SO4: sulfuric acid (from SO3)
    """
    return [
        "h2so3_sulfurous_acid_from_so2",
        "h2so4_sulfuric_acid_from_so3",
        "h2so4_is_strong_dibasic_acid",
    ]
