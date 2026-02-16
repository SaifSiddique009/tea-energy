"""Objective functions for multi-objective optimization.

Reference: Section 2.5, Equations 1, 6-7

Eq 1: min F(x) = (f1(COE), f2(UME)) with ε-constraint
Eq 6: Ri_h = 1 - UME_h (Reliability index)
Eq 7: f2(UME) = Σ_h [(P^D_h + P^ELZ_h) - P^HRES_h] / P^HRES_h

The two objectives are:
- f1(COE): Minimize Cost of Energy ($/kWh)
- f2(UME): Minimize Unmet Energy (fraction)
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np

from economics.costs import CostCalculator, SystemCosts
from economics.coe_calculator import COECalculator
from config.parameters import ComponentCosts, EconomicParameters


@dataclass
class ObjectiveValues:
    """Objective function values."""

    coe: float  # f1: Cost of Energy ($/kWh)
    ume: float  # f2: Unmet Energy fraction
    reliability: float  # Ri = 1 - UME


class ObjectiveCalculator:
    """Calculator for objective functions f1(COE) and f2(UME)."""

    def __init__(
        self,
        costs: Optional[ComponentCosts] = None,
        economic: Optional[EconomicParameters] = None,
    ):
        """Initialize objective calculator.

        Args:
            costs: Component cost parameters
            economic: Economic parameters
        """
        self.costs = costs or ComponentCosts()
        self.economic = economic or EconomicParameters()
        self.coe_calculator = COECalculator(self.costs, self.economic)

    def calculate_f1_coe(
        self,
        system_costs: SystemCosts,
        annual_energy_kwh: float,
        h2_sold_kg: float = 0.0,
        h2_price: Optional[float] = None,
        include_h2_market: bool = True,
    ) -> float:
        """Calculate f1: Cost of Energy (COE).

        Implements COE calculation from Equation 2.

        Args:
            system_costs: System cost breakdown
            annual_energy_kwh: Annual energy served
            h2_sold_kg: Annual H2 sold
            h2_price: H2 price (uses default if not provided)
            include_h2_market: Whether to include H2 revenue

        Returns:
            COE in $/kWh
        """
        result = self.coe_calculator.calculate_coe(
            system_costs,
            annual_energy_kwh,
            h2_sold_kg,
            h2_price,
            include_h2_market,
        )
        return result.coe

    def calculate_f2_ume(
        self,
        demand_profile_kw: np.ndarray,
        supply_profile_kw: np.ndarray,
        elz_consumption_kw: np.ndarray,
    ) -> float:
        """Calculate f2: Unmet Energy (UME).

        Implements Equation 7:
        f2(UME) = Σ_h [(P^D_h + P^ELZ_h) - P^HRES_h] / Σ P^HRES_h

        Args:
            demand_profile_kw: Hourly load demand (kW)
            supply_profile_kw: Hourly HRES supply (kW)
            elz_consumption_kw: Hourly electrolyzer consumption (kW)

        Returns:
            UME fraction (0-1)
        """
        # Total demand includes load + electrolyzer
        total_demand = demand_profile_kw + elz_consumption_kw

        # Unmet energy at each hour
        unmet = np.maximum(total_demand - supply_profile_kw, 0)

        # Total unmet energy
        total_unmet = np.sum(unmet)

        # Total supply
        total_supply = np.sum(supply_profile_kw)

        if total_supply > 0:
            ume = total_unmet / total_supply
        else:
            ume = 1.0  # All unmet if no supply

        return ume

    def calculate_reliability(
        self,
        demand_profile_kw: np.ndarray,
        supply_profile_kw: np.ndarray,
        elz_consumption_kw: np.ndarray,
    ) -> float:
        """Calculate reliability index.

        Implements Equation 6:
        Ri = 1 - UME

        Args:
            demand_profile_kw: Hourly load demand (kW)
            supply_profile_kw: Hourly HRES supply (kW)
            elz_consumption_kw: Hourly electrolyzer consumption (kW)

        Returns:
            Reliability index (0-1)
        """
        ume = self.calculate_f2_ume(
            demand_profile_kw, supply_profile_kw, elz_consumption_kw
        )
        return 1 - ume

    def calculate_hourly_ume(
        self,
        demand_profile_kw: np.ndarray,
        supply_profile_kw: np.ndarray,
        elz_consumption_kw: np.ndarray,
    ) -> np.ndarray:
        """Calculate hourly unmet energy.

        Args:
            demand_profile_kw: Hourly load demand (kW)
            supply_profile_kw: Hourly HRES supply (kW)
            elz_consumption_kw: Hourly electrolyzer consumption (kW)

        Returns:
            Hourly unmet energy (kW)
        """
        total_demand = demand_profile_kw + elz_consumption_kw
        unmet = np.maximum(total_demand - supply_profile_kw, 0)
        return unmet

    def calculate_objectives(
        self,
        system_costs: SystemCosts,
        demand_profile_kw: np.ndarray,
        supply_profile_kw: np.ndarray,
        elz_consumption_kw: np.ndarray,
        h2_sold_kg: float = 0.0,
        h2_price: Optional[float] = None,
        include_h2_market: bool = True,
    ) -> ObjectiveValues:
        """Calculate both objective functions.

        Args:
            system_costs: System cost breakdown
            demand_profile_kw: Hourly load demand (kW)
            supply_profile_kw: Hourly HRES supply (kW)
            elz_consumption_kw: Hourly electrolyzer consumption (kW)
            h2_sold_kg: Annual H2 sold
            h2_price: H2 price
            include_h2_market: Whether to include H2 revenue

        Returns:
            ObjectiveValues with f1(COE), f2(UME), and reliability
        """
        # Calculate energy served
        total_demand = demand_profile_kw + elz_consumption_kw
        unmet = np.maximum(total_demand - supply_profile_kw, 0)
        served = total_demand - unmet
        annual_energy_kwh = np.sum(served)

        # f1: COE
        coe = self.calculate_f1_coe(
            system_costs,
            annual_energy_kwh,
            h2_sold_kg,
            h2_price,
            include_h2_market,
        )

        # f2: UME
        ume = self.calculate_f2_ume(
            demand_profile_kw, supply_profile_kw, elz_consumption_kw
        )

        # Reliability
        reliability = 1 - ume

        return ObjectiveValues(coe=coe, ume=ume, reliability=reliability)

    def calculate_loss_of_load_probability(
        self,
        demand_profile_kw: np.ndarray,
        supply_profile_kw: np.ndarray,
    ) -> float:
        """Calculate Loss of Load Probability (LOLP).

        LOLP = (Hours with unmet load) / (Total hours)

        Args:
            demand_profile_kw: Hourly load demand (kW)
            supply_profile_kw: Hourly supply (kW)

        Returns:
            LOLP (0-1)
        """
        unmet_hours = np.sum(supply_profile_kw < demand_profile_kw)
        total_hours = len(demand_profile_kw)

        return unmet_hours / total_hours

    def calculate_expected_unserved_energy(
        self,
        demand_profile_kw: np.ndarray,
        supply_profile_kw: np.ndarray,
    ) -> float:
        """Calculate Expected Unserved Energy (EUE).

        EUE = Total unmet energy / Total demand

        Args:
            demand_profile_kw: Hourly load demand (kW)
            supply_profile_kw: Hourly supply (kW)

        Returns:
            EUE fraction (0-1)
        """
        unmet = np.maximum(demand_profile_kw - supply_profile_kw, 0)
        total_unmet = np.sum(unmet)
        total_demand = np.sum(demand_profile_kw)

        if total_demand > 0:
            return total_unmet / total_demand
        return 0.0

    def is_pareto_dominated(
        self,
        solution_a: ObjectiveValues,
        solution_b: ObjectiveValues,
    ) -> bool:
        """Check if solution A is dominated by solution B.

        A is dominated by B if B is at least as good in all objectives
        and strictly better in at least one.

        Args:
            solution_a: First solution
            solution_b: Second solution

        Returns:
            True if A is dominated by B
        """
        # Both objectives are to be minimized
        a_not_worse = (solution_b.coe <= solution_a.coe) and (
            solution_b.ume <= solution_a.ume
        )
        b_strictly_better = (solution_b.coe < solution_a.coe) or (
            solution_b.ume < solution_a.ume
        )

        return a_not_worse and b_strictly_better

    def find_pareto_front(
        self,
        solutions: list,
    ) -> list:
        """Find non-dominated (Pareto optimal) solutions.

        Args:
            solutions: List of ObjectiveValues

        Returns:
            List of non-dominated solutions
        """
        pareto_front = []

        for i, sol_i in enumerate(solutions):
            dominated = False
            for j, sol_j in enumerate(solutions):
                if i != j and self.is_pareto_dominated(sol_i, sol_j):
                    dominated = True
                    break
            if not dominated:
                pareto_front.append(sol_i)

        return pareto_front

    def find_knee_point(
        self,
        pareto_front: list,
    ) -> Tuple[int, ObjectiveValues]:
        """Find knee point of Pareto front.

        The knee point represents the best trade-off between objectives.
        Uses the maximum curvature method.

        Args:
            pareto_front: List of ObjectiveValues on Pareto front

        Returns:
            Tuple of (index, ObjectiveValues) for knee point
        """
        if len(pareto_front) <= 2:
            return 0, pareto_front[0]

        # Normalize objectives
        coes = np.array([s.coe for s in pareto_front])
        umes = np.array([s.ume for s in pareto_front])

        coe_min, coe_max = coes.min(), coes.max()
        ume_min, ume_max = umes.min(), umes.max()

        if coe_max - coe_min > 0:
            coe_norm = (coes - coe_min) / (coe_max - coe_min)
        else:
            coe_norm = np.zeros_like(coes)

        if ume_max - ume_min > 0:
            ume_norm = (umes - ume_min) / (ume_max - ume_min)
        else:
            ume_norm = np.zeros_like(umes)

        # Find point with maximum distance from line connecting extremes
        # Line from (0,1) to (1,0) in normalized space
        distances = np.abs(coe_norm + ume_norm - 1) / np.sqrt(2)

        knee_idx = np.argmax(distances)
        return knee_idx, pareto_front[knee_idx]
