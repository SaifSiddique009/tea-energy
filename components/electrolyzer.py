"""PEM Electrolyzer model.

Reference: Section 2.5.2.3, Equation 13, Supplementary S2
Q^ELZ = (η_ELZ * P^ELZ) / (2 * F * V_rev)

Where:
- Q^ELZ: Hydrogen production rate (mol/s)
- η_ELZ: Electrolyzer efficiency (voltage × Faradaic × auxiliary)
- P^ELZ: Electrical power input (W)
- F: Faraday constant (96,485 C/mol)
- V_rev: Reversible voltage (~1.23 V at STP)

H2 production in kg/h:
m_H2 = Q^ELZ * M_H2 * 3600 / 1000
     = (η_ELZ * P^ELZ) / (2 * F * V_rev) * 2.016 * 3.6
"""

import numpy as np
from typing import Optional, Union

from components.base import PowerConsumer, ComponentOutput
from config.parameters import ElectrolyzerParameters, ComponentCosts
from config.constants import PHYSICAL, H2


class Electrolyzer(PowerConsumer):
    """PEM Electrolyzer model implementing Equation 13."""

    def __init__(
        self,
        capacity_kw: float,
        params: Optional[ElectrolyzerParameters] = None,
        costs: Optional[ComponentCosts] = None,
    ):
        """Initialize PEM Electrolyzer.

        Args:
            capacity_kw: Rated electrical capacity in kW
            params: Electrolyzer parameters (uses defaults if not provided)
            costs: Component costs (uses defaults if not provided)
        """
        super().__init__(capacity=capacity_kw, name="Electrolyzer")
        self.params = params or ElectrolyzerParameters()
        self.costs = costs or ComponentCosts()

    def calculate_reversible_voltage(
        self,
        temperature_c: float = 80.0,
        pressure_bar: float = 1.0,
    ) -> float:
        """Calculate reversible (thermodynamic) voltage.

        V_rev = E0 + (R*T)/(2*F) * ln(P_H2 * sqrt(P_O2))

        At standard conditions (25°C, 1 bar): V_rev = 1.229 V
        Temperature affects this via Nernst equation.

        Args:
            temperature_c: Operating temperature in °C
            pressure_bar: Operating pressure in bar

        Returns:
            Reversible voltage in V
        """
        # Standard reversible potential
        E0 = 1.229  # V at 25°C

        # Temperature correction
        # dE/dT ≈ -0.85 mV/K for water electrolysis
        temperature_k = temperature_c + 273.15
        T_ref = 298.15  # 25°C in K

        v_rev = E0 - 0.00085 * (temperature_k - T_ref)

        # Pressure correction (simplified Nernst)
        if pressure_bar > 1:
            v_rev += (PHYSICAL.GAS_CONSTANT * temperature_k / (2 * PHYSICAL.FARADAY)) * np.log(
                pressure_bar
            )

        return v_rev

    def calculate_output(
        self,
        power_input_kw: Union[float, np.ndarray],
        temperature_c: float = 80.0,
    ) -> ComponentOutput:
        """Calculate hydrogen production from power input.

        Implements Equation 13:
        Q^ELZ = (η_ELZ * P^ELZ) / (2 * F * V_rev)

        Args:
            power_input_kw: Electrical power input in kW
            temperature_c: Operating temperature in °C

        Returns:
            ComponentOutput with H2 production in kg/h
        """
        power_input_kw = np.atleast_1d(power_input_kw).astype(float)

        # Apply minimum load constraint
        min_power = self.capacity * self.params.min_load_fraction
        power_effective = np.where(
            power_input_kw >= min_power, power_input_kw, 0.0
        )

        # Cap at rated capacity
        power_effective = np.minimum(power_effective, self.capacity)

        # Calculate reversible voltage
        v_rev = self.calculate_reversible_voltage(temperature_c)

        # Convert kW to W
        power_w = power_effective * 1000

        # Hydrogen production rate (mol/s)
        # Q^ELZ = (η_ELZ * P^ELZ) / (2 * F * V_rev)
        h2_mol_per_s = (
            self.params.efficiency * power_w / (2 * PHYSICAL.FARADAY * v_rev)
        )

        # Convert to kg/h
        # M_H2 = 2.016 g/mol = 0.002016 kg/mol
        # 1 hour = 3600 seconds
        h2_kg_per_h = h2_mol_per_s * H2.MOLAR_MASS * 3.6

        # Calculate specific energy consumption (kWh/kg H2)
        with np.errstate(divide="ignore", invalid="ignore"):
            specific_energy = np.where(
                h2_kg_per_h > 0,
                power_effective / h2_kg_per_h,
                0.0,
            )

        # Handle scalar case
        if len(h2_kg_per_h) == 1:
            h2_kg_per_h = float(h2_kg_per_h[0])
            power_effective = float(power_effective[0])
            specific_energy = float(specific_energy[0]) if not np.isnan(specific_energy[0]) else 0.0

        is_operating = np.any(h2_kg_per_h > 0) if hasattr(h2_kg_per_h, "__len__") else h2_kg_per_h > 0

        return ComponentOutput(
            power_kw=-power_effective if isinstance(power_effective, float) else -np.array(power_effective),  # Negative = consumption
            efficiency=self.params.efficiency,
            is_operating=bool(is_operating),
            details={
                "h2_production_kg_h": h2_kg_per_h,
                "power_consumed_kw": power_effective,
                "specific_energy_kwh_kg": specific_energy,
                "reversible_voltage_v": v_rev,
                "operating_temp_c": temperature_c,
            },
        )

    def calculate_h2_production(
        self,
        power_input_kw: Union[float, np.ndarray],
        temperature_c: float = 80.0,
    ) -> Union[float, np.ndarray]:
        """Calculate H2 production rate directly.

        Args:
            power_input_kw: Electrical power input in kW
            temperature_c: Operating temperature in °C

        Returns:
            H2 production rate in kg/h
        """
        output = self.calculate_output(power_input_kw, temperature_c)
        return output.details["h2_production_kg_h"]

    def calculate_power_for_h2(
        self,
        h2_rate_kg_h: float,
        temperature_c: float = 80.0,
    ) -> float:
        """Calculate power needed to produce given H2 rate.

        Inverse of Equation 13:
        P^ELZ = Q^ELZ * 2 * F * V_rev / η_ELZ

        Args:
            h2_rate_kg_h: Desired H2 production rate in kg/h
            temperature_c: Operating temperature in °C

        Returns:
            Required power in kW
        """
        v_rev = self.calculate_reversible_voltage(temperature_c)

        # Convert kg/h to mol/s
        h2_mol_per_s = h2_rate_kg_h / (H2.MOLAR_MASS * 3.6)

        # Power in W
        power_w = h2_mol_per_s * 2 * PHYSICAL.FARADAY * v_rev / self.params.efficiency

        # Convert to kW
        power_kw = power_w / 1000

        return min(power_kw, self.capacity)

    def get_capital_cost(self) -> float:
        """Get capital cost for electrolyzer.

        Returns:
            Capital cost in $
        """
        return self.capacity * self.costs.electrolyzer_capital

    def get_om_cost(self, hours_operated: float = 8760) -> float:
        """Get annual O&M cost.

        Electrolyzer O&M is based on capacity.

        Returns:
            Annual O&M cost in $
        """
        return self.capacity * self.costs.electrolyzer_om_annual

    def get_max_h2_production(self, temperature_c: float = 80.0) -> float:
        """Get maximum H2 production rate at rated capacity.

        Args:
            temperature_c: Operating temperature in °C

        Returns:
            Maximum H2 production in kg/h
        """
        return self.calculate_h2_production(self.capacity, temperature_c)

    def validate_output(
        self,
        power_profile_kw: np.ndarray,
        temperature_c: float = 80.0,
    ) -> dict:
        """Validate electrolyzer performance.

        Args:
            power_profile_kw: Hourly power consumption profile
            temperature_c: Operating temperature

        Returns:
            Validation metrics
        """
        h2_profile = self.calculate_h2_production(power_profile_kw, temperature_c)
        h2_profile = np.atleast_1d(h2_profile)

        total_h2_kg = np.sum(h2_profile)
        total_energy_kwh = np.sum(np.minimum(power_profile_kw, self.capacity))
        avg_specific_energy = total_energy_kwh / total_h2_kg if total_h2_kg > 0 else 0

        # Theoretical minimum: ~39.4 kWh/kg at 100% efficiency
        theoretical_min = H2.LHV_MJ_KG / 3.6  # Convert MJ/kg to kWh/kg

        return {
            "total_h2_production_kg": total_h2_kg,
            "total_energy_consumed_kwh": total_energy_kwh,
            "avg_specific_energy_kwh_kg": avg_specific_energy,
            "theoretical_min_kwh_kg": theoretical_min,
            "hours_operating": np.sum(h2_profile > 0),
            "utilization_factor": np.mean(power_profile_kw) / self.capacity if self.capacity > 0 else 0,
        }
