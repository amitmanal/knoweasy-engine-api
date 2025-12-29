"""
Chemical Kinetics v1 — Advanced (deterministic, closed-form)

Scope (LOCKED):
- Second-order (single reactant) integrated law:
    1/[A]t = 1/[A]0 + k t
    => [A]t = 1 / (1/[A]0 + k t)
- Second-order half-life:
    t1/2 = 1 / (k [A]0)
- Pseudo-first-order:
    if rate = k [A]^a [B]^b and [B] is in large excess (constant),
    define k' = k [B]^b so that rate behaves as k' [A]^a

No solvers, no iteration. Pure algebraic helpers only.
"""

from __future__ import annotations

import math


class ChemicalKineticsAdvancedError(ValueError):
    """Raised when invalid inputs are provided to advanced kinetics helpers."""


def _ensure_finite_number(x: float, name: str) -> None:
    if x is None:
        raise ChemicalKineticsAdvancedError(f"{name} must not be None.")
    if isinstance(x, float) and x != x:
        raise ChemicalKineticsAdvancedError(f"{name} must be a finite number (not NaN).")


def _validate_positive(x: float, name: str) -> None:
    _ensure_finite_number(x, name)
    if x <= 0:
        raise ChemicalKineticsAdvancedError(f"{name} must be > 0.")


def _validate_non_negative(x: float, name: str) -> None:
    _ensure_finite_number(x, name)
    if x < 0:
        raise ChemicalKineticsAdvancedError(f"{name} must be >= 0.")


# -------------------------
# Second order (single reactant)
# -------------------------

def conc_second_order_single(a0: float, k: float, time_s: float) -> float:
    """
    Second-order (single reactant) integrated:
      1/[A]t = 1/[A]0 + k t

    Returns [A]t.
    """
    _validate_positive(a0, "a0")
    _validate_non_negative(k, "k")
    _validate_non_negative(time_s, "time_s")

    denom = (1.0 / a0) + (k * time_s)
    if denom <= 0:
        # Should not happen with validated inputs, but keep deterministic.
        raise ChemicalKineticsAdvancedError("Invalid denominator in second-order concentration formula.")
    return 1.0 / denom


def k_second_order_single(a0: float, at: float, time_s: float) -> float:
    """
    Rate constant for second-order single reactant:
      k = (1/t) * (1/[A]t - 1/[A]0)
    """
    _validate_positive(a0, "a0")
    _validate_positive(at, "at")
    _validate_positive(time_s, "time_s")
    if at > a0:
        raise ChemicalKineticsAdvancedError("at cannot be greater than a0 for decay.")
    return (1.0 / time_s) * ((1.0 / at) - (1.0 / a0))


def half_life_second_order_single(a0: float, k: float) -> float:
    """
    Second-order half-life:
      t1/2 = 1 / (k [A]0)
    """
    _validate_positive(a0, "a0")
    _validate_positive(k, "k")
    return 1.0 / (k * a0)


# -------------------------
# Pseudo-first-order
# -------------------------

def pseudo_first_order_kprime(k: float, b_conc: float, order_b: int = 1) -> float:
    """
    If rate = k [A]^a [B]^b and [B] is constant (excess),
    define k' = k [B]^b.

    order_b must be >= 0 (integer).
    """
    _ensure_finite_number(k, "k")
    _validate_non_negative(b_conc, "b_conc")
    if order_b < 0:
        raise ChemicalKineticsAdvancedError("order_b must be >= 0.")
    return k * (b_conc ** order_b)


def pseudo_first_order_rate(kprime: float, a_conc: float, order_a: int = 1) -> float:
    """
    Rate under pseudo-first-order assumption:
      rate = k' [A]^a

    order_a must be >= 0 (integer).
    """
    _ensure_finite_number(kprime, "kprime")
    _validate_non_negative(a_conc, "a_conc")
    if order_a < 0:
        raise ChemicalKineticsAdvancedError("order_a must be >= 0.")
    return kprime * (a_conc ** order_a)
