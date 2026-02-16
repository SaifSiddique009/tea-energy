"""Component costs and total cost calculation.

Reference: Section 2.5.1, Table 2, Equations 3-4

Eq 3: TC = Σ_h Σ_τ P^HRES_hτ · λ_τ
Eq 4: λ_τ = λ_PV + λ_WT + λ_ELZ + λ_FC + λ_Hst + λ_OM

Where:
- TC: Total cost
- P^HRES_hτ: Power from component τ at hour h
- λ_τ: Unit cost of component τ
"""

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np

from config.parameters import ComponentCosts, ComponentLifetimes, EconomicParameters


@dataclass
class SystemCosts:
    """System cost breakdown."""

    pv_capital: float = 0.0
    wind_capital: float = 0.0
    electrolyzer_capital: float = 0.0
    fuel_cell_capital: float = 0.0
    h2_storage_capital: float = 0.0
    biomass_capital: float = 0.0

    pv_om: float = 0.0
    wind_om: float = 0.0
    electrolyzer_om: float = 0.0
    fuel_cell_om: float = 0.0
    h2_storage_om: float = 0.0
    biomass_om: float = 0.0

    pv_replacement: float = 0.0
    wind_replacement: float = 0.0
    electrolyzer_replacement: float = 0.0
    fuel_cell_replacement: float = 0.0
    h2_storage_replacement: float = 0.0
    biomass_replacement: float = 0.0

    @property
    def total_capital(self) -> float:
        """Total capital cost."""
        return (
            self.pv_capital
            + self.wind_capital
            + self.electrolyzer_capital
            + self.fuel_cell_capital
            + self.h2_storage_capital
            + self.biomass_capital
        )

    @property
    def total_replacement(self) -> float:
        """Total replacement cost (NPV)."""
        return (
            self.pv_replacement
            + self.wind_replacement
            + self.electrolyzer_replacement
            + self.fuel_cell_replacement
            + self.h2_storage_replacement
            + self.biomass_replacement
        )

    @property
    def total_om(self) -> float:
        """Total O&M cost."""
        return (
            self.pv_om
            + self.wind_om
            + self.electrolyzer_om
            + self.fuel_cell_om
            + self.h2_storage_om
            + self.biomass_om
        )

    @property
    def total_cost(self) -> float:
        """Total system cost (capital + O&M + replacement)."""
        return self.total_capital + self.total_om + self.total_replacement

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "pv_capital": self.pv_capital,
            "wind_capital": self.wind_capital,
            "electrolyzer_capital": self.electrolyzer_capital,
            "fuel_cell_capital": self.fuel_cell_capital,
            "h2_storage_capital": self.h2_storage_capital,
            "biomass_capital": self.biomass_capital,
            "pv_om": self.pv_om,
            "wind_om": self.wind_om,
            "electrolyzer_om": self.electrolyzer_om,
            "fuel_cell_om": self.fuel_cell_om,
            "h2_storage_om": self.h2_storage_om,
            "biomass_om": self.biomass_om,
            "total_capital": self.total_capital,
            "total_om": self.total_om,
            "total_cost": self.total_cost,
        }


class CostCalculator:
    """Calculator for system costs based on Table 2 parameters."""

    def __init__(
        self,
        costs: Optional[ComponentCosts] = None,
        economic: Optional[EconomicParameters] = None,
        lifetimes: Optional[ComponentLifetimes] = None,
    ):
        """Initialize cost calculator.

        Args:
            costs: Component cost parameters
            economic: Economic parameters
            lifetimes: Component lifetimes
        """
        self.costs = costs or ComponentCosts()
        self.economic = economic or EconomicParameters()
        self.lifetimes = lifetimes or ComponentLifetimes()

    def calculate_replacement_costs(
        self,
        pv_capacity_kw: float = 0.0,
        wind_capacity_kw: float = 0.0,
        electrolyzer_capacity_kw: float = 0.0,
        fuel_cell_capacity_kw: float = 0.0,
        h2_storage_capacity_kg: float = 0.0,
        biomass_capacity_kw: float = 0.0,
    ) -> Dict[str, float]:
        """Calculate NPV of replacement costs.

        Args:
            Component capacities

        Returns:
            Dict with replacement cost NPV for each component
        """
        project_life = self.economic.project_lifetime
        dr = self.economic.discount_rate
        
        replacements = {}
        
        # Calculate for each component
        for name, capacity, unit_cost, lifetime in [
            ("pv", pv_capacity_kw, self.costs.pv_capital, self.lifetimes.pv),
            ("wind", wind_capacity_kw, self.costs.wind_capital, self.lifetimes.wind),
            ("electrolyzer", electrolyzer_capacity_kw, self.costs.electrolyzer_capital, self.lifetimes.electrolyzer),
            ("fuel_cell", fuel_cell_capacity_kw, self.costs.fuel_cell_capital, self.lifetimes.fuel_cell),
            ("h2_storage", h2_storage_capacity_kg, self.costs.h2_tank_capital, self.lifetimes.h2_tank),
            ("biomass", biomass_capacity_kw, self.costs.biomass_capital, self.lifetimes.biomass),
        ]:
            npv_rep = 0.0
            if lifetime < project_life:
                # Number of replacements
                # E.g., Life=25, Component=5 -> replacements at 5, 10, 15, 20
                for year in range(lifetime, project_life, lifetime):
                    cost = capacity * unit_cost
                    npv_rep += cost / ((1 + dr) ** year)
            
            replacements[name] = npv_rep
            
        return replacements

    def calculate_capital_costs(
        self,
        pv_capacity_kw: float = 0.0,
        wind_capacity_kw: float = 0.0,
        electrolyzer_capacity_kw: float = 0.0,
        fuel_cell_capacity_kw: float = 0.0,
        h2_storage_capacity_kg: float = 0.0,
        biomass_capacity_kw: float = 0.0,
    ) -> Dict[str, float]:
        """Calculate capital costs for all components.

        Args:
            pv_capacity_kw: PV capacity in kW
            wind_capacity_kw: Wind capacity in kW
            electrolyzer_capacity_kw: Electrolyzer capacity in kW
            fuel_cell_capacity_kw: Fuel cell capacity in kW
            h2_storage_capacity_kg: H2 storage capacity in kg
            biomass_capacity_kw: Biomass generator capacity in kW

        Returns:
            Dict with capital costs for each component
        """
        return {
            "pv": pv_capacity_kw * self.costs.pv_capital,
            "wind": wind_capacity_kw * self.costs.wind_capital,
            "electrolyzer": electrolyzer_capacity_kw * self.costs.electrolyzer_capital,
            "fuel_cell": fuel_cell_capacity_kw * self.costs.fuel_cell_capital,
            "h2_storage": h2_storage_capacity_kg * self.costs.h2_tank_capital,
            "biomass": biomass_capacity_kw * self.costs.biomass_capital,
        }

    def calculate_om_costs(
        self,
        pv_capacity_kw: float = 0.0,
        wind_capacity_kw: float = 0.0,
        electrolyzer_capacity_kw: float = 0.0,
        fuel_cell_hours: float = 0.0,
        h2_storage_capacity_kg: float = 0.0,
        biomass_capacity_kw: float = 0.0,
        biomass_fuel_consumed_ton: float = 0.0,
    ) -> Dict[str, float]:
        """Calculate annual O&M costs for all components.

        Args:
            pv_capacity_kw: PV capacity in kW
            wind_capacity_kw: Wind capacity in kW
            electrolyzer_capacity_kw: Electrolyzer capacity in kW
            fuel_cell_hours: Fuel cell operating hours
            h2_storage_capacity_kg: H2 storage capacity in kg
            biomass_capacity_kw: Biomass generator capacity in kW
            biomass_fuel_consumed_ton: Annual biomass fuel consumption in tons

        Returns:
            Dict with annual O&M costs for each component
        """
        return {
            "pv": pv_capacity_kw * self.costs.pv_om_annual,
            "wind": wind_capacity_kw * self.costs.wind_om_annual,
            "electrolyzer": electrolyzer_capacity_kw * self.costs.electrolyzer_om_annual,
            "fuel_cell": fuel_cell_hours * self.costs.fuel_cell_om_hourly,
            "h2_storage": h2_storage_capacity_kg * self.costs.h2_tank_om_annual,
            "biomass": (biomass_capacity_kw * self.costs.biomass_om_annual) 
                       + (biomass_fuel_consumed_ton * self.costs.biomass_fuel_cost),
        }

    def calculate_system_costs(
        self,
        pv_capacity_kw: float = 0.0,
        wind_capacity_kw: float = 0.0,
        electrolyzer_capacity_kw: float = 0.0,
        fuel_cell_capacity_kw: float = 0.0,
        h2_storage_capacity_kg: float = 0.0,
        biomass_capacity_kw: float = 0.0,
        fuel_cell_hours: float = 0.0,
        biomass_fuel_consumed_ton: float = 0.0,
    ) -> SystemCosts:
        """Calculate complete system costs.

        Args:
            All component capacities and fuel cell operating hours

        Returns:
            SystemCosts with all cost components
        """
        capital = self.calculate_capital_costs(
            pv_capacity_kw,
            wind_capacity_kw,
            electrolyzer_capacity_kw,
            fuel_cell_capacity_kw,
            h2_storage_capacity_kg,
            biomass_capacity_kw,
        )

        om = self.calculate_om_costs(
            pv_capacity_kw,
            wind_capacity_kw,
            electrolyzer_capacity_kw,
            fuel_cell_hours,
            h2_storage_capacity_kg,
            biomass_capacity_kw,
            biomass_fuel_consumed_ton,
        )

        replacement = self.calculate_replacement_costs(
            pv_capacity_kw,
            wind_capacity_kw,
            electrolyzer_capacity_kw,
            fuel_cell_capacity_kw,
            h2_storage_capacity_kg,
            biomass_capacity_kw,
        )

        return SystemCosts(
            pv_capital=capital["pv"],
            wind_capital=capital["wind"],
            electrolyzer_capital=capital["electrolyzer"],
            fuel_cell_capital=capital["fuel_cell"],
            h2_storage_capital=capital["h2_storage"],
            biomass_capital=capital["biomass"],
            pv_om=om["pv"],
            wind_om=om["wind"],
            electrolyzer_om=om["electrolyzer"],
            fuel_cell_om=om["fuel_cell"],
            h2_storage_om=om["h2_storage"],
            biomass_om=om["biomass"],
            pv_replacement=replacement["pv"],
            wind_replacement=replacement["wind"],
            electrolyzer_replacement=replacement["electrolyzer"],
            fuel_cell_replacement=replacement["fuel_cell"],
            h2_storage_replacement=replacement["h2_storage"],
            biomass_replacement=replacement["biomass"],
        )

    def calculate_annualized_cost(
        self,
        system_costs: SystemCosts,
    ) -> float:
        """Calculate annualized cost using CRF.

        Annualized = Capital * CRF + Annual O&M

        Args:
            system_costs: SystemCosts object

        Returns:
            Annualized cost in $/year
        """
        crf = self.economic.capital_recovery_factor()
        annualized_capital = system_costs.total_capital * crf
        annualized_replacement = system_costs.total_replacement * crf
        annual_om = system_costs.total_om

        return annualized_capital + annualized_replacement + annual_om

    def calculate_npv_costs(
        self,
        system_costs: SystemCosts,
        years: Optional[int] = None,
    ) -> float:
        """Calculate NPV of all costs over project lifetime.

        Args:
            system_costs: SystemCosts object
            years: Project lifetime (uses default if not provided)

        Returns:
            NPV of costs in $
        """
        if years is None:
            years = self.economic.project_lifetime

        dr = self.economic.discount_rate

        # Capital at year 0
        npv = system_costs.total_capital + system_costs.total_replacement

        # Annual O&M discounted
        for year in range(1, years + 1):
            npv += system_costs.total_om / (1 + dr) ** year

        return npv

    def calculate_lcoe_components(
        self,
        system_costs: SystemCosts,
        annual_energy_kwh: float,
    ) -> Dict[str, float]:
        """Calculate LCOE contribution from each component.

        Args:
            system_costs: SystemCosts object
            annual_energy_kwh: Annual energy production in kWh

        Returns:
            Dict with LCOE contribution from each component ($/kWh)
        """
        if annual_energy_kwh <= 0:
            return {k: 0.0 for k in ["pv", "wind", "electrolyzer", "fuel_cell", "h2_storage", "biomass"]}

        crf = self.economic.capital_recovery_factor()

        for name, cap, om, rep in [
            ("pv", system_costs.pv_capital, system_costs.pv_om, system_costs.pv_replacement),
            ("wind", system_costs.wind_capital, system_costs.wind_om, system_costs.wind_replacement),
            ("electrolyzer", system_costs.electrolyzer_capital, system_costs.electrolyzer_om, system_costs.electrolyzer_replacement),
            ("fuel_cell", system_costs.fuel_cell_capital, system_costs.fuel_cell_om, system_costs.fuel_cell_replacement),
            ("h2_storage", system_costs.h2_storage_capital, system_costs.h2_storage_om, system_costs.h2_storage_replacement),
            ("biomass", system_costs.biomass_capital, system_costs.biomass_om, system_costs.biomass_replacement),
        ]:
            annualized = cap * crf + om + rep * crf
            components[name] = annualized / annual_energy_kwh

        return components
