"""Run single-objective optimization to validate optimal configuration."""

import sys
import time
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

import numpy as np
import pandas as pd
from optimization.epsilon_constraint import EpsilonConstraintOptimizer, OptimizationResult
from simulation.hourly_simulation import HourlySimulator

def validate_optimal_configuration():
    """Run minimization of COE to find optimal configuration."""
    print("=" * 60)
    print("Validating Optimal Configuration (Paper Table 5)")
    print("Goal: Find capacities that minimize COE")
    print("=" * 60)

    # Load data
    print("Loading data...", end="", flush=True)
    simulator = HourlySimulator()
    met_data = simulator.load_meteorological_data(2023)
    demand_data = simulator.load_demand_profile(2023)

    demand = demand_data["load_kw"].values
    irradiance = met_data["irradiance"].values
    wind_speed = met_data["wind_speed_50m"].values

    # Normalize to 0-1 range
    irradiance_factor = irradiance / 1000.0
    irradiance_factor = np.clip(irradiance_factor, 0, 1)

    v_ci, v_r, v_co = 3.0, 12.0, 25.0
    wind_factor = np.zeros_like(wind_speed)
    mask1 = (wind_speed >= v_ci) & (wind_speed < v_r)
    wind_factor[mask1] = (wind_speed[mask1]**3 - v_ci**3) / (v_r**3 - v_ci**3)
    mask2 = (wind_speed >= v_r) & (wind_speed <= v_co)
    wind_factor[mask2] = 1.0
    print(" Done.")

    print("Initializing optimizer...", end="", flush=True)
    optimizer = EpsilonConstraintOptimizer(
        demand_profile=demand,
        irradiance_factor=irradiance_factor,
        wind_factor=wind_factor,
        h2_price=6.6,
    )
    print(" Done.")

    print("\nRunning Optimization (Finding Knee Point with Reliability ~96.1%)...")
    print("(This usually takes 1-5 minutes)")
    
    start_time = time.time()
    # The paper's optimal configuration has reliability ~0.961 (UME ~0.039)
    # We solve for the minimum cost THAT ALSO meets this reliability target.
    target_reliability = 0.961
    target_ume = 1.0 - target_reliability
    
    # Add small buffer to target UME to ensure feasibility
    # OPTIMIZATION: Set 2% optimality gap (gapRel=0.02) to speed up convergence significantly
    import pulp
    optimizer.solver = pulp.HiGHS(msg=True, gapRel=0.02)
    
    print("\nStarting Solver (Logs enabled)...")
    result = optimizer.solve_epsilon_constraint(target_ume + 0.001)
    duration = time.time() - start_time
    
    print(f"\nOptimization Complete! ({duration:.1f}s)")
    
    # Paper Values (Table 5)
    paper_values = {
        "PV (kW)": 41.8,
        "Wind (kW)": 30.1,
        "Biomass (kW)": 27.4,
        "Fuel Cell (kW)": 15.1,
        "Electrolyzer (kW)": 40.3,
        "COE ($/kWh)": 0.494
    }
    
    model_values = {
        "PV (kW)": result.pv_capacity,
        "Wind (kW)": result.wind_capacity,
        "Biomass (kW)": result.biomass_capacity,
        "Fuel Cell (kW)": result.fuel_cell_capacity,
        "Electrolyzer (kW)": result.electrolyzer_capacity,
        "COE ($/kWh)": result.coe
    }
    
    print("\nComparison Results:")
    print("-" * 75)
    print(f"{'Component':<20} {'Paper (Table 5)':<15} {'Optimized Model':<15} {'Diff (%)':<10} {'Status'}")
    print("-" * 75)
    
    all_pass = True
    
    for key, expected in paper_values.items():
        calculated = model_values[key]
        if expected > 0:
            diff_pct = abs(calculated - expected) / expected * 100
        else:
            diff_pct = 0.0 if calculated == 0 else 100.0
            
        status = "PASS" if diff_pct <= 5.0 else "FAIL"
        if status == "FAIL":
            all_pass = False
            
        print(f"{key:<20} {expected:<15.1f} {calculated:<15.1f} {diff_pct:<10.1f} {status}")
        
    print("-" * 75)
    
    if all_pass:
        print("\nSUCCESS: All values match within 5% tolerance.")
    else:
        print("\nWARNING: Some values deviate more than 5%.")
        print("Note: Small deviations expected due to synthetic data vs paper's real data.")

if __name__ == "__main__":
    validate_optimal_configuration()
