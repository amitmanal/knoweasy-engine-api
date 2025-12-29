"""
Thermodynamics v1 — Part-3 (Work: PV work + basic paths)

Chemistry sign convention (locked):
- Work done BY the system (expansion) is NEGATIVE.
- Work done ON the system (compression) is POSITIVE.

Core formulas (exam-safe):
1) Isobaric:      w = -P_ext * ΔV
2) Isochoric:     w = 0
3) Isothermal (ideal gas, reversible):
                  w = -n R T ln(V2/V1)

Units:
- Pressure: Pa (N/m^2) if using SI
- Volume: m^3 if using SI
=> Work in Joules (J)

For many exam questions, pressure may be given in atm and volume in L.
This module does NOT auto-convert units: caller must keep units consistent.

Deterministic, pure functions only.
"""

from __future__ import annotations

import math


class ThermodynamicsWorkError(ValueError):
    """Raised when invalid inputs are provided to work helpers."""


R_IDEAL_DEFAULT = 8.314  # J/mol·K


def _ensure_finite_number(x: float, name: str) -> None:
    if x is None:
        raise ThermodynamicsWorkError(f"{name} must not be None.")
    if isinstance(x, float) and x != x:
        raise ThermodynamicsWorkError(f"{name} must be a finite number (not NaN).")


def work_isobaric(p_ext: float, v_initial: float, v_final: float) -> float:
    """
    Isobaric PV work (constant external pressure):
        w = -P_ext * (Vf - Vi)

    Expansion (Vf > Vi) => negative
    Compression (Vf < Vi) => positive
    """
    _ensure_finite_number(p_ext, "p_ext")
    _ensure_finite_number(v_initial, "v_initial")
    _ensure_finite_number(v_final, "v_final")

    # Allow negative ΔV as normal, but P should be >= 0 in exam physics/chemistry.
    if p_ext < 0:
        raise ThermodynamicsWorkError("p_ext must be >= 0.")

    return -p_ext * (v_final - v_initial)


def work_isochoric() -> float:
    """
    Isochoric (constant volume): ΔV = 0 => w = 0
    """
    return 0.0


def work_isothermal_reversible_ideal_gas(
    n_mol: float,
    temperature_k: float,
    v_initial: float,
    v_final: float,
    r: float = R_IDEAL_DEFAULT,
) -> float:
    """
    Isothermal reversible expansion/compression for ideal gas:
        w = -nRT ln(V2/V1)

    Requirements:
    - n > 0
    - T > 0
    - V1 > 0, V2 > 0
    - r > 0
    """
    _ensure_finite_number(n_mol, "n_mol")
    _ensure_finite_number(temperature_k, "temperature_k")
    _ensure_finite_number(v_initial, "v_initial")
    _ensure_finite_number(v_final, "v_final")
    _ensure_finite_number(r, "r")

    if n_mol <= 0:
        raise ThermodynamicsWorkError("n_mol must be > 0.")
    if temperature_k <= 0:
        raise ThermodynamicsWorkError("temperature_k must be > 0.")
    if v_initial <= 0 or v_final <= 0:
        raise ThermodynamicsWorkError("Volumes must be > 0 for ln(V2/V1).")
    if r <= 0:
        raise ThermodynamicsWorkError("r must be > 0.")

    return -n_mol * r * temperature_k * math.log(v_final / v_initial)


def work_sign_for_process(v_initial: float, v_final: float) -> str:
    """
    Returns a deterministic sign label using chemistry convention:
    - "negative" for expansion (Vf > Vi)
    - "positive" for compression (Vf < Vi)
    - "zero" for no volume change (Vf == Vi)
    """
    _ensure_finite_number(v_initial, "v_initial")
    _ensure_finite_number(v_final, "v_final")

    if v_final > v_initial:
        return "negative"
    if v_final < v_initial:
        return "positive"
    return "zero"


def isothermal_work_magnitude(
    n_mol: float,
    temperature_k: float,
    v_initial: float,
    v_final: float,
    r: float = R_IDEAL_DEFAULT,
) -> float:
    """
    Convenience helper:
    returns |w| for isothermal reversible ideal gas.
    """
    w = work_isothermal_reversible_ideal_gas(n_mol, temperature_k, v_initial, v_final, r=r)
    return abs(w)
