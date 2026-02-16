"""Wind turbine model.

Reference: Section 2.5.2.2, Equation 12
Cubic power curve with cut-in, rated, and cut-out speeds.

P^WT = {
    0,                                          if v < v_ci or v > v_co
    P_rated * (v^3 - v_ci^3) / (v_r^3 - v_ci^3), if v_ci ≤ v < v_r
    P_rated,                                     if v_r ≤ v ≤ v_co
}

Where:
- v: Wind speed at hub height (m/s)
- v_ci: Cut-in speed (3 m/s)
- v_r: Rated speed (12 m/s)
- v_co: Cut-out speed (25 m/s)
- P_rated: Rated power (kW)
"""

import numpy as np
from typing import Optional, Union

from components.base import PowerGenerator, ComponentOutput
from config.parameters import WindParameters, ComponentCosts


class WindTurbine(PowerGenerator):
    """Wind turbine model implementing Equation 12."""

    def __init__(
        self,
        capacity_kw: float,
        params: Optional[WindParameters] = None,
        costs: Optional[ComponentCosts] = None,
    ):
        """Initialize Wind Turbine.

        Args:
            capacity_kw: Rated capacity in kW
            params: Wind parameters (uses defaults if not provided)
            costs: Component costs (uses defaults if not provided)
        """
        super().__init__(capacity=capacity_kw, name="WindTurbine")
        self.params = params or WindParameters()
        self.costs = costs or ComponentCosts()

    def adjust_wind_speed(
        self,
        wind_speed: Union[float, np.ndarray],
        reference_height: Optional[float] = None,
    ) -> Union[float, np.ndarray]:
        """Adjust wind speed from reference height to hub height.

        Uses wind shear power law:
        v_hub = v_ref * (h_hub / h_ref)^α

        Args:
            wind_speed: Wind speed at reference height (m/s)
            reference_height: Reference measurement height (m)

        Returns:
            Wind speed at hub height (m/s)
        """
        if reference_height is None:
            reference_height = self.params.reference_height

        # Wind shear adjustment
        height_ratio = self.params.hub_height / reference_height
        adjustment = height_ratio ** self.params.wind_shear_exponent

        return wind_speed * adjustment

    def calculate_output(
        self,
        wind_speed: Union[float, np.ndarray],
        at_hub_height: bool = False,
    ) -> ComponentOutput:
        """Calculate wind turbine power output.

        Implements Equation 12 (cubic power curve):
        - Below cut-in: 0
        - Between cut-in and rated: cubic interpolation
        - Between rated and cut-out: rated power
        - Above cut-out: 0

        Args:
            wind_speed: Wind speed in m/s (can be array for hourly)
            at_hub_height: If True, wind speed is already at hub height

        Returns:
            ComponentOutput with power in kW
        """
        wind_speed = np.atleast_1d(wind_speed).astype(float)

        # Adjust to hub height if needed
        if not at_hub_height:
            wind_speed_hub = self.adjust_wind_speed(wind_speed)
        else:
            wind_speed_hub = wind_speed

        # Get parameters
        v_ci = self.params.v_cut_in
        v_r = self.params.v_rated
        v_co = self.params.v_cut_out

        # Initialize power array
        power_kw = np.zeros_like(wind_speed_hub)

        # Region 1: Below cut-in (v < v_ci) -> 0
        # Already initialized to 0

        # Region 2: Between cut-in and rated (v_ci ≤ v < v_r)
        # P = P_rated * (v^3 - v_ci^3) / (v_r^3 - v_ci^3)
        mask_region2 = (wind_speed_hub >= v_ci) & (wind_speed_hub < v_r)
        if np.any(mask_region2):
            v = wind_speed_hub[mask_region2]
            power_kw[mask_region2] = self.capacity * (v**3 - v_ci**3) / (
                v_r**3 - v_ci**3
            )

        # Region 3: Between rated and cut-out (v_r ≤ v ≤ v_co)
        # P = P_rated
        mask_region3 = (wind_speed_hub >= v_r) & (wind_speed_hub <= v_co)
        power_kw[mask_region3] = self.capacity

        # Region 4: Above cut-out (v > v_co) -> 0
        mask_region4 = wind_speed_hub > v_co
        power_kw[mask_region4] = 0.0

        # Ensure non-negative and capped at capacity
        power_kw = np.clip(power_kw, 0.0, self.capacity)

        # Calculate efficiency (power coefficient)
        # Betz limit is ~0.593, typical turbines achieve 0.35-0.45
        if np.any(wind_speed_hub > 0):
            # Simplified efficiency based on operational region
            efficiency = np.where(
                power_kw > 0, np.minimum(power_kw / self.capacity, 0.45), 0.0
            )
        else:
            efficiency = np.zeros_like(power_kw)

        # Handle scalar case
        if len(power_kw) == 1:
            power_kw = float(power_kw[0])
            efficiency = float(efficiency[0])

        is_operating = np.any(power_kw > 0) if hasattr(power_kw, "__len__") else power_kw > 0

        return ComponentOutput(
            power_kw=power_kw,
            efficiency=float(np.mean(efficiency)) if hasattr(efficiency, "__len__") else efficiency,
            is_operating=bool(is_operating),
            details={
                "wind_speed_hub_m_s": wind_speed_hub if len(wind_speed_hub) > 1 else float(wind_speed_hub[0]),
                "v_cut_in": v_ci,
                "v_rated": v_r,
                "v_cut_out": v_co,
                "hub_height_m": self.params.hub_height,
            },
        )

    def calculate_hourly_output(
        self,
        wind_speed: np.ndarray,
        at_hub_height: bool = False,
    ) -> np.ndarray:
        """Calculate hourly power output for a full year.

        Args:
            wind_speed: Hourly wind speed array (8760 values)
            at_hub_height: If True, wind speed is already at hub height

        Returns:
            Hourly power output in kW (8760 values)
        """
        output = self.calculate_output(wind_speed, at_hub_height)
        return output.power_kw

    def get_capital_cost(self) -> float:
        """Get capital cost for wind turbine.

        Returns:
            Capital cost in $
        """
        return self.capacity * self.costs.wind_capital

    def get_om_cost(self, hours_operated: float = 8760) -> float:
        """Get annual O&M cost.

        Wind O&M is based on capacity, not hours operated.

        Returns:
            Annual O&M cost in $
        """
        return self.capacity * self.costs.wind_om_annual

    def get_annual_energy(
        self,
        wind_speed: np.ndarray,
        at_hub_height: bool = False,
    ) -> float:
        """Calculate annual energy production.

        Args:
            wind_speed: Hourly wind speed (8760 values)
            at_hub_height: If True, wind speed is already at hub height

        Returns:
            Annual energy in kWh
        """
        hourly_power = self.calculate_hourly_output(wind_speed, at_hub_height)
        return np.sum(hourly_power)

    def validate_output(
        self,
        wind_speed: np.ndarray,
        at_hub_height: bool = False,
    ) -> dict:
        """Validate output against expected paper values.

        Expected from paper (Section 3.1):
        - Peak wind speed: 11.3 m/s
        - Average wind speed: 3.69 m/s
        """
        hourly_output = self.calculate_hourly_output(wind_speed, at_hub_height)

        peak_output = np.max(hourly_output)
        avg_output = np.mean(hourly_output)
        capacity_factor = avg_output / self.capacity if self.capacity > 0 else 0

        # Hours in each operational region
        if not at_hub_height:
            wind_hub = self.adjust_wind_speed(wind_speed)
        else:
            wind_hub = wind_speed

        hours_below_cutin = np.sum(wind_hub < self.params.v_cut_in)
        hours_operational = np.sum(
            (wind_hub >= self.params.v_cut_in) & (wind_hub <= self.params.v_cut_out)
        )
        hours_rated = np.sum(
            (wind_hub >= self.params.v_rated) & (wind_hub <= self.params.v_cut_out)
        )

        return {
            "peak_output_kw": peak_output,
            "avg_output_kw": avg_output,
            "annual_energy_kwh": np.sum(hourly_output),
            "capacity_factor": capacity_factor,
            "hours_below_cutin": int(hours_below_cutin),
            "hours_operational": int(hours_operational),
            "hours_at_rated": int(hours_rated),
        }
