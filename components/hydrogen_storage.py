"""Hydrogen storage tank model.

Reference: Section 2.5.2.3, Equation 16
H_h = H_{h-1} + Q^ELZ - Q^FC - G^H

Where:
- H_h: Hydrogen stored at hour h (kg)
- H_{h-1}: Hydrogen stored at previous hour (kg)
- Q^ELZ: Hydrogen produced by electrolyzer (kg/h)
- Q^FC: Hydrogen consumed by fuel cell (kg/h)
- G^H: Hydrogen sold to market (kg/h)

Constraints:
- H_min ≤ H_h ≤ H_max
- SOC_min = 0.10, SOC_max = 0.95
"""

import numpy as np
from typing import Optional, Tuple, Union

from components.base import EnergyStorage, ComponentOutput
from config.parameters import HydrogenStorageParameters, ComponentCosts


class HydrogenStorage(EnergyStorage):
    """Hydrogen storage tank model implementing Equation 16."""

    def __init__(
        self,
        capacity_kg: float,
        params: Optional[HydrogenStorageParameters] = None,
        costs: Optional[ComponentCosts] = None,
    ):
        """Initialize Hydrogen Storage Tank.

        Args:
            capacity_kg: Storage capacity in kg
            params: Storage parameters (uses defaults if not provided)
            costs: Component costs (uses defaults if not provided)
        """
        self.storage_params = params or HydrogenStorageParameters()
        super().__init__(
            capacity=capacity_kg,
            soc_min=self.storage_params.soc_min,
            soc_max=self.storage_params.soc_max,
            initial_soc=self.storage_params.initial_soc,
            name="HydrogenStorage",
        )
        self.costs = costs or ComponentCosts()

        # Initialize storage level
        self.h2_stored_kg = self.capacity * self.initial_soc

    def calculate_output(
        self,
        h2_in_kg: float = 0.0,
        h2_out_kg: float = 0.0,
    ) -> ComponentOutput:
        """Update storage level and return new state.

        Implements Equation 16:
        H_h = H_{h-1} + Q^ELZ - Q^FC - G^H

        Args:
            h2_in_kg: Hydrogen added (from electrolyzer) in kg
            h2_out_kg: Hydrogen removed (FC + sales) in kg

        Returns:
            ComponentOutput with storage state
        """
        # Apply storage efficiency to incoming H2
        h2_in_effective = h2_in_kg * self.storage_params.storage_efficiency

        # Calculate new storage level
        new_level = self.h2_stored_kg + h2_in_effective - h2_out_kg

        # Calculate actual flows based on constraints
        h2_min = self.capacity * self.soc_min
        h2_max = self.capacity * self.soc_max

        # Handle charging limits
        if new_level > h2_max:
            h2_excess = new_level - h2_max
            actual_in = h2_in_effective - h2_excess
            new_level = h2_max
        else:
            actual_in = h2_in_effective

        # Handle discharging limits
        if new_level < h2_min:
            h2_deficit = h2_min - new_level
            actual_out = h2_out_kg - h2_deficit
            new_level = h2_min
        else:
            actual_out = h2_out_kg

        # Update state
        self.h2_stored_kg = new_level
        self.current_soc = new_level / self.capacity if self.capacity > 0 else 0

        return ComponentOutput(
            power_kw=0.0,  # Storage doesn't produce power directly
            efficiency=self.storage_params.storage_efficiency,
            is_operating=(actual_in > 0 or actual_out > 0),
            details={
                "h2_stored_kg": self.h2_stored_kg,
                "soc": self.current_soc,
                "h2_in_kg": actual_in,
                "h2_out_kg": actual_out,
                "available_to_discharge_kg": self.available_to_discharge,
                "available_to_charge_kg": self.available_to_charge,
            },
        )

    def can_discharge(self, h2_requested_kg: float) -> Tuple[bool, float]:
        """Check if discharge is possible and return available amount.

        Args:
            h2_requested_kg: Requested H2 amount in kg

        Returns:
            Tuple of (can_discharge, available_amount)
        """
        available = self.available_to_discharge
        if h2_requested_kg <= available:
            return True, h2_requested_kg
        else:
            return False, available

    def can_charge(self, h2_offered_kg: float) -> Tuple[bool, float]:
        """Check if charging is possible and return acceptable amount.

        Args:
            h2_offered_kg: Offered H2 amount in kg

        Returns:
            Tuple of (can_charge, acceptable_amount)
        """
        space = self.available_to_charge / self.storage_params.storage_efficiency
        if h2_offered_kg <= space:
            return True, h2_offered_kg
        else:
            return False, space

    def simulate_hour(
        self,
        h2_from_elz: float,
        h2_to_fc: float,
        h2_to_market: float,
    ) -> dict:
        """Simulate one hour of storage operation.

        Implements Equation 16 with priority:
        1. Accept H2 from electrolyzer (if space available)
        2. Supply H2 to fuel cell (if available)
        3. Supply H2 to market (if available and requested)

        Args:
            h2_from_elz: H2 from electrolyzer in kg
            h2_to_fc: H2 requested by fuel cell in kg
            h2_to_market: H2 requested for market sales in kg

        Returns:
            Dict with actual flows and storage state
        """
        initial_level = self.h2_stored_kg
        initial_soc = self.current_soc

        # Step 1: Accept H2 from electrolyzer
        can_charge, actual_charge = self.can_charge(h2_from_elz)
        h2_excess = h2_from_elz - actual_charge

        # Step 2: Supply H2 to fuel cell
        can_discharge, actual_fc = self.can_discharge(h2_to_fc)
        h2_fc_deficit = h2_to_fc - actual_fc

        # Step 3: Supply H2 to market (only after FC needs met)
        remaining_discharge = self.available_to_discharge - actual_fc
        actual_market = min(h2_to_market, remaining_discharge)
        h2_market_deficit = h2_to_market - actual_market

        # Update storage
        total_out = actual_fc + actual_market
        output = self.calculate_output(actual_charge, total_out)

        return {
            "initial_level_kg": initial_level,
            "initial_soc": initial_soc,
            "h2_charged_kg": actual_charge,
            "h2_excess_kg": h2_excess,
            "h2_to_fc_kg": actual_fc,
            "h2_fc_deficit_kg": h2_fc_deficit,
            "h2_to_market_kg": actual_market,
            "h2_market_deficit_kg": h2_market_deficit,
            "final_level_kg": self.h2_stored_kg,
            "final_soc": self.current_soc,
        }

    def get_capital_cost(self) -> float:
        """Get capital cost for H2 storage.

        Cost is per kg capacity.

        Returns:
            Capital cost in $
        """
        return self.capacity * self.costs.h2_tank_capital

    def get_om_cost(self, hours_operated: float = 8760) -> float:
        """Get annual O&M cost.

        H2 tank has negligible O&M.

        Returns:
            Annual O&M cost in $
        """
        return self.capacity * self.costs.h2_tank_om_annual

    def reset(self):
        """Reset storage to initial state."""
        super().reset()
        self.h2_stored_kg = self.capacity * self.initial_soc

    def get_annual_cycles(
        self,
        h2_in_profile: np.ndarray,
        h2_out_profile: np.ndarray,
    ) -> float:
        """Calculate equivalent full cycles over a year.

        Args:
            h2_in_profile: Hourly H2 input profile (kg)
            h2_out_profile: Hourly H2 output profile (kg)

        Returns:
            Number of equivalent full cycles
        """
        total_throughput = np.sum(h2_in_profile) + np.sum(h2_out_profile)
        usable_capacity = self.usable_capacity

        if usable_capacity > 0:
            return total_throughput / (2 * usable_capacity)
        return 0.0

    def validate_operation(
        self,
        h2_in_profile: np.ndarray,
        h2_out_profile: np.ndarray,
    ) -> dict:
        """Validate storage operation over simulation period.

        Args:
            h2_in_profile: Hourly H2 input profile (kg)
            h2_out_profile: Hourly H2 output profile (kg)

        Returns:
            Validation metrics
        """
        self.reset()

        soc_profile = []
        level_profile = []

        for h2_in, h2_out in zip(h2_in_profile, h2_out_profile):
            self.calculate_output(h2_in, h2_out)
            soc_profile.append(self.current_soc)
            level_profile.append(self.h2_stored_kg)

        soc_array = np.array(soc_profile)
        level_array = np.array(level_profile)

        return {
            "min_soc": np.min(soc_array),
            "max_soc": np.max(soc_array),
            "avg_soc": np.mean(soc_array),
            "soc_violations": np.sum(
                (soc_array < self.soc_min) | (soc_array > self.soc_max)
            ),
            "total_h2_stored_kg": np.sum(h2_in_profile),
            "total_h2_withdrawn_kg": np.sum(h2_out_profile),
            "annual_cycles": self.get_annual_cycles(h2_in_profile, h2_out_profile),
        }
