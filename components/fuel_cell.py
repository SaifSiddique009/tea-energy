"""PEM Fuel Cell model.

Reference: Section 2.5.2.3, Equations 14-15, Supplementary S1

Eq 14: P^FC = V_cell * I_cell * N_fc
Eq 15: Q^FC = P^FC / (2 * F * V_cell * N_fc)

Where:
- P^FC: Fuel cell power output (W)
- V_cell: Cell voltage (V)
- I_cell: Cell current (A)
- N_fc: Number of cells in stack
- Q^FC: Hydrogen consumption rate (mol/s)
- F: Faraday constant (96,485 C/mol)
"""

import numpy as np
from typing import Optional, Union

from components.base import PowerGenerator, ComponentOutput
from config.parameters import FuelCellParameters, ComponentCosts
from config.constants import PHYSICAL, H2


class FuelCell(PowerGenerator):
    """PEM Fuel Cell model implementing Equations 14-15."""

    def __init__(
        self,
        capacity_kw: float,
        params: Optional[FuelCellParameters] = None,
        costs: Optional[ComponentCosts] = None,
    ):
        """Initialize PEM Fuel Cell.

        Args:
            capacity_kw: Rated electrical capacity in kW
            params: Fuel cell parameters (uses defaults if not provided)
            costs: Component costs (uses defaults if not provided)
        """
        super().__init__(capacity=capacity_kw, name="FuelCell")
        self.params = params or FuelCellParameters()
        self.costs = costs or ComponentCosts()
        self._hours_operated = 0.0  # Track for O&M cost

    def calculate_cell_voltage(
        self,
        current_density_a_cm2: float = 0.5,
        temperature_c: float = 80.0,
        pressure_bar: float = 2.0,
    ) -> float:
        """Calculate cell voltage using simplified polarization model.

        V_cell = E_rev - V_act - V_ohm - V_conc

        From Supplementary S1:
        - E_rev: Reversible potential (~1.23 V)
        - V_act: Activation losses
        - V_ohm: Ohmic losses
        - V_conc: Concentration losses

        Args:
            current_density_a_cm2: Current density in A/cm²
            temperature_c: Operating temperature in °C
            pressure_bar: Operating pressure in bar

        Returns:
            Cell voltage in V
        """
        temperature_k = temperature_c + 273.15

        # Reversible (Nernst) potential
        # E_rev = 1.229 - 0.85e-3*(T-298.15) + (RT/2F)*ln(P_H2*sqrt(P_O2))
        E_rev = 1.229 - 0.85e-3 * (temperature_k - 298.15)

        # Pressure correction (simplified)
        if pressure_bar > 1:
            E_rev += (PHYSICAL.GAS_CONSTANT * temperature_k / (2 * PHYSICAL.FARADAY)) * np.log(
                pressure_bar
            )

        # Activation overpotential (Tafel equation simplified)
        # V_act = (RT/αF) * ln(i/i0)
        alpha = 0.5  # Charge transfer coefficient
        i0 = 1e-6  # Exchange current density (A/cm²)
        if current_density_a_cm2 > 0:
            V_act = (
                (PHYSICAL.GAS_CONSTANT * temperature_k)
                / (alpha * PHYSICAL.FARADAY)
                * np.log(current_density_a_cm2 / i0)
            )
            V_act = min(V_act, 0.4)  # Cap activation losses
        else:
            V_act = 0

        # Ohmic overpotential
        # V_ohm = i * R_ohm
        R_ohm = 0.1  # Ohm-cm² (area-specific resistance)
        V_ohm = current_density_a_cm2 * R_ohm

        # Concentration overpotential (significant at high current)
        # V_conc = (RT/nF) * ln(1 - i/i_L)
        i_L = 2.0  # Limiting current density (A/cm²)
        if current_density_a_cm2 < i_L:
            V_conc = -(
                (PHYSICAL.GAS_CONSTANT * temperature_k)
                / (2 * PHYSICAL.FARADAY)
                * np.log(1 - current_density_a_cm2 / i_L)
            )
        else:
            V_conc = 0.3  # Maximum concentration loss

        # Cell voltage
        V_cell = E_rev - V_act - V_ohm - V_conc
        V_cell = max(V_cell, 0.4)  # Minimum practical voltage

        return V_cell

    def calculate_output(
        self,
        power_demand_kw: Union[float, np.ndarray],
        h2_available_kg: Union[float, np.ndarray] = float("inf"),
        temperature_c: float = 80.0,
    ) -> ComponentOutput:
        """Calculate fuel cell power output and H2 consumption.

        Implements Equations 14-15:
        - Eq 14: P^FC = V_cell * I_cell * N_fc
        - Eq 15: Q^FC = P^FC / (2 * F * V_cell * N_fc)

        Args:
            power_demand_kw: Power demand to meet (kW)
            h2_available_kg: Available H2 in storage (kg)
            temperature_c: Operating temperature in °C

        Returns:
            ComponentOutput with power output and H2 consumption
        """
        power_demand_kw = np.atleast_1d(power_demand_kw).astype(float)
        h2_available_kg = np.atleast_1d(h2_available_kg).astype(float)

        # Ensure same length
        if len(h2_available_kg) == 1 and len(power_demand_kw) > 1:
            h2_available_kg = np.full_like(power_demand_kw, h2_available_kg[0])

        # Cap power at rated capacity
        power_output_kw = np.minimum(power_demand_kw, self.capacity)
        power_output_kw = np.maximum(power_output_kw, 0.0)

        # Calculate cell voltage at typical operating point
        current_density = 0.5  # A/cm²
        V_cell = self.calculate_cell_voltage(
            current_density, temperature_c, self.params.operating_pressure
        )

        # Fuel cell efficiency
        # η_FC = V_cell / E_thermo (thermoneutral voltage = 1.48 V)
        E_thermo = 1.48
        efficiency = V_cell / E_thermo

        # H2 consumption rate (kg/h)
        # From Eq 15: Q^FC = P^FC / (2 * F * V_cell)
        # Convert to kg/h: m_H2 = Q^FC * M_H2 * 3600 / 1000
        #
        # Simplified: H2 consumption ≈ Power / (efficiency * LHV_H2)
        # LHV_H2 = 120 MJ/kg = 33.33 kWh/kg
        h2_consumption_kg_h = power_output_kw / (efficiency * H2.LHV_KWH_KG)

        # Check H2 availability constraint
        h2_limited_power = np.where(
            h2_consumption_kg_h > h2_available_kg,
            h2_available_kg * efficiency * H2.LHV_KWH_KG,
            power_output_kw,
        )

        # Recalculate H2 consumption with limited power
        actual_h2_consumption = np.where(
            h2_consumption_kg_h > h2_available_kg,
            h2_available_kg,
            h2_consumption_kg_h,
        )

        power_output_kw = h2_limited_power

        # Handle scalar case
        if len(power_output_kw) == 1:
            power_output_kw = float(power_output_kw[0])
            actual_h2_consumption = float(actual_h2_consumption[0])

        is_operating = (
            np.any(power_output_kw > 0)
            if hasattr(power_output_kw, "__len__")
            else power_output_kw > 0
        )

        return ComponentOutput(
            power_kw=power_output_kw,
            efficiency=efficiency,
            is_operating=bool(is_operating),
            details={
                "h2_consumption_kg_h": actual_h2_consumption,
                "cell_voltage_v": V_cell,
                "operating_temp_c": temperature_c,
                "operating_pressure_bar": self.params.operating_pressure,
            },
        )

    def calculate_h2_consumption(
        self,
        power_output_kw: Union[float, np.ndarray],
        temperature_c: float = 80.0,
    ) -> Union[float, np.ndarray]:
        """Calculate H2 consumption for given power output.

        Args:
            power_output_kw: Power output in kW
            temperature_c: Operating temperature in °C

        Returns:
            H2 consumption in kg/h
        """
        output = self.calculate_output(power_output_kw, float("inf"), temperature_c)
        return output.details["h2_consumption_kg_h"]

    def calculate_power_from_h2(
        self,
        h2_rate_kg_h: float,
        temperature_c: float = 80.0,
    ) -> float:
        """Calculate power output from given H2 consumption rate.

        Args:
            h2_rate_kg_h: H2 consumption rate in kg/h
            temperature_c: Operating temperature in °C

        Returns:
            Power output in kW
        """
        # Calculate efficiency
        V_cell = self.calculate_cell_voltage(0.5, temperature_c)
        efficiency = V_cell / 1.48

        # Power = H2 * efficiency * LHV
        power_kw = h2_rate_kg_h * efficiency * H2.LHV_KWH_KG

        return min(power_kw, self.capacity)

    def get_capital_cost(self) -> float:
        """Get capital cost for fuel cell.

        Returns:
            Capital cost in $
        """
        return self.capacity * self.costs.fuel_cell_capital

    def get_om_cost(self, hours_operated: float = 8760) -> float:
        """Get annual O&M cost.

        Fuel cell O&M is based on hours of operation.

        Args:
            hours_operated: Annual hours of operation

        Returns:
            Annual O&M cost in $
        """
        return hours_operated * self.costs.fuel_cell_om_hourly

    def update_hours_operated(self, hours: float):
        """Update cumulative hours operated."""
        self._hours_operated += hours

    def validate_output(
        self,
        power_profile_kw: np.ndarray,
        temperature_c: float = 80.0,
    ) -> dict:
        """Validate fuel cell performance.

        Args:
            power_profile_kw: Hourly power output profile
            temperature_c: Operating temperature

        Returns:
            Validation metrics
        """
        h2_profile = self.calculate_h2_consumption(power_profile_kw, temperature_c)
        h2_profile = np.atleast_1d(h2_profile)

        total_h2_kg = np.sum(h2_profile)
        total_energy_kwh = np.sum(np.minimum(power_profile_kw, self.capacity))

        # Calculate average efficiency
        V_cell = self.calculate_cell_voltage(0.5, temperature_c)
        efficiency = V_cell / 1.48

        return {
            "total_h2_consumption_kg": total_h2_kg,
            "total_energy_produced_kwh": total_energy_kwh,
            "avg_efficiency": efficiency,
            "hours_operating": np.sum(power_profile_kw > 0),
            "capacity_factor": np.mean(power_profile_kw) / self.capacity if self.capacity > 0 else 0,
        }
