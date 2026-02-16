"""Scenario runner for the 8 scenarios from Table 6.

Reference: Section 3.1, Table 6

8 scenarios based on combinations of:
- LHV (High/Low based on precipitation)
- Solar Irradiance (High/Low)
- Wind Speed (High/Low)
"""

import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from simulation.hourly_simulation import HourlySimulator, SimulationConfig, SimulationResult
from economics.costs import CostCalculator
from config.scenarios import Scenarios, ScenarioConfig, MONTH_SCENARIO_MAP
from config.parameters import SystemParameters, DEFAULT_PARAMS


@dataclass
class ScenarioResult:
    """Result for a single scenario simulation."""

    scenario: ScenarioConfig
    simulation: SimulationResult
    monthly_coe: float
    monthly_reliability: float
    monthly_h2_sold: float


@dataclass
class AllScenariosResult:
    """Results for all 8 scenarios."""

    scenarios: Dict[str, ScenarioResult]
    dry_season_avg_coe: float
    wet_season_avg_coe: float
    overall_avg_coe: float
    overall_reliability: float


class ScenarioRunner:
    """Runner for the 8 scenarios from Table 6."""

    def __init__(
        self,
        params: Optional[SystemParameters] = None,
    ):
        """Initialize scenario runner.

        Args:
            params: System parameters
        """
        self.params = params or DEFAULT_PARAMS
        self.simulator = HourlySimulator(self.params)
        self.cost_calculator = CostCalculator(self.params.costs, self.params.economic)

    def get_scenario_month_data(
        self,
        scenario: ScenarioConfig,
        met_data: pd.DataFrame,
        demand_data: pd.DataFrame,
    ) -> tuple:
        """Extract data for the representative month of a scenario.

        Args:
            scenario: Scenario configuration
            met_data: Full year meteorological data
            demand_data: Full year demand data

        Returns:
            Tuple of (met_slice, demand_slice, lhv_value)
        """
        # Map month name to number
        month_map = {
            "January": 1, "February": 2, "March": 3, "April": 4,
            "May": 5, "June": 6, "July": 7, "August": 8,
            "September": 9, "October": 10, "November": 11, "December": 12,
        }

        month_num = month_map.get(scenario.month, 1)

        # Filter data for this month
        met_month = met_data[met_data.index.month == month_num]
        demand_month = demand_data[demand_data.index.month == month_num]

        return met_month, demand_month, scenario.lhv_value

    def run_scenario(
        self,
        scenario: ScenarioConfig,
        config: SimulationConfig,
        met_data: pd.DataFrame,
        demand_data: pd.DataFrame,
    ) -> ScenarioResult:
        """Run simulation for a single scenario.

        Args:
            scenario: Scenario configuration
            config: System configuration
            met_data: Full year meteorological data
            demand_data: Full year demand data

        Returns:
            ScenarioResult
        """
        # Get month-specific data
        met_month, demand_month, lhv = self.get_scenario_month_data(
            scenario, met_data, demand_data
        )

        # Run full year simulation with scenario-specific modifications
        result = self.simulator.run_simulation(config, met_data, demand_data)

        # Extract monthly metrics for the scenario's representative month
        month_map = {
            "January": 1, "February": 2, "March": 3, "April": 4,
            "May": 5, "June": 6, "July": 7, "August": 8,
            "September": 9, "October": 10, "November": 11, "December": 12,
        }
        month_num = month_map.get(scenario.month, 1)

        # Get hours for this month
        dates = pd.date_range(start=f"{config.year}-01-01", periods=8760, freq="h")
        month_mask = dates.month == month_num

        # Calculate monthly metrics
        # Usage of Supply for COE denominator is incorrect as it includes Curtailed energy.
        # Correct denominator is Served Energy = (Load + Elz) - Unmet.
        
        monthly_unmet = result.unmet_power[month_mask]
        monthly_h2_sold = result.h2_sold[month_mask]
        
        
        
        monthly_load_total = demand_month["load_kw"].sum()
        monthly_unmet_total = np.sum(monthly_unmet)
        monthly_h2_total = np.sum(monthly_h2_sold)

        # Denominator should be Useful Energy (Load + H2 Sold)
        # Exclude Electrolyzer consumption as it is internal load
        monthly_energy = (monthly_load_total + monthly_h2_total) - monthly_unmet_total
        # Approximate monthly COE (scaled from annualized cost)
        monthly_fraction = np.sum(month_mask) / 8760
        annualized_cost = self.cost_calculator.calculate_annualized_cost(result.system_costs)
        monthly_cost = annualized_cost * monthly_fraction
        monthly_h2_revenue = monthly_h2_total * config.h2_price

        if monthly_energy > 0:
            monthly_coe = (monthly_cost - monthly_h2_revenue) / monthly_energy
        else:
            monthly_coe = float("inf")

        monthly_reliability = 1 - (monthly_unmet_total / (monthly_energy + monthly_unmet_total)) \
            if (monthly_energy + monthly_unmet_total) > 0 else 0

        return ScenarioResult(
            scenario=scenario,
            simulation=result,
            monthly_coe=monthly_coe,
            monthly_reliability=monthly_reliability,
            monthly_h2_sold=monthly_h2_total,
        )

    def run_all_scenarios(
        self,
        config: SimulationConfig,
    ) -> AllScenariosResult:
        """Run all 8 scenarios.

        Args:
            config: System configuration

        Returns:
            AllScenariosResult with all scenario results
        """
        # Load data once
        met_data = self.simulator.load_meteorological_data(config.year)
        demand_data = self.simulator.load_demand_profile(config.year)

        # Run each scenario
        all_scenarios = Scenarios.all()
        results = {}
        for i, scenario in enumerate(all_scenarios, start=1):
            print(f"  Running scenario {scenario.name} ({scenario.month} - {scenario.climate.value})...", end=" ", flush=True)
            t0 = time.time()
            result = self.run_scenario(scenario, config, met_data, demand_data)
            elapsed = time.time() - t0
            print(f"Done ({elapsed:.1f}s)")
            results[scenario.name] = result

        # Calculate seasonal averages
        dry_coes = [results[s.name].monthly_coe for s in Scenarios.dry_season()]
        wet_coes = [results[s.name].monthly_coe for s in Scenarios.wet_season()]

        dry_avg = np.mean([c for c in dry_coes if c < float("inf")])
        wet_avg = np.mean([c for c in wet_coes if c < float("inf")])

        all_coes = dry_coes + wet_coes
        overall_avg = np.mean([c for c in all_coes if c < float("inf")])

        all_reliabilities = [results[s.name].monthly_reliability for s in Scenarios.all()]
        overall_reliability = np.mean(all_reliabilities)

        return AllScenariosResult(
            scenarios=results,
            dry_season_avg_coe=dry_avg,
            wet_season_avg_coe=wet_avg,
            overall_avg_coe=overall_avg,
            overall_reliability=overall_reliability,
        )

    def run_optimal_all_scenarios(
        self,
        year: int = 2023,
        h2_price: float = 6.6,
    ) -> AllScenariosResult:
        """Run all scenarios with optimal configuration from Table 5.

        Args:
            year: Simulation year
            h2_price: H2 price

        Returns:
            AllScenariosResult
        """
        config = SimulationConfig(
            pv_capacity_kw=41.8,
            wind_capacity_kw=30.1,
            electrolyzer_capacity_kw=40.3,
            fuel_cell_capacity_kw=15.1,
            h2_storage_capacity_kg=275.0,
            biomass_capacity_kw=27.4,
            year=year,
            include_h2_market=True,
            h2_price=h2_price,
        )

        return self.run_all_scenarios(config)

    def compare_h2_prices(
        self,
        config: SimulationConfig,
    ) -> Dict[float, AllScenariosResult]:
        """Compare scenarios at different H2 prices.

        Args:
            config: Base system configuration

        Returns:
            Dict mapping H2 price to AllScenariosResult
        """
        prices = [self.params.economic.h2_price_base, self.params.economic.h2_price_high]
        results = {}

        for price in prices:
            config_with_price = SimulationConfig(
                pv_capacity_kw=config.pv_capacity_kw,
                wind_capacity_kw=config.wind_capacity_kw,
                electrolyzer_capacity_kw=config.electrolyzer_capacity_kw,
                fuel_cell_capacity_kw=config.fuel_cell_capacity_kw,
                h2_storage_capacity_kg=config.h2_storage_capacity_kg,
                biomass_capacity_kw=config.biomass_capacity_kw,
                year=config.year,
                include_h2_market=True,
                h2_price=price,
            )
            results[price] = self.run_all_scenarios(config_with_price)

        return results

    def generate_summary_table(
        self,
        results: AllScenariosResult,
    ) -> pd.DataFrame:
        """Generate summary table similar to Table 8.

        Args:
            results: All scenarios result

        Returns:
            DataFrame with scenario summaries
        """
        data = []

        for scenario in Scenarios.all():
            result = results.scenarios[scenario.name]
            data.append({
                "Scenario": scenario.name,
                "Month": scenario.month,
                "LHV": scenario.lhv_level.value,
                "Irradiance": scenario.irradiance_level.value,
                "Wind": scenario.wind_level.value,
                "Climate": scenario.climate.value,
                "LHV_MJ_kg": scenario.lhv_value,
                "COE_$/kWh": result.monthly_coe,
                "Reliability": result.monthly_reliability,
                "H2_Sold_kg": result.monthly_h2_sold,
            })

        df = pd.DataFrame(data)
        return df

    def validate_seasonal_coe(
        self,
        results: AllScenariosResult,
    ) -> Dict[str, bool]:
        """Validate seasonal COE against Table 8 values.

        Expected from Table 8:
        - Dry season @ $6.6/kg: $0.452/kWh
        - Wet season @ $6.6/kg: $0.511/kWh
        - Dry season @ $9.9/kg: $0.398/kWh
        - Wet season @ $9.9/kg: $0.442/kWh

        Args:
            results: All scenarios result

        Returns:
            Validation results
        """
        # Get H2 price from first result
        h2_price = results.scenarios["SC1"].simulation.config.h2_price

        if h2_price == 6.6:
            expected_dry = 0.452
            expected_wet = 0.511
        elif h2_price == 9.9:
            expected_dry = 0.398
            expected_wet = 0.442
        else:
            expected_dry = 0.45  # Estimate
            expected_wet = 0.50

        tolerance = 0.15  # 15% tolerance

        return {
            "dry_season_valid": abs(results.dry_season_avg_coe - expected_dry) / expected_dry < tolerance,
            "wet_season_valid": abs(results.wet_season_avg_coe - expected_wet) / expected_wet < tolerance,
            "calculated": {
                "dry_season_coe": results.dry_season_avg_coe,
                "wet_season_coe": results.wet_season_avg_coe,
            },
            "expected": {
                "dry_season_coe": expected_dry,
                "wet_season_coe": expected_wet,
                "h2_price": h2_price,
            },
        }
