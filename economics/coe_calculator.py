"""Cost of Energy (COE) calculator.

Reference: Section 2.5.1, Equation 2

Eq 2: f1(COE) = [TC - β·(G^H·p^H)]/(1+dr)^n / [P^HRES/(1+dr)^n]

Simplified:
COE = (TC - H2_Revenue) / Total_Energy

Where:
- TC: Total cost (capital + O&M)
- β: Binary indicator (1 if H2 market exists, 0 otherwise)
- G^H: Total hydrogen sold (kg)
- p^H: Hydrogen price ($/kg)
- dr: Discount rate
- n: Project lifetime
- P^HRES: Total energy served (kWh)
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np

from economics.costs import CostCalculator, SystemCosts
from config.parameters import ComponentCosts, EconomicParameters


@dataclass
class COEResult:
    """COE calculation result."""

    coe: float  # $/kWh
    total_cost: float  # $ (NPV)
    h2_revenue: float  # $ (NPV)
    net_cost: float  # $ (NPV)
    total_energy_kwh: float  # kWh
    h2_sold_kg: float  # kg
    reliability: float  # 0-1

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "coe_usd_kwh": self.coe,
            "total_cost_usd": self.total_cost,
            "h2_revenue_usd": self.h2_revenue,
            "net_cost_usd": self.net_cost,
            "total_energy_kwh": self.total_energy_kwh,
            "h2_sold_kg": self.h2_sold_kg,
            "reliability": self.reliability,
        }


class COECalculator:
    """Calculator for Cost of Energy (COE) using Equation 2."""

    def __init__(
        self,
        costs: Optional[ComponentCosts] = None,
        economic: Optional[EconomicParameters] = None,
    ):
        """Initialize COE calculator.

        Args:
            costs: Component cost parameters
            economic: Economic parameters
        """
        self.costs = costs or ComponentCosts()
        self.economic = economic or EconomicParameters()
        self.cost_calculator = CostCalculator(self.costs, self.economic)

    def calculate_coe(
        self,
        system_costs: SystemCosts,
        annual_energy_kwh: float,
        h2_sold_kg: float = 0.0,
        h2_price: Optional[float] = None,
        include_h2_market: bool = True,
        unmet_energy_kwh: float = 0.0,
    ) -> COEResult:
        """Calculate Cost of Energy.

        Implements Equation 2:
        COE = (TC - β·(G^H·p^H)) / P^HRES

        Args:
            system_costs: SystemCosts object
            annual_energy_kwh: Annual energy served in kWh
            h2_sold_kg: Annual hydrogen sold in kg
            h2_price: H2 price in $/kg (uses default if not provided)
            include_h2_market: Whether to include H2 revenue (β)
            unmet_energy_kwh: Unmet energy in kWh (for reliability)

        Returns:
            COEResult with COE and related metrics
        """
        if h2_price is None:
            h2_price = self.economic.h2_price_base

        # Calculate NPV of costs
        total_cost_npv = self.cost_calculator.calculate_npv_costs(system_costs)

        # Calculate H2 revenue (NPV)
        if include_h2_market and h2_sold_kg > 0:
            h2_annual_revenue = h2_sold_kg * h2_price
            # NPV of H2 revenue over project lifetime
            h2_revenue_npv = self._calculate_annuity_npv(h2_annual_revenue)
        else:
            h2_revenue_npv = 0.0

        # Net cost
        net_cost = total_cost_npv - h2_revenue_npv

        # Total energy over project lifetime (NPV-weighted)
        energy_npv = self._calculate_annuity_npv(annual_energy_kwh)

        # COE calculation
        if energy_npv > 0:
            coe = net_cost / energy_npv
        else:
            coe = float("inf")

        # Reliability calculation
        total_demand = annual_energy_kwh + unmet_energy_kwh
        if total_demand > 0:
            reliability = 1 - (unmet_energy_kwh / total_demand)
        else:
            reliability = 1.0

        return COEResult(
            coe=coe,
            total_cost=total_cost_npv,
            h2_revenue=h2_revenue_npv,
            net_cost=net_cost,
            total_energy_kwh=annual_energy_kwh,
            h2_sold_kg=h2_sold_kg,
            reliability=reliability,
        )

    def _calculate_annuity_npv(self, annual_value: float) -> float:
        """Calculate NPV of an annual value over project lifetime.

        Args:
            annual_value: Annual value (e.g., revenue, energy)

        Returns:
            NPV of the annual value stream
        """
        dr = self.economic.discount_rate
        n = self.economic.project_lifetime

        # NPV of annuity: PV = A * [(1 - (1+r)^-n) / r]
        if dr > 0:
            npv = annual_value * (1 - (1 + dr) ** (-n)) / dr
        else:
            npv = annual_value * n

        return npv

    def calculate_coe_sensitivity(
        self,
        system_costs: SystemCosts,
        annual_energy_kwh: float,
        h2_sold_kg: float = 0.0,
        h2_prices: Optional[list] = None,
    ) -> Dict[float, COEResult]:
        """Calculate COE for different H2 prices.

        Args:
            system_costs: SystemCosts object
            annual_energy_kwh: Annual energy served in kWh
            h2_sold_kg: Annual hydrogen sold in kg
            h2_prices: List of H2 prices to evaluate

        Returns:
            Dict mapping H2 price to COEResult
        """
        if h2_prices is None:
            h2_prices = [self.economic.h2_price_base, self.economic.h2_price_high]

        results = {}
        for price in h2_prices:
            results[price] = self.calculate_coe(
                system_costs,
                annual_energy_kwh,
                h2_sold_kg,
                h2_price=price,
                include_h2_market=True,
            )

        return results

    def calculate_coe_without_h2(
        self,
        system_costs: SystemCosts,
        annual_energy_kwh: float,
        unmet_energy_kwh: float = 0.0,
    ) -> COEResult:
        """Calculate COE without hydrogen market.

        This represents the scenario where β = 0 in Equation 2.

        Args:
            system_costs: SystemCosts object
            annual_energy_kwh: Annual energy served in kWh
            unmet_energy_kwh: Unmet energy in kWh

        Returns:
            COEResult with COE (no H2 revenue)
        """
        return self.calculate_coe(
            system_costs,
            annual_energy_kwh,
            h2_sold_kg=0.0,
            include_h2_market=False,
            unmet_energy_kwh=unmet_energy_kwh,
        )

    def compare_scenarios(
        self,
        system_costs: SystemCosts,
        annual_energy_kwh: float,
        h2_sold_kg: float,
        unmet_energy_kwh: float = 0.0,
    ) -> Dict[str, COEResult]:
        """Compare COE across different market scenarios.

        Args:
            system_costs: SystemCosts object
            annual_energy_kwh: Annual energy served in kWh
            h2_sold_kg: Annual hydrogen sold in kg
            unmet_energy_kwh: Unmet energy in kWh

        Returns:
            Dict with COE for each scenario
        """
        return {
            "no_h2_market": self.calculate_coe_without_h2(
                system_costs, annual_energy_kwh, unmet_energy_kwh
            ),
            "h2_base_price": self.calculate_coe(
                system_costs,
                annual_energy_kwh,
                h2_sold_kg,
                h2_price=self.economic.h2_price_base,
                unmet_energy_kwh=unmet_energy_kwh,
            ),
            "h2_high_price": self.calculate_coe(
                system_costs,
                annual_energy_kwh,
                h2_sold_kg,
                h2_price=self.economic.h2_price_high,
                unmet_energy_kwh=unmet_energy_kwh,
            ),
        }

    def validate_against_paper(
        self,
        coe_with_h2: float,
        coe_without_h2: float,
        reliability_with_h2: float,
        reliability_without_h2: float,
    ) -> Dict[str, bool]:
        """Validate calculated COE against paper results.

        Expected results from paper:
        - COE with H2 market @ $6.6/kg: $0.494/kWh
        - COE without H2 market: $0.668/kWh
        - Reliability with H2 market: 0.961
        - Reliability without H2 market: 0.978

        Args:
            coe_with_h2: Calculated COE with H2 market
            coe_without_h2: Calculated COE without H2 market
            reliability_with_h2: Calculated reliability with H2 market
            reliability_without_h2: Calculated reliability without H2 market

        Returns:
            Dict with validation results
        """
        # Expected values from paper
        EXPECTED_COE_WITH_H2 = 0.494
        EXPECTED_COE_WITHOUT_H2 = 0.668
        EXPECTED_REL_WITH_H2 = 0.961
        EXPECTED_REL_WITHOUT_H2 = 0.978

        # Tolerances
        COE_TOLERANCE = 0.03  # 3%
        REL_TOLERANCE = 0.02  # 0.02 absolute

        return {
            "coe_with_h2_valid": abs(coe_with_h2 - EXPECTED_COE_WITH_H2) / EXPECTED_COE_WITH_H2 <= COE_TOLERANCE,
            "coe_without_h2_valid": abs(coe_without_h2 - EXPECTED_COE_WITHOUT_H2) / EXPECTED_COE_WITHOUT_H2 <= COE_TOLERANCE,
            "reliability_with_h2_valid": abs(reliability_with_h2 - EXPECTED_REL_WITH_H2) <= REL_TOLERANCE,
            "reliability_without_h2_valid": abs(reliability_without_h2 - EXPECTED_REL_WITHOUT_H2) <= REL_TOLERANCE,
            "calculated_values": {
                "coe_with_h2": coe_with_h2,
                "coe_without_h2": coe_without_h2,
                "reliability_with_h2": reliability_with_h2,
                "reliability_without_h2": reliability_without_h2,
            },
            "expected_values": {
                "coe_with_h2": EXPECTED_COE_WITH_H2,
                "coe_without_h2": EXPECTED_COE_WITHOUT_H2,
                "reliability_with_h2": EXPECTED_REL_WITH_H2,
                "reliability_without_h2": EXPECTED_REL_WITHOUT_H2,
            },
        }
