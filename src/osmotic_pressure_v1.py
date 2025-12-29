# src/osmotic_pressure_v1.py
# Physical Chemistry v1 – Osmotic Pressure
# LOCKED MODE: additive only

R = 0.082057  # L·atm·mol⁻¹·K⁻¹ (exam-standard)


def osmotic_pressure(molarity, temperature_K, vanthoff_factor=1.0):
    """
    Π = i * M * R * T
    Returns osmotic pressure in atm.
    """
    if molarity < 0:
        raise ValueError("Molarity cannot be negative")
    if temperature_K <= 0:
        raise ValueError("Temperature must be positive in Kelvin")
    if vanthoff_factor <= 0:
        raise ValueError("van't Hoff factor must be positive")
    return vanthoff_factor * molarity * R * temperature_K


def molar_mass_from_osmotic_pressure(
    mass_solute_g,
    volume_solution_L,
    osmotic_pressure_atm,
    temperature_K,
    vanthoff_factor=1.0
):
    """
    Uses ΠV = i(n)RT  and n = mass / molar mass
    => M = (i * mass * R * T) / (Π * V)
    Returns molar mass in g/mol.
    """
    if mass_solute_g <= 0:
        raise ValueError("Mass of solute must be positive")
    if volume_solution_L <= 0:
        raise ValueError("Volume of solution must be positive")
    if osmotic_pressure_atm <= 0:
        raise ValueError("Osmotic pressure must be positive")
    if temperature_K <= 0:
        raise ValueError("Temperature must be positive")
    if vanthoff_factor <= 0:
        raise ValueError("van't Hoff factor must be positive")

    numerator = vanthoff_factor * mass_solute_g * R * temperature_K
    denominator = osmotic_pressure_atm * volume_solution_L
    return numerator / denominator
