"""Physical constants used in H2-HRES calculations.

Reference: Mulumba & Farzaneh (2025) - International Journal of Hydrogen Energy
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PhysicalConstants:
    """Physical constants for electrochemical and thermodynamic calculations."""

    # Faraday constant (C/mol)
    FARADAY: float = 96485.33212

    # Universal gas constant (J/mol·K)
    GAS_CONSTANT: float = 8.314462618

    # Standard temperature (K)
    STANDARD_TEMP: float = 298.15

    # Standard pressure (Pa)
    STANDARD_PRESSURE: float = 101325.0

    # Latent heat of vaporization of water at 25°C (kJ/kg)
    LATENT_HEAT_WATER: float = 2441.0

    # Higher heating value of hydrogen (MJ/kg)
    HHV_HYDROGEN: float = 141.8

    # Lower heating value of hydrogen (MJ/kg)
    LHV_HYDROGEN: float = 120.0

    # Standard test condition irradiance for PV (W/m²)
    G_STC: float = 1000.0

    # Nominal Operating Cell Temperature (°C)
    T_NOCT: float = 45.0

    # Reference cell temperature at STC (°C)
    T_STC: float = 25.0

    # Hours in a year
    HOURS_PER_YEAR: int = 8760

    # Reversible voltage for water electrolysis at STC (V)
    V_REV: float = 1.23

    # Thermoneutral voltage for water electrolysis (V)
    V_TN: float = 1.48


# Location coordinates for Embakasi Pipeline Estate, Nairobi, Kenya
@dataclass(frozen=True)
class LocationConstants:
    """Geographic constants for the study area."""

    # Latitude (degrees, negative for South)
    LATITUDE: float = -1.3206

    # Longitude (degrees)
    LONGITUDE: float = 36.8939

    # Altitude (m above sea level)
    ALTITUDE: float = 1795.0

    # Timezone offset from UTC
    TIMEZONE: int = 3  # East Africa Time (EAT)


@dataclass(frozen=True)
class STCConstants:
    """Standard Test Conditions for PV panels."""

    # Irradiance at STC (W/m²)
    IRRADIANCE: float = 1000.0

    # Temperature at STC (°C)
    TEMPERATURE: float = 25.0

    # Air mass at STC
    AIR_MASS: float = 1.5


@dataclass(frozen=True)
class HydrogenConstants:
    """Hydrogen properties."""

    # Molar mass (g/mol)
    MOLAR_MASS: float = 2.016

    # Lower heating value (MJ/kg)
    LHV_MJ_KG: float = 120.0

    # Lower heating value (kWh/kg)
    LHV_KWH_KG: float = 33.33

    # Higher heating value (MJ/kg)
    HHV_MJ_KG: float = 141.8

    # Density at STP (kg/m³)
    DENSITY_STP: float = 0.0899


# Default instances for easy import
PHYSICAL = PhysicalConstants()
LOCATION = LocationConstants()
STC = STCConstants()
H2 = HydrogenConstants()
