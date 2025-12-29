"""
Ionic Equilibrium v1 — Core deterministic utilities (Class 11–12 exam-safe)

Scope (LOCKED):
- pH / pOH / Kw relations
- Strong acid/base pH
- Weak acid/base pH (approximation)
- Degree of ionization (approx)
- Buffer pH (Henderson–Hasselbalch)
- Ka/Kb/Kw relations

No numerical solvers, no iteration, no ICE tables.
Pure algebraic helpers only.
"""

from __future__ import annotations

import math


class IonicEquilibriumError(ValueError):
    """Raised when invalid inputs are provided to ionic equilibrium helpers."""


def _ensure_finite_number(x: float, name: str) -> None:
    if x is None:
        raise IonicEquilibriumError(f"{name} must not be None.")
    if isinstance(x, float) and x != x:
        raise IonicEquilibriumError(f"{name} must be a finite number (not NaN).")


def _validate_positive(x: float, name: str) -> None:
    _ensure_finite_number(x, name)
    if x <= 0:
        raise IonicEquilibriumError(f"{name} must be > 0.")


def _validate_non_negative(x: float, name: str) -> None:
    _ensure_finite_number(x, name)
    if x < 0:
        raise IonicEquilibriumError(f"{name} must be >= 0.")


# -------------------------
# pH / pOH / Kw relations
# -------------------------

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


def poh_from_ph(ph: float, pkw: float = 14.0) -> float:
    _ensure_finite_number(ph, "ph")
    _ensure_finite_number(pkw, "pkw")
    return pkw - ph


def kw_from_pkw(pkw: float = 14.0) -> float:
    _ensure_finite_number(pkw, "pkw")
    return 10.0 ** (-pkw)


def pkw_from_kw(kw: float) -> float:
    _validate_positive(kw, "kw")
    return -math.log10(kw)


def h_from_ph(ph: float) -> float:
    _ensure_finite_number(ph, "ph")
    return 10.0 ** (-ph)


def oh_from_poh(poh: float) -> float:
    _ensure_finite_number(poh, "poh")
    return 10.0 ** (-poh)


# -------------------------
# Strong acids & bases
# -------------------------

def ph_strong_acid(c_molar: float, basicity: int = 1) -> float:
    _validate_non_negative(c_molar, "c_molar")
    if basicity <= 0:
        raise IonicEquilibriumError("basicity must be >= 1.")
    h = basicity * c_molar
    if h <= 0:
        raise IonicEquilibriumError("Computed [H+] <= 0; pH undefined.")
    return ph_from_h(h)


def ph_strong_base(c_molar: float, acidity: int = 1, pkw: float = 14.0) -> float:
    _validate_non_negative(c_molar, "c_molar")
    if acidity <= 0:
        raise IonicEquilibriumError("acidity must be >= 1.")
    oh = acidity * c_molar
    if oh <= 0:
        raise IonicEquilibriumError("Computed [OH-] <= 0; pH undefined.")
    return ph_from_poh(poh_from_oh(oh), pkw=pkw)


# -------------------------
# Weak acids & bases (approx)
# -------------------------

def h_conc_weak_acid_approx(ka: float, c_molar: float) -> float:
    _validate_non_negative(ka, "ka")
    _validate_positive(c_molar, "c_molar")
    return math.sqrt(ka * c_molar)


def oh_conc_weak_base_approx(kb: float, c_molar: float) -> float:
    _validate_non_negative(kb, "kb")
    _validate_positive(c_molar, "c_molar")
    return math.sqrt(kb * c_molar)


def ph_weak_acid_approx(ka: float, c_molar: float) -> float:
    return ph_from_h(h_conc_weak_acid_approx(ka, c_molar))


def ph_weak_base_approx(kb: float, c_molar: float, pkw: float = 14.0) -> float:
    poh = poh_from_oh(oh_conc_weak_base_approx(kb, c_molar))
    return ph_from_poh(poh, pkw=pkw)


def alpha_weak_acid_approx(ka: float, c_molar: float) -> float:
    _validate_non_negative(ka, "ka")
    _validate_positive(c_molar, "c_molar")
    alpha = math.sqrt(ka / c_molar)
    if alpha >= 1:
        raise IonicEquilibriumError("alpha >= 1; invalid for weak-acid approximation.")
    return alpha


def alpha_weak_base_approx(kb: float, c_molar: float) -> float:
    _validate_non_negative(kb, "kb")
    _validate_positive(c_molar, "c_molar")
    alpha = math.sqrt(kb / c_molar)
    if alpha >= 1:
        raise IonicEquilibriumError("alpha >= 1; invalid for weak-base approximation.")
    return alpha


# -------------------------
# Ka / Kb / Kw relations
# -------------------------

def kb_from_ka(ka: float, kw: float) -> float:
    _validate_positive(ka, "ka")
    _validate_positive(kw, "kw")
    return kw / ka


def ka_from_kb(kb: float, kw: float) -> float:
    _validate_positive(kb, "kb")
    _validate_positive(kw, "kw")
    return kw / kb


# -------------------------
# Buffers
# -------------------------

def buffer_ph_henderson(pka: float, salt_conc: float, acid_conc: float) -> float:
    _ensure_finite_number(pka, "pka")
    _validate_positive(salt_conc, "salt_conc")
    _validate_positive(acid_conc, "acid_conc")
    return pka + math.log10(salt_conc / acid_conc)


def buffer_ph_basic_henderson(
    pkb: float,
    base_conc: float,
    salt_conc: float,
    pkw: float = 14.0,
) -> float:
    _ensure_finite_number(pkb, "pkb")
    _validate_positive(base_conc, "base_conc")
    _validate_positive(salt_conc, "salt_conc")

    poh = pkb + math.log10(salt_conc / base_conc)
    return ph_from_poh(poh, pkw=pkw)
