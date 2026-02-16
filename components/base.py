"""Abstract base class for system components.

All component models inherit from this base class which defines
the common interface for power generation/consumption calculations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np


@dataclass
class ComponentOutput:
    """Standard output structure for component calculations."""

    power_kw: float  # Power output (positive) or consumption (negative)
    efficiency: float  # Current operating efficiency
    is_operating: bool  # Whether component is active
    details: Dict[str, Any]  # Component-specific details ; for every other component it is different


class Component(ABC):
    """Abstract base class for all H2-HRES components.

    All components must implement:
    - calculate_output(): Compute power/production for given inputs
    - get_capital_cost(): Return capital cost for given capacity
    - get_om_cost(): Return O&M cost for given capacity/operation
    """

    def __init__(
        self,
        capacity: float,
        name: Optional[str] = None,
    ):
        """Initialize component.

        Args:
            capacity: Rated capacity (kW or kg for storage)
            name: Optional component name for identification
        """
        self.capacity = capacity
        self.name = name or self.__class__.__name__

    @abstractmethod
    def calculate_output(self, **kwargs) -> ComponentOutput:
        """Calculate component output for given conditions.

        Returns:
            ComponentOutput with power, efficiency, and details
        """
        pass

    @abstractmethod
    def get_capital_cost(self) -> float:
        """Calculate capital cost for the component.

        Returns:
            Capital cost in $
        """
        pass

    @abstractmethod
    def get_om_cost(self, hours_operated: float = 8760) -> float:
        """Calculate O&M cost for given operation hours.

        Args:
            hours_operated: Hours of operation per year

        Returns:
            Annual O&M cost in $
        """
        pass

    def get_annualized_cost(
        self,
        crf: float,
        hours_operated: float = 8760,
    ) -> float:
        """Calculate annualized cost including capital and O&M.

        Args:
            crf: Capital Recovery Factor
            hours_operated: Annual hours of operation

        Returns:
            Annualized cost in $/year
        """
        capital = self.get_capital_cost()
        om = self.get_om_cost(hours_operated)
        return capital * crf + om

    def validate_capacity(self, min_cap: float = 0, max_cap: float = float("inf")):
        """Validate that capacity is within bounds."""
        if self.capacity < min_cap:
            raise ValueError(
                f"{self.name} capacity {self.capacity} below minimum {min_cap}"
            )
        if self.capacity > max_cap:
            raise ValueError(
                f"{self.name} capacity {self.capacity} above maximum {max_cap}"
            )

    def __repr__(self) -> str:
        return f"{self.name}(capacity={self.capacity:.2f})"


class PowerGenerator(Component):
    """Base class for power-generating components (PV, Wind, Biomass, FC)."""

    def calculate_capacity_factor(
        self,
        actual_output: np.ndarray,
    ) -> float:
        """Calculate capacity factor from hourly output.

        Args:
            actual_output: Array of hourly power outputs (kW)

        Returns:
            Capacity factor (0-1)
        """
        if self.capacity <= 0:
            return 0.0
        return np.mean(actual_output) / self.capacity


class PowerConsumer(Component):
    """Base class for power-consuming components (Electrolyzer)."""

    def calculate_utilization(
        self,
        actual_consumption: np.ndarray,
    ) -> float:
        """Calculate utilization factor from hourly consumption.

        Args:
            actual_consumption: Array of hourly power consumption (kW)

        Returns:
            Utilization factor (0-1)
        """
        if self.capacity <= 0:
            return 0.0
        return np.mean(actual_consumption) / self.capacity


class EnergyStorage(Component):
    """Base class for energy storage components (H2 Tank)."""

    def __init__(
        self,
        capacity: float,
        soc_min: float = 0.1,
        soc_max: float = 0.95,
        initial_soc: float = 0.5,
        name: Optional[str] = None,
    ):
        """Initialize storage component.

        Args:
            capacity: Storage capacity (kg for H2)
            soc_min: Minimum state of charge (fraction)
            soc_max: Maximum state of charge (fraction)
            initial_soc: Initial state of charge (fraction)
            name: Optional component name
        """
        super().__init__(capacity, name)
        self.soc_min = soc_min
        self.soc_max = soc_max
        self.initial_soc = initial_soc
        self.current_soc = initial_soc

    @property
    def usable_capacity(self) -> float:
        """Get usable capacity between SOC limits."""
        return self.capacity * (self.soc_max - self.soc_min)

    @property
    def current_level(self) -> float:
        """Get current storage level."""
        return self.capacity * self.current_soc

    @property
    def available_to_discharge(self) -> float:
        """Get available energy above minimum SOC."""
        return self.capacity * (self.current_soc - self.soc_min)

    @property
    def available_to_charge(self) -> float:
        """Get available capacity below maximum SOC."""
        return self.capacity * (self.soc_max - self.current_soc)

    def reset(self):
        """Reset storage to initial state."""
        self.current_soc = self.initial_soc
