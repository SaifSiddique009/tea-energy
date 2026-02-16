# User Guide: H2-HRES Optimization System

Complete guide to running and configuring the hydrogen-based hybrid renewable energy system optimization.

---

## Table of Contents

1. [Installation](#1-installation)
2. [Quick Test Run](#2-quick-test-run)
3. [Configuration](#3-configuration)
4. [Running Simulations](#4-running-simulations)
5. [Running Optimization](#5-running-optimization)
6. [Generating Outputs](#6-generating-outputs)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Installation

### 1.1 Prerequisites

- **Python 3.10+** (tested with 3.11, 3.12)
- **uv** package manager ([install guide](https://docs.astral.sh/uv/getting-started/installation/))
- **CBC Solver** (bundled with PuLP, no separate install needed)

### 1.2 Setup

```bash
# Navigate to project directory
cd "C:\Users\Saif Siddique\Desktop\Codes\samin_research"

# Create virtual environment and install dependencies
uv sync

# Verify PuLP and CBC solver
uv run python -c "
import pulp
print('PuLP version:', pulp.__version__)
solvers = pulp.listSolvers(onlyAvailable=True)
print('Available solvers:', solvers)
"
```

Expected output:
```
PuLP version: 2.8.0
Available solvers: ['PULP_CBC_CMD']
```

### 1.3 Test Import

```bash
uv run python -c "
from simulation.hourly_simulation import HourlySimulator
from optimization.epsilon_constraint import EpsilonConstraintOptimizer
print('All imports successful!')
"
```

---

## 2. Quick Test Run

### 2.1 Validation with Optimal Config

Test the system with the paper's optimal configuration (Table 5):

```bash
uv run python main.py --validate
```

This runs a full-year simulation (8760 hours) with synthetic meteorological data and validates results against expected values.

### 2.2 Understanding Output

```
================================================================================
VALIDATION RESULTS
================================================================================
Configuration (Table 5):
  PV Capacity:      41.8 kW
  Wind Capacity:    30.1 kW
  Biomass:          27.4 kW
  Fuel Cell:        15.1 kW
  Electrolyzer:     40.3 kW
  H2 Storage:       100.0 kg

Results:
  Reliability:      0.992 (Paper: 0.961) [PASS within tolerance]
  COE:              $0.XXX/kWh (Paper: $0.494/kWh)

Note: COE varies with meteorological data. Use real NASA POWER data for validation.
```

### 2.3 Quick Scenario Test

Test a single scenario (runs faster):

```bash
uv run python -c "
from simulation.scenario_runner import ScenarioRunner
from simulation.hourly_simulation import SimulationConfig

runner = ScenarioRunner()
config = SimulationConfig(
    pv_capacity_kw=41.8,
    wind_capacity_kw=30.1,
    electrolyzer_capacity_kw=40.3,
    fuel_cell_capacity_kw=15.1,
    h2_storage_capacity_kg=100.0,
    biomass_capacity_kw=27.4,
    year=2023,
    include_h2_market=True,
    h2_price=6.6,
)
print('Configuration loaded successfully')
"
```

---

## 3. Configuration

### 3.1 System Parameters

All parameters are defined in `config/parameters.py`. Key sections:

**Economic Parameters** (Table 2):
```python
# config/parameters.py
@dataclass
class EconomicParameters:
    discount_rate: float = 0.12          # 12% per paper
    project_lifetime: int = 25           # years
    h2_price_base: float = 6.6           # $/kg
    h2_price_high: float = 9.9           # $/kg

    # Capital costs ($/kW)
    pv_capital: float = 900.0
    wind_capital: float = 1200.0
    electrolyzer_capital: float = 890.0
    fuel_cell_capital: float = 1000.0
    biomass_capital: float = 600.0
    h2_storage_capital: float = 1100.0   # $/kg
```

### 3.2 Modify Simulation Config

Create a custom configuration:

```python
from simulation.hourly_simulation import SimulationConfig

# Custom configuration
config = SimulationConfig(
    # Component capacities
    pv_capacity_kw=50.0,        # Increase PV
    wind_capacity_kw=30.1,
    electrolyzer_capacity_kw=40.3,
    fuel_cell_capacity_kw=15.1,
    h2_storage_capacity_kg=100.0,
    biomass_capacity_kw=27.4,

    # Simulation settings
    year=2023,
    include_h2_market=True,
    h2_price=6.6,
)
```

### 3.3 Scenario Configuration

8 scenarios from Table 6 are defined in `config/scenarios.py`:

| Scenario | Month | LHV | Irradiance | Wind |
|----------|-------|-----|------------|------|
| SC1 | January | High (17.5) | High | High |
| SC2 | February | High | High | Low |
| SC3 | April | High | Low | High |
| SC4 | July | High | Low | Low |
| SC5 | December | Low (14.3) | High | High |
| SC6 | May | Low | High | Low |
| SC7 | November | Low | Low | High |
| SC8 | May | Low | Low | Low |

---

## 4. Running Simulations

### 4.1 Full Year Simulation

```python
from simulation.hourly_simulation import HourlySimulator, SimulationConfig
from config.parameters import DEFAULT_PARAMS

# Create simulator
simulator = HourlySimulator(DEFAULT_PARAMS)

# Define configuration
config = SimulationConfig(
    pv_capacity_kw=41.8,
    wind_capacity_kw=30.1,
    electrolyzer_capacity_kw=40.3,
    fuel_cell_capacity_kw=15.1,
    h2_storage_capacity_kg=100.0,
    biomass_capacity_kw=27.4,
    year=2023,
    include_h2_market=True,
    h2_price=6.6,
)

# Load data
met_data = simulator.load_meteorological_data(2023)
demand_data = simulator.load_demand_profile(2023)

# Run simulation
result = simulator.run_simulation(config, met_data, demand_data)

# Access results
print(f"Total PV energy: {result.pv_power.sum():.0f} kWh")
print(f"Total wind energy: {result.wind_power.sum():.0f} kWh")
print(f"Reliability: {result.metrics['reliability']:.3f}")
print(f"COE: ${result.metrics['coe']:.3f}/kWh")
```

### 4.2 All 8 Scenarios

```bash
uv run python main.py --scenarios
```

Or programmatically:

```python
from simulation.scenario_runner import ScenarioRunner

runner = ScenarioRunner()
results = runner.run_optimal_all_scenarios(year=2023, h2_price=6.6)

# Print summary table
df = runner.generate_summary_table(results)
print(df.to_string())
```

### 4.3 Sensitivity Analysis (H2 Price)

```python
from simulation.scenario_runner import ScenarioRunner
from simulation.hourly_simulation import SimulationConfig

runner = ScenarioRunner()

config = SimulationConfig(
    pv_capacity_kw=41.8,
    wind_capacity_kw=30.1,
    electrolyzer_capacity_kw=40.3,
    fuel_cell_capacity_kw=15.1,
    h2_storage_capacity_kg=100.0,
    biomass_capacity_kw=27.4,
)

# Compare H2 prices
results_6_6 = runner.run_all_scenarios(config._replace(h2_price=6.6))
results_9_9 = runner.run_all_scenarios(config._replace(h2_price=9.9))

print(f"COE @ $6.6/kg: ${results_6_6.overall_avg_coe:.3f}/kWh")
print(f"COE @ $9.9/kg: ${results_9_9.overall_avg_coe:.3f}/kWh")
```

---

## 5. Running Optimization

### 5.1 Full MILP Optimization

**Warning:** Full optimization takes 30-60+ minutes depending on hardware.

```bash
uv run python main.py --optimize
```

### 5.2 Reduced Optimization (Faster Testing)

For testing, reduce the number of epsilon points:

```python
from optimization.epsilon_constraint import EpsilonConstraintOptimizer
from simulation.hourly_simulation import HourlySimulator
from config.parameters import DEFAULT_PARAMS

simulator = HourlySimulator(DEFAULT_PARAMS)
met_data = simulator.load_meteorological_data(2023)
demand_data = simulator.load_demand_profile(2023)

optimizer = EpsilonConstraintOptimizer(
    met_data=met_data,
    demand_data=demand_data,
    params=DEFAULT_PARAMS,
)

# Reduce epsilon points for faster testing
pareto_front = optimizer.solve(
    num_epsilon_points=5,  # Default is 20
    include_h2_market=True,
    h2_price=6.6,
)

for solution in pareto_front:
    print(f"COE: ${solution.coe:.3f}, UME: {solution.ume:.4f}")
```

### 5.3 Understanding Optimization Output

```
Epsilon-Constraint Optimization
================================
Step 1: Minimize COE (UME unconstrained)
  COE* = $0.494/kWh, UME = 0.039

Step 2: Minimize UME (COE unconstrained)
  UME* = 0.022, COE = $0.668/kWh

Step 3: Generate Pareto front (20 points)
  Point 1: COE=$0.494, UME=0.039
  Point 2: COE=$0.502, UME=0.037
  ...
  Point 20: COE=$0.668, UME=0.022

Knee point (best trade-off):
  COE = $0.494/kWh
  UME = 0.039 (Reliability = 96.1%)

Optimal Configuration:
  PV: 41.8 kW
  Wind: 30.1 kW
  Biomass: 27.4 kW
  Fuel Cell: 15.1 kW
  Electrolyzer: 40.3 kW
```

---

## 6. Generating Outputs

### 6.1 Generate All Figures

```bash
uv run python main.py --figures
```

Outputs saved to `results/figures/`:
- `figure_9_pareto.png` - Pareto front curves
- `figure_11_scenarios.png` - Demand-supply for 8 scenarios
- `figure_12_h2_dynamics.png` - H2 production/consumption
- `figure_13_biomass.png` - Biomass operation
- `figure_14_sensitivity.png` - H2 price sensitivity

### 6.2 Generate Specific Figures

```python
from visualization.pareto_plots import ParetoPlotter
from visualization.dispatch_plots import DispatchPlotter

# After running optimization...
pareto_plotter = ParetoPlotter()
fig = pareto_plotter.plot_pareto_front(pareto_results)
fig.savefig("results/figures/custom_pareto.png", dpi=300)

# After running simulation...
dispatch_plotter = DispatchPlotter()
fig = dispatch_plotter.plot_hourly_dispatch(
    result,
    hours=range(0, 168),  # First week
    title="Week 1 Dispatch",
)
fig.savefig("results/figures/week1_dispatch.png", dpi=300)
```

### 6.3 Export Tables

```python
from simulation.scenario_runner import ScenarioRunner

runner = ScenarioRunner()
results = runner.run_optimal_all_scenarios()

# Generate Table 8 equivalent
df = runner.generate_summary_table(results)

# Export to CSV
df.to_csv("results/scenario_summary.csv", index=False)

# Export to LaTeX
print(df.to_latex(index=False, float_format="%.3f"))
```

---

## 7. Troubleshooting

### 7.1 Import Errors

**Error:** `ImportError: cannot import name 'STC' from 'config.constants'`

**Solution:** Ensure `config/constants.py` has all required constants:
```python
from config.constants import PHYSICAL, LOCATION, STC, H2
```

### 7.2 Pandas Frequency Error

**Error:** `ValueError: Invalid frequency: H. Did you mean h?`

**Solution:** Use lowercase `freq="h"` (pandas 2.0+ requirement)

### 7.3 Solver Not Found

**Error:** `pulp.apis.core.PulpSolverError: Solver not available`

**Solution:**
```bash
# Check available solvers
uv run python -c "import pulp; print(pulp.listSolvers(onlyAvailable=True))"

# If CBC not available, install GLPK
pip install glpk
```

### 7.4 Memory Issues

For large optimizations, reduce problem size:

```python
# Use fewer hours (e.g., one month instead of full year)
met_data_month = met_data.iloc[:720]  # January only
demand_data_month = demand_data.iloc[:720]
```

### 7.5 Slow Optimization

- Reduce `num_epsilon_points` to 5-10 for testing
- Use GLPK instead of CBC (sometimes faster)
- Run on machine with more RAM/CPU

---

## Quick Reference Commands

| Task | Command |
|------|---------|
| Install | `uv sync` |
| Validate | `uv run python main.py --validate` |
| Run scenarios | `uv run python main.py --scenarios` |
| Run optimization | `uv run python main.py --optimize` |
| Generate figures | `uv run python main.py --figures` |
| Fetch NASA data | See [DATA_GUIDE.md](DATA_GUIDE.md) |

---

## Next Steps

- [DATA_GUIDE.md](DATA_GUIDE.md) - How to fetch and cache real NASA POWER data
- [VALIDATION_GUIDE.md](VALIDATION_GUIDE.md) - Validate results against paper
- [MILP_ALGORITHM.md](MILP_ALGORITHM.md) - Understand the optimization algorithm
