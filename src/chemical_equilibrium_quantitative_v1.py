"""
Chemical Equilibrium v1 — Quantitative Extensions (α-based, deterministic)

Scope (LOCKED):
- Ostwald dilution law helpers (safe closed forms, no equation solving)
- Classic gaseous dissociation case:
    AB(g) ⇌ A(g) + B(g)
  with degree of dissociation α and total pressure P
  => Kp = (α^2 * P) / (1 - α^2)

All functions are pure and deterministic. No ICE-table solvers.
"""

from __future__ import annotations


class ChemicalEquilibriumQuantitativeError(ValueError):
    """Raised when invalid inputs are provided to quantitative equilibrium helpers."""


def _ensure_finite_number(x: float, name: str) -> None:
    if x is None:
        raise ChemicalEquilibriumQuantitativeError(f"{name} must not be None.")
    if isinstance(x, float) and x != x:
        raise ChemicalEquilibriumQuantitativeError(f"{name} must be a finite number (not NaN).")


def _validate_alpha(alpha: float) -> None:
    _ensure_finite_number(alpha, "alpha")
    # α in [0, 1) for standard degree of dissociation in these models
    if alpha < 0 or alpha >= 1:
        raise ChemicalEquilibriumQuantitativeError("alpha must be in [0, 1).")


def ostwald_ka_from_c_alpha(c_molar: float, alpha: float) -> float:
    """
    Ostwald dilution law (weak acid, HA ⇌ H+ + A-):
        Ka = (C * α^2) / (1 - α)

    Deterministic helper (no solving). Valid for dilute weak electrolytes.

    Args:
        c_molar: analytical concentration C (mol/L), must be > 0
        alpha: degree of dissociation in [0,1)

    Returns:
        Ka
    """
    _ensure_finite_number(c_molar, "c_molar")
    _validate_alpha(alpha)
    if c_molar <= 0:
        raise ChemicalEquilibriumQuantitativeError("c_molar must be > 0.")
    denom = (1.0 - alpha)
    if denom == 0:
        raise ChemicalEquilibriumQuantitativeError("alpha too close to 1 for this expression.")
    return (c_molar * (alpha ** 2)) / denom


def ostwald_alpha_approx_from_ka_c(ka: float, c_molar: float) -> float:
    """
    Common approximation for weak acids/bases at low dissociation:
        α ≈ sqrt(Ka / C)

    Deterministic approximation helper.
    """
    _ensure_finite_number(ka, "ka")
    _ensure_finite_number(c_molar, "c_molar")
    if ka < 0:
        raise ChemicalEquilibriumQuantitativeError("ka must be >= 0.")
    if c_molar <= 0:
        raise ChemicalEquilibriumQuantitativeError("c_molar must be > 0.")
    alpha = (ka / c_molar) ** 0.5
    # Clamp is NOT allowed (would hide errors). Validate instead.
    if alpha >= 1:
        raise ChemicalEquilibriumQuantitativeError("Approximation gives alpha >= 1; invalid for weak electrolyte approximation.")
    return alpha


def kp_dissociation_ab_to_a_b(alpha: float, total_pressure: float) -> float:
    """
    For AB(g) ⇌ A(g) + B(g), starting with 1 mol AB, degree of dissociation = α.

    At equilibrium:
      n_AB = 1 - α
      n_A  = α
      n_B  = α
      n_total = 1 + α

    Partial pressures:
      p_A  = (α/(1+α)) P
      p_B  = (α/(1+α)) P
      p_AB = ((1-α)/(1+α)) P

    Kp = (p_A * p_B) / p_AB
       = (α^2 P) / (1 - α^2)

    Args:
        alpha: degree of dissociation in [0,1)
        total_pressure: total pressure P (must be > 0), any consistent unit

    Returns:
        Kp
    """
    _validate_alpha(alpha)
    _ensure_finite_number(total_pressure, "total_pressure")
    if total_pressure <= 0:
        raise ChemicalEquilibriumQuantitativeError("total_pressure must be > 0.")

    denom = (1.0 - alpha ** 2)
    if denom == 0:
        raise ChemicalEquilibriumQuantitativeError("alpha too close to 1 for this expression.")
    return (alpha ** 2) * total_pressure / denom


def alpha_from_kp_dissociation_ab_to_a_b(kp: float, total_pressure: float) -> float:
    """
    Inverse of:
      Kp = (α^2 P) / (1 - α^2)

    Solve closed-form:
      Kp(1 - α^2) = α^2 P
      Kp = α^2(P + Kp)
      α^2 = Kp / (P + Kp)
      α = sqrt(Kp / (P + Kp))

    Args:
        kp: equilibrium constant Kp (>= 0)
        total_pressure: P (>0)

    Returns:
        alpha in [0,1)
    """
    _ensure_finite_number(kp, "kp")
    _ensure_finite_number(total_pressure, "total_pressure")
    if kp < 0:
        raise ChemicalEquilibriumQuantitativeError("kp must be >= 0.")
    if total_pressure <= 0:
        raise ChemicalEquilibriumQuantitativeError("total_pressure must be > 0.")

    alpha_sq = kp / (total_pressure + kp) if (total_pressure + kp) != 0 else 0.0
    alpha = alpha_sq ** 0.5
    # For kp>=0 and P>0, alpha will be in [0,1). Still validate for safety.
    _validate_alpha(alpha)
    return alpha


def partial_pressures_ab_dissociation(alpha: float, total_pressure: float) -> dict:
    """
    Returns partial pressures for AB(g) ⇌ A(g) + B(g) case.

    Output keys: "AB", "A", "B"
    """
    _validate_alpha(alpha)
    _ensure_finite_number(total_pressure, "total_pressure")
    if total_pressure <= 0:
        raise ChemicalEquilibriumQuantitativeError("total_pressure must be > 0.")

    p_a = (alpha / (1.0 + alpha)) * total_pressure
    p_b = p_a
    p_ab = ((1.0 - alpha) / (1.0 + alpha)) * total_pressure

    return {"AB": p_ab, "A": p_a, "B": p_b}
