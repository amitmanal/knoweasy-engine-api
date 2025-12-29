"""
Surface Chemistry v1 — Deterministic utilities (JEE + NEET)

Scope (LOCKED):
- Adsorption classification helpers (physisorption vs chemisorption) as rule checks
- Freundlich adsorption isotherm:
    x/m = k * P^(1/n)   (gas on solid)  [also used with concentration C in solutions]
    log(x/m) = log k + (1/n) log P
- Langmuir adsorption isotherm (classic form):
    theta = (b P) / (1 + b P)
- Simple colloid rules:
    - Hardy–Schulze rule: coagulating power increases with valency of oppositely charged ions.
      We implement deterministic comparison based on valency.

No curve fitting. No experimental inference. Pure formula helpers.
"""

from __future__ import annotations

import math
from typing import Literal


class SurfaceChemistryError(ValueError):
    """Raised when invalid inputs are provided to surface chemistry helpers."""


AdsorptionType = Literal["physisorption", "chemisorption"]


def _ensure_finite_number(x: float, name: str) -> None:
    if x is None:
        raise SurfaceChemistryError(f"{name} must not be None.")
    if isinstance(x, float) and x != x:
        raise SurfaceChemistryError(f"{name} must be a finite number (not NaN).")


def _validate_positive(x: float, name: str) -> None:
    _ensure_finite_number(x, name)
    if x <= 0:
        raise SurfaceChemistryError(f"{name} must be > 0.")


def classify_adsorption(
    heat_of_adsorption_kj_per_mol: float,
    is_reversible: bool,
    is_specific: bool,
) -> AdsorptionType:
    """
    Deterministic rule-based classification (exam-style heuristics):

    - Physisorption: low heat (~< 40 kJ/mol), reversible, non-specific.
    - Chemisorption: higher heat, usually irreversible, specific.

    If inputs are mixed, we choose based on stronger signal:
      high heat or specific -> chemisorption else physisorption.
    """
    _ensure_finite_number(heat_of_adsorption_kj_per_mol, "heat_of_adsorption_kj_per_mol")
    if heat_of_adsorption_kj_per_mol < 0:
        raise SurfaceChemistryError("heat_of_adsorption_kj_per_mol must be >= 0.")

    if heat_of_adsorption_kj_per_mol >= 40.0:
        return "chemisorption"
    if is_specific:
        return "chemisorption"
    if is_reversible and not is_specific and heat_of_adsorption_kj_per_mol <= 40.0:
        return "physisorption"
    return "physisorption"


# -------------------------
# Freundlich isotherm
# -------------------------

def freundlich_x_over_m(k: float, pressure_or_conc: float, n: float) -> float:
    """
    Freundlich:
      x/m = k * P^(1/n)

    Args:
      k > 0
      pressure_or_conc > 0
      n > 0
    """
    _validate_positive(k, "k")
    _validate_positive(pressure_or_conc, "pressure_or_conc")
    _validate_positive(n, "n")
    return k * (pressure_or_conc ** (1.0 / n))


def freundlich_log_form(k: float, pressure_or_conc: float, n: float) -> tuple[float, float]:
    """
    Returns (log10(x/m), log10(P)) using:
      log10(x/m) = log10(k) + (1/n) * log10(P)
    """
    _validate_positive(k, "k")
    _validate_positive(pressure_or_conc, "pressure_or_conc")
    _validate_positive(n, "n")
    log_p = math.log10(pressure_or_conc)
    log_xm = math.log10(k) + (1.0 / n) * log_p
    return (log_xm, log_p)


# -------------------------
# Langmuir isotherm
# -------------------------

def langmuir_theta(b: float, pressure: float) -> float:
    """
    Langmuir:
      theta = (bP) / (1 + bP)

    Args:
      b >= 0, pressure >= 0
    Returns:
      theta in [0,1)
    """
    _ensure_finite_number(b, "b")
    _ensure_finite_number(pressure, "pressure")
    if b < 0:
        raise SurfaceChemistryError("b must be >= 0.")
    if pressure < 0:
        raise SurfaceChemistryError("pressure must be >= 0.")
    bp = b * pressure
    return bp / (1.0 + bp) if (1.0 + bp) != 0 else 0.0


# -------------------------
# Colloids: Hardy–Schulze rule
# -------------------------

def compare_coagulating_power(valency_ion1: int, valency_ion2: int) -> str:
    """
    Hardy–Schulze rule (deterministic):
      Higher valency of oppositely charged ion => greater coagulating power.

    Returns:
      "ion1_stronger" / "ion2_stronger" / "equal"
    """
    if not isinstance(valency_ion1, int) or not isinstance(valency_ion2, int):
        raise SurfaceChemistryError("Valencies must be integers.")
    if valency_ion1 <= 0 or valency_ion2 <= 0:
        raise SurfaceChemistryError("Valencies must be >= 1.")

    if valency_ion1 > valency_ion2:
        return "ion1_stronger"
    if valency_ion2 > valency_ion1:
        return "ion2_stronger"
    return "equal"
