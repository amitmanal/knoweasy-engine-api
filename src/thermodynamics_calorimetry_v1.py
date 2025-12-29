"""
Thermodynamics v1 — Part-2 (Calorimetry + q at constant P/V + Cp/Cv basics)

LOCKED DESIGN GOALS:
- Deterministic, exam-oriented, pure functions
- No coupling to governor/normalizer/output formats
- Additive module only

Conventions:
- q is in Joules (J)
- Temperature change should be provided as delta_T in Kelvin or Celsius difference (same numeric value).
- R default is 8.314 J/mol·K (ideal gas constant, common exam value)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


R_IDEAL_DEFAULT = 8.314  # J/mol·K


class ThermodynamicsCalorimetryError(ValueError):
    """Raised when invalid inputs are provided to calorimetry helpers."""


def _ensure_finite_number(x: float, name: str) -> None:
    # Avoid importing math/isfinite to keep minimal; still handle obvious invalids.
    if x is None:
        raise ThermodynamicsCalorimetryError(f"{name} must not be None.")
    # NaN check: NaN != NaN
    if isinstance(x, float) and x != x:
        raise ThermodynamicsCalorimetryError(f"{name} must be a finite number (not NaN).")


def heat_q_mass_specific_heat(mass_g: float, specific_heat_j_per_gk: float, delta_t: float) -> float:
    """
    Calorimetry: q = m * c * ΔT

    Args:
        mass_g: mass in grams (g). Must be >= 0.
        specific_heat_j_per_gk: specific heat capacity in J/g·K. Must be >= 0.
        delta_t: temperature change (ΔT) in K (or °C difference). Can be negative.

    Returns:
        q in Joules (J).
    """
    _ensure_finite_number(mass_g, "mass_g")
    _ensure_finite_number(specific_heat_j_per_gk, "specific_heat_j_per_gk")
    _ensure_finite_number(delta_t, "delta_t")

    if mass_g < 0:
        raise ThermodynamicsCalorimetryError("mass_g must be >= 0.")
    if specific_heat_j_per_gk < 0:
        raise ThermodynamicsCalorimetryError("specific_heat_j_per_gk must be >= 0.")

    return mass_g * specific_heat_j_per_gk * delta_t


def heat_q_moles_molar_heat_capacity(n_mol: float, molar_heat_capacity_j_per_mol_k: float, delta_t: float) -> float:
    """
    Calorimetry using molar heat capacity: q = n * C * ΔT

    Args:
        n_mol: amount in moles. Must be >= 0.
        molar_heat_capacity_j_per_mol_k: J/mol·K. Must be >= 0.
        delta_t: ΔT in K (or °C difference). Can be negative.

    Returns:
        q in Joules (J).
    """
    _ensure_finite_number(n_mol, "n_mol")
    _ensure_finite_number(molar_heat_capacity_j_per_mol_k, "molar_heat_capacity_j_per_mol_k")
    _ensure_finite_number(delta_t, "delta_t")

    if n_mol < 0:
        raise ThermodynamicsCalorimetryError("n_mol must be >= 0.")
    if molar_heat_capacity_j_per_mol_k < 0:
        raise ThermodynamicsCalorimetryError("molar_heat_capacity_j_per_mol_k must be >= 0.")

    return n_mol * molar_heat_capacity_j_per_mol_k * delta_t


def q_constant_volume(delta_u_j: float) -> float:
    """
    At constant volume (V = const): q_v = ΔU  (only PV-work context, ideal exam form)

    Args:
        delta_u_j: change in internal energy ΔU in Joules.

    Returns:
        q_v in Joules.
    """
    _ensure_finite_number(delta_u_j, "delta_u_j")
    return float(delta_u_j)


def q_constant_pressure(delta_h_j: float) -> float:
    """
    At constant pressure (P = const): q_p = ΔH  (ideal exam form)

    Args:
        delta_h_j: enthalpy change ΔH in Joules.

    Returns:
        q_p in Joules.
    """
    _ensure_finite_number(delta_h_j, "delta_h_j")
    return float(delta_h_j)


def cp_minus_cv(cp_j_per_mol_k: float, cv_j_per_mol_k: float) -> float:
    """
    Returns (Cp - Cv) in J/mol·K.

    For ideal gas: Cp - Cv = R

    Args:
        cp_j_per_mol_k: Cp in J/mol·K
        cv_j_per_mol_k: Cv in J/mol·K

    Returns:
        Cp - Cv in J/mol·K
    """
    _ensure_finite_number(cp_j_per_mol_k, "cp_j_per_mol_k")
    _ensure_finite_number(cv_j_per_mol_k, "cv_j_per_mol_k")
    return cp_j_per_mol_k - cv_j_per_mol_k


def compute_cv_from_cp_ideal_gas(cp_j_per_mol_k: float, r: float = R_IDEAL_DEFAULT) -> float:
    """
    Ideal gas relation: Cp - Cv = R  =>  Cv = Cp - R
    """
    _ensure_finite_number(cp_j_per_mol_k, "cp_j_per_mol_k")
    _ensure_finite_number(r, "r")
    if r <= 0:
        raise ThermodynamicsCalorimetryError("r must be > 0 for ideal gas relation.")
    return cp_j_per_mol_k - r


def compute_cp_from_cv_ideal_gas(cv_j_per_mol_k: float, r: float = R_IDEAL_DEFAULT) -> float:
    """
    Ideal gas relation: Cp - Cv = R  =>  Cp = Cv + R
    """
    _ensure_finite_number(cv_j_per_mol_k, "cv_j_per_mol_k")
    _ensure_finite_number(r, "r")
    if r <= 0:
        raise ThermodynamicsCalorimetryError("r must be > 0 for ideal gas relation.")
    return cv_j_per_mol_k + r


def gamma_from_cp_cv(cp_j_per_mol_k: float, cv_j_per_mol_k: float) -> float:
    """
    Heat capacity ratio: γ = Cp/Cv (for gases; common exam identity)
    """
    _ensure_finite_number(cp_j_per_mol_k, "cp_j_per_mol_k")
    _ensure_finite_number(cv_j_per_mol_k, "cv_j_per_mol_k")
    if cv_j_per_mol_k == 0:
        raise ThermodynamicsCalorimetryError("cv_j_per_mol_k must not be 0 for gamma.")
    return cp_j_per_mol_k / cv_j_per_mol_k


def is_cp_cv_consistent_ideal_gas(
    cp_j_per_mol_k: float,
    cv_j_per_mol_k: float,
    r: float = R_IDEAL_DEFAULT,
    tol: float = 1e-6,
) -> bool:
    """
    Checks whether Cp - Cv ≈ R within tolerance.

    Deterministic helper for unit tests and rule-checking.
    """
    _ensure_finite_number(cp_j_per_mol_k, "cp_j_per_mol_k")
    _ensure_finite_number(cv_j_per_mol_k, "cv_j_per_mol_k")
    _ensure_finite_number(r, "r")
    _ensure_finite_number(tol, "tol")
    if r <= 0:
        raise ThermodynamicsCalorimetryError("r must be > 0.")
    if tol < 0:
        raise ThermodynamicsCalorimetryError("tol must be >= 0.")
    return abs((cp_j_per_mol_k - cv_j_per_mol_k) - r) <= tol
