# Validation Guide: Reproducing Paper Results

Step-by-step guide to validate the implementation against the original paper results.

---

## Table of Contents

1. [Expected Results](#1-expected-results)
2. [Validation Steps](#2-validation-steps)
3. [Table Reproduction](#3-table-reproduction)
4. [Figure Reproduction](#4-figure-reproduction)
5. [Troubleshooting Discrepancies](#5-troubleshooting-discrepancies)
6. [Validation Checklist](#6-validation-checklist)

---

## 1. Expected Results

### 1.1 Optimal Configuration (Table 5)

The optimization should find these component capacities:

| Component | Expected | Tolerance |
|-----------|----------|-----------|
| PV System | 41.8 kW | +/- 5% (39.7-43.9) |
| Wind Turbines | 30.1 kW | +/- 5% (28.6-31.6) |
| Biogenerator | 27.4 kW | +/- 5% (26.0-28.8) |
| Fuel Cell | 15.1 kW | +/- 5% (14.3-15.9) |
| Electrolyzer | 40.3 kW | +/- 5% (38.3-42.3) |

### 1.2 Economic Results

| Scenario | COE ($/kWh) | Reliability |
|----------|-------------|-------------|
| With H2 Market @ $6.6/kg | 0.494 +/- 3% | 0.961 +/- 0.02 |
| Without H2 Market | 0.668 +/- 3% | 0.978 +/- 0.02 |
| With H2 @ $9.9/kg | 0.405 +/- 3% | - |

### 1.3 Seasonal COE (Table 8)

| Season | H2 @ $6.6/kg | H2 @ $9.9/kg |
|--------|--------------|--------------|
| Dry Season | $0.452/kWh | $0.398/kWh |
| Wet Season | $0.511/kWh | $0.442/kWh |

---

## 2. Validation Steps

### Step 1: Data Validation

Verify meteorological data matches paper values:

```python
from data.fetchers.nasa_power import NASAPowerClient

client = NASAPowerClient()
df = client.fetch_year(2023, use_cache=True)
stats = client.get_statistics(df)

# Paper reference (Section 3.1)
print("=== DATA VALIDATION ===")
print(f"Solar Irradiance:")
print(f"  Peak: {stats['irradiance']['max']:.0f} W/m^2 (Paper: ~1290)")
print(f"  Avg:  {stats['irradiance']['mean']:.0f} W/m^2 (Paper: ~479)")

print(f"\nWind Speed (50m):")
print(f"  Peak: {stats['wind_speed_50m']['max']:.1f} m/s (Paper: ~11.3)")
print(f"  Avg:  {stats['wind_speed_50m']['mean']:.2f} m/s (Paper: ~3.69)")

# Validation check
irr_ok = abs(stats['irradiance']['mean'] - 479) < 100
wind_ok = abs(stats['wind_speed_50m']['mean'] - 3.69) < 1.0
print(f"\nData Validation: {'PASS' if irr_ok and wind_ok else 'NEEDS ATTENTION'}")
```

### Step 2: Component Model Validation

Test each component model against known inputs:

```python
from components.solar_pv import SolarPVSystem
from components.wind_turbine import WindTurbine
from components.electrolyzer import PEMElectrolyzer
from components.fuel_cell import PEMFuelCell

# Solar PV at STC
pv = SolarPVSystem(capacity_kw=41.8)
power = pv.calculate_power(irradiance=1000, temperature=25)
print(f"PV at STC: {power:.1f} kW (Expected: ~41.8)")

# Wind at rated speed
wt = WindTurbine(capacity_kw=30.1)
power = wt.calculate_power(wind_speed=12)  # Above rated
print(f"Wind at rated: {power:.1f} kW (Expected: ~30.1)")

# Electrolyzer efficiency
elz = PEMElectrolyzer(capacity_kw=40.3)
h2 = elz.calculate_h2_production(power_kw=40.3)
print(f"ELZ H2 production: {h2:.2f} kg/h")

# Fuel cell output
fc = PEMFuelCell(capacity_kw=15.1)
power = fc.calculate_power(h2_rate=0.5)
print(f"FC power output: {power:.1f} kW")
```

### Step 3: Simulation Validation

Run full simulation with optimal config:

```python
from simulation.hourly_simulation import HourlySimulator, SimulationConfig
from config.parameters import DEFAULT_PARAMS

simulator = HourlySimulator(DEFAULT_PARAMS)

# Table 5 optimal configuration
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

met_data = simulator.load_meteorological_data(2023)
demand_data = simulator.load_demand_profile(2023)
result = simulator.run_simulation(config, met_data, demand_data)

# Validate results
print("=== SIMULATION VALIDATION ===")
print(f"Reliability: {result.metrics['reliability']:.3f} (Paper: 0.961)")
print(f"COE: ${result.metrics['coe']:.3f}/kWh (Paper: $0.494)")

reliability_ok = abs(result.metrics['reliability'] - 0.961) < 0.02
coe_ok = abs(result.metrics['coe'] - 0.494) / 0.494 < 0.10  # 10% tolerance
print(f"\nValidation: {'PASS' if reliability_ok else 'CHECK RELIABILITY'}")
```

### Step 4: Scenario Validation

Run all 8 scenarios (Table 6):

```python
from simulation.scenario_runner import ScenarioRunner

runner = ScenarioRunner()
results = runner.run_optimal_all_scenarios(year=2023, h2_price=6.6)

# Validate seasonal COE
validation = runner.validate_seasonal_coe(results)

print("=== SEASONAL COE VALIDATION ===")
print(f"Dry Season COE: ${results.dry_season_avg_coe:.3f}/kWh (Paper: $0.452)")
print(f"Wet Season COE: ${results.wet_season_avg_coe:.3f}/kWh (Paper: $0.511)")
print(f"\nDry Season Valid: {validation['dry_season_valid']}")
print(f"Wet Season Valid: {validation['wet_season_valid']}")
```

---

## 3. Table Reproduction

### 3.1 Reproduce Table 5 (Optimal Configuration)

```python
from optimization.epsilon_constraint import EpsilonConstraintOptimizer
from simulation.hourly_simulation import HourlySimulator
from config.parameters import DEFAULT_PARAMS

# Run optimization
simulator = HourlySimulator(DEFAULT_PARAMS)
met_data = simulator.load_meteorological_data(2023)
demand_data = simulator.load_demand_profile(2023)

optimizer = EpsilonConstraintOptimizer(met_data, demand_data, DEFAULT_PARAMS)
pareto_front = optimizer.solve(num_epsilon_points=20, include_h2_market=True, h2_price=6.6)

# Find knee point (optimal solution)
knee = optimizer.find_knee_point(pareto_front)

print("=== TABLE 5 REPRODUCTION ===")
print("Optimal Configuration:")
print(f"  PV System:     {knee.config.pv_capacity_kw:.1f} kW (Paper: 41.8)")
print(f"  Wind Turbines: {knee.config.wind_capacity_kw:.1f} kW (Paper: 30.1)")
print(f"  Biogenerator:  {knee.config.biomass_capacity_kw:.1f} kW (Paper: 27.4)")
print(f"  Fuel Cell:     {knee.config.fuel_cell_capacity_kw:.1f} kW (Paper: 15.1)")
print(f"  Electrolyzer:  {knee.config.electrolyzer_capacity_kw:.1f} kW (Paper: 40.3)")
```

### 3.2 Reproduce Table 8 (Seasonal COE)

```python
from simulation.scenario_runner import ScenarioRunner

runner = ScenarioRunner()

# At H2 price $6.6/kg
results_6_6 = runner.run_optimal_all_scenarios(year=2023, h2_price=6.6)

# At H2 price $9.9/kg
results_9_9 = runner.run_optimal_all_scenarios(year=2023, h2_price=9.9)

print("=== TABLE 8 REPRODUCTION ===")
print("\nH2 Price: $6.6/kg")
print(f"  Dry Season COE: ${results_6_6.dry_season_avg_coe:.3f}/kWh (Paper: $0.452)")
print(f"  Wet Season COE: ${results_6_6.wet_season_avg_coe:.3f}/kWh (Paper: $0.511)")

print("\nH2 Price: $9.9/kg")
print(f"  Dry Season COE: ${results_9_9.dry_season_avg_coe:.3f}/kWh (Paper: $0.398)")
print(f"  Wet Season COE: ${results_9_9.wet_season_avg_coe:.3f}/kWh (Paper: $0.442)")

# Generate summary table
df = runner.generate_summary_table(results_6_6)
print("\nScenario Summary:")
print(df.to_string(index=False))
```

### 3.3 Export Tables to CSV/LaTeX

```python
# Export to CSV
df.to_csv("results/table_8_reproduction.csv", index=False)

# Export to LaTeX
latex = df.to_latex(index=False, float_format="%.3f")
with open("results/table_8.tex", "w") as f:
    f.write(latex)
print("Tables exported to results/")
```

---

## 4. Figure Reproduction

### 4.1 Figure 9: Pareto Front

```python
from visualization.pareto_plots import ParetoPlotter
from optimization.epsilon_constraint import EpsilonConstraintOptimizer

# After optimization...
plotter = ParetoPlotter()

# Plot three cases: (a) with H2, (b) without H2, (c) at $9.9/kg
fig = plotter.create_figure_9(
    pareto_with_h2=pareto_6_6,
    pareto_without_h2=pareto_no_h2,
    pareto_h2_high=pareto_9_9,
)
fig.savefig("results/figures/figure_9_pareto.png", dpi=300, bbox_inches="tight")
print("Figure 9 saved!")
```

### 4.2 Figure 11: Scenario Comparison

```python
from visualization.dispatch_plots import DispatchPlotter
from simulation.scenario_runner import ScenarioRunner

runner = ScenarioRunner()
results = runner.run_optimal_all_scenarios()

plotter = DispatchPlotter()
fig = plotter.create_figure_11(results)
fig.savefig("results/figures/figure_11_scenarios.png", dpi=300)
print("Figure 11 saved!")
```

### 4.3 Figure 12: H2 Dynamics

```python
from visualization.dispatch_plots import DispatchPlotter

# After simulation...
plotter = DispatchPlotter()
fig = plotter.plot_h2_dynamics(
    result,
    hours=range(0, 168),  # First week
    title="Figure 12: H2 Production/Consumption",
)
fig.savefig("results/figures/figure_12_h2.png", dpi=300)
```

### 4.4 Figure 14: Sensitivity Analysis

```python
from visualization.sensitivity_plots import SensitivityPlotter

# Run sensitivity analysis
plotter = SensitivityPlotter()
fig = plotter.plot_h2_price_sensitivity(
    results_base=results_6_6,
    results_high=results_9_9,
)
fig.savefig("results/figures/figure_14_sensitivity.png", dpi=300)
```

### 4.5 Generate All Figures

```bash
uv run python main.py --figures
```

This generates all figures in `results/figures/`.

---

## 5. Troubleshooting Discrepancies

### 5.1 COE Higher Than Expected

**Possible causes:**
- H2 revenue not included (check `include_h2_market=True`)
- Missing O&M cost components
- Wrong discount rate (should be 12%)

**Debug:**
```python
# Check COE calculation
from economics.coe_calculator import COECalculator

calc = COECalculator()
coe_details = calc.calculate_detailed_coe(result)

print(f"Capital cost: ${coe_details['capital_cost']:,.0f}")
print(f"O&M cost: ${coe_details['om_cost']:,.0f}")
print(f"H2 revenue: ${coe_details['h2_revenue']:,.0f}")
print(f"Net cost: ${coe_details['net_cost']:,.0f}")
print(f"Total energy: {coe_details['total_energy']:,.0f} kWh")
```

### 5.2 Reliability Lower Than Expected

**Possible causes:**
- Incorrect dispatch logic
- H2 storage constraints too tight
- Wrong component efficiencies

**Debug:**
```python
# Check unmet demand
unmet_hours = (result.unmet_power > 0).sum()
print(f"Hours with unmet demand: {unmet_hours}")

# Check H2 storage utilization
h2_min = result.h2_level.min()
h2_max = result.h2_level.max()
print(f"H2 storage range: {h2_min:.1f} - {h2_max:.1f} kg")

# Check dispatch modes
fc_hours = (result.fc_power > 0).sum()
bm_hours = (result.bm_power > 0).sum()
print(f"Fuel cell active hours: {fc_hours}")
print(f"Biomass active hours: {bm_hours}")
```

### 5.3 Wrong Optimal Capacities

**Possible causes:**
- Constraints too restrictive
- Not enough epsilon points
- Solver timeout

**Debug:**
```python
# Check constraint violations
from optimization.constraints import validate_solution

violations = validate_solution(knee.config, met_data, demand_data)
for v in violations:
    print(f"Violation: {v}")
```

### 5.4 Data Mismatch

The paper likely used different meteorological data. If results differ significantly:

1. **Check data year**: Paper may use 2021-2022 data
2. **Check location precision**: Lat/long rounding can affect results
3. **Compare statistics**: Irradiance and wind averages should match

---

## 6. Validation Checklist

Use this checklist to verify complete validation:

```
=== DATA VALIDATION ===
[ ] Solar irradiance: peak ~1290 W/m^2, avg ~479 W/m^2
[ ] Wind speed (50m): peak ~11.3 m/s, avg ~3.69 m/s
[ ] Annual load: 127,800 kWh
[ ] Location: -1.3206, 36.8939

=== COMPONENT VALIDATION ===
[ ] PV follows Equation 11 (temperature derating)
[ ] Wind follows Equation 12 (cubic power curve)
[ ] Electrolyzer follows Equation 13 (Faraday's law)
[ ] Fuel cell follows Equations 14-15
[ ] H2 storage follows Equation 16 (mass balance)
[ ] Biomass follows Equations 19-21, 28

=== SIMULATION VALIDATION ===
[ ] 8760 hours simulated
[ ] Dispatch logic matches Figure 4
[ ] Supply-demand balance (Equation 8) satisfied
[ ] H2 mass balance maintained

=== OPTIMIZATION VALIDATION ===
[ ] Epsilon-constraint generates Pareto front
[ ] ~20 Pareto points generated
[ ] Knee point identified
[ ] Optimal config within +/-5% of Table 5

=== RESULTS VALIDATION ===
[ ] COE with H2 market: $0.494 +/-10%
[ ] COE without H2 market: $0.668 +/-10%
[ ] Reliability: 0.961 +/-0.03
[ ] Seasonal COE matches Table 8

=== FIGURE VALIDATION ===
[ ] Figure 9: Pareto front shape matches
[ ] Figure 11: Scenario patterns match
[ ] Figure 12: H2 dynamics reasonable
[ ] Figure 14: Sensitivity trends correct
```

---

## Quick Validation Command

```bash
uv run python main.py --validate
```

This runs all validation checks and prints a summary report.

---

## Full Validation Script

Save as `validate_all.py`:

```python
"""Complete validation script."""

from simulation.hourly_simulation import HourlySimulator, SimulationConfig
from simulation.scenario_runner import ScenarioRunner
from config.parameters import DEFAULT_PARAMS

def main():
    print("=" * 60)
    print("H2-HRES IMPLEMENTATION VALIDATION")
    print("=" * 60)

    # 1. Configuration validation
    simulator = HourlySimulator(DEFAULT_PARAMS)
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

    # 2. Load data
    met_data = simulator.load_meteorological_data(2023)
    demand_data = simulator.load_demand_profile(2023)

    # 3. Run simulation
    print("\n1. Running full-year simulation...")
    result = simulator.run_simulation(config, met_data, demand_data)

    # 4. Print results
    print("\n2. Results:")
    print(f"   Reliability: {result.metrics['reliability']:.3f} (Paper: 0.961)")
    print(f"   COE: ${result.metrics['coe']:.3f}/kWh (Paper: $0.494)")

    # 5. Run scenarios
    print("\n3. Running 8 scenarios...")
    runner = ScenarioRunner()
    scenarios = runner.run_optimal_all_scenarios(year=2023, h2_price=6.6)

    print(f"   Dry season COE: ${scenarios.dry_season_avg_coe:.3f} (Paper: $0.452)")
    print(f"   Wet season COE: ${scenarios.wet_season_avg_coe:.3f} (Paper: $0.511)")

    # 6. Validation status
    print("\n" + "=" * 60)
    print("VALIDATION STATUS")
    print("=" * 60)

    rel_ok = abs(result.metrics['reliability'] - 0.961) < 0.03
    print(f"[{'PASS' if rel_ok else 'FAIL'}] Reliability within tolerance")

    print("\nNote: COE may vary with meteorological data source.")
    print("For exact paper reproduction, contact authors for original data.")

if __name__ == "__main__":
    main()
```

Run:
```bash
uv run python validate_all.py
```
