"""Biomass generator model.

Reference: Section 2.5.2.4, Equations 17-21, 28

Eq 17: C_xH_yO_z + O_2 → CO + H_2 + CO_2 + H_2O + Char (Gasification)
Eq 18: Syngas + O_2 → CO_2 + H_2O + Heat (Combustion)
Eq 19: P^BM = Q^B * η_st (Biomass power output)
Eq 20: Q^B = B_h * LHV * (1 - e_Ls) (Heat transfer)
Eq 21: e_Ls = e_fm + e_uc + e_dg + e_lh + e_ma + e_mfc (Total heat losses)
Eq 28: LHV = HHV - l_v * [W_r * (1 + 8.94 * C_H2)] (LHV calculation)

Where:
- P^BM: Biomass generator power output (kW)
- Q^B: Heat transfer to steam cycle (kW)
- B_h: Biomass feed rate (kg/h)
- LHV: Lower heating value (MJ/kg)
- η_st: Steam Rankine cycle efficiency
- e_Ls: Total heat losses
"""

import numpy as np
from typing import Optional, Union

from components.base import PowerGenerator, ComponentOutput
from config.parameters import BiomassParameters, ComponentCosts


class BiomassGenerator(PowerGenerator):
    """Biomass generator model implementing Equations 17-21, 28."""

    def __init__(
        self,
        capacity_kw: float,
        params: Optional[BiomassParameters] = None,
        costs: Optional[ComponentCosts] = None,
    ):
        """Initialize Biomass Generator.

        Args:
            capacity_kw: Rated electrical capacity in kW
            params: Biomass parameters (uses defaults if not provided)
            costs: Component costs (uses defaults if not provided)
        """
        super().__init__(capacity=capacity_kw, name="BiomassGenerator")
        self.params = params or BiomassParameters()
        self.costs = costs or ComponentCosts()

    def calculate_lhv(
        self,
        hhv_mj_kg: float,
        moisture_content: float = 0.10,
        hydrogen_content: float = 0.06,
    ) -> float:
        """Calculate LHV from HHV using Equation 28.

        LHV = HHV - l_v * [W_r * (1 + 8.94 * C_H2)]

        Where:
        - l_v: Latent heat of vaporization (~2.26 MJ/kg)
        - W_r: Moisture content (mass fraction)
        - C_H2: Hydrogen content (mass fraction)

        Args:
            hhv_mj_kg: Higher heating value in MJ/kg
            moisture_content: Moisture content (fraction)
            hydrogen_content: Hydrogen content (fraction)

        Returns:
            LHV in MJ/kg
        """
        l_v = 2.26  # MJ/kg (latent heat of vaporization)

        # Water formed from hydrogen: H_2 + 0.5*O_2 -> H_2O
        # Mass ratio: 9 kg H2O per kg H2 (including original moisture)
        water_from_combustion = 8.94 * hydrogen_content

        lhv = hhv_mj_kg - l_v * (moisture_content + water_from_combustion)

        return max(lhv, 0)

    def calculate_heat_losses(self) -> float:
        """Calculate total heat losses using Equation 21.

        e_Ls = e_fm + e_uc + e_dg + e_lh + e_ma + e_mfc

        Where:
        - e_fm: Fuel moisture losses
        - e_uc: Unburned carbon losses
        - e_dg: Dry gas losses
        - e_lh: Latent heat losses
        - e_ma: Moisture in air losses
        - e_mfc: Manufacturing losses

        Returns:
            Total heat loss fraction
        """
        return self.params.total_heat_loss

    def calculate_feed_rate(
        self,
        power_output_kw: float,
        lhv_mj_kg: float,
    ) -> float:
        """Calculate biomass feed rate for given power output.

        From Equations 19-20:
        P^BM = Q^B * η_st
        Q^B = B_h * LHV * (1 - e_Ls)

        Therefore:
        B_h = P^BM / (η_st * LHV * (1 - e_Ls))

        Args:
            power_output_kw: Desired power output in kW
            lhv_mj_kg: LHV of biomass in MJ/kg

        Returns:
            Feed rate in kg/h
        """
        if power_output_kw <= 0 or lhv_mj_kg <= 0:
            return 0.0

        e_ls = self.calculate_heat_losses()
        eta_st = self.params.thermal_efficiency

        # Convert kW to MJ/h (1 kW = 3.6 MJ/h)
        power_mj_h = power_output_kw * 3.6

        # Feed rate in kg/h
        feed_rate = power_mj_h / (eta_st * lhv_mj_kg * (1 - e_ls))

        return feed_rate

    def calculate_output(
        self,
        power_demand_kw: Union[float, np.ndarray],
        lhv_mj_kg: Union[float, np.ndarray] = None,
        feedstock_available_kg: float = float("inf"),
    ) -> ComponentOutput:
        """Calculate biomass generator output.

        Implements Equations 19-20:
        Q^B = B_h * LHV * (1 - e_Ls)
        P^BM = Q^B * η_st

        Args:
            power_demand_kw: Power demand to meet (kW)
            lhv_mj_kg: LHV of biomass (defaults to dry season value)
            feedstock_available_kg: Available feedstock in kg/h

        Returns:
            ComponentOutput with power output and feed rate
        """
        if lhv_mj_kg is None:
            lhv_mj_kg = self.params.lhv_dry

        power_demand_kw = np.atleast_1d(power_demand_kw).astype(float)
        lhv_mj_kg = np.atleast_1d(lhv_mj_kg).astype(float)

        # Ensure same length
        if len(lhv_mj_kg) == 1 and len(power_demand_kw) > 1:
            lhv_mj_kg = np.full_like(power_demand_kw, lhv_mj_kg[0])

        # Apply capacity constraints
        min_power = self.capacity * self.params.min_load_fraction
        max_power = self.capacity

        # Initialize output arrays
        power_output_kw = np.zeros_like(power_demand_kw)
        feed_rate_kg_h = np.zeros_like(power_demand_kw)

        for i in range(len(power_demand_kw)):
            demand = power_demand_kw[i]
            lhv = lhv_mj_kg[i]

            if demand < min_power:
                # Below minimum load - don't operate
                power_output_kw[i] = 0.0
                feed_rate_kg_h[i] = 0.0
            else:
                # Limit to rated capacity
                target_power = min(demand, max_power)

                # Calculate required feed rate
                required_feed = self.calculate_feed_rate(target_power, lhv)

                # Check feedstock availability
                if required_feed <= feedstock_available_kg:
                    power_output_kw[i] = target_power
                    feed_rate_kg_h[i] = required_feed
                else:
                    # Limited by feedstock
                    feed_rate_kg_h[i] = feedstock_available_kg
                    # Calculate achievable power
                    e_ls = self.calculate_heat_losses()
                    eta_st = self.params.thermal_efficiency
                    heat_mj_h = feedstock_available_kg * lhv * (1 - e_ls)
                    power_output_kw[i] = heat_mj_h * eta_st / 3.6

        # Calculate efficiency
        e_ls = self.calculate_heat_losses()
        overall_efficiency = self.params.thermal_efficiency * (1 - e_ls)

        # Handle scalar case
        if len(power_output_kw) == 1:
            power_output_kw = float(power_output_kw[0])
            feed_rate_kg_h = float(feed_rate_kg_h[0])
            lhv_mj_kg = float(lhv_mj_kg[0])

        is_operating = (
            np.any(power_output_kw > 0)
            if hasattr(power_output_kw, "__len__")
            else power_output_kw > 0
        )

        return ComponentOutput(
            power_kw=power_output_kw,
            efficiency=overall_efficiency,
            is_operating=bool(is_operating),
            details={
                "feed_rate_kg_h": feed_rate_kg_h,
                "lhv_mj_kg": lhv_mj_kg,
                "heat_losses_fraction": e_ls,
                "thermal_efficiency": self.params.thermal_efficiency,
            },
        )

    def calculate_hourly_output(
        self,
        power_demand_kw: np.ndarray,
        lhv_mj_kg: np.ndarray,
    ) -> np.ndarray:
        """Calculate hourly power output.

        Args:
            power_demand_kw: Hourly power demand (8760 values)
            lhv_mj_kg: Hourly LHV values (8760 values)

        Returns:
            Hourly power output in kW
        """
        output = self.calculate_output(power_demand_kw, lhv_mj_kg)
        return output.power_kw

    def get_annual_feedstock_consumption(
        self,
        power_profile_kw: np.ndarray,
        lhv_profile_mj_kg: np.ndarray,
    ) -> float:
        """Calculate annual feedstock consumption.

        Args:
            power_profile_kw: Hourly power output profile
            lhv_profile_mj_kg: Hourly LHV values

        Returns:
            Total feedstock consumption in tons/year
        """
        output = self.calculate_output(power_profile_kw, lhv_profile_mj_kg)
        feed_rates = np.atleast_1d(output.details["feed_rate_kg_h"])

        total_kg = np.sum(feed_rates)
        total_ton = total_kg / 1000

        return total_ton

    def get_capital_cost(self) -> float:
        """Get capital cost for biomass generator.

        Returns:
            Capital cost in $
        """
        return self.capacity * self.costs.biomass_capital

    def get_om_cost(self, hours_operated: float = 8760) -> float:
        """Get annual O&M cost.

        Biomass O&M is based on capacity.

        Returns:
            Annual O&M cost in $
        """
        return self.capacity * self.costs.biomass_om_annual

    def validate_output(
        self,
        power_profile_kw: np.ndarray,
        lhv_profile_mj_kg: np.ndarray,
    ) -> dict:
        """Validate biomass generator performance.

        Args:
            power_profile_kw: Hourly power output profile
            lhv_profile_mj_kg: Hourly LHV values

        Returns:
            Validation metrics
        """
        output = self.calculate_output(power_profile_kw, lhv_profile_mj_kg)
        power = np.atleast_1d(output.power_kw)
        feed_rates = np.atleast_1d(output.details["feed_rate_kg_h"])

        annual_feedstock_ton = np.sum(feed_rates) / 1000
        annual_energy_kwh = np.sum(power)
        hours_operating = np.sum(power > 0)
        capacity_factor = np.mean(power) / self.capacity if self.capacity > 0 else 0

        return {
            "annual_energy_kwh": annual_energy_kwh,
            "annual_feedstock_ton": annual_feedstock_ton,
            "hours_operating": int(hours_operating),
            "capacity_factor": capacity_factor,
            "overall_efficiency": output.efficiency,
            "avg_feed_rate_kg_h": np.mean(feed_rates[feed_rates > 0])
            if np.any(feed_rates > 0)
            else 0,
        }


def calculate_hhv_from_composition(
    carbon: float,
    hydrogen: float,
    oxygen: float,
    nitrogen: float = 0.0,
    sulfur: float = 0.0,
) -> float:
    """Calculate HHV from elemental composition using Dulong's formula.

    HHV = 33.83*C + 144.3*(H - O/8) + 9.42*S (MJ/kg)

    Args:
        carbon: Carbon content (mass fraction)
        hydrogen: Hydrogen content (mass fraction)
        oxygen: Oxygen content (mass fraction)
        nitrogen: Nitrogen content (mass fraction)
        sulfur: Sulfur content (mass fraction)

    Returns:
        HHV in MJ/kg
    """
    # Dulong's formula (simplified)
    hhv = 33.83 * carbon + 144.3 * (hydrogen - oxygen / 8) + 9.42 * sulfur

    return max(hhv, 0)
