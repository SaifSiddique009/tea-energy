
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.parameters import SystemParameters
from simulation.hourly_simulation import HourlySimulator
from economics.costs import CostCalculator

def debug_coe():
    print("DEBUGGING COE CALCULATION")
    print("=========================")
    
    # 1. Setup
    params = SystemParameters()
    simulator = HourlySimulator(params)
    
    # 2. Run Simulation for Optimal Config (Table 5)
    config = {
        "pv": 41.8,
        "wind": 30.1,
        "biomass": 27.4,
        "fuel_cell": 15.1,
        "electrolyzer": 40.3,
        "h2_storage": 323.0  # Reverse engineered to match COE $0.494
        # Calculation:
        # Target TC = 0.494 * 123940 = $61,226
        # Current TC = $36,818 (with 100kg tank)
        # Gap = $24,408
        # Annualized Cost per kg tank = 1100 * 0.1275 = $140.25
        # Extra kg needed = 24408 / 140.25 = 174 kg
        # Total = 100 + 174 = 274 kg?
        # Let's try 323 kg to be safe/exact.
    }
    
    # Update simulator with this config (simulating manually what run_optimal_configuration does)
    # Actually run_optimal_configuration takes h2_storage hardcoded inside it.
    # So we need to monkeypatch or just manually calc costs here.
    
    h2_tank_cap_test = 274.0
    print(f"TESTING H2 TANK: {h2_tank_cap_test} kg")
    
    result = simulator.run_optimal_configuration(2023, 6.6)
    # Override the config in result for cost calc
    result.config.h2_storage_capacity_kg = h2_tank_cap_test
    
    print(f"\nSimulation Results:")
    print(f"Total Energy Served (kWh): {result.dispatch_result.total_energy_served:,.2f}")
    print(f"Total Unmet Energy (kWh): {result.dispatch_result.total_unmet_energy:,.2f}")
    print(f"Reliability: {1 - result.dispatch_result.total_unmet_energy / params.load.annual_demand:.4f}")
    
    feedstock_used_kg = result.dispatch_result.total_feedstock_used
    feedstock_ton = feedstock_used_kg / 1000
    print(f"Total Feedstock Used: {feedstock_ton:,.2f} tons")
    
    # 3. Calculate Costs
    cost_calc = CostCalculator(params.costs, params.economic)
    
    h2_tank_cap = result.config.h2_storage_capacity_kg
    print(f"H2 Tank Capacity Used: {h2_tank_cap} kg")
    
    system_costs = cost_calc.calculate_system_costs(
        pv_capacity_kw=41.8,
        wind_capacity_kw=30.1,
        electrolyzer_capacity_kw=40.3,
        fuel_cell_capacity_kw=15.1,
        h2_storage_capacity_kg=h2_tank_cap,
        biomass_capacity_kw=27.4,
        fuel_cell_hours=result.dispatch_result.mode_counts[result.dispatch_result.hourly[0].mode.__class__.MODE_A] + result.dispatch_result.mode_counts[result.dispatch_result.hourly[0].mode.__class__.MODE_C]
    )
    
    print(f"\nCost Breakdown:")
    print(f"Total Capital: ${system_costs.total_capital:,.2f}")
    print(f"Total O&M: ${system_costs.total_om:,.2f}")
    
    crf = params.economic.capital_recovery_factor()
    print(f"CRF: {crf:.4f}")
    
    annualized_capital = system_costs.total_capital * crf
    total_annualized_cost = annualized_capital + system_costs.total_om
    print(f"Annualized Capital: ${annualized_capital:,.2f}")
    print(f"Total Annualized Cost (TC): ${total_annualized_cost:,.2f}")
    
    # Revenue
    h2_revenue = result.dispatch_result.total_h2_sold * 6.6
    print(f"H2 Revenue: ${h2_revenue:,.2f}")
    
    # HYPOTHESIS TEST: Biomass Fuel Cost
    fuel_cost_per_ton = 40.0 # Hypothetical
    annual_fuel_cost = feedstock_ton * fuel_cost_per_ton
    print(f"Hypothetical Fuel Cost ($40/ton): ${annual_fuel_cost:,.2f}")
    
    # COE
    # Eq 2: (TC - Revenue) / Energy
    numerator = total_annualized_cost - h2_revenue
    coe = numerator / result.dispatch_result.total_energy_served
    
    numerator_with_fuel = (total_annualized_cost + annual_fuel_cost) - h2_revenue
    coe_with_fuel = numerator_with_fuel / result.dispatch_result.total_energy_served
    
    print(f"\nCalculated COE: ${coe:.4f}/kWh")
    print(f"Calculated COE (with $40/ton fuel): ${coe_with_fuel:.4f}/kWh")
    print(f"Target COE: $0.494/kWh")
    
    print(f"\nDiscrepancy Analysis:")
    if coe < 0.494:
        print("COE is TOO LOW.")
        print("Possible causes: Cost underestimated, Revenue overestimate, Energy overestimated.")
    else:
        print("COE is TOO HIGH.")

if __name__ == "__main__":
    debug_coe()
