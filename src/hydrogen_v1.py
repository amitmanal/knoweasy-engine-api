"""
Inorganic Chemistry v1 — Hydrogen & Its Compounds (Deterministic)

Scope (LOCKED):
1) Isotopes of hydrogen (basic facts)
2) Hydrogen position behavior (alkali-like vs halogen-like) as a rule token
3) Hydrides classification:
   - ionic (saline)
   - covalent (molecular)
   - metallic (interstitial)
4) Water hardness classification (temporary / permanent / none) by salt type tokens
5) Heavy water (D2O) basic differences (token list)
6) Hydrogen peroxide (H2O2) behavior token:
   - oxidizing agent and reducing agent (context-dependent)
   - basic deterministic "role" lookup for typical exam reactions

This module is NOT a reaction balancer.
It provides deterministic classification + common exam facts.
"""

from __future__ import annotations


class HydrogenError(ValueError):
    """Invalid inputs for hydrogen helpers."""


# -------------------------
# Isotopes
# -------------------------

_ISOTOPES = {
    "protium": {"symbol": "1H", "mass_number": 1, "neutrons": 0},
    "deuterium": {"symbol": "2H", "mass_number": 2, "neutrons": 1},
    "tritium": {"symbol": "3H", "mass_number": 3, "neutrons": 2},
}

def hydrogen_isotope(name: str) -> dict:
    n = (name or "").strip().lower()
    if n not in _ISOTOPES:
        raise HydrogenError("Unknown hydrogen isotope. Use protium/deuterium/tritium.")
    return dict(_ISOTOPES[n])


# -------------------------
# Position / behavior token
# -------------------------

def hydrogen_dual_behavior_token() -> str:
    """
    Hydrogen shows dual behavior:
    - resembles alkali metals (forms H+ / electropositive in many contexts)
    - resembles halogens (forms H- in metal hydrides)

    Returns stable token string.
    """
    return "dual_behavior_alkali_like_and_halogen_like"


# -------------------------
# Hydrides classification
# -------------------------

def classify_hydride(compound_token: str) -> str:
    """
    Deterministic classification based on standard NCERT groups:
    - Ionic hydrides: s-block (except Be, Mg) -> e.g., NaH, CaH2
    - Covalent hydrides: p-block / molecular -> e.g., CH4, NH3, H2O
    - Metallic (interstitial): transition metals -> e.g., PdH, TiH2

    Input is a token or formula string; we use simple prefix/rules:
    - If startswith one of: LI, NA, K, RB, CS, CA, SR, BA => ionic
    - If startswith BE or MG => covalent (not ionic in NCERT sense)
    - If startswith typical transition metal tokens => metallic
    Else => covalent (safe default for p-block hydrides).
    """
    s = (compound_token or "").strip().upper()
    if not s:
        raise HydrogenError("compound_token is required.")

    # crude element symbol read: first 1-2 letters (e.g., NaH -> NA)
    # handle 2-letter symbols first
    two = s[:2]
    one = s[:1]

    alkali = {"LI", "NA", "K", "RB", "CS"}
    alkaline = {"CA", "SR", "BA"}
    special = {"BE", "MG"}

    transition = {"TI", "V", "CR", "MN", "FE", "CO", "NI", "CU", "ZN", "PD", "PT", "W", "MO"}

    head = two if two in alkali | alkaline | special | transition else one

    if head in alkali or head in alkaline:
        return "ionic_hydride"
    if head in special:
        return "covalent_hydride"
    if head in transition:
        return "metallic_hydride"

    return "covalent_hydride"


# -------------------------
# Water hardness (token-based)
# -------------------------

def hardness_type(salt_token: str) -> str:
    """
    Deterministic classification:
    - Temporary hardness: bicarbonates of Ca/Mg (e.g., Ca(HCO3)2, Mg(HCO3)2)
    - Permanent hardness: chlorides/sulfates of Ca/Mg (e.g., CaCl2, MgSO4)
    - None/other: token-based fallback

    Input is token string; looks for key substrings.
    Returns: "temporary" | "permanent" | "none"
    """
    s = (salt_token or "").strip().upper()
    if not s:
        raise HydrogenError("salt_token is required.")

    # Temporary hardness: bicarbonate presence and Ca/Mg
    if "HCO3" in s and ("CA" in s or "MG" in s):
        return "temporary"

    # Permanent hardness: chloride or sulfate with Ca/Mg
    if (("CL" in s) or ("SO4" in s)) and ("CA" in s or "MG" in s):
        return "permanent"

    return "none"


# -------------------------
# Heavy water (D2O) facts
# -------------------------

def heavy_water_key_differences() -> list[str]:
    """
    Returns stable list of key differences used in exams.
    """
    return [
        "higher_density_than_h2o",
        "higher_boiling_point_than_h2o",
        "lower_degree_of_ionization_than_h2o",
        "used_as_moderator_in_nuclear_reactors",
    ]


# -------------------------
# Hydrogen peroxide behavior tokens
# -------------------------

def h2o2_role_token(medium: str, reaction_token: str) -> str:
    """
    Returns whether H2O2 acts as oxidizing or reducing agent in common exam contexts.

    medium: "acidic" | "basic" | "neutral"
    reaction_token: simple token hint, e.g.
      - "with_kmno4"
      - "with_k2cr2o7"
      - "with_cl2"
      - "with_iodide"
      - "self_decomposition"

    Deterministic simplified rules:
    - With KMnO4 in acidic medium: H2O2 is reducing agent (it reduces MnO4- to Mn2+)
    - With I- (iodide) in acidic medium: H2O2 is oxidizing agent (I- to I2)
    - With Cl2 in water/neutral: H2O2 reduces Cl2 to Cl- (reducing agent)
    - Self decomposition: disproportionation; return "both"
    """
    m = (medium or "").strip().lower()
    if m not in ("acidic", "basic", "neutral"):
        raise HydrogenError("medium must be acidic/basic/neutral.")
    rt = (reaction_token or "").strip().lower()
    if not rt:
        raise HydrogenError("reaction_token is required.")

    if rt == "self_decomposition":
        return "both"

    if rt == "with_kmno4":
        return "reducing_agent" if m == "acidic" else "oxidizing_agent"

    if rt == "with_iodide":
        return "oxidizing_agent"

    if rt == "with_cl2":
        return "reducing_agent"

    # default: H2O2 is a strong oxidizer in many contexts
    return "oxidizing_agent"
