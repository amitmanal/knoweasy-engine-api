# src/solutions_concentration_v1.py
# Physical Chemistry v1 – Solutions (Concentration Basics)
# LOCKED MODE: additive only

def molarity(moles_solute, volume_liters):
    """
    M = moles of solute / volume of solution (L)
    """
    if volume_liters <= 0:
        raise ValueError("Volume must be positive")
    return moles_solute / volume_liters


def moles_from_molarity(M, volume_liters):
    if volume_liters < 0:
        raise ValueError("Volume cannot be negative")
    return M * volume_liters


def molality(moles_solute, mass_solvent_kg):
    """
    m = moles solute / mass of solvent (kg)
    """
    if mass_solvent_kg <= 0:
        raise ValueError("Mass of solvent must be positive")
    return moles_solute / mass_solvent_kg


def normality(equivalents, volume_liters):
    """
    N = equivalents / volume(L)
    """
    if volume_liters <= 0:
        raise ValueError("Volume must be positive")
    return equivalents / volume_liters


def ppm_w_w(mass_solute_g, mass_solution_g):
    """
    ppm (w/w) = (mass solute / mass solution) * 1e6
    """
    if mass_solution_g <= 0:
        raise ValueError("Mass of solution must be positive")
    if mass_solute_g < 0:
        raise ValueError("Mass of solute cannot be negative")
    return (mass_solute_g / mass_solution_g) * 1_000_000.0


def dilution_final_concentration(C1, V1, V2):
    """
    C1 * V1 = C2 * V2  => C2 = (C1*V1)/V2
    Units: any consistent (e.g., M and L, or M and mL both ok if consistent)
    """
    if V2 <= 0:
        raise ValueError("Final volume must be positive")
    if V1 < 0:
        raise ValueError("Initial volume cannot be negative")
    return (C1 * V1) / V2


def dilution_required_volume(C1, C2, V2):
    """
    C1*V1 = C2*V2  => V1 = (C2*V2)/C1
    """
    if C1 == 0:
        raise ValueError("Initial concentration cannot be zero")
    if V2 < 0:
        raise ValueError("Final volume cannot be negative")
    return (C2 * V2) / C1


def mix_same_solute(moles_list, total_volume_liters):
    """
    For mixing solutions containing the same solute:
    total moles = sum(moles)
    M_final = total moles / total volume
    """
    if total_volume_liters <= 0:
        raise ValueError("Total volume must be positive")
    total_moles = sum(moles_list)
    return total_moles / total_volume_liters
