# src/thermodynamics_v1.py
# Physical Chemistry v1 – Thermodynamics (Part-1)
# LOCKED MODE: additive only

ATM_L_TO_J = 101.325  # 1 L·atm = 101.325 J (standard conversion)


def delta_u(q, w):
    """
    First law: ΔU = q + w
    Sign convention:
      q > 0 : heat absorbed by system
      w > 0 : work done ON system
    """
    return q + w


def pv_work_constant_pressure_atm(P_ext_atm, delta_V_L):
    """
    PV work at constant external pressure (atm):
      w = -P_ext * ΔV
    Returns work in Joules.

    Note:
      ΔV > 0 expansion => w negative (system does work on surroundings)
      ΔV < 0 compression => w positive
    """
    return (-P_ext_atm * delta_V_L) * ATM_L_TO_J


def pv_work_constant_pressure_kpa(P_ext_kpa, delta_V_L):
    """
    PV work at constant external pressure (kPa):
      w = -P_ext * ΔV
    Returns work in Joules.

    Since 1 kPa·L = 1 J, conversion is direct.
    """
    return (-P_ext_kpa * delta_V_L)


def heat_q_from_specific_heat(mass_g, specific_heat_J_per_gK, delta_T_K):
    """
    q = m * c * ΔT
    """
    if mass_g < 0:
        raise ValueError("Mass cannot be negative")
    if specific_heat_J_per_gK < 0:
        raise ValueError("Specific heat cannot be negative")
    return mass_g * specific_heat_J_per_gK * delta_T_K


def heat_q_from_molar_heat_capacity(moles, molar_heat_capacity_J_per_molK, delta_T_K):
    """
    q = n * C * ΔT
    """
    if moles < 0:
        raise ValueError("Moles cannot be negative")
    if molar_heat_capacity_J_per_molK < 0:
        raise ValueError("Molar heat capacity cannot be negative")
    return moles * molar_heat_capacity_J_per_molK * delta_T_K


def delta_h_at_constant_pressure(q_p):
    """
    Definition (for PV work only):
      At constant pressure, ΔH = q_p
    """
    return q_p
