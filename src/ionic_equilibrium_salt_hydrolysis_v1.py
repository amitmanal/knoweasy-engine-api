"""
Ionic Equilibrium v1 — Salt Hydrolysis (closed-form, exam-safe)

Scope (LOCKED):
- Hydrolysis constant relations (Kh)
- pH of salts (approximate, dilute solutions)
  1) Weak acid + strong base (e.g., CH3COONa) => basic
  2) Strong acid + weak base (e.g., NH4Cl)    => acidic
  3) Weak acid + weak base (e.g., NH4CH3COO)  => depends on Ka vs Kb (approx)

No numerical solvers, no ICE-table solving.
Pure algebraic helpers only.

Conventions:
- Concentrations in mol/L (M)
- Ka, Kb, Kw in exam-style dimensionless usage
- Default pKw = 14 at 25°C
"""

from __future__ import annotations

import math


class IonicSaltHydrolysisError(ValueError):
    """Raised when invalid inputs are provided to salt hydrolysis helpers."""


def _ensure_finite_number(x: float, name: str) -> None:
    if x is None:
        raise IonicSaltHydrolysisError(f"{name} must not be None.")
    if isinstance(x, float) and x != x:
        raise IonicSaltHydrolysisError(f"{name} must be a finite number (not NaN).")


def _validate_positive(x: float, name: str) -> None:
    _ensure_finite_number(x, name)
    if x <= 0:
        raise IonicSaltHydrolysisError(f"{name} must be > 0.")


def _validate_non_negative(x: float, name: str) -> None:
    _ensure_finite_number(x, name)
    if x < 0:
        raise IonicSaltHydrolysisError(f"{name} must be >= 0.")


def kw_from_pkw(pkw: float = 14.0) -> float:
    _ensure_finite_number(pkw, "pkw")
    return 10.0 ** (-pkw)


def ph_from_h(h_conc: float) -> float:
    _validate_positive(h_conc, "h_conc")
    return -math.log10(h_conc)


def poh_from_oh(oh_conc: float) -> float:
    _validate_positive(oh_conc, "oh_conc")
    return -math.log10(oh_conc)


def ph_from_poh(poh: float, pkw: float = 14.0) -> float:
    _ensure_finite_number(poh, "poh")
    _ensure_finite_number(pkw, "pkw")
    return pkw - poh


# -------------------------
# Hydrolysis constants
# -------------------------

def kh_weak_acid_strong_base(ka: float, kw: float) -> float:
    """
    Salt of weak acid & strong base (A- hydrolyzes):
      A- + H2O ⇌ HA + OH-
      Kh = Kw / Ka
    """
    _validate_positive(ka, "ka")
    _validate_positive(kw, "kw")
    return kw / ka


def kh_strong_acid_weak_base(kb: float, kw: float) -> float:
    """
    Salt of strong acid & weak base (BH+ hydrolyzes):
      BH+ + H2O ⇌ B + H3O+
      Kh = Kw / Kb
    """
    _validate_positive(kb, "kb")
    _validate_positive(kw, "kw")
    return kw / kb


def kh_weak_acid_weak_base(ka: float, kb: float, kw: float) -> float:
    """
    Salt of weak acid & weak base (BH+ A-):
    Often Kh = Kw / (Ka * Kb) in exam derivations for overall hydrolysis measure.
    We expose it as a deterministic helper for formula questions.
    """
    _validate_positive(ka, "ka")
    _validate_positive(kb, "kb")
    _validate_positive(kw, "kw")
    return kw / (ka * kb)


# -------------------------
# pH of salts (approx)
# -------------------------

def ph_salt_weak_acid_strong_base(
    c_salt_molar: float,
    ka: float,
    pkw: float = 14.0,
) -> float:
    """
    Salt of weak acid & strong base (e.g., CH3COONa) => basic.
    Approximation (dilute):
      [OH-] ≈ sqrt(Kh * C)  where Kh = Kw/Ka

    Then pOH = -log[OH-], pH = pKw - pOH
    """
    _validate_positive(c_salt_molar, "c_salt_molar")
    _validate_non_negative(ka, "ka")
    _ensure_finite_number(pkw, "pkw")
    if ka <= 0:
        raise IonicSaltHydrolysisError("ka must be > 0 for this salt type.")

    kw = kw_from_pkw(pkw)
    kh = kh_weak_acid_strong_base(ka, kw)
    oh = math.sqrt(kh * c_salt_molar)
    return ph_from_poh(poh_from_oh(oh), pkw=pkw)


def ph_salt_strong_acid_weak_base(
    c_salt_molar: float,
    kb: float,
    pkw: float = 14.0,
) -> float:
    """
    Salt of strong acid & weak base (e.g., NH4Cl) => acidic.
    Approximation (dilute):
      [H+] ≈ sqrt(Kh * C)  where Kh = Kw/Kb

    Then pH = -log[H+]
    """
    _validate_positive(c_salt_molar, "c_salt_molar")
    _validate_non_negative(kb, "kb")
    _ensure_finite_number(pkw, "pkw")
    if kb <= 0:
        raise IonicSaltHydrolysisError("kb must be > 0 for this salt type.")

    kw = kw_from_pkw(pkw)
    kh = kh_strong_acid_weak_base(kb, kw)
    h = math.sqrt(kh * c_salt_molar)
    return ph_from_h(h)


def ph_salt_weak_acid_weak_base(
    ka: float,
    kb: float,
    pkw: float = 14.0,
) -> float:
    """
    Salt of weak acid & weak base (e.g., NH4CH3COO):
    Approx exam result:
      pH = 7 + 0.5 * log10(Kb/Ka)
    More generally:
      pH = 0.5*(pKw + pKa - pKb)
    We implement the Kb/Ka form:
      pH = 0.5 * (pKw + log10(Kb/Ka))

    Note: concentration cancels in this approximation.
    """
    _validate_positive(ka, "ka")
    _validate_positive(kb, "kb")
    _ensure_finite_number(pkw, "pkw")

    return 0.5 * (pkw + math.log10(kb / ka))


# -------------------------
# Degree of hydrolysis (h) approximations
# -------------------------

def degree_of_hydrolysis_weak_acid_strong_base(c_salt_molar: float, ka: float, pkw: float = 14.0) -> float:
    """
    For salt of weak acid & strong base:
      h ≈ sqrt(Kh / C) where Kh = Kw/Ka
    """
    _validate_positive(c_salt_molar, "c_salt_molar")
    _validate_positive(ka, "ka")
    kw = kw_from_pkw(pkw)
    kh = kh_weak_acid_strong_base(ka, kw)
    h = math.sqrt(kh / c_salt_molar)
    if h >= 1:
        raise IonicSaltHydrolysisError("Computed degree of hydrolysis >= 1; approximation invalid.")
    return h


def degree_of_hydrolysis_strong_acid_weak_base(c_salt_molar: float, kb: float, pkw: float = 14.0) -> float:
    """
    For salt of strong acid & weak base:
      h ≈ sqrt(Kh / C) where Kh = Kw/Kb
    """
    _validate_positive(c_salt_molar, "c_salt_molar")
    _validate_positive(kb, "kb")
    kw = kw_from_pkw(pkw)
    kh = kh_strong_acid_weak_base(kb, kw)
    h = math.sqrt(kh / c_salt_molar)
    if h >= 1:
        raise IonicSaltHydrolysisError("Computed degree of hydrolysis >= 1; approximation invalid.")
    return h
