"""
Thermodynamics v1 — Part-2 (Calorimeter mixing + phase change basics)

LOCKED GOALS:
- Deterministic, exam-oriented, pure functions
- No coupling to governor/normalizer/output formats
- Additive module only

Conventions:
- Mass in grams (g)
- Specific heat capacity in J/g·K
- Temperature in °C or K (differences behave the same)
- Heat q in Joules (J)
"""

from __future__ import annotations


class ThermodynamicsCalorimeterMixingError(ValueError):
    """Raised when invalid inputs are provided to calorimeter mixing helpers."""


def _ensure_finite_number(x: float, name: str) -> None:
    if x is None:
        raise ThermodynamicsCalorimeterMixingError(f"{name} must not be None.")
    # NaN check: NaN != NaN
    if isinstance(x, float) and x != x:
        raise ThermodynamicsCalorimeterMixingError(f"{name} must be a finite number (not NaN).")


def sensible_heat_q(mass_g: float, specific_heat_j_per_gk: float, delta_t: float) -> float:
    """
    Calorimetry (sensible heat): q = m * c * ΔT
    """
    _ensure_finite_number(mass_g, "mass_g")
    _ensure_finite_number(specific_heat_j_per_gk, "specific_heat_j_per_gk")
    _ensure_finite_number(delta_t, "delta_t")

    if mass_g < 0:
        raise ThermodynamicsCalorimeterMixingError("mass_g must be >= 0.")
    if specific_heat_j_per_gk < 0:
        raise ThermodynamicsCalorimeterMixingError("specific_heat_j_per_gk must be >= 0.")

    return mass_g * specific_heat_j_per_gk * delta_t


def final_temperature_two_bodies_no_loss(
    m1_g: float,
    c1_j_per_gk: float,
    t1: float,
    m2_g: float,
    c2_j_per_gk: float,
    t2: float,
) -> float:
    """
    Mixing two bodies in an isolated system (no heat loss):
      m1*c1*(Tf - T1) + m2*c2*(Tf - T2) = 0
    => Tf = (m1*c1*T1 + m2*c2*T2) / (m1*c1 + m2*c2)

    Returns:
        Tf
    """
    _ensure_finite_number(m1_g, "m1_g")
    _ensure_finite_number(c1_j_per_gk, "c1_j_per_gk")
    _ensure_finite_number(t1, "t1")
    _ensure_finite_number(m2_g, "m2_g")
    _ensure_finite_number(c2_j_per_gk, "c2_j_per_gk")
    _ensure_finite_number(t2, "t2")

    if m1_g < 0 or m2_g < 0:
        raise ThermodynamicsCalorimeterMixingError("Mass must be >= 0.")
    if c1_j_per_gk < 0 or c2_j_per_gk < 0:
        raise ThermodynamicsCalorimeterMixingError("Specific heat must be >= 0.")

    cap1 = m1_g * c1_j_per_gk
    cap2 = m2_g * c2_j_per_gk
    denom = cap1 + cap2
    if denom == 0:
        raise ThermodynamicsCalorimeterMixingError("Total heat capacity must be > 0.")

    return (cap1 * t1 + cap2 * t2) / denom


def final_temperature_with_calorimeter_no_loss(
    m_hot_g: float,
    c_hot_j_per_gk: float,
    t_hot: float,
    m_cold_g: float,
    c_cold_j_per_gk: float,
    t_cold: float,
    calorimeter_heat_capacity_j_per_k: float,
    calorimeter_initial_temp: float,
) -> float:
    """
    Mixing with calorimeter present (no heat loss):
      m_hot*c_hot*(Tf - Th) + m_cold*c_cold*(Tf - Tc) + C_cal*(Tf - Tcal0) = 0
    => Tf = (m_hot*c_hot*Th + m_cold*c_cold*Tc + C_cal*Tcal0) /
            (m_hot*c_hot + m_cold*c_cold + C_cal)

    Args:
        calorimeter_heat_capacity_j_per_k: C_cal in J/K (>=0)
        calorimeter_initial_temp: initial calorimeter temperature (Tcal0)

    Returns:
        Tf
    """
    _ensure_finite_number(m_hot_g, "m_hot_g")
    _ensure_finite_number(c_hot_j_per_gk, "c_hot_j_per_gk")
    _ensure_finite_number(t_hot, "t_hot")
    _ensure_finite_number(m_cold_g, "m_cold_g")
    _ensure_finite_number(c_cold_j_per_gk, "c_cold_j_per_gk")
    _ensure_finite_number(t_cold, "t_cold")
    _ensure_finite_number(calorimeter_heat_capacity_j_per_k, "calorimeter_heat_capacity_j_per_k")
    _ensure_finite_number(calorimeter_initial_temp, "calorimeter_initial_temp")

    if m_hot_g < 0 or m_cold_g < 0:
        raise ThermodynamicsCalorimeterMixingError("Mass must be >= 0.")
    if c_hot_j_per_gk < 0 or c_cold_j_per_gk < 0:
        raise ThermodynamicsCalorimeterMixingError("Specific heat must be >= 0.")
    if calorimeter_heat_capacity_j_per_k < 0:
        raise ThermodynamicsCalorimeterMixingError("Calorimeter heat capacity must be >= 0.")

    cap_hot = m_hot_g * c_hot_j_per_gk
    cap_cold = m_cold_g * c_cold_j_per_gk
    denom = cap_hot + cap_cold + calorimeter_heat_capacity_j_per_k
    if denom == 0:
        raise ThermodynamicsCalorimeterMixingError("Total heat capacity must be > 0.")

    num = (cap_hot * t_hot) + (cap_cold * t_cold) + (calorimeter_heat_capacity_j_per_k * calorimeter_initial_temp)
    return num / denom


def latent_heat_q(mass_g: float, latent_heat_j_per_g: float, direction: str = "absorb") -> float:
    """
    Latent heat: q = m * L

    direction:
      - "absorb"  => + mL  (melting/vaporization)
      - "release" => - mL  (freezing/condensation)
    """
    _ensure_finite_number(mass_g, "mass_g")
    _ensure_finite_number(latent_heat_j_per_g, "latent_heat_j_per_g")

    if mass_g < 0:
        raise ThermodynamicsCalorimeterMixingError("mass_g must be >= 0.")
    if latent_heat_j_per_g < 0:
        raise ThermodynamicsCalorimeterMixingError("latent_heat_j_per_g must be >= 0.")

    d = (direction or "").strip().lower()
    if d not in ("absorb", "release"):
        raise ThermodynamicsCalorimeterMixingError('direction must be "absorb" or "release".')

    sign = 1.0 if d == "absorb" else -1.0
    return sign * mass_g * latent_heat_j_per_g


def heat_for_temperature_change_with_single_transition(
    mass_g: float,
    specific_heat_j_per_gk: float,
    t_initial: float,
    t_final: float,
    t_transition: float,
    latent_heat_j_per_g: float,
) -> float:
    """
    Exam-deterministic helper:
    Computes total heat for changing temperature from t_initial to t_final
    when a single phase transition may occur at t_transition with latent heat L.

    If the path crosses t_transition:
      q = m*c*(t_transition - t_initial) + sign*(m*L) + m*c*(t_final - t_transition)

    Where sign is:
      - + for heating across transition (t_final > t_initial and crossing upward)
      - - for cooling across transition (t_final < t_initial and crossing downward)

    If no crossing:
      q = m*c*(t_final - t_initial)

    Notes:
    - This is a "single transition" model (one latent event at one temperature).
    - Deterministic closed-form only (no iteration).
    """
    _ensure_finite_number(mass_g, "mass_g")
    _ensure_finite_number(specific_heat_j_per_gk, "specific_heat_j_per_gk")
    _ensure_finite_number(t_initial, "t_initial")
    _ensure_finite_number(t_final, "t_final")
    _ensure_finite_number(t_transition, "t_transition")
    _ensure_finite_number(latent_heat_j_per_g, "latent_heat_j_per_g")

    if mass_g < 0:
        raise ThermodynamicsCalorimeterMixingError("mass_g must be >= 0.")
    if specific_heat_j_per_gk < 0:
        raise ThermodynamicsCalorimeterMixingError("specific_heat_j_per_gk must be >= 0.")
    if latent_heat_j_per_g < 0:
        raise ThermodynamicsCalorimeterMixingError("latent_heat_j_per_g must be >= 0.")

    if t_initial == t_final:
        return 0.0

    # Determine if the segment crosses the transition temperature
    crossing_up = (t_initial < t_transition) and (t_final >= t_transition)
    crossing_down = (t_initial > t_transition) and (t_final <= t_transition)

    if not (crossing_up or crossing_down):
        return sensible_heat_q(mass_g, specific_heat_j_per_gk, (t_final - t_initial))

    # Split into sensible + latent + sensible
    q1 = sensible_heat_q(mass_g, specific_heat_j_per_gk, (t_transition - t_initial))
    q2 = mass_g * latent_heat_j_per_g
    q3 = sensible_heat_q(mass_g, specific_heat_j_per_gk, (t_final - t_transition))

    if crossing_up:
        return q1 + q2 + q3
    else:
        # cooling across transition releases latent heat
        return q1 - q2 + q3
