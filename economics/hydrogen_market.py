"""Hydrogen market module for H2 sales revenue.

Reference: Section 2.5.1, Table 7

H2 price scenarios:
- H1 (Base): $6.6/kg
- H2 (High): $9.9/kg

The hydrogen market allows excess H2 to be sold, providing
revenue that offsets system costs in the COE calculation.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from config.parameters import EconomicParameters


@dataclass
class H2MarketResult:
    """Result of hydrogen market analysis."""

    h2_sold_kg: float  # Total H2 sold
    h2_revenue: float  # Total revenue ($)
    avg_price: float  # Average price ($/kg)
    hours_selling: int  # Hours with H2 sales
    avg_rate_kg_h: float  # Average sales rate (kg/h)
    max_rate_kg_h: float  # Maximum sales rate (kg/h)


class HydrogenMarket:
    """Hydrogen market model for H2 sales."""

    def __init__(
        self,
        base_price: float = 6.6,
        high_price: float = 9.9,
        economic: Optional[EconomicParameters] = None,
    ):
        """Initialize hydrogen market.

        Args:
            base_price: Base H2 price ($/kg)
            high_price: High H2 price for sensitivity ($/kg)
            economic: Economic parameters
        """
        self.base_price = base_price
        self.high_price = high_price
        self.economic = economic or EconomicParameters()

    def calculate_revenue(
        self,
        h2_sold_kg: float,
        price_scenario: str = "base",
    ) -> float:
        """Calculate revenue from H2 sales.

        Args:
            h2_sold_kg: Hydrogen sold in kg
            price_scenario: "base" or "high"

        Returns:
            Revenue in $
        """
        if price_scenario == "high":
            price = self.high_price
        else:
            price = self.base_price

        return h2_sold_kg * price

    def calculate_hourly_revenue(
        self,
        h2_profile_kg_h: np.ndarray,
        price_scenario: str = "base",
    ) -> np.ndarray:
        """Calculate hourly revenue from H2 sales.

        Args:
            h2_profile_kg_h: Hourly H2 sales profile (kg/h)
            price_scenario: "base" or "high"

        Returns:
            Hourly revenue array ($)
        """
        if price_scenario == "high":
            price = self.high_price
        else:
            price = self.base_price

        return h2_profile_kg_h * price

    def analyze_h2_sales(
        self,
        h2_profile_kg_h: np.ndarray,
        price_scenario: str = "base",
    ) -> H2MarketResult:
        """Analyze hydrogen sales over simulation period.

        Args:
            h2_profile_kg_h: Hourly H2 sales profile (kg/h)
            price_scenario: "base" or "high"

        Returns:
            H2MarketResult with sales analysis
        """
        if price_scenario == "high":
            price = self.high_price
        else:
            price = self.base_price

        total_sold = np.sum(h2_profile_kg_h)
        revenue = total_sold * price
        hours_selling = np.sum(h2_profile_kg_h > 0)

        if hours_selling > 0:
            avg_rate = total_sold / hours_selling
        else:
            avg_rate = 0.0

        max_rate = np.max(h2_profile_kg_h)

        return H2MarketResult(
            h2_sold_kg=total_sold,
            h2_revenue=revenue,
            avg_price=price,
            hours_selling=int(hours_selling),
            avg_rate_kg_h=avg_rate,
            max_rate_kg_h=max_rate,
        )

    def compare_price_scenarios(
        self,
        h2_profile_kg_h: np.ndarray,
    ) -> Dict[str, H2MarketResult]:
        """Compare H2 sales under different price scenarios.

        Args:
            h2_profile_kg_h: Hourly H2 sales profile (kg/h)

        Returns:
            Dict with results for each price scenario
        """
        return {
            "base": self.analyze_h2_sales(h2_profile_kg_h, "base"),
            "high": self.analyze_h2_sales(h2_profile_kg_h, "high"),
        }

    def calculate_breakeven_h2(
        self,
        system_cost: float,
        annual_energy_kwh: float,
        target_coe: float,
        price_scenario: str = "base",
    ) -> float:
        """Calculate H2 sales needed to achieve target COE.

        From COE = (TC - H2_Revenue) / Energy:
        H2_Revenue = TC - COE * Energy
        H2_sold = H2_Revenue / price

        Args:
            system_cost: Total system cost ($)
            annual_energy_kwh: Annual energy served (kWh)
            target_coe: Target COE ($/kWh)
            price_scenario: "base" or "high"

        Returns:
            H2 sales needed (kg)
        """
        if price_scenario == "high":
            price = self.high_price
        else:
            price = self.base_price

        required_revenue = system_cost - target_coe * annual_energy_kwh
        h2_needed = required_revenue / price

        return max(h2_needed, 0)

    def calculate_coe_reduction(
        self,
        h2_sold_kg: float,
        annual_energy_kwh: float,
        price_scenario: str = "base",
    ) -> float:
        """Calculate COE reduction from H2 sales.

        Args:
            h2_sold_kg: Hydrogen sold (kg)
            annual_energy_kwh: Annual energy served (kWh)
            price_scenario: "base" or "high"

        Returns:
            COE reduction ($/kWh)
        """
        if annual_energy_kwh <= 0:
            return 0.0

        revenue = self.calculate_revenue(h2_sold_kg, price_scenario)

        # Calculate NPV of revenue
        dr = self.economic.discount_rate
        n = self.economic.project_lifetime

        if dr > 0:
            revenue_npv = revenue * (1 - (1 + dr) ** (-n)) / dr
        else:
            revenue_npv = revenue * n

        # Energy NPV
        if dr > 0:
            energy_npv = annual_energy_kwh * (1 - (1 + dr) ** (-n)) / dr
        else:
            energy_npv = annual_energy_kwh * n

        return revenue_npv / energy_npv

    def get_optimal_h2_strategy(
        self,
        h2_available_profile: np.ndarray,
        storage_capacity_kg: float,
        fc_consumption_profile: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Determine optimal H2 allocation between FC and market.

        Simple strategy: Prioritize FC, sell excess.

        Args:
            h2_available_profile: H2 production profile (kg/h)
            storage_capacity_kg: H2 storage capacity (kg)
            fc_consumption_profile: FC H2 consumption profile (kg/h)

        Returns:
            Tuple of (h2_to_fc, h2_to_market) profiles
        """
        h2_to_fc = np.minimum(h2_available_profile, fc_consumption_profile)
        h2_to_market = h2_available_profile - h2_to_fc

        # Clip to non-negative
        h2_to_market = np.maximum(h2_to_market, 0)

        return h2_to_fc, h2_to_market

    def calculate_npv_revenue(
        self,
        annual_h2_revenue: float,
        years: Optional[int] = None,
    ) -> float:
        """Calculate NPV of H2 revenue stream.

        Args:
            annual_h2_revenue: Annual H2 revenue ($)
            years: Project lifetime (uses default if not provided)

        Returns:
            NPV of revenue ($)
        """
        if years is None:
            years = self.economic.project_lifetime

        dr = self.economic.discount_rate

        if dr > 0:
            npv = annual_h2_revenue * (1 - (1 + dr) ** (-years)) / dr
        else:
            npv = annual_h2_revenue * years

        return npv

    def validate_h2_pricing(self) -> Dict[str, float]:
        """Validate H2 pricing against paper values.

        Expected from Table 7:
        - H1 (Base): $6.6/kg
        - H2 (High): $9.9/kg

        Returns:
            Validation results
        """
        expected_base = 6.6
        expected_high = 9.9

        return {
            "base_price": self.base_price,
            "expected_base": expected_base,
            "base_valid": abs(self.base_price - expected_base) < 0.1,
            "high_price": self.high_price,
            "expected_high": expected_high,
            "high_valid": abs(self.high_price - expected_high) < 0.1,
        }
