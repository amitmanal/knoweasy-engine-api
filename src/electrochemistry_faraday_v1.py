"""
Electrochemistry v1 — Faraday's Laws (Electrolysis)

Scope (LOCKED):
- Charge: Q = I * t
- Faraday constant F (default 96485 C/mol)
- Moles of electrons: n_e = Q / F
- Mass deposited/liberated:
    m = (Q * M) / (n * F)
  where:
    M = molar mass (g/mol)
    n = number of electrons exchanged per formula unit (valency in electrolysis context)

No simulations. Pure deterministic helpers only.

Units:
- I in amperes (A) = C/s
- t in seconds (s)
- Q in coulombs (C)
- F in C/mol
- M in g/mol
- m in grams (g)
"""

from __future__ import annotations


class ElectrochemistryFaradayError(ValueError):
    """Raised when invalid inputs are provided to Faraday-law helpers."""


FARADAY_DEFAULT = 96485.0  # C/mol


def _ensure_finite_number(x: float, name: str) -> None:
    if x is None:
        raise ElectrochemistryFaradayError(f"{name} must not be None.")
    if isinstance(x, float) and x != x:
        raise ElectrochemistryFaradayError(f"{name} must be a finite number (not NaN).")


def _validate_positive(x: float, name: str) -> None:
    _ensure_finite_number(x, name)
    if x <= 0:
        raise ElectrochemistryFaradayError(f"{name} must be > 0.")


def _validate_non_negative(x: float, name: str) -> None:
    _ensure_finite_number(x, name)
    if x < 0:
        raise ElectrochemistryFaradayError(f"{name} must be >= 0.")


def charge_from_current_time(current_a: float, time_s: float) -> float:
    """
    Q = I * t
    """
    _validate_non_negative(current_a, "current_a")
    _validate_non_negative(time_s, "time_s")
    return current_a * time_s


def moles_of_electrons_from_charge(charge_c: float, faraday: float = FARADAY_DEFAULT) -> float:
    """
    n(e-) = Q / F
    """
    _validate_non_negative(charge_c, "charge_c")
    _ensure_finite_number(faraday, "faraday")
    _validate_positive(faraday, "faraday")
    return charge_c / faraday


def mass_deposited(
    current_a: float,
    time_s: float,
    molar_mass_g_per_mol: float,
    n_electrons: int,
    faraday: float = FARADAY_DEFAULT,
) -> float:
    """
    Mass deposited/liberated in electrolysis:
      Q = I t
      m = (Q * M) / (n * F)

    Args:
      molar_mass_g_per_mol: M (g/mol) > 0
      n_electrons: n >= 1 (electrons per formula unit)
    """
    _validate_non_negative(current_a, "current_a")
    _validate_non_negative(time_s, "time_s")
    _validate_positive(molar_mass_g_per_mol, "molar_mass_g_per_mol")
    if n_electrons <= 0:
        raise ElectrochemistryFaradayError("n_electrons must be >= 1.")
    _ensure_finite_number(faraday, "faraday")
    _validate_positive(faraday, "faraday")

    q = charge_from_current_time(current_a, time_s)
    return (q * molar_mass_g_per_mol) / (n_electrons * faraday)


def time_required_for_mass(
    mass_g: float,
    current_a: float,
    molar_mass_g_per_mol: float,
    n_electrons: int,
    faraday: float = FARADAY_DEFAULT,
) -> float:
    """
    Rearranged Faraday law:
      m = (I t M) / (n F)
      t = (m n F) / (I M)

    Returns time in seconds.
    """
    _validate_non_negative(mass_g, "mass_g")
    _validate_positive(current_a, "current_a")
    _validate_positive(molar_mass_g_per_mol, "molar_mass_g_per_mol")
    if n_electrons <= 0:
        raise ElectrochemistryFaradayError("n_electrons must be >= 1.")
    _ensure_finite_number(faraday, "faraday")
    _validate_positive(faraday, "faraday")

    return (mass_g * n_electrons * faraday) / (current_a * molar_mass_g_per_mol)


def current_required_for_mass(
    mass_g: float,
    time_s: float,
    molar_mass_g_per_mol: float,
    n_electrons: int,
    faraday: float = FARADAY_DEFAULT,
) -> float:
    """
    Rearranged Faraday law:
      I = (m n F) / (t M)

    Returns current in amperes.
    """
    _validate_non_negative(mass_g, "mass_g")
    _validate_positive(time_s, "time_s")
    _validate_positive(molar_mass_g_per_mol, "molar_mass_g_per_mol")
    if n_electrons <= 0:
        raise ElectrochemistryFaradayError("n_electrons must be >= 1.")
    _ensure_finite_number(faraday, "faraday")
    _validate_positive(faraday, "faraday")

    return (mass_g * n_electrons * faraday) / (time_s * molar_mass_g_per_mol)
