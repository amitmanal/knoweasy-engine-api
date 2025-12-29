"""
Thermodynamics v1 — Part-4 (First Law utilities + ΔU/ΔH ideal-gas relations)

LOCKED SIGN CONVENTION (Chemistry):
- q > 0 : heat absorbed by system
- w > 0 : work done ON the system
- w < 0 : work done BY the system (expansion)
First Law: ΔU = q + w

Ideal gas (exam-safe):
- ΔU = n * Cv * ΔT
- ΔH = n * Cp * ΔT
- ΔH - ΔU = n * R * ΔT   (since Cp - Cv = R)

Units:
- q, w, ΔU, ΔH : Joules (J)
- n : moles
- Cv, Cp : J/mol·K
- ΔT : K (or °C difference)
- R default: 8.314 J/mol·K

Deterministic, pure functions only.
"""

from __future__ import annotations


R_IDEAL_DEFAULT = 8.314  # J/mol·K


class ThermodynamicsFirstLawError(ValueError):
    """Raised when invalid inputs are provided to first-law helpers."""


def _ensure_finite_number(x: float, name: str) -> None:
    if x is None:
        raise ThermodynamicsFirstLawError(f"{name} must not be None.")
    if isinstance(x, float) and x != x:
        raise ThermodynamicsFirstLawError(f"{name} must be a finite number (not NaN).")


def delta_u_from_q_w(q_j: float, w_j: float) -> float:
    """
    First Law: ΔU = q + w
    """
    _ensure_finite_number(q_j, "q_j")
    _ensure_finite_number(w_j, "w_j")
    return q_j + w_j


def q_from_delta_u_w(delta_u_j: float, w_j: float) -> float:
    """
    Rearranged: q = ΔU - w
    """
    _ensure_finite_number(delta_u_j, "delta_u_j")
    _ensure_finite_number(w_j, "w_j")
    return delta_u_j - w_j


def w_from_delta_u_q(delta_u_j: float, q_j: float) -> float:
    """
    Rearranged: w = ΔU - q
    """
    _ensure_finite_number(delta_u_j, "delta_u_j")
    _ensure_finite_number(q_j, "q_j")
    return delta_u_j - q_j


def delta_u_ideal_gas(n_mol: float, cv_j_per_mol_k: float, delta_t: float) -> float:
    """
    Ideal gas: ΔU = n * Cv * ΔT
    """
    _ensure_finite_number(n_mol, "n_mol")
    _ensure_finite_number(cv_j_per_mol_k, "cv_j_per_mol_k")
    _ensure_finite_number(delta_t, "delta_t")
    if n_mol < 0:
        raise ThermodynamicsFirstLawError("n_mol must be >= 0.")
    if cv_j_per_mol_k < 0:
        raise ThermodynamicsFirstLawError("cv_j_per_mol_k must be >= 0.")
    return n_mol * cv_j_per_mol_k * delta_t


def delta_h_ideal_gas(n_mol: float, cp_j_per_mol_k: float, delta_t: float) -> float:
    """
    Ideal gas: ΔH = n * Cp * ΔT
    """
    _ensure_finite_number(n_mol, "n_mol")
    _ensure_finite_number(cp_j_per_mol_k, "cp_j_per_mol_k")
    _ensure_finite_number(delta_t, "delta_t")
    if n_mol < 0:
        raise ThermodynamicsFirstLawError("n_mol must be >= 0.")
    if cp_j_per_mol_k < 0:
        raise ThermodynamicsFirstLawError("cp_j_per_mol_k must be >= 0.")
    return n_mol * cp_j_per_mol_k * delta_t


def delta_h_minus_delta_u_ideal_gas(n_mol: float, delta_t: float, r: float = R_IDEAL_DEFAULT) -> float:
    """
    Ideal gas relation: ΔH - ΔU = n * R * ΔT
    """
    _ensure_finite_number(n_mol, "n_mol")
    _ensure_finite_number(delta_t, "delta_t")
    _ensure_finite_number(r, "r")
    if n_mol < 0:
        raise ThermodynamicsFirstLawError("n_mol must be >= 0.")
    if r <= 0:
        raise ThermodynamicsFirstLawError("r must be > 0.")
    return n_mol * r * delta_t


def delta_h_from_delta_u_ideal_gas(delta_u_j: float, n_mol: float, delta_t: float, r: float = R_IDEAL_DEFAULT) -> float:
    """
    ΔH = ΔU + nRΔT (ideal gas)
    """
    _ensure_finite_number(delta_u_j, "delta_u_j")
    return delta_u_j + delta_h_minus_delta_u_ideal_gas(n_mol=n_mol, delta_t=delta_t, r=r)


def delta_u_from_delta_h_ideal_gas(delta_h_j: float, n_mol: float, delta_t: float, r: float = R_IDEAL_DEFAULT) -> float:
    """
    ΔU = ΔH - nRΔT (ideal gas)
    """
    _ensure_finite_number(delta_h_j, "delta_h_j")
    return delta_h_j - delta_h_minus_delta_u_ideal_gas(n_mol=n_mol, delta_t=delta_t, r=r)


def isochoric_first_law(delta_u_j: float) -> float:
    """
    Isochoric (ΔV=0): w = 0  =>  q = ΔU
    Returns q.
    """
    _ensure_finite_number(delta_u_j, "delta_u_j")
    return float(delta_u_j)


def isobaric_first_law(delta_h_j: float) -> float:
    """
    Isobaric (constant pressure): q = ΔH
    Returns q.
    """
    _ensure_finite_number(delta_h_j, "delta_h_j")
    return float(delta_h_j)
