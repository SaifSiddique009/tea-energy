# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

H2-HRES: Python implementation of an epsilon-constraint MILP optimization model for a hydrogen-based hybrid renewable energy system. Based on Mulumba & Farzaneh (2025) research paper "Techno-economic analysis of a hydrogen-based hybrid renewable energy system for off-grid power supply in Kenya's urban area" (International Journal of Hydrogen Energy 178, 151474).

## Build & Development Commands

**Package manager:** `uv` (not pip/poetry). Build system: hatchling.

```bash
# Install all dependencies
uv sync

# Default run (optimal config simulation)
uv run python main.py
uv run python main.py --year 2023 --h2-price 6.6

# Quick validation (~30 seconds, synthetic data)
uv run python main.py --validate

# Run 8 scenarios (Table 6 from paper)
uv run python main.py --scenarios

# Full MILP optimization (30-60+ minutes)
uv run python main.py --optimize --pareto-points 10

# Generate figures (saved to results/figures/)
uv run python main.py --figures

# Utility scripts
uv run python validate_optimization.py      # Single-objective validation against Table 5
uv run python run_optimization_visual.py     # Optimization with progress logging
uv run python debug_coe.py                   # COE calculation debugging

# Fetch NASA POWER data (caches locally to data/cache/)
uv run python -c "from data.fetchers.nasa_power import NASAPowerClient; NASAPowerClient().fetch_year(2023)"
```

**Note:** The `tests/` directory is configured in pyproject.toml but currently has no test files.

## Architecture

### Component Model Pattern
`components/base.py` defines the class hierarchy:
- `Component` (ABC): base with `calculate_output()`, `get_capital_cost()`, `get_om_cost()`, `get_annualized_cost()`
- `PowerGenerator(Component)`: for PV, Wind, Biomass, FC — adds `calculate_capacity_factor()`
- `PowerConsumer(Component)`: for Electrolyzer — adds `calculate_utilization()`
- `EnergyStorage(Component)`: for H2 Tank — adds SOC tracking, usable capacity

Components:
- `solar_pv.py` — SolarPV
- `wind_turbine.py` — WindTurbine
- `electrolyzer.py` — Electrolyzer
- `fuel_cell.py` — FuelCell
- `hydrogen_storage.py` — HydrogenStorage
- `biomass_generator.py` — BiomassGenerator
- `gibbs_minimization.py` — GibbsMinimizer, HHV/LHV calculation (Equations 22-27)

### Multi-Objective Optimization
- **Algorithm:** ε-constraint MILP minimizing COE subject to reliability constraint (UME ≤ ε)
- **Solver:** PuLP with CBC (free, no license)
- **Entry point:** `optimization/epsilon_constraint.py` (EpsilonConstraintOptimizer)
- **Objectives:** `optimization/objectives.py` (ObjectiveCalculator — COE and UME functions)
- **Constraints:** `optimization/constraints.py` (ConstraintBuilder, CapacityBounds — power balance, dispatch modes, storage, feedstock)
- **Outputs:** Pareto front with knee point detection

### Dispatch Logic
`optimization/dispatch_scheduler.py` implements 4-priority hourly dispatch:
1. PV + Wind only
2. + Fuel Cell (if H2 available)
3. + Biomass generator
4. + Biomass + Fuel Cell combined

### Economics
- `economics/costs.py` — CostCalculator, SystemCosts (Equations 3-4, Table 2)
- `economics/coe_calculator.py` — COECalculator (Equation 2)
- `economics/hydrogen_market.py` — HydrogenMarket (H2 price scenarios: $6.6/kg base, $9.9/kg high)

### Data Flow
- NASA POWER API → `data/fetchers/nasa_power.py` → JSON cache in `data/cache/`
- Load profile: `data/fetchers/load_profile.py` (127.8 MWh/year target)
- Biomass feedstock: `data/fetchers/biomass_data.py` (LULC classification, Equations 29-32, Tables 3-4)
- Simulation: `simulation/hourly_simulation.py` runs 8760-hour annual simulation
- Scenarios: `simulation/scenario_runner.py` runs all 8 scenarios (Table 6)

### Visualization
`visualization/` generates paper figures (saved to `results/figures/`):
- `pareto_plots.py` — ParetoPlotter (Figures 9-10: Pareto front, capacity breakdown)
- `dispatch_plots.py` — DispatchPlotter (Figures 11-13: scenarios, H2 dynamics, biomass)
- `sensitivity_plots.py` — SensitivityPlotter (Figure 14: H2 price sensitivity, seasonal comparison)

### Configuration
- `config/parameters.py` — SystemParameters, ComponentCosts, EconomicParameters, BiomassParameters, ComponentLifetimes (Table 2)
- `config/scenarios.py` — 8 scenario configurations (Table 6: LHV × Irradiance × Wind combinations)
- `config/constants.py` — Physical constants (Faraday, gas constant, LHV)

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | CLI entry point: `--validate`, `--scenarios`, `--optimize`, `--figures`, `--year`, `--h2-price`, `--pareto-points` |
| `optimization/epsilon_constraint.py` | Core MILP optimizer (EpsilonConstraintOptimizer, OptimizationResult) |
| `optimization/objectives.py` | Objective functions: COE minimization, UME minimization |
| `optimization/constraints.py` | MILP constraints: power balance, dispatch, storage, feedstock |
| `optimization/dispatch_scheduler.py` | 4-priority hourly dispatch logic |
| `simulation/hourly_simulation.py` | 8760-hour dispatch simulation engine (HourlySimulator, SimulationConfig) |
| `simulation/scenario_runner.py` | 8-scenario runner with seasonal COE validation (ScenarioRunner) |
| `economics/costs.py` | Component & system cost calculation (CostCalculator) |
| `economics/coe_calculator.py` | Cost-of-Energy calculation (Equations 2-4) |
| `economics/hydrogen_market.py` | H2 sales revenue model |
| `components/gibbs_minimization.py` | Gibbs free energy minimization for biomass HHV (Equations 22-27) |
| `validate_optimization.py` | Standalone validation script against Table 5 |
| `run_optimization_visual.py` | Optimization with step-by-step progress output |
| `debug_coe.py` | COE calculation debugging utility |

## Dependencies

numpy, pandas, scipy, pulp, matplotlib, seaborn, requests, pyyaml, tqdm, pyarrow

## Paper Reference Values

Optimal configuration (Table 5): PV 41.8kW, Wind 30.1kW, Biomass 27.4kW, FC 15.1kW, Electrolyzer 40.3kW, H2 Tank 100kg

Target metrics: COE $0.494/kWh (with H2 market @ $6.6/kg), Reliability 96.1%

H2 price scenarios (Table 7): Base $6.6/kg, High $9.9/kg

## Platform Notes

- Python 3.11 pinned in `.python-version` (requires >=3.10)
- Full optimization may require 4GB+ RAM
- Handles Windows path separators correctly
- Generated figures output to `results/figures/`
