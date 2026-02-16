"""Solar PV system model.

Reference: Section 2.5.2.2, Equation 11
P^PV = (PV_max * N_p * PV_df) * (G_h / G_STC) * (1 + K_T * ΔT)

Where:
- PV_max: Maximum power per panel (W)
- N_p: Number of panels
- PV_df: Derating factor (0.80)
- G_h: Hourly irradiance (W/m²)
- G_STC: Standard Test Conditions irradiance (1000 W/m²)
- K_T: Temperature coefficient (-0.0045 /°C)
- ΔT: Temperature deviation from STC (T_cell - 25°C)
- T_cell = T_ambient + (G_h / 800) * (T_NOCT - 20)
"""

import numpy as np
from typing import Optional, Union

from components.base import PowerGenerator, ComponentOutput
from config.parameters import PVParameters, ComponentCosts
from config.constants import STC, PHYSICAL


class SolarPV(PowerGenerator):
    """Solar PV system model implementing Equation 11."""

    def __init__(
        self,
        capacity_kw: float,
        params: Optional[PVParameters] = None,
        costs: Optional[ComponentCosts] = None,
    ):
        """Initialize Solar PV system.

        Args:
            capacity_kw: Rated capacity in kW
            params: PV parameters (uses defaults if not provided)
            costs: Component costs (uses defaults if not provided)
        """
        super().__init__(capacity=capacity_kw, name="SolarPV")
        self.params = params or PVParameters()
        self.costs = costs or ComponentCosts()

    def calculate_output(
        self,
        irradiance: Union[float, np.ndarray],
        temperature: Union[float, np.ndarray],
    ) -> ComponentOutput:
        """Calculate PV power output.

        Implements Equation 11:
        P^PV = (PV_max * PV_df) * (G_h / G_STC) * (1 + K_T * ΔT)

        Args:
            irradiance: Solar irradiance in W/m² (can be array for hourly)
            temperature: Ambient temperature in °C (can be array for hourly)

        Returns:
            ComponentOutput with power in kW
        """
        # Ensure arrays for consistent handling
        irradiance = np.atleast_1d(irradiance)
        temperature = np.atleast_1d(temperature)

        # Calculate cell temperature using NOCT model (Eq 11)
        # T_cell = T_ambient + (G_h / 800) * (T_NOCT - 20)
        t_cell = temperature + (irradiance / 800.0) * (PHYSICAL.T_NOCT - 20.0)

        # Temperature deviation from STC (25°C)
        delta_t = t_cell - STC.TEMPERATURE

        # Temperature correction factor: 1 + K_T * ΔT
        # K_T is typically negative (-0.0045), so higher temps reduce output
        temp_factor = 1 + self.params.temp_coefficient * delta_t

        # Irradiance ratio: G_h / G_STC
        irr_ratio = irradiance / STC.IRRADIANCE

        # PV output: capacity * derating * irradiance_ratio * temp_factor
        power_kw = (
            self.capacity * self.params.derating_factor * irr_ratio * temp_factor
        )

        # Ensure non-negative output
        power_kw = np.maximum(power_kw, 0.0)

        # Cap at rated capacity
        power_kw = np.minimum(power_kw, self.capacity)

        # Calculate efficiency
        if np.any(irradiance > 0):
            # Actual efficiency based on output vs ideal
            ideal_power = self.capacity * irr_ratio
            efficiency = np.where(
                ideal_power > 0, power_kw / ideal_power, self.params.efficiency_stc
            )
        else:
            efficiency = np.zeros_like(power_kw)

        # Handle scalar case
        if len(power_kw) == 1:
            power_kw = float(power_kw[0])
            efficiency = float(efficiency[0]) if hasattr(efficiency, "__len__") else efficiency

        is_operating = np.any(power_kw > 0) if hasattr(power_kw, "__len__") else power_kw > 0

        return ComponentOutput(
            power_kw=power_kw,
            efficiency=float(np.mean(efficiency)) if hasattr(efficiency, "__len__") else efficiency,
            is_operating=bool(is_operating),
            details={
                "irradiance_w_m2": irradiance if len(irradiance) > 1 else float(irradiance[0]),
                "temperature_c": temperature if len(temperature) > 1 else float(temperature[0]),
                "derating_factor": self.params.derating_factor,
                "temp_coefficient": self.params.temp_coefficient,
            },
        )

    def calculate_hourly_output(
        self,
        irradiance: np.ndarray,
        temperature: np.ndarray,
    ) -> np.ndarray:
        """Calculate hourly power output for a full year.

        Args:
            irradiance: Hourly irradiance array (8760 values)
            temperature: Hourly temperature array (8760 values)

        Returns:
            Hourly power output in kW (8760 values)
        """
        output = self.calculate_output(irradiance, temperature)
        return output.power_kw

    def get_capital_cost(self) -> float:
        """Get capital cost for PV system.

        Returns:
            Capital cost in $
        """
        return self.capacity * self.costs.pv_capital

    def get_om_cost(self, hours_operated: float = 8760) -> float:
        """Get annual O&M cost.

        PV O&M is based on capacity, not hours operated.

        Returns:
            Annual O&M cost in $
        """
        return self.capacity * self.costs.pv_om_annual

    def get_annual_energy(
        self,
        irradiance: np.ndarray,
        temperature: np.ndarray,
    ) -> float:
        """Calculate annual energy production.

        Args:
            irradiance: Hourly irradiance (8760 values)
            temperature: Hourly temperature (8760 values)

        Returns:
            Annual energy in kWh
        """
        hourly_power = self.calculate_hourly_output(irradiance, temperature)
        return np.sum(hourly_power)

    def validate_output(
        self,
        irradiance: np.ndarray,
        temperature: np.ndarray,
    ) -> dict:
        """Validate output against expected paper values.

        Expected from paper (Section 3.1):
        - Peak irradiance: 1290 W/m²
        - Average irradiance: 479 W/m²
        """
        hourly_output = self.calculate_hourly_output(irradiance, temperature)

        peak_output = np.max(hourly_output)
        avg_output = np.mean(hourly_output)
        capacity_factor = avg_output / self.capacity if self.capacity > 0 else 0

        return {
            "peak_output_kw": peak_output,
            "avg_output_kw": avg_output,
            "annual_energy_kwh": np.sum(hourly_output),
            "capacity_factor": capacity_factor,
            "hours_above_50pct": np.sum(hourly_output > 0.5 * self.capacity),
        }
