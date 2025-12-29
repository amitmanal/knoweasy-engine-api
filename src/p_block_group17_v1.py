# src/p_block_group17_v1.py
"""
KnowEasy Engine v1 — p-Block Group 17 (Halogens) — v1 (Deterministic)

Scope (LOCKED):
- Configuration (ns² np⁵)
- Oxidation states + exceptions
- Anomalous behavior of fluorine
- Interhalogen compounds
- Oxoacids of halogens
- Halogen displacement reactions
- Reactivity trends

Design goals:
- Deterministic, exam-safe, explainable outputs
- No external dependencies
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional


HALOGENS: Tuple[str, ...] = ("F", "Cl", "Br", "I")
# (At is typically outside Class 11–12 exam focus; keep core four.)


def group17_general_configuration() -> str:
    """General valence shell configuration for Group 17."""
    return "ns2 np5"


def halogens_list() -> List[str]:
    return list(HALOGENS)


def common_oxidation_states(element: str) -> List[int]:
    """
    Returns common oxidation states for a given halogen (exam-safe).
    Notes:
    - All: -1 common
    - F: only -1 (never positive in compounds) and 0 in F2
    - Cl/Br/I: -1, 0, +1, +3, +5, +7
    """
    e = element.strip().capitalize()
    if e == "F":
        return [-1, 0]
    if e in ("Cl", "Br", "I"):
        return [-1, 0, +1, +3, +5, +7]
    raise ValueError(f"Unsupported element for Group 17 v1: {element!r}")


def fluorine_anomalies() -> List[str]:
    """
    Key anomalous behaviors of fluorine (relative to other halogens).
    Deterministic bullets used in explanations.
    """
    return [
        "Smallest size and highest electronegativity",
        "Shows only −1 oxidation state in compounds (no positive oxidation states)",
        "Does not show d-orbital expansion (no valence d orbitals in 2nd period)",
        "Strongest oxidizing agent among halogens (F2)",
        "Forms strong H–F bond; HF is weak acid compared to HCl/HBr/HI",
        "Shows strong hydrogen bonding in HF (higher boiling point than expected)",
        "Does not form oxoacids like HOF/HOCl series in the same stable way as others (oxides/oxoacids chemistry is limited)",
    ]


def hydrogen_halide_acid_strength_order() -> List[str]:
    """
    Increasing acidic strength in water (standard exam order).
    HF is weakest due to strong H–F bond and H-bonding; HI strongest.
    """
    return ["HF", "HCl", "HBr", "HI"]


def oxidizing_power_order() -> List[str]:
    """
    Oxidizing power of halogens (strongest to weakest) in aqueous solution.
    Standard: F2 > Cl2 > Br2 > I2
    """
    return ["F2", "Cl2", "Br2", "I2"]


def reducing_power_of_halide_order() -> List[str]:
    """
    Reducing power of halide ions (strongest to weakest).
    I- > Br- > Cl- > F-
    """
    return ["I-", "Br-", "Cl-", "F-"]


def reactivity_order_halogen_displacement() -> List[str]:
    """
    Reactivity order for displacement reactions: higher oxidizing halogen displaces lower halide.
    F2 > Cl2 > Br2 > I2
    """
    return ["F2", "Cl2", "Br2", "I2"]


def can_halogen_displace(halogen: str, halide_ion: str) -> bool:
    """
    Determines if a halogen (X2) can displace a halide ion (Y-) from solution.

    Rule (exam-safe):
      A more reactive halogen oxidizes a less reactive halide:
        X2 + 2Y- -> 2X- + Y2  if X2 is above Y2 in reactivity order.

    Inputs:
      halogen: "Cl2", "Br2", "I2", "F2"
      halide_ion: "Cl-", "Br-", "I-", "F-"
    """
    h = halogen.strip().upper()
    y = halide_ion.strip().upper()

    order = reactivity_order_halogen_displacement()  # ["F2","Cl2","Br2","I2"] but mixed case
    order_u = [s.upper() for s in order]

    if h not in order_u:
        raise ValueError(f"Unsupported halogen for displacement: {halogen!r}")
    if y not in ("F-", "CL-", "BR-", "I-"):
        raise ValueError(f"Unsupported halide ion for displacement: {halide_ion!r}")

    # Map halide ion to corresponding halogen molecule label
    ion_to_halogen = {"F-": "F2", "CL-": "CL2", "BR-": "BR2", "I-": "I2"}
    y2 = ion_to_halogen[y]

    return order_u.index(h) < order_u.index(y2)


def displacement_reaction_products(halogen: str, halide_ion: str) -> Optional[Dict[str, str]]:
    """
    If displacement is possible, returns products mapping:
      {"formed_halide": "X-", "liberated_halogen": "Y2"}
    else returns None.
    """
    if not can_halogen_displace(halogen, halide_ion):
        return None
    h = halogen.strip().upper()  # e.g., CL2
    y = halide_ion.strip().upper()  # e.g., BR-
    # formed halide is X-
    formed = h.replace("2", "") + "-"  # CL-
    # liberated halogen is Y2
    ion_to_halogen = {"F-": "F2", "CL-": "CL2", "BR-": "BR2", "I-": "I2"}
    liberated = ion_to_halogen[y]
    # normalize symbols back to typical capitalization
    normalize = {"F2": "F2", "CL2": "Cl2", "BR2": "Br2", "I2": "I2",
                 "F-": "F-", "CL-": "Cl-", "BR-": "Br-", "I-": "I-"}
    return {
        "formed_halide": normalize.get(formed, formed),
        "liberated_halogen": normalize.get(liberated, liberated),
    }


@dataclass(frozen=True)
class Interhalogen:
    formula: str
    type: str  # XY, XY3, XY5, XY7
    central_atom: str
    ligands: Tuple[str, ...]


def interhalogen_possible(central: str, ligand: str, kind: str) -> bool:
    """
    Determines if an interhalogen of the form XY_n is plausible (exam-safe).
    Rules:
    - Central atom is the larger, less electronegative halogen (typically Cl/Br/I).
    - Ligand is smaller/more electronegative (typically F, sometimes Cl as ligand to Br/I).
    - Known common types: XY, XY3, XY5, XY7 (XY7 mainly for iodine: IF7).
    """
    c = central.strip().capitalize()
    l = ligand.strip().capitalize()
    k = kind.strip().upper()

    if c not in HALOGENS or l not in HALOGENS or c == l:
        return False
    if k not in ("XY", "XY3", "XY5", "XY7"):
        return False

    # Basic size/EN heuristic: F is best ligand; iodine best central.
    # Permit typical exam set:
    allowed = {
        # XY
        ("Cl", "F", "XY"), ("Br", "F", "XY"), ("I", "F", "XY"),
        ("Br", "Cl", "XY"), ("I", "Cl", "XY"), ("I", "Br", "XY"),
        # XY3
        ("Cl", "F", "XY3"), ("Br", "F", "XY3"), ("I", "F", "XY3"),
        # XY5
        ("Br", "F", "XY5"), ("I", "F", "XY5"),
        # XY7
        ("I", "F", "XY7"),
    }
    return (c, l, k) in allowed


def build_interhalogen(central: str, ligand: str, kind: str) -> Interhalogen:
    """
    Builds a known interhalogen compound representation (deterministic).
    Raises ValueError if not supported by v1 rules.
    """
    if not interhalogen_possible(central, ligand, kind):
        raise ValueError(f"Unsupported interhalogen request: central={central!r}, ligand={ligand!r}, kind={kind!r}")

    c = central.strip().capitalize()
    l = ligand.strip().capitalize()
    k = kind.strip().upper()

    if k == "XY":
        formula = f"{c}{l}"
        ligands = (l,)
    elif k == "XY3":
        formula = f"{c}{l}3"
        ligands = (l, l, l)
    elif k == "XY5":
        formula = f"{c}{l}5"
        ligands = (l, l, l, l, l)
    else:  # XY7
        formula = f"{c}{l}7"
        ligands = (l, l, l, l, l, l, l)

    return Interhalogen(formula=formula, type=k, central_atom=c, ligands=ligands)


def oxoacids_of_halogens(halogen: str) -> List[Dict[str, object]]:
    """
    Returns common oxoacids for Cl/Br/I (exam-safe set).
    Fluorine oxoacids are generally not included in standard Class 11–12 due to instability/limited chemistry.

    For Cl (similar pattern for Br, I):
      HOX   : +1
      HXO2  : +3
      HXO3  : +5
      HXO4  : +7
    """
    x = halogen.strip().capitalize()
    if x == "F":
        return []  # exam-safe: treat as none for v1

    if x not in ("Cl", "Br", "I"):
        raise ValueError(f"Unsupported element for oxoacids: {halogen!r}")

    # Use generic placeholders expanded per halogen
    if x == "Cl":
        return [
            {"acid": "HOCl", "oxidation_state": +1, "name": "Hypochlorous acid"},
            {"acid": "HClO2", "oxidation_state": +3, "name": "Chlorous acid"},
            {"acid": "HClO3", "oxidation_state": +5, "name": "Chloric acid"},
            {"acid": "HClO4", "oxidation_state": +7, "name": "Perchloric acid"},
        ]
    if x == "Br":
        return [
            {"acid": "HOBr", "oxidation_state": +1, "name": "Hypobromous acid"},
            {"acid": "HBrO2", "oxidation_state": +3, "name": "Bromous acid"},
            {"acid": "HBrO3", "oxidation_state": +5, "name": "Bromic acid"},
            {"acid": "HBrO4", "oxidation_state": +7, "name": "Perbromic acid"},
        ]
    # I
    return [
        {"acid": "HOI", "oxidation_state": +1, "name": "Hypoiodous acid"},
        {"acid": "HIO2", "oxidation_state": +3, "name": "Iodous acid"},
        {"acid": "HIO3", "oxidation_state": +5, "name": "Iodic acid"},
        {"acid": "HIO4", "oxidation_state": +7, "name": "Periodic acid"},
    ]


def oxoacid_strength_trend_for_fixed_halogen(halogen: str) -> List[str]:
    """
    For a fixed halogen X, acidity increases with oxidation state:
      HOX < HXO2 < HXO3 < HXO4
    Returns the acids in increasing strength order.
    """
    acids = oxoacids_of_halogens(halogen)
    if not acids:
        return []
    # Already in increasing oxidation state order in our tables
    return [d["acid"] for d in acids]


def oxoacid_strength_trend_same_oxidation_state(oxoacid_across_halogen: str) -> List[str]:
    """
    For same oxidation state (e.g., HOX), acidity increases with electronegativity of X:
      HOI < HOBr < HOCl  (HF not used here)
    Input:
      "HOX" for +1 series,
      "HXO2" for +3 series,
      "HXO3" for +5 series,
      "HXO4" for +7 series.
    """
    key = oxoacid_across_halogen.strip().upper()
    if key not in ("HOX", "HXO2", "HXO3", "HXO4"):
        raise ValueError(f"Unsupported oxoacid series key: {oxoacid_across_halogen!r}")

    if key == "HOX":
        return ["HOI", "HOBr", "HOCl"]
    if key == "HXO2":
        return ["HIO2", "HBrO2", "HClO2"]
    if key == "HXO3":
        return ["HIO3", "HBrO3", "HClO3"]
    return ["HIO4", "HBrO4", "HClO4"]


def halogen_reactivity_trends_summary() -> Dict[str, List[str]]:
    """
    Returns a compact, exam-oriented trends summary.
    """
    return {
        "oxidizing_power": oxidizing_power_order(),
        "halogen_displacement_reactivity": reactivity_order_halogen_displacement(),
        "halide_reducing_power": reducing_power_of_halide_order(),
        "hydrogen_halide_acid_strength": hydrogen_halide_acid_strength_order(),
    }
