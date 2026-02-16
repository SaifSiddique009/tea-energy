"""Run epsilon-constraint optimization with progress logging."""

import sys
import time
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

import numpy as np
from optimization.epsilon_constraint import EpsilonConstraintOptimizer, OptimizationResult
from simulation.hourly_simulation import HourlySimulator

def run_visual_optimization(n_pareto_points: int = 5):
    """Run optimization with progress updates."""
    print("=" * 60)
    print("Running Visual Epsilon-Constraint Optimization")
    print(f"Points: {n_pareto_points} (Reduced for faster feedback)")
    print("=" * 60)

    # Load data
    print("[1/3] Loading meteorological and demand data...")
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

    print("[2/3] Initializing optimizer...")
    optimizer = EpsilonConstraintOptimizer(
        demand_profile=demand,
        irradiance_factor=irradiance_factor,
        wind_factor=wind_factor,
        h2_price=6.6,
    )

    print("[3/3] Starting optimization loop...")
    start_time = time.time()
    
    # 1. Minimize COE
    print("      Step 1: Finding Min COE anchor... ", end="", flush=True)
    t0 = time.time()
    f1_anchor = optimizer.minimize_coe()
    t1 = time.time()
    print(f"Done (${f1_anchor.coe:.3f}/kWh) [{t1-t0:.1f}s]")

    # 2. Minimize UME
    print("      Step 2: Finding Min UME anchor... ", end="", flush=True)
    t0 = time.time()
    f2_anchor = optimizer.minimize_ume()
    t1 = time.time()
    print(f"Done (UME={f2_anchor.ume:.4f}) [{t1-t0:.1f}s]")

    # Calculate epsilons
    ume_at_min_coe = f1_anchor.ume
    ume_at_min_ume = f2_anchor.ume
    epsilon_values = np.linspace(ume_at_min_ume, ume_at_min_coe, n_pareto_points)

    print(f"      Step 3: Generating Pareto Front ({n_pareto_points} points)...")
    solutions = [f2_anchor]

    # Loop through epsilons
    for i, eps in enumerate(epsilon_values[1:-1]):
        step = i + 1
        total_steps = len(epsilon_values) - 2
        print(f"              Point {step}/{total_steps} (Goal UME <= {eps:.4f})... ", end="", flush=True)
        
        t0 = time.time()
        result = optimizer.solve_epsilon_constraint(eps)
        t1 = time.time()
        
        coe_str = f"${result.coe:.3f}" if result.status == "Optimal" else "INF"
        print(f"{result.status} ({coe_str}) [{t1-t0:.1f}s]")
        
        if result.status == "Optimal":
            solutions.append(result)

    solutions.append(f1_anchor)
    total_time = time.time() - start_time
    
    print("\n" + "=" * 60)
    print(f"Optimization Complete! (Total time: {total_time:.1f}s)")
    print("=" * 60)

    # Print results table
    print(f"{'Point':>5} {'COE ($/kWh)':>12} {'Reliability':>12} {'PV (kW)':>10} {'Wind (kW)':>10}")
    print("-" * 60)

    for i, sol in enumerate(solutions):
        print(f"{i+1:>5} {sol.coe:>12.3f} {sol.reliability:>12.3f} {sol.pv_capacity:>10.1f} {sol.wind_capacity:>10.1f}")
    
    print("-" * 60)
    print("\nNext: Use 'uv run python main.py --figures' to execute visualization logic if needed.")

if __name__ == "__main__":
    run_visual_optimization()
