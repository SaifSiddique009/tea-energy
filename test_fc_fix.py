"""Quick diagnostic: test if FC > 0 after BM min load + fuel cost changes."""
import numpy as np
from simulation.hourly_simulation import HourlySimulator
from optimization.epsilon_constraint import EpsilonConstraintOptimizer
from optimization.constraints import CapacityBounds
from data.fetchers.biomass_data import BiomassDataProvider

# Load data
simulator = HourlySimulator()
met_data = simulator.load_meteorological_data(2023)
demand_data = simulator.load_demand_profile(2023)

demand = demand_data["load_kw"].values
irradiance = met_data["irradiance"].values
wind_speed = met_data["wind_speed_50m"].values

irradiance_factor = np.clip(irradiance / 1000.0, 0, 1)

v_ci, v_r, v_co = 3.0, 12.0, 25.0
wind_factor = np.zeros_like(wind_speed)
mask1 = (wind_speed >= v_ci) & (wind_speed < v_r)
wind_factor[mask1] = (wind_speed[mask1]**3 - v_ci**3) / (v_r**3 - v_ci**3)
mask2 = (wind_speed >= v_r) & (wind_speed <= v_co)
wind_factor[mask2] = 1.0

lhv_profile = BiomassDataProvider().get_hourly_lhv(2023)

print(f"Demand: {len(demand)} hours, peak={np.max(demand):.1f} kW, avg={np.mean(demand):.1f} kW")
print(f"BM fuel cost range: ${np.min(lhv_profile):.1f}-{np.max(lhv_profile):.1f} MJ/kg")
print()

# Bounds: ~30-50% headroom above paper optimal values
# Paper: PV=41.8, Wind=30.1, BM=27.4, FC=15.1, ELZ=40.3, H2=100
bounds = CapacityBounds(
    pv_max=60.0,
    wind_max=45.0,
    biomass_max=45.0,       # Paper: 27.4, cap to prevent oversizing
    electrolyzer_max=60.0,  # Paper: 40.3, cap to prevent oversizing
    fuel_cell_max=30.0,     # Paper: 15.1
    h2_storage_max=200.0,   # Paper: ~100, allow room
)

# Use CBC for better heuristics (finds good feasible solutions faster)
optimizer = EpsilonConstraintOptimizer(
    demand_profile=demand,
    irradiance_factor=irradiance_factor,
    wind_factor=wind_factor,
    h2_price=6.6,
    lhv_profile=lhv_profile,
    bounds=bounds,
    solver="CBC",
    time_limit_sec=900,     # 15 minutes for better convergence
    gap_tolerance=0.05,
    solver_verbose=True,
)

print("=" * 60)
print("Solving single epsilon-constraint: UME <= 0.04 (~96% reliability)")
print("4-hour BM blocks, reduced H2 sales (500 kg/yr), tighter bounds")
print("=" * 60)

result = optimizer.solve_epsilon_constraint(epsilon=0.04)

print()
print("=" * 60)
print(f"Status: {result.status}")
print(f"COE: ${result.coe:.3f}/kWh (paper: $0.494)")
print(f"Reliability: {result.reliability:.3f} (paper: 0.961)")
print()
print("Component Capacities:")
print(f"  PV:           {result.pv_capacity:.1f} kW (paper: 41.8)")
print(f"  Wind:         {result.wind_capacity:.1f} kW (paper: 30.1)")
print(f"  Biomass:      {result.biomass_capacity:.1f} kW (paper: 27.4)")
print(f"  Fuel Cell:    {result.fuel_cell_capacity:.1f} kW (paper: 15.1)")
print(f"  Electrolyzer: {result.electrolyzer_capacity:.1f} kW (paper: 40.3)")
print(f"  H2 Storage:   {result.h2_storage_capacity:.1f} kg (paper: ~100)")
print()
print(f"  H2 sold:      {result.annual_h2_sold_kg:.0f} kg/yr")
print(f"  Unmet energy:  {result.annual_unmet_kwh:.0f} kWh/yr")
print(f"  Total cost:   ${result.total_cost:.0f}/yr")
print(f"  H2 revenue:   ${result.h2_revenue:.0f}/yr")
print("=" * 60)

if result.fuel_cell_capacity > 0 and result.biomass_capacity > 0:
    print("\n*** SUCCESS: FC > 0 AND BM > 0! ***")
elif result.fuel_cell_capacity > 0:
    print("\n*** FC > 0 but BM = 0. Need further investigation. ***")
else:
    print("\n*** FC = 0. Need further investigation. ***")
