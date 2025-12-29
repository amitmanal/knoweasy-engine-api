# src/colligative_properties_v1.py
# Physical Chemistry v1 – Colligative Properties
# LOCKED MODE: additive only

def relative_lowering_vapour_pressure(moles_solute, moles_solvent):
    """
    RLVP = moles_solute / (moles_solute + moles_solvent)
    """
    if moles_solvent <= 0:
        raise ValueError("Moles of solvent must be positive")
    if moles_solute < 0:
        raise ValueError("Moles of solute cannot be negative")
    return moles_solute / (moles_solute + moles_solvent)


def elevation_boiling_point(Kb, molality, vanthoff_factor=1.0):
    """
    ΔTb = i * Kb * m
    """
    if Kb < 0 or molality < 0 or vanthoff_factor <= 0:
        raise ValueError("Invalid input for boiling point elevation")
    return vanthoff_factor * Kb * molality


def depression_freezing_point(Kf, molality, vanthoff_factor=1.0):
    """
    ΔTf = i * Kf * m
    """
    if Kf < 0 or molality < 0 or vanthoff_factor <= 0:
        raise ValueError("Invalid input for freezing point depression")
    return vanthoff_factor * Kf * molality


def vanthoff_factor_from_dissociation(n_particles_before, n_particles_after):
    """
    i = particles after / particles before
    """
    if n_particles_before <= 0 or n_particles_after <= 0:
        raise ValueError("Number of particles must be positive")
    return n_particles_after / n_particles_before


def vanthoff_factor_from_degree_dissociation(n, alpha):
    """
    For dissociation into n particles:
    i = 1 + alpha*(n - 1)
    """
    if n <= 0:
        raise ValueError("n must be positive")
    if alpha < 0 or alpha > 1:
        raise ValueError("Degree of dissociation must be between 0 and 1")
    return 1 + alpha * (n - 1)


def vanthoff_factor_from_association(n, alpha):
    """
    For association into 1 particle from n:
    i = 1 - alpha*(n - 1)/n
    """
    if n <= 1:
        raise ValueError("n must be greater than 1 for association")
    if alpha < 0 or alpha > 1:
        raise ValueError("Degree of association must be between 0 and 1")
    return 1 - (alpha * (n - 1) / n)
