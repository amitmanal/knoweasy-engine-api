"""
Inorganic Chemistry v1 — p-Block Group 13 (Boron family), Deterministic

Group 13 elements (Class 11/12 focus):
  B, Al, Ga, In, Tl

Scope (LOCKED, exam-safe):
- General outer electronic configuration token
- Common oxidation states + inert pair effect trend token
- Nature of compounds (covalent/ionic tendency) token
- Diagonal relationship token (B ~ Si)
- Boron halides Lewis acidity trend (BF3 < BCl3 < BBr3 < BI3)
- Diborane (B2H6) bonding token (3c-2e)
- Key borax/boric acid identifiers (fact tokens)

This module is NOT a full chemistry DB; it encodes standard NCERT/JEE facts.
"""

from __future__ import annotations


class PBlockGroup13Error(ValueError):
    """Invalid inputs for Group 13 helpers."""


_GROUP13 = ["B", "AL", "GA", "IN", "TL"]


def _norm(elem: str) -> str:
    e = (elem or "").strip().upper()
    if not e:
        raise PBlockGroup13Error("Element symbol required.")
    return e


def is_group13(elem: str) -> bool:
    e = _norm(elem)
    return e in _GROUP13


def group13_outer_configuration_token() -> str:
    """
    General outer electronic configuration:
      ns^2 np^1
    """
    return "ns2_np1"


def common_oxidation_states(elem: str) -> list[int]:
    """
    Deterministic oxidation states (exam-safe):
    - B, Al: +3 dominant
    - Ga, In: +3 and +1 possible
    - Tl: +1 dominant, +3 possible (inert pair effect strong)
    """
    e = _norm(elem)
    if e not in _GROUP13:
        raise PBlockGroup13Error("Element not supported in Group 13 v1.")

    if e in ("B", "AL"):
        return [3]
    if e in ("GA", "IN"):
        return [3, 1]
    if e == "TL":
        return [1, 3]
    return [3]


def inert_pair_effect_trend_token() -> str:
    """
    Inert pair effect increases down the group.
    """
    return "inert_pair_effect_increases_down_group"


def dominant_oxidation_state(elem: str) -> int:
    """
    Dominant oxidation state:
    - B, Al, Ga, In -> +3
    - Tl -> +1
    """
    e = _norm(elem)
    if e not in _GROUP13:
        raise PBlockGroup13Error("Element not supported in Group 13 v1.")
    return 1 if e == "TL" else 3


def diagonal_relationship_tokens() -> list[str]:
    """
    Key diagonal relationship in this area:
      Boron ~ Silicon
    """
    return ["B_similar_to_Si_diagonal_relationship"]


def boron_trihalide_lewis_acidity_order() -> list[str]:
    """
    Lewis acidity:
      BF3 < BCl3 < BBr3 < BI3
    (Back bonding strongest in BF3 reduces acidity)
    """
    return ["BF3", "BCL3", "BBR3", "BI3"]


def is_stronger_lewis_acid_boron_trihalide(halide1: str, halide2: str) -> str:
    """
    Compare two boron trihalides from set {BF3, BCl3, BBr3, BI3}.
    Returns:
      "halide1_stronger" / "halide2_stronger" / "equal"
    """
    order = boron_trihalide_lewis_acidity_order()
    h1 = (halide1 or "").strip().upper()
    h2 = (halide2 or "").strip().upper()
    if h1 not in order or h2 not in order:
        raise PBlockGroup13Error("Halides must be one of BF3, BCl3, BBr3, BI3.")
    i1 = order.index(h1)
    i2 = order.index(h2)
    # later in list is stronger acid
    if i1 > i2:
        return "halide1_stronger"
    if i2 > i1:
        return "halide2_stronger"
    return "equal"


def diborane_bonding_token() -> str:
    """
    Diborane contains 3-center-2-electron (banana) bonds.
    """
    return "diborane_has_3c_2e_bridges"


def borax_fact_tokens() -> list[str]:
    """
    Borax (Na2B4O7·10H2O) key exam identifiers.
    """
    return [
        "borax_formula_na2b4o7_10h2o",
        "borax_is_sodium_tetraborate_decahydrate",
        "borax_forms_metaborate_and_boric_acid_on_acidification",
    ]


def boric_acid_fact_tokens() -> list[str]:
    """
    Boric acid (H3BO3) key exam identifiers.
    """
    return [
        "boric_acid_formula_h3bo3",
        "boric_acid_is_weak_monobasic_lewis_acid",
        "boric_acid_acts_as_lewis_acid_by_accepting_oh_minus",
    ]
