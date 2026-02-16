"""Gibbs free energy minimization for HHV calculation.

Reference: Section 2.5.2.4, Equations 22-27

The Gibbs free energy minimization method is used to calculate the
Higher Heating Value (HHV) of biomass feedstock based on its
elemental composition.

Equations 22-27 describe the thermodynamic equilibrium of gasification:
- Eq 22-23: Gibbs free energy of components
- Eq 24-25: Chemical equilibrium constraints
- Eq 26: Mass balance constraints
- Eq 27: Energy balance

This module provides both:
1. Simplified correlations (Dulong, Channiwala-Parikh)
2. Gibbs minimization approach (for validation)
"""

import numpy as np
from scipy.optimize import minimize
from typing import Dict, Optional, Tuple

from config.constants import PHYSICAL


class GibbsMinimizer:
    """Gibbs free energy minimization for biomass HHV calculation."""

    # Standard Gibbs free energy of formation (kJ/mol) at 298.15 K
    GIBBS_FORMATION = {
        "CO": -137.2,
        "CO2": -394.4,
        "H2O": -228.6,
        "H2": 0.0,
        "CH4": -50.5,
        "C": 0.0,
        "O2": 0.0,
        "N2": 0.0,
    }

    # Standard enthalpy of formation (kJ/mol)
    ENTHALPY_FORMATION = {
        "CO": -110.5,
        "CO2": -393.5,
        "H2O_g": -241.8,  # Gas
        "H2O_l": -285.8,  # Liquid
        "H2": 0.0,
        "CH4": -74.8,
        "C": 0.0,
        "O2": 0.0,
    }

    # Molar masses (g/mol)
    MOLAR_MASS = {
        "C": 12.01,
        "H": 1.008,
        "O": 16.00,
        "N": 14.01,
        "S": 32.07,
    }

    def __init__(
        self,
        temperature_k: float = 1073.15,  # 800°C gasification temp
        pressure_bar: float = 1.0,
    ):
        """Initialize Gibbs minimizer.

        Args:
            temperature_k: Gasification temperature in K
            pressure_bar: Gasification pressure in bar
        """
        self.temperature = temperature_k
        self.pressure = pressure_bar

    def calculate_hhv_dulong(
        self,
        carbon: float,
        hydrogen: float,
        oxygen: float,
        nitrogen: float = 0.0,
        sulfur: float = 0.0,
        ash: float = 0.0,
    ) -> float:
        """Calculate HHV using Dulong's formula.

        HHV = 33.83*C + 144.3*(H - O/8) + 9.42*S (MJ/kg)

        This is a simplified empirical correlation widely used
        for biomass HHV estimation.

        Args:
            carbon: Carbon content (mass fraction, dry basis)
            hydrogen: Hydrogen content (mass fraction, dry basis)
            oxygen: Oxygen content (mass fraction, dry basis)
            nitrogen: Nitrogen content (mass fraction, dry basis)
            sulfur: Sulfur content (mass fraction, dry basis)
            ash: Ash content (mass fraction, dry basis)

        Returns:
            HHV in MJ/kg (dry basis)
        """
        # Validate inputs sum to approximately 1
        total = carbon + hydrogen + oxygen + nitrogen + sulfur + ash
        if abs(total - 1.0) > 0.05:
            # Normalize
            factor = 1.0 / total
            carbon *= factor
            hydrogen *= factor
            oxygen *= factor
            nitrogen *= factor
            sulfur *= factor

        hhv = 33.83 * carbon + 144.3 * (hydrogen - oxygen / 8) + 9.42 * sulfur

        return max(hhv, 0)

    def calculate_hhv_channiwala(
        self,
        carbon: float,
        hydrogen: float,
        oxygen: float,
        nitrogen: float = 0.0,
        sulfur: float = 0.0,
        ash: float = 0.0,
    ) -> float:
        """Calculate HHV using Channiwala-Parikh correlation.

        HHV = 0.3491*C + 1.1783*H + 0.1005*S - 0.1034*O - 0.0151*N - 0.0211*A

        This correlation is more accurate for biomass fuels.
        All values in mass fractions, result in MJ/kg.

        Args:
            carbon: Carbon content (mass fraction, dry basis)
            hydrogen: Hydrogen content (mass fraction, dry basis)
            oxygen: Oxygen content (mass fraction, dry basis)
            nitrogen: Nitrogen content (mass fraction, dry basis)
            sulfur: Sulfur content (mass fraction, dry basis)
            ash: Ash content (mass fraction, dry basis)

        Returns:
            HHV in MJ/kg (dry basis)
        """
        # Channiwala-Parikh formula coefficients
        hhv = (
            0.3491 * carbon * 100  # Convert fraction to %
            + 1.1783 * hydrogen * 100
            + 0.1005 * sulfur * 100
            - 0.1034 * oxygen * 100
            - 0.0151 * nitrogen * 100
            - 0.0211 * ash * 100
        )

        return max(hhv, 0)

    def calculate_lhv_from_hhv(
        self,
        hhv_mj_kg: float,
        hydrogen: float,
        moisture: float = 0.0,
    ) -> float:
        """Calculate LHV from HHV.

        LHV = HHV - 2.442 * (8.94*H + M)

        Where 2.442 MJ/kg is the latent heat of vaporization at 25°C,
        8.94 is the mass ratio of water to hydrogen (H2 + 0.5O2 -> H2O),
        H is hydrogen content (dry basis), and M is moisture content.

        Args:
            hhv_mj_kg: HHV in MJ/kg
            hydrogen: Hydrogen content (mass fraction, dry basis)
            moisture: Moisture content (mass fraction, as-received)

        Returns:
            LHV in MJ/kg
        """
        # Water from hydrogen combustion
        water_from_h = 8.94 * hydrogen

        # Total water to evaporate
        total_water = water_from_h + moisture

        # Latent heat of vaporization
        latent_heat = 2.442  # MJ/kg at 25°C

        lhv = hhv_mj_kg - latent_heat * total_water

        return max(lhv, 0)

    def calculate_gibbs_free_energy(
        self,
        species: str,
        n_moles: float,
        temperature_k: float,
    ) -> float:
        """Calculate Gibbs free energy for a species.

        G = G°_f + RT*ln(a)

        Where a is the activity (= partial pressure for ideal gas).

        Args:
            species: Chemical species
            n_moles: Number of moles
            temperature_k: Temperature in K

        Returns:
            Gibbs free energy in kJ
        """
        if species not in self.GIBBS_FORMATION:
            return 0.0

        G_f = self.GIBBS_FORMATION[species]
        R = PHYSICAL.GAS_CONSTANT / 1000  # kJ/(mol·K)

        # For ideal gas, activity = partial pressure / P_ref
        # Simplified: assume ideal mixing
        G = n_moles * (G_f + R * temperature_k * np.log(max(n_moles, 1e-10)))

        return G

    def minimize_gibbs(
        self,
        carbon: float,
        hydrogen: float,
        oxygen: float,
    ) -> Dict[str, float]:
        """Minimize Gibbs free energy to find equilibrium composition.

        Implements Equations 22-27 for gasification equilibrium.

        Args:
            carbon: Moles of carbon in feedstock
            hydrogen: Moles of hydrogen (as H atoms)
            oxygen: Moles of oxygen (as O atoms)

        Returns:
            Dict with equilibrium moles of each species
        """
        # Initial guess (moles): CO, CO2, H2, H2O, CH4, C_solid
        x0 = np.array([0.3, 0.2, 0.3, 0.1, 0.05, 0.05])

        # Bounds (non-negative moles)
        bounds = [(0, None)] * 6

        def objective(x):
            """Total Gibbs free energy to minimize."""
            n_CO, n_CO2, n_H2, n_H2O, n_CH4, n_C = x
            T = self.temperature

            G_total = 0
            G_total += self.calculate_gibbs_free_energy("CO", n_CO, T)
            G_total += self.calculate_gibbs_free_energy("CO2", n_CO2, T)
            G_total += self.calculate_gibbs_free_energy("H2", n_H2, T)
            G_total += self.calculate_gibbs_free_energy("H2O", n_H2O, T)
            G_total += self.calculate_gibbs_free_energy("CH4", n_CH4, T)
            G_total += self.calculate_gibbs_free_energy("C", n_C, T)

            return G_total

        def constraint_carbon(x):
            """Carbon balance: C_in = CO + CO2 + CH4 + C_solid."""
            n_CO, n_CO2, n_H2, n_H2O, n_CH4, n_C = x
            return carbon - (n_CO + n_CO2 + n_CH4 + n_C)

        def constraint_hydrogen(x):
            """Hydrogen balance: H_in = 2*H2 + 2*H2O + 4*CH4."""
            n_CO, n_CO2, n_H2, n_H2O, n_CH4, n_C = x
            return hydrogen - (2 * n_H2 + 2 * n_H2O + 4 * n_CH4)

        def constraint_oxygen(x):
            """Oxygen balance: O_in = CO + 2*CO2 + H2O."""
            n_CO, n_CO2, n_H2, n_H2O, n_CH4, n_C = x
            return oxygen - (n_CO + 2 * n_CO2 + n_H2O)

        constraints = [
            {"type": "eq", "fun": constraint_carbon},
            {"type": "eq", "fun": constraint_hydrogen},
            {"type": "eq", "fun": constraint_oxygen},
        ]

        result = minimize(
            objective,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000},
        )

        if result.success:
            n_CO, n_CO2, n_H2, n_H2O, n_CH4, n_C = result.x
            return {
                "CO": n_CO,
                "CO2": n_CO2,
                "H2": n_H2,
                "H2O": n_H2O,
                "CH4": n_CH4,
                "C_solid": n_C,
                "converged": True,
            }
        else:
            return {
                "CO": 0,
                "CO2": 0,
                "H2": 0,
                "H2O": 0,
                "CH4": 0,
                "C_solid": 0,
                "converged": False,
            }

    def calculate_syngas_hhv(
        self,
        syngas_composition: Dict[str, float],
    ) -> float:
        """Calculate HHV of syngas from its composition.

        Args:
            syngas_composition: Dict with moles of CO, H2, CH4

        Returns:
            HHV in MJ/mol of syngas
        """
        # HHV of components (MJ/mol)
        HHV_CO = 0.283  # CO + 0.5O2 -> CO2
        HHV_H2 = 0.286  # H2 + 0.5O2 -> H2O
        HHV_CH4 = 0.891  # CH4 + 2O2 -> CO2 + 2H2O

        total_moles = sum(syngas_composition.values())
        if total_moles <= 0:
            return 0

        hhv = (
            syngas_composition.get("CO", 0) * HHV_CO
            + syngas_composition.get("H2", 0) * HHV_H2
            + syngas_composition.get("CH4", 0) * HHV_CH4
        )

        return hhv


def calculate_biomass_hhv(
    carbon: float = 0.45,
    hydrogen: float = 0.06,
    oxygen: float = 0.40,
    nitrogen: float = 0.02,
    sulfur: float = 0.01,
    ash: float = 0.06,
    method: str = "channiwala",
) -> float:
    """Calculate biomass HHV using specified method.

    Args:
        carbon: Carbon content (mass fraction)
        hydrogen: Hydrogen content (mass fraction)
        oxygen: Oxygen content (mass fraction)
        nitrogen: Nitrogen content (mass fraction)
        sulfur: Sulfur content (mass fraction)
        ash: Ash content (mass fraction)
        method: "dulong" or "channiwala"

    Returns:
        HHV in MJ/kg
    """
    minimizer = GibbsMinimizer()

    if method.lower() == "dulong":
        return minimizer.calculate_hhv_dulong(
            carbon, hydrogen, oxygen, nitrogen, sulfur, ash
        )
    else:
        return minimizer.calculate_hhv_channiwala(
            carbon, hydrogen, oxygen, nitrogen, sulfur, ash
        )


def calculate_biomass_lhv(
    hhv_mj_kg: Optional[float] = None,
    carbon: float = 0.45,
    hydrogen: float = 0.06,
    oxygen: float = 0.40,
    nitrogen: float = 0.02,
    sulfur: float = 0.01,
    ash: float = 0.06,
    moisture: float = 0.10,
) -> Tuple[float, float]:
    """Calculate biomass LHV from composition or HHV.

    Args:
        hhv_mj_kg: Optional pre-calculated HHV
        carbon, hydrogen, etc.: Elemental composition (mass fractions)
        moisture: Moisture content (as-received)

    Returns:
        Tuple of (HHV, LHV) in MJ/kg
    """
    minimizer = GibbsMinimizer()

    if hhv_mj_kg is None:
        hhv_mj_kg = minimizer.calculate_hhv_channiwala(
            carbon, hydrogen, oxygen, nitrogen, sulfur, ash
        )

    lhv_mj_kg = minimizer.calculate_lhv_from_hhv(hhv_mj_kg, hydrogen, moisture)

    return hhv_mj_kg, lhv_mj_kg
