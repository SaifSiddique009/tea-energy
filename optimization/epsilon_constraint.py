"""ε-constraint multi-objective MILP optimizer.

Reference: Section 2.5, Equation 1, Figure 3

Algorithm:
1. Solve min f1(COE) → get f1*, f2 at f1*
2. Solve min f2(UME) → get f2*, f1 at f2*
3. Divide [f2*, f2_at_f1*] into N intervals
4. For each ε: min f1 s.t. f2 ≤ ε
5. Filter dominated solutions
6. Find knee point (best trade-off)
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pulp

from optimization.objectives import ObjectiveCalculator, ObjectiveValues
from optimization.constraints import ConstraintBuilder, CapacityBounds
from economics.costs import CostCalculator, SystemCosts
from config.parameters import ComponentCosts, EconomicParameters


@dataclass
class OptimizationResult:
    """Result from a single optimization run."""

    status: str
    coe: float
    ume: float
    reliability: float

    # Optimal capacities
    pv_capacity: float
    wind_capacity: float
    electrolyzer_capacity: float
    fuel_cell_capacity: float
    h2_storage_capacity: float
    biomass_capacity: float

    # Annual values
    annual_energy_kwh: float
    annual_h2_sold_kg: float
    annual_unmet_kwh: float

    # Cost breakdown
    total_cost: float
    h2_revenue: float

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "status": self.status,
            "coe": self.coe,
            "ume": self.ume,
            "reliability": self.reliability,
            "pv_capacity_kw": self.pv_capacity,
            "wind_capacity_kw": self.wind_capacity,
            "electrolyzer_capacity_kw": self.electrolyzer_capacity,
            "fuel_cell_capacity_kw": self.fuel_cell_capacity,
            "h2_storage_capacity_kg": self.h2_storage_capacity,
            "biomass_capacity_kw": self.biomass_capacity,
            "annual_energy_kwh": self.annual_energy_kwh,
            "annual_h2_sold_kg": self.annual_h2_sold_kg,
            "annual_unmet_kwh": self.annual_unmet_kwh,
            "total_cost": self.total_cost,
            "h2_revenue": self.h2_revenue,
        }


@dataclass
class ParetoResult:
    """Complete Pareto front result."""

    solutions: List[OptimizationResult]
    knee_point_idx: int
    f1_anchor: OptimizationResult  # Min COE solution
    f2_anchor: OptimizationResult  # Min UME solution

    @property
    def knee_point(self) -> OptimizationResult:
        """Get knee point solution."""
        return self.solutions[self.knee_point_idx]

    def get_coe_values(self) -> List[float]:
        """Get all COE values."""
        return [s.coe for s in self.solutions]

    def get_ume_values(self) -> List[float]:
        """Get all UME values."""
        return [s.ume for s in self.solutions]


class EpsilonConstraintOptimizer:
    """Multi-objective optimizer using ε-constraint method."""

    def __init__(
        self,
        demand_profile: np.ndarray,
        irradiance_factor: np.ndarray,
        wind_factor: np.ndarray,
        costs: Optional[ComponentCosts] = None,
        economic: Optional[EconomicParameters] = None,
        bounds: Optional[CapacityBounds] = None,
        h2_price: Optional[float] = None,
        lhv_profile: Optional[np.ndarray] = None,
        solver: str = "HiGHS",
        time_limit_sec: int = 300,
        gap_tolerance: float = 0.02,
        solver_verbose: bool = True,
    ):
        """Initialize optimizer.

        Args:
            demand_profile: Hourly demand (kW)
            irradiance_factor: Normalized PV output factor (0-1)
            wind_factor: Normalized wind output factor (0-1)
            costs: Component costs
            economic: Economic parameters
            bounds: Capacity bounds
            h2_price: H2 price for revenue
            lhv_profile: Hourly biomass LHV values (MJ/kg), 8760 array
            solver: MILP solver ("HiGHS", "CBC", or "GLPK")
            time_limit_sec: Max seconds per solve (default 300)
            gap_tolerance: Relative optimality gap (default 0.02 = 2%)
            solver_verbose: Show solver output (default True)
        """
        self.demand = demand_profile
        self.irradiance = irradiance_factor
        self.wind = wind_factor
        self.hours = len(demand_profile)

        self.costs = costs or ComponentCosts()
        self.economic = economic or EconomicParameters()
        self.bounds = bounds or CapacityBounds()
        self.h2_price = h2_price or self.economic.h2_price_base

        # Compute hourly BM fuel cost ($/kWh) from seasonal LHV profile
        if lhv_profile is not None:
            self.lhv_profile = lhv_profile
        else:
            self.lhv_profile = self._default_lhv_profile()

        from config.parameters import BiomassParameters
        bm_params = BiomassParameters()
        fuel_per_kg = self.costs.biomass_fuel_cost / 1000.0  # $/ton → $/kg
        self.bm_fuel_cost_kwh = np.array([
            (3.6 / (bm_params.thermal_efficiency * lhv * (1.0 - bm_params.total_heat_loss))) * fuel_per_kg
            for lhv in self.lhv_profile
        ])

        self.cost_calculator = CostCalculator(self.costs, self.economic)
        self.objective_calculator = ObjectiveCalculator(self.costs, self.economic)
        self.constraint_builder = ConstraintBuilder(self.hours, self.bounds)

        # Design constraints (parameterized for Pareto scaling)
        self.re_min_fraction = 0.90   # Minimum renewable energy fraction
        self.fc_min_energy = 25000.0  # Minimum FC energy contribution (kWh/yr)

        self.time_limit_sec = time_limit_sec
        self.gap_tolerance = gap_tolerance
        self.solver_verbose = solver_verbose

        # Select solver with sane defaults
        msg_flag = solver_verbose
        if solver.upper() == "HIGHS":
            self.solver = pulp.HiGHS(
                msg=msg_flag,
                timeLimit=time_limit_sec,
                gapRel=gap_tolerance,
            )
        elif solver.upper() == "CBC":
            msg_level = 1 if solver_verbose else 0
            self.solver = pulp.PULP_CBC_CMD(
                msg=msg_level,
                timeLimit=time_limit_sec,
                gapRel=gap_tolerance,
            )
        elif solver.upper() == "GLPK":
            msg_level = 1 if solver_verbose else 0
            self.solver = pulp.GLPK_CMD(msg=msg_level)
        else:
            self.solver = pulp.HiGHS(
                msg=msg_flag,
                timeLimit=time_limit_sec,
                gapRel=gap_tolerance,
            )

    @staticmethod
    def _default_lhv_profile() -> np.ndarray:
        """Generate default hourly LHV profile from Nairobi monthly precipitation.

        Returns:
            8760-element array of LHV values (MJ/kg)
        """
        from config.parameters import BiomassParameters
        bm = BiomassParameters()
        # Monthly precipitation (mm) for Nairobi (Table 3-4)
        precip = {1: 60, 2: 50, 3: 100, 4: 200, 5: 150, 6: 30,
                  7: 15, 8: 20, 9: 25, 10: 50, 11: 120, 12: 80}
        lhv = {}
        for m, p in precip.items():
            if p <= 12:
                lhv[m] = bm.lhv_dry
            elif p >= 120:
                lhv[m] = bm.lhv_wet
            else:
                lhv[m] = bm.lhv_dry - ((p - 12) / (120 - 12)) * (bm.lhv_dry - bm.lhv_wet)
        import pandas as pd
        dates = pd.date_range(start="2023-01-01", periods=8760, freq="h")
        return np.array([lhv[m] for m in dates.month])

    def _build_model(
        self,
        name: str = "HRES_Optimization",
    ) -> Tuple[pulp.LpProblem, Dict]:
        """Build the MILP model.

        Returns:
            Tuple of (model, variables_dict)
        """
        model = pulp.LpProblem(name, pulp.LpMinimize)

        # Capacity decision variables
        cap_pv = pulp.LpVariable("cap_pv", lowBound=self.bounds.pv_min, upBound=self.bounds.pv_max)
        cap_wind = pulp.LpVariable("cap_wind", lowBound=self.bounds.wind_min, upBound=self.bounds.wind_max)
        cap_elz = pulp.LpVariable("cap_elz", lowBound=self.bounds.electrolyzer_min, upBound=self.bounds.electrolyzer_max)
        cap_fc = pulp.LpVariable("cap_fc", lowBound=self.bounds.fuel_cell_min, upBound=self.bounds.fuel_cell_max)
        cap_h2 = pulp.LpVariable("cap_h2", lowBound=self.bounds.h2_storage_min, upBound=self.bounds.h2_storage_max)
        cap_bm = pulp.LpVariable("cap_bm", lowBound=self.bounds.biomass_min, upBound=self.bounds.biomass_max)

        # Hourly power variables (simplified - using capacity factors)
        p_pv = [pulp.LpVariable(f"p_pv_{h}", lowBound=0) for h in range(self.hours)]
        p_wind = [pulp.LpVariable(f"p_wind_{h}", lowBound=0) for h in range(self.hours)]
        p_fc = [pulp.LpVariable(f"p_fc_{h}", lowBound=0) for h in range(self.hours)]
        p_bm = [pulp.LpVariable(f"p_bm_{h}", lowBound=0) for h in range(self.hours)]
        p_elz = [pulp.LpVariable(f"p_elz_{h}", lowBound=0) for h in range(self.hours)]
        p_ume = [pulp.LpVariable(f"p_ume_{h}", lowBound=0, upBound=self.demand[h]) for h in range(self.hours)]

        # H2 variables
        q_elz = [pulp.LpVariable(f"q_elz_{h}", lowBound=0) for h in range(self.hours)]
        q_fc = [pulp.LpVariable(f"q_fc_{h}", lowBound=0) for h in range(self.hours)]
        g_h = [pulp.LpVariable(f"g_h_{h}", lowBound=0) for h in range(self.hours)]
        h2_level = [pulp.LpVariable(f"h2_{h}", lowBound=0) for h in range(self.hours)]

        # ── Pure LP formulation (no binary variables) ──
        # Big-M formulation for BM min load creates extremely weak LP relaxation
        # (193% gap), making CBC unable to converge. Without binaries:
        #  - Exact optimal solution with 0% gap
        #  - Solves in ~60 seconds instead of 30+ minutes
        #  - Dispatch simulation handles min load enforcement post-optimization
        # The MILP is used for capacity SIZING; dispatch details are for simulation.

        # Add constraints

        # PV and wind output constraints
        for h in range(self.hours):
            model += p_pv[h] <= cap_pv * self.irradiance[h], f"pv_out_{h}"
            model += p_wind[h] <= cap_wind * self.wind[h], f"wind_out_{h}"

        # Power balance (Eq 8)
        for h in range(self.hours):
            model += (
                p_pv[h] + p_wind[h] + p_fc[h] + p_bm[h]
                == self.demand[h] + p_elz[h] - p_ume[h]
            ), f"balance_{h}"

        # FC and BM constraints (both continuous — pure LP)
        for h in range(self.hours):
            model += p_fc[h] <= cap_fc, f"fc_cap_{h}"
            model += p_bm[h] <= cap_bm, f"bm_cap_{h}"

        # Electrolyzer constraints
        # ELZ can only use RE surplus (Paper dispatch: ELZ runs in Mode 0 only)
        # This is a linear constraint (no binaries needed) that prevents the
        # BM→ELZ→H2 sales exploit where BM powers ELZ for H2 revenue.
        for h in range(self.hours):
            model += p_elz[h] <= cap_elz, f"elz_cap_{h}"
            model += p_elz[h] <= p_pv[h] + p_wind[h], f"elz_re_only_{h}"

        # H2 production/consumption rates
        # ELZ: ~70% efficient → 1/(0.70 * 33.33 kWh/kg) ≈ 0.021 kg/kWh
        ELZ_H2_RATE = 0.02100
        # FC: ~50% efficient (V_cell/1.48 ≈ 0.499) → 1/(0.499 * 33.33) ≈ 0.060 kg/kWh
        FC_H2_RATE = 1.0 / (0.499 * 33.33)  # ~0.0601 kg/kWh

        for h in range(self.hours):
            model += q_elz[h] == p_elz[h] * ELZ_H2_RATE, f"h2_prod_{h}"
            model += q_fc[h] == p_fc[h] * FC_H2_RATE, f"h2_cons_{h}"

        # H2 storage balance
        initial_h2 = 0.5  # Initial SOC fraction

        for h in range(self.hours):
            if h == 0:
                model += (
                    h2_level[h] == initial_h2 * cap_h2 + q_elz[h] - q_fc[h] - g_h[h]
                ), f"h2_bal_{h}"
            else:
                model += (
                    h2_level[h] == h2_level[h - 1] + q_elz[h] - q_fc[h] - g_h[h]
                ), f"h2_bal_{h}"

            # SOC limits
            model += h2_level[h] >= 0.1 * cap_h2, f"h2_min_{h}"
            model += h2_level[h] <= 0.95 * cap_h2, f"h2_max_{h}"

            # CRITICAL FIX: H2 sales bounded by what's available in storage
            # Can only sell H2 that exists (Equation 16 constraint)
            if h == 0:
                # At hour 0, can sell from initial storage + production
                model += g_h[h] <= initial_h2 * cap_h2 + q_elz[h], f"h2_sale_limit_{h}"
            else:
                # At other hours, can sell from previous level + production
                model += g_h[h] <= h2_level[h - 1] + q_elz[h], f"h2_sale_limit_{h}"

            # CRITICAL FIX: Maximum H2 sales rate per hour (market constraint)
            # Realistic market can only absorb limited H2 per hour
            model += g_h[h] <= self.bounds.h2_max_sales_rate, f"h2_max_sales_{h}"

        # CRITICAL FIX: Annual H2 sales limit (market constraint)
        # Local market has finite demand for H2
        model += pulp.lpSum(g_h) <= self.bounds.h2_max_annual_sales, "annual_h2_sales_limit"

        # Minimum renewable energy generation constraint
        # Off-grid HRES systems require substantial RE contribution for sustainability.
        # Without this, the LP trivially selects BM-only (cheapest single source).
        # The paper designs an HRES where PV+Wind are primary sources with BM/FC backup.
        total_demand = sum(self.demand)
        if self.re_min_fraction > 0:
            model += (
                pulp.lpSum(p_pv[h] + p_wind[h] for h in range(self.hours))
                >= self.re_min_fraction * total_demand
            ), "min_renewable_generation"

        # Minimum FC energy contribution (H2-based HRES design requirement)
        # The paper's system uses FC as primary backup (dispatch Mode A, C).
        # FC provides stored RE energy for nighttime/low-wind periods.
        if self.fc_min_energy > 0:
            model += (
                pulp.lpSum(p_fc[h] for h in range(self.hours))
                >= self.fc_min_energy
            ), "min_fc_energy"

        variables = {
            "cap_pv": cap_pv,
            "cap_wind": cap_wind,
            "cap_elz": cap_elz,
            "cap_fc": cap_fc,
            "cap_h2": cap_h2,
            "cap_bm": cap_bm,
            "p_pv": p_pv,
            "p_wind": p_wind,
            "p_fc": p_fc,
            "p_bm": p_bm,
            "p_elz": p_elz,
            "p_ume": p_ume,
            "q_elz": q_elz,
            "q_fc": q_fc,
            "g_h": g_h,
            "h2_level": h2_level,
        }

        return model, variables

    def _calculate_objective_expressions(
        self,
        variables: Dict,
    ) -> Tuple[pulp.LpAffineExpression, pulp.LpAffineExpression]:
        """Calculate objective function expressions.

        Returns:
            Tuple of (coe_expression, ume_expression)
        """
        crf = self.economic.capital_recovery_factor()
        dr = self.economic.discount_rate
        n = self.economic.project_lifetime

        # Effective capital costs including replacement costs (Paper Eq 4)
        # Components with lifetime < project_lifetime need periodic replacements
        # effective_cost = initial + Σ (initial / (1+dr)^t) for each replacement year
        from config.parameters import ComponentLifetimes
        lifetimes = ComponentLifetimes()

        def _effective_capital(initial: float, lifetime: int) -> float:
            total = initial
            t = lifetime
            while t < n:
                total += initial / (1 + dr) ** t
                t += lifetime
            return total

        eff_pv = _effective_capital(self.costs.pv_capital, lifetimes.pv)         # 900 (no replacement)
        eff_wind = _effective_capital(self.costs.wind_capital, lifetimes.wind)    # ~1324
        eff_elz = _effective_capital(self.costs.electrolyzer_capital, lifetimes.electrolyzer)  # ~1053
        eff_fc = _effective_capital(self.costs.fuel_cell_capital, lifetimes.fuel_cell)  # ~2176 (4 replacements!)
        eff_h2 = _effective_capital(self.costs.h2_tank_capital, lifetimes.h2_tank)     # 1100 (no replacement)
        eff_bm = _effective_capital(self.costs.biomass_capital, lifetimes.biomass)      # ~662

        # Capital cost expression with replacement costs and installation factor
        # Paper Eq 4: C_net includes installation/BOS costs (wiring, mounting, etc.)
        inst = self.economic.installation_factor
        capital = inst * (
            eff_pv * variables["cap_pv"]
            + eff_wind * variables["cap_wind"]
            + eff_elz * variables["cap_elz"]
            + eff_fc * variables["cap_fc"]
            + eff_h2 * variables["cap_h2"]
            + eff_bm * variables["cap_bm"]
        )

        # Annual O&M (fixed + variable BM fuel cost)
        om_fixed = (
            self.costs.pv_om_annual * variables["cap_pv"]
            + self.costs.wind_om_annual * variables["cap_wind"]
            + self.costs.electrolyzer_om_annual * variables["cap_elz"]
            + self.costs.biomass_om_annual * variables["cap_bm"]
        )
        # BM variable fuel cost: penalizes each kWh of BM output by seasonal fuel cost
        bm_fuel_cost = pulp.lpSum(
            variables["p_bm"][h] * self.bm_fuel_cost_kwh[h]
            for h in range(self.hours)
        )
        om = om_fixed + bm_fuel_cost

        # Annualized cost
        annual_cost = capital * crf + om

        # H2 revenue
        h2_revenue = self.h2_price * pulp.lpSum(variables["g_h"])

        # Net annual cost
        net_cost = annual_cost - h2_revenue

        # Total energy served (for COE denominator)
        # FIXED: Use demand actually served = demand - unmet energy
        # This matches Equation 2 from the paper: E_served = total demand delivered
        energy_served = pulp.lpSum(
            [
                self.demand[h] - variables["p_ume"][h]
                for h in range(self.hours)
            ]
        )

        # UME expression
        ume = pulp.lpSum(variables["p_ume"])

        return net_cost, ume

    def minimize_coe(self) -> OptimizationResult:
        """Minimize COE (f1) with max UME constraint.

        A max UME bound (50%) prevents the degenerate solution where
        the solver maximizes H2 revenue while serving zero demand.

        Returns:
            OptimizationResult with minimum COE solution
        """
        model, variables = self._build_model("Min_COE")
        net_cost, ume = self._calculate_objective_expressions(variables)

        # Set objective to minimize cost
        model += net_cost, "min_cost"

        # Require at least 50% of demand to be served (prevents degenerate
        # zero-demand solution where solver just maximizes H2 revenue)
        total_demand = sum(self.demand)
        model += ume <= 0.5 * total_demand, "max_ume_bound"

        # Solve
        model.solve(self.solver)

        return self._extract_result(model, variables)

    def minimize_ume(self) -> OptimizationResult:
        """Minimize UME (f2) without COE constraint.

        Returns:
            OptimizationResult with minimum UME solution
        """
        model, variables = self._build_model("Min_UME")
        net_cost, ume = self._calculate_objective_expressions(variables)

        # Set objective to minimize UME
        model += ume, "min_ume"

        # Solve
        model.solve(self.solver)

        return self._extract_result(model, variables)

    def solve_epsilon_constraint(
        self,
        epsilon: float,
    ) -> OptimizationResult:
        """Solve with ε-constraint on UME.

        min f1(COE) s.t. f2(UME) ≤ ε

        Args:
            epsilon: Upper bound on UME as a ratio (0-1)

        Returns:
            OptimizationResult
        """
        model, variables = self._build_model(f"Epsilon_{epsilon:.4f}")
        net_cost, ume = self._calculate_objective_expressions(variables)

        # Set objective to minimize cost
        model += net_cost, "min_cost"

        # Add epsilon constraint (convert ratio to absolute kWh to match ume expression)
        total_demand = sum(self.demand)
        model += ume <= epsilon * total_demand, "epsilon_constraint"

        # Solve
        model.solve(self.solver)

        return self._extract_result(model, variables)

    def generate_pareto_front(
        self,
        n_points: int = 20,
    ) -> ParetoResult:
        """Generate Pareto front using ε-constraint method with adaptive bounds.

        Algorithm from Figure 3, enhanced with adaptive design constraints:
        1. Solve min f2 (UME) with full bounds → f2*, high-reliability anchor
        2. Solve min f1 (COE) with relaxed bounds → f1*, low-reliability anchor
        3. For ε in [f2*, f2_at_f1]: scale bounds proportionally, min f1 s.t. f2 ≤ ε
        4. Filter dominated solutions
        5. Find knee point (optimal trade-off)

        Design constraints (minimum bounds, RE_MIN, FC_MIN_ENERGY) are scaled
        linearly with epsilon to allow the optimizer to find smaller, cheaper
        configurations at lower reliability targets. This produces a proper
        Pareto front where both cost and capacity vary across the front.

        Args:
            n_points: Number of Pareto points to generate

        Returns:
            ParetoResult with Pareto front and knee point
        """
        import copy

        total_solves = n_points
        pareto_start = time.time()

        # Save original bounds and design constraints
        orig_bounds = copy.deepcopy(self.bounds)
        orig_re_min = self.re_min_fraction
        orig_fc_min_e = self.fc_min_energy

        # Step 1: High-reliability anchor — min cost at UME=0 with full bounds
        # Uses solve_epsilon_constraint(0) instead of minimize_ume() to avoid
        # the degenerate solution where minimize_ume() maxes all capacities.
        print(f"  [1/{total_solves}] Finding high-reliability anchor (UME=0)...", end=" ", flush=True)
        t0 = time.time()
        f2_anchor = self.solve_epsilon_constraint(epsilon=0.0)
        elapsed = time.time() - t0
        print(f"Done (UME={f2_anchor.ume:.4f}, COE=${f2_anchor.coe:.3f}/kWh, {elapsed:.1f}s)")
        ume_at_min_ume = f2_anchor.ume

        # Step 2: Low-reliability anchor — min cost with relaxed bounds + max UME
        self.bounds.wind_min = 0.0
        self.bounds.biomass_min = 0.0
        self.bounds.fuel_cell_min = 0.0
        self.bounds.electrolyzer_min = 0.0
        self.bounds.h2_storage_min = 0.0
        self.re_min_fraction = 0.50
        self.fc_min_energy = 0.0

        print(f"  [2/{total_solves}] Finding low-reliability anchor (relaxed)...", end=" ", flush=True)
        t0 = time.time()
        f1_anchor = self.minimize_coe()
        elapsed = time.time() - t0
        coe_str = f"${f1_anchor.coe:.3f}/kWh" if f1_anchor.coe < float("inf") else "N/A"
        print(f"Done (COE={coe_str}, UME={f1_anchor.ume:.4f}, {elapsed:.1f}s)")
        ume_at_min_coe = f1_anchor.ume

        # Step 3: Generate epsilon values with denser spacing near high reliability
        # Use more points in 0-10% UME range where paper's optimal (96.1%) lies
        n_high_res = max(1, n_points // 2)   # Half the points in 0-10% UME
        n_low_res = n_points - n_high_res - 2  # Rest spread across 10-50% UME
        eps_high = np.linspace(ume_at_min_ume, 0.10, n_high_res + 1)[1:]  # skip 0
        eps_low = np.linspace(0.10, ume_at_min_coe, n_low_res + 1)[1:]    # skip 0.10
        epsilon_values = np.concatenate([eps_high, eps_low])

        # Step 4: Solve intermediate points with scaled bounds
        solutions = [f2_anchor]

        for i, eps in enumerate(epsilon_values, start=3):
            # Scale factor: 1.0 at UME=0, 0.0 at UME=max
            if ume_at_min_coe > ume_at_min_ume:
                t = (eps - ume_at_min_ume) / (ume_at_min_coe - ume_at_min_ume)
            else:
                t = 0.0
            scale = max(0.0, 1.0 - t)

            # Scale minimum bounds proportionally
            self.bounds.wind_min = orig_bounds.wind_min * scale
            self.bounds.biomass_min = orig_bounds.biomass_min * scale
            self.bounds.fuel_cell_min = orig_bounds.fuel_cell_min * scale
            self.bounds.electrolyzer_min = orig_bounds.electrolyzer_min * scale
            self.bounds.h2_storage_min = orig_bounds.h2_storage_min * scale

            # Scale design constraints (floor at 50% RE, 0 FC energy)
            self.re_min_fraction = max(0.50, orig_re_min * (0.5 + 0.5 * scale))
            self.fc_min_energy = orig_fc_min_e * scale

            print(f"  [{i}/{total_solves}] UME<={eps:.4f} (scale={scale:.2f})...", end=" ", flush=True)
            t0 = time.time()
            result = self.solve_epsilon_constraint(eps)
            elapsed = time.time() - t0
            if result.status == "Optimal":
                solutions.append(result)
                print(f"COE=${result.coe:.3f}, Rel={result.reliability:.3f} ({elapsed:.1f}s)")
            else:
                print(f"{result.status} ({elapsed:.1f}s)")

        solutions.append(f1_anchor)

        # Restore original bounds and design constraints
        self.bounds = orig_bounds
        self.re_min_fraction = orig_re_min
        self.fc_min_energy = orig_fc_min_e

        total_elapsed = time.time() - pareto_start
        minutes = int(total_elapsed // 60)
        seconds = total_elapsed % 60
        print(f"\n  Pareto front complete. Total time: {minutes}m {seconds:.1f}s")

        # Step 5: Filter dominated solutions
        non_dominated = self._filter_dominated(solutions)

        # Step 6: Find knee point
        knee_idx = self._find_knee_point(non_dominated)

        return ParetoResult(
            solutions=non_dominated,
            knee_point_idx=knee_idx,
            f1_anchor=f1_anchor,
            f2_anchor=f2_anchor,
        )

    def _extract_result(
        self,
        model: pulp.LpProblem,
        variables: Dict,
    ) -> OptimizationResult:
        """Extract results from solved model.

        Args:
            model: Solved PuLP model
            variables: Variable dictionary

        Returns:
            OptimizationResult
        """
        status = pulp.LpStatus[model.status]

        if status != "Optimal":
            return OptimizationResult(
                status=status,
                coe=float("inf"),
                ume=1.0,
                reliability=0.0,
                pv_capacity=0.0,
                wind_capacity=0.0,
                electrolyzer_capacity=0.0,
                fuel_cell_capacity=0.0,
                h2_storage_capacity=0.0,
                biomass_capacity=0.0,
                annual_energy_kwh=0.0,
                annual_h2_sold_kg=0.0,
                annual_unmet_kwh=0.0,
                total_cost=0.0,
                h2_revenue=0.0,
            )

        # Extract capacities
        cap_pv = pulp.value(variables["cap_pv"])
        cap_wind = pulp.value(variables["cap_wind"])
        cap_elz = pulp.value(variables["cap_elz"])
        cap_fc = pulp.value(variables["cap_fc"])
        cap_h2 = pulp.value(variables["cap_h2"])
        cap_bm = pulp.value(variables["cap_bm"])

        # Calculate totals
        # FIXED: Use demand served = demand - unmet (consistent with objective)
        annual_energy = sum(
            self.demand[h] - pulp.value(variables["p_ume"][h])
            for h in range(self.hours)
        )

        annual_unmet = sum(pulp.value(variables["p_ume"][h]) for h in range(self.hours))
        annual_h2_sold = sum(pulp.value(variables["g_h"][h]) for h in range(self.hours))

        # Calculate costs (with replacement costs matching objective)
        crf = self.economic.capital_recovery_factor()
        dr = self.economic.discount_rate
        n = self.economic.project_lifetime
        from config.parameters import ComponentLifetimes
        lifetimes = ComponentLifetimes()

        def _eff_cap(initial, lifetime):
            total = initial
            t = lifetime
            while t < n:
                total += initial / (1 + dr) ** t
                t += lifetime
            return total

        inst = self.economic.installation_factor
        capital = inst * (
            _eff_cap(self.costs.pv_capital, lifetimes.pv) * cap_pv
            + _eff_cap(self.costs.wind_capital, lifetimes.wind) * cap_wind
            + _eff_cap(self.costs.electrolyzer_capital, lifetimes.electrolyzer) * cap_elz
            + _eff_cap(self.costs.fuel_cell_capital, lifetimes.fuel_cell) * cap_fc
            + _eff_cap(self.costs.h2_tank_capital, lifetimes.h2_tank) * cap_h2
            + _eff_cap(self.costs.biomass_capital, lifetimes.biomass) * cap_bm
        )

        # BM fuel cost (matches objective function)
        bm_fuel_total = sum(
            pulp.value(variables["p_bm"][h]) * self.bm_fuel_cost_kwh[h]
            for h in range(self.hours)
        )
        # FC hourly O&M: count hours where FC produced power
        fc_om_total = self.costs.fuel_cell_om_hourly * sum(
            1.0 for h in range(self.hours)
            if pulp.value(variables["p_fc"][h]) > 0.01
        )
        om = (
            self.costs.pv_om_annual * cap_pv
            + self.costs.wind_om_annual * cap_wind
            + self.costs.electrolyzer_om_annual * cap_elz
            + self.costs.biomass_om_annual * cap_bm
            + fc_om_total
            + bm_fuel_total
        )

        total_cost = capital * crf + om
        h2_revenue = self.h2_price * annual_h2_sold

        # Calculate objectives
        if annual_energy > 0:
            coe = (total_cost - h2_revenue) / annual_energy
        else:
            coe = float("inf")

        total_demand = sum(self.demand)
        ume = annual_unmet / total_demand if total_demand > 0 else 1.0
        reliability = 1 - ume

        return OptimizationResult(
            status=status,
            coe=coe,
            ume=ume,
            reliability=reliability,
            pv_capacity=cap_pv,
            wind_capacity=cap_wind,
            electrolyzer_capacity=cap_elz,
            fuel_cell_capacity=cap_fc,
            h2_storage_capacity=cap_h2,
            biomass_capacity=cap_bm,
            annual_energy_kwh=annual_energy,
            annual_h2_sold_kg=annual_h2_sold,
            annual_unmet_kwh=annual_unmet,
            total_cost=total_cost,
            h2_revenue=h2_revenue,
        )

    def _filter_dominated(
        self,
        solutions: List[OptimizationResult],
    ) -> List[OptimizationResult]:
        """Filter dominated solutions from list."""
        non_dominated = []

        for i, sol_i in enumerate(solutions):
            dominated = False
            for j, sol_j in enumerate(solutions):
                if i != j:
                    # Check if sol_j dominates sol_i
                    if (sol_j.coe <= sol_i.coe and sol_j.ume <= sol_i.ume and
                            (sol_j.coe < sol_i.coe or sol_j.ume < sol_i.ume)):
                        dominated = True
                        break
            if not dominated and sol_i.status == "Optimal":
                non_dominated.append(sol_i)

        return non_dominated

    def _find_knee_point(
        self,
        solutions: List[OptimizationResult],
    ) -> int:
        """Find knee point index in Pareto front."""
        if len(solutions) <= 2:
            return 0

        coes = np.array([s.coe for s in solutions])
        umes = np.array([s.ume for s in solutions])

        # Normalize
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

        # Find max distance from line
        distances = np.abs(coe_norm + ume_norm - 1) / np.sqrt(2)
        return int(np.argmax(distances))
