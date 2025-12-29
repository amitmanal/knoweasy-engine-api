"""
Chemical Kinetics v1 — Deterministic utilities (JEE + NEET)

Scope (LOCKED):
- Average rate and simple rate law evaluation
- Integrated rate equations:
    * Zero order:   [A]t = [A]0 - k t
    * First order:  ln([A]0/[A]t) = k t  => [A]t = [A]0 * e^(-k t)
- Half-life:
    * Zero order:   t1/2 = [A]0 / (2k)
    * First order:  t1/2 = 0.693 / k
- Arrhenius equation (log form):
    ln(k2/k1) = -Ea/R * (1/T2 - 1/T1)

No numerical solvers. Pure algebra only.

Conventions:
- Concentration in mol/L (or any consistent unit)
- Time in seconds (or consistent)
- k units depend on order (engine doesn't enforce units)
- Temperatures in Kelvin
- Ea in J/mol
"""

from __future__ import annotations

import math


class ChemicalKineticsError(ValueError):
    """Raised when invalid inputs are provided to kinetics helpers."""


R_GAS_DEFAULT = 8.314  # J/mol·K


def _ensure_finite_number(x: float, name: str) -> None:
    if x is None:
        raise ChemicalKineticsError(f"{name} must not be None.")
    if isinstance(x, float) and x != x:
        raise ChemicalKineticsError(f"{name} must be a finite number (not NaN).")


def _validate_positive(x: float, name: str) -> None:
    _ensure_finite_number(x, name)
    if x <= 0:
        raise ChemicalKineticsError(f"{name} must be > 0.")


def _validate_non_negative(x: float, name: str) -> None:
    _ensure_finite_number(x, name)
    if x < 0:
        raise ChemicalKineticsError(f"{name} must be >= 0.")


def average_rate(conc_initial: float, conc_final: float, time_s: float) -> float:
    """
    Average rate of disappearance of reactant A:
      rate = ([A]0 - [A]t) / t

    Returns non-negative for usual disappearance scenario.
    """
    _validate_non_negative(conc_initial, "conc_initial")
    _validate_non_negative(conc_final, "conc_final")
    _validate_positive(time_s, "time_s")
    return (conc_initial - conc_final) / time_s


def rate_law(k: float, concentrations: dict[str, float], orders: dict[str, int]) -> float:
    """
    Generic rate law:
      rate = k * Π [X]^{order_X}

    orders: species -> integer order (0,1,2,...)
    concentrations: species -> concentration (>=0)

    Deterministic helper; does not infer k or orders.
    """
    _ensure_finite_number(k, "k")
    if not concentrations or not orders:
        raise ChemicalKineticsError("concentrations and orders must not be empty.")
    rate = k
    for sp, order in orders.items():
        if sp not in concentrations:
            raise ChemicalKineticsError(f"Missing concentration for {sp}.")
        c = concentrations[sp]
        _ensure_finite_number(c, f"[{sp}]")
        if c < 0:
            raise ChemicalKineticsError("Concentrations must be >= 0.")
        if order < 0:
            raise ChemicalKineticsError("Orders must be >= 0.")
        rate *= c ** order
    return rate


# -------------------------
# Zero order (integrated)
# -------------------------

def conc_zero_order(a0: float, k: float, time_s: float) -> float:
    """
    Zero order integrated:
      [A]t = [A]0 - k t
    """
    _validate_non_negative(a0, "a0")
    _validate_non_negative(k, "k")
    _validate_non_negative(time_s, "time_s")
    at = a0 - k * time_s
    if at < 0:
        # Deterministic guard: concentration cannot be negative
        return 0.0
    return at


def time_zero_order(a0: float, at: float, k: float) -> float:
    """
    Zero order time to reach concentration at:
      t = ([A]0 - [A]t) / k
    """
    _validate_non_negative(a0, "a0")
    _validate_non_negative(at, "at")
    _validate_positive(k, "k")
    if at > a0:
        raise ChemicalKineticsError("at cannot be greater than a0 for zero-order decay.")
    return (a0 - at) / k


def half_life_zero_order(a0: float, k: float) -> float:
    """
    Zero order half-life:
      t1/2 = [A]0 / (2k)
    """
    _validate_non_negative(a0, "a0")
    _validate_positive(k, "k")
    return a0 / (2.0 * k)


# -------------------------
# First order (integrated)
# -------------------------

def conc_first_order(a0: float, k: float, time_s: float) -> float:
    """
    First order integrated:
      [A]t = [A]0 * e^(-k t)
    """
    _validate_non_negative(a0, "a0")
    _validate_non_negative(k, "k")
    _validate_non_negative(time_s, "time_s")
    return a0 * math.exp(-k * time_s)


def k_first_order(a0: float, at: float, time_s: float) -> float:
    """
    First order rate constant:
      k = (1/t) * ln([A]0/[A]t)
    """
    _validate_positive(a0, "a0")
    _validate_positive(at, "at")
    _validate_positive(time_s, "time_s")
    if at > a0:
        raise ChemicalKineticsError("at cannot be greater than a0 for first-order decay.")
    return (1.0 / time_s) * math.log(a0 / at)


def half_life_first_order(k: float) -> float:
    """
    First order half-life:
      t1/2 = 0.693 / k
    """
    _validate_positive(k, "k")
    return 0.693 / k


# -------------------------
# Arrhenius relation
# -------------------------

def ln_k2_over_k1_from_ea(
    ea_j_per_mol: float,
    t1_k: float,
    t2_k: float,
    r_gas: float = R_GAS_DEFAULT,
) -> float:
    """
    ln(k2/k1) = -Ea/R * (1/T2 - 1/T1)
    """
    _validate_non_negative(ea_j_per_mol, "ea_j_per_mol")
    _validate_positive(t1_k, "t1_k")
    _validate_positive(t2_k, "t2_k")
    _validate_positive(r_gas, "r_gas")
    return -(ea_j_per_mol / r_gas) * ((1.0 / t2_k) - (1.0 / t1_k))


def k2_from_k1_arrhenius(
    k1: float,
    ea_j_per_mol: float,
    t1_k: float,
    t2_k: float,
    r_gas: float = R_GAS_DEFAULT,
) -> float:
    """
    k2 = k1 * exp( ln(k2/k1) )
    """
    _validate_non_negative(k1, "k1")
    ln_ratio = ln_k2_over_k1_from_ea(ea_j_per_mol, t1_k, t2_k, r_gas=r_gas)
    return k1 * math.exp(ln_ratio)
