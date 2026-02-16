# H2-HRES Implementation Plan
## Techno-Economic Analysis of Hydrogen-Based Hybrid Renewable Energy System

### Paper Reference
**Title:** "Techno-economic analysis of a hydrogen-based hybrid renewable energy system for off-grid power supply in Kenya's urban area"
**Authors:** Mulumba & Farzaneh (2025)
**Journal:** International Journal of Hydrogen Energy 178 (2025) 151474
**Location:** Embakasi Pipeline Estate, Nairobi, Kenya (1°19'14.33"S, 36°53'38.1"E)
**DOI:** https://doi.org/10.1016/j.ijhydene.2025.151474

---

## 1. Project Structure

```
samin_research/
├── pyproject.toml             # uv package management
├── .python-version            # Python version pinning
├── config/
│   ├── __init__.py
│   ├── parameters.py          # Table 2 costs, system specs
│   ├── scenarios.py           # 8 scenarios from Table 6
│   └── constants.py           # Physical constants (F, R, etc.)
├── data/
│   ├── __init__.py
│   ├── fetchers/
│   │   ├── __init__.py
│   │   ├── nasa_power.py      # NASA POWER API client
│   │   ├── load_profile.py    # 127.8 MWh/year profile generator
│   │   └── biomass_data.py    # GIS/LULC feedstock data
│   └── cache/                 # Cached API responses
├── components/
│   ├── __init__.py
│   ├── base.py                # Abstract component class
│   ├── solar_pv.py            # Equation 11
│   ├── wind_turbine.py        # Equation 12
│   ├── electrolyzer.py        # Equation 13
│   ├── fuel_cell.py           # Equations 14-15
│   ├── hydrogen_storage.py    # Equation 16
│   ├── biomass_generator.py   # Equations 17-21, 28
│   └── gibbs_minimization.py  # Equations 22-27 (HHV calc)
├── economics/
│   ├── __init__.py
│   ├── costs.py               # Capital & O&M (Table 2)
│   ├── coe_calculator.py      # Equation 2-4
│   └── hydrogen_market.py     # H2 revenue calculation
├── optimization/
│   ├── __init__.py
│   ├── objectives.py          # f1(COE), f2(UME) - Eq 1-7
│   ├── constraints.py         # Technical constraints
│   ├── dispatch_scheduler.py  # Equations 8-10, Figure 4
│   └── epsilon_constraint.py  # Multi-objective MILP solver
├── simulation/
│   ├── __init__.py
│   ├── hourly_simulation.py   # 8760-hour engine
│   └── scenario_runner.py     # 8 scenarios analysis
├── visualization/
│   ├── __init__.py
│   ├── pareto_plots.py        # Figure 9 reproduction
│   ├── dispatch_plots.py      # Figures 11-13
│   └── sensitivity_plots.py   # Figure 14
├── tests/
│   ├── __init__.py
│   ├── unit/                  # Component tests
│   ├── integration/           # System tests
│   └── validation/            # Paper results comparison
├── results/
│   └── figures/
└── main.py
```

---

## 2. Key Equations to Implement

### 2.1 Objective Functions (Equations 1-7)
```
Eq 1: min F(x) = (f1(COE), f2(UME)) with ε-constraint
Eq 2: f1(COE) = [TC - β·(G^H·p^H)]/(1+dr)^n / [P^HRES/(1+dr)^n]
Eq 3: TC = Σ_h Σ_τ P^HRES_hτ · λ_τ
Eq 6: Ri_h = 1 - UME_h
Eq 7: f2(UME) = Σ_h [(P^D_h + P^ELZ_h) - P^HRES_h] / P^HRES_h
```

### 2.2 Component Models
| Component | Equation | Key Formula |
|-----------|----------|-------------|
| Solar PV | Eq 11 | P^PV = (PV_max·N_p·PV_df)·(G_h/G_STC)·(1+K_T·ΔT) |
| Wind Turbine | Eq 12 | Cubic power curve with cut-in/rated/cut-out |
| Electrolyzer | Eq 13 | Q^ELZ = (η_ELZ·P^ELZ)/(2F·V_rev) |
| Fuel Cell | Eq 14-15 | P^FC = V_cell·I_cell·N_fc |
| H2 Storage | Eq 16 | H_h = H_{h-1} + Q^ELZ - Q^FC - G^H |
| Biomass | Eq 19-21 | P^BM = Q^B·η_st, Q^B = B·LHV·(1-e_Ls) |
| HHV (Gibbs) | Eq 22-27 | Gibbs free energy minimization |
| LHV | Eq 28 | LHV = HHV - l_v·[W_r·(1+8.94·C_H2)] |

### 2.3 Dispatch Logic (Equations 8-10)
```
Eq 8: P^HRES_h = P^D_h + P^ELZ_h (supply-demand balance)
Eq 9: P^HRES = {ℶ_0·(PV+WT), ℶ_a·(PV+WT+FC), ℶ_b·(PV+WT+BM), ℶ_c·(PV+WT+BM+FC)}
Eq 10: ℶ_0, ℶ_a, ℶ_b, ℶ_c ∈ {0, 1}
```

---

## 3. Decision Variables (MILP)

| Variable | Type | Description | Bounds |
|----------|------|-------------|--------|
| P_pv[h] | Continuous | PV power output | [0, capacity×irradiance] |
| P_wt[h] | Continuous | Wind power output | [0, capacity×f(wind)] |
| P_bm[h] | Continuous | Biomass power | [0.3×cap×y_bm, cap×y_bm] |
| P_fc[h] | Continuous | Fuel cell power | [0, cap×y_fc] |
| P_elz[h] | Continuous | Electrolyzer consumption | [0, cap×y_elz] |
| Q_elz[h] | Continuous | H2 produced (kg/h) | [0, ∞] |
| Q_fc[h] | Continuous | H2 consumed (kg/h) | [0, ∞] |
| G_h[h] | Continuous | H2 sold (kg/h) | [0, ∞] |
| H_storage[h] | Continuous | H2 tank level (kg) | [H_min, H_max] |
| UME[h] | Continuous | Unmet energy | [0, demand] |
| ℶ_0, ℶ_a, ℶ_b, ℶ_c | Binary | Dispatch mode flags | {0, 1} |
| y_bm, y_fc, y_elz | Binary | On/off status | {0, 1} |

---

## 4. Component Cost Parameters (Table 2)

| Component | Capital ($/kW) | O&M |
|-----------|----------------|-----|
| PV Panel | 900 | $55/year |
| Wind Turbine | 1200 | $41.78/year |
| Electrolyzer | 890 | $20/year |
| Fuel Cell | 1000 | $0.01/hour |
| H2 Tank | 1100 | $0/year |
| Biomass Gen | 600 | $15/year |

**Economic Parameters:**
- Discount rate: 12%
- H2 price: $6.6/kg (base), $9.9/kg (sensitivity)

---

## 5. Target Results for Validation

### 5.1 Optimal Configuration (Table 5)
| Component | Capacity |
|-----------|----------|
| PV System | 41.8 kW |
| Wind Turbines | 30.1 kW |
| Biogenerator | 27.4 kW |
| Fuel Cell | 15.1 kW |
| Electrolyzer | 40.3 kW |

### 5.2 COE & Reliability Results
| Scenario | COE ($/kWh) | Reliability |
|----------|-------------|-------------|
| With H2 market @ $6.6/kg | 0.494 | 0.961 |
| Without H2 market | 0.668 | 0.978 |
| With H2 @ $9.9/kg | 0.405 | - |

### 5.3 Seasonal COE (Table 8)
| Season | H2@$6.6/kg | H2@$9.9/kg |
|--------|------------|------------|
| Dry | $0.452/kWh | $0.398/kWh |
| Wet | $0.511/kWh | $0.442/kWh |

---

## 6. Data Requirements

### 6.1 Meteorological Data (NASA POWER API)
- **Location:** -1.3206°, 36.8939° (Nairobi)
- **Parameters:**
  - ALLSKY_SFC_SW_DWN (solar irradiance, W/m²)
  - T2M (temperature at 2m, °C)
  - WS10M, WS50M (wind speed, m/s)
  - PRECTOTCORR (precipitation, mm/h)
- **Resolution:** Hourly, 8760 hours/year
- **From paper:** Peak irradiance 1290 W/m², avg 479 W/m²; Peak wind 11.3 m/s, avg 3.69 m/s

### 6.2 Load Profile
- **Total annual demand:** 127.8 MWh (127,800 kWh)
- **Households:** 70 (three 7-story buildings)
- **Peak hours:** 8-11 AM, 8-10 PM

### 6.3 Biomass Feedstock (Table 3-4)
- Dry grass pellets: 19,315,584 ton/year
- Wood pellets: 1,622,350 ton/year
- Mix ratio: 1:10 (wood:grass)
- LHV range: 14.3 MJ/kg (wet) to 17.5 MJ/kg (dry)

---

## 7. Implementation Phases

### Phase 1: Foundation
1. `pyproject.toml` - uv package configuration
2. Virtual environment setup with uv
3. `config/parameters.py` - All paper parameters
4. `config/constants.py` - Physical constants
5. `data/fetchers/nasa_power.py` - NASA POWER API
6. `data/fetchers/load_profile.py` - Load generator
7. `components/base.py` - Abstract base class
8. Unit tests for config/data modules

### Phase 2: Component Models
9. `components/solar_pv.py` - Equation 11
10. `components/wind_turbine.py` - Equation 12
11. `components/electrolyzer.py` - Equation 13
12. `components/fuel_cell.py` - Equations 14-15
13. `components/hydrogen_storage.py` - Equation 16
14. `components/biomass_generator.py` - Equations 17-21, 28
15. `components/gibbs_minimization.py` - Equations 22-27
16. Unit tests for all components

### Phase 3: Economics & Optimization
17. `economics/costs.py` - Table 2 implementation
18. `economics/coe_calculator.py` - Equations 2-4
19. `economics/hydrogen_market.py` - H2 revenue
20. `optimization/objectives.py` - f1(COE), f2(UME)
21. `optimization/constraints.py` - Technical constraints
22. `optimization/dispatch_scheduler.py` - Equations 8-10
23. `optimization/epsilon_constraint.py` - MILP solver
24. Integration tests

### Phase 4: Simulation & Validation
25. `simulation/hourly_simulation.py` - 8760-hour engine
26. `simulation/scenario_runner.py` - 8 scenarios
27. `visualization/pareto_plots.py` - Figure 9
28. `visualization/dispatch_plots.py` - Figures 11-13
29. `tests/validation/test_table5.py` - Config validation
30. `tests/validation/test_coe_results.py` - COE validation
31. `tests/validation/test_scenarios.py` - Scenario validation
32. `main.py` - Entry point
33. Final validation report

---

## 8. Key Technical Decisions

### 8.1 Package Management
- **Tool:** uv (fast Python package manager)
- **Setup:** `uv venv && uv pip install -e .`
- **Config:** pyproject.toml with dependencies

### 8.2 Optimization Solver
- **Primary:** PuLP with CBC solver (open-source)
- **Backup:** GLPK
- **Variables:** ~150,000 (8760×17), ~130,000 constraints

### 8.3 ε-Constraint Implementation
1. Solve min f1(COE) → get f1*, f2 at f1*
2. Solve min f2(UME) → get f2*, f1 at f2*
3. Divide [f2*, f2_at_f1*] into 20 intervals
4. For each ε: min f1 s.t. f2 ≤ ε
5. Filter dominated solutions
6. Find knee point (best trade-off)

### 8.4 Dispatch Logic (Figure 4)
```
IF P_PV + P_WT ≥ P_D:
    MODE_0: Excess → Electrolyzer → H2 storage/sales
ELSE (deficit):
    IF H2_available > H_min:
        MODE_A: Activate Fuel Cell
    ELIF Biomass_available:
        MODE_B: Activate Biomass
    ELSE:
        MODE_C: Both FC + Biomass
```

---

## 9. Validation Criteria

| Metric | Tolerance | Method |
|--------|-----------|--------|
| Component capacities | ±5% | Relative error |
| COE values | ±3% | Relative error |
| Reliability index | ±0.02 | Absolute error |
| Pareto front shape | Visual | Qualitative match |
| Dispatch patterns | Qualitative | Scenario comparison |

---

## 10. Dependencies (pyproject.toml)

```toml
[project]
name = "h2-hres"
version = "0.1.0"
description = "Hydrogen-based Hybrid Renewable Energy System optimization"
requires-python = ">=3.10"
dependencies = [
    "numpy>=1.24.0",
    "pandas>=2.0.0",
    "scipy>=1.10.0",
    "pulp>=2.7.0",
    "matplotlib>=3.7.0",
    "seaborn>=0.12.0",
    "requests>=2.28.0",
    "pyyaml>=6.0",
    "tqdm>=4.65.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.3.0",
    "pytest-cov>=4.1.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

---

## 11. Critical Files Summary

| Priority | File | Purpose |
|----------|------|---------|
| 1 | `optimization/epsilon_constraint.py` | Core MILP solver |
| 2 | `optimization/dispatch_scheduler.py` | Dispatch logic (Eq 8-10) |
| 3 | `components/biomass_generator.py` | Complex thermodynamics |
| 4 | `simulation/hourly_simulation.py` | 8760-hour integration |
| 5 | `tests/validation/test_coe_results.py` | Result validation |

---

## 12. Complete Equation Mapping (Paper → Implementation)

| Eq # | Paper Section | Formula | Implementation File | Verification |
|------|--------------|---------|---------------------|--------------|
| 1 | 2.5 | min F(x) = (f1(COE), f2(UME)) | `optimization/epsilon_constraint.py` | Multi-objective setup |
| 2 | 2.5.1 | f1(COE) = [TC - β·(G^H·p^H)]/(1+dr)^n / [P^HRES/(1+dr)^n] | `economics/coe_calculator.py` | COE with H2 revenue |
| 3 | 2.5.1 | TC = Σ_h Σ_τ P^HRES_hτ · λ_τ | `economics/costs.py` | Total cost aggregation |
| 4 | 2.5.1 | λ_τ = λ_PV + λ_WT + λ_ELZ + λ_FC + λ_Hst + λ_OM | `economics/costs.py` | Unit cost breakdown |
| 5 | 2.5.1 | P^HRES = Σ(P^PV + P^WT + P^BM + P^FC) | `simulation/hourly_simulation.py` | Total generation |
| 6 | 2.5.1 | Ri_h = 1 - UME_h | `optimization/objectives.py` | Reliability index |
| 7 | 2.5.1 | f2(UME) = Σ[(P^D + P^ELZ) - P^HRES] / P^HRES | `optimization/objectives.py` | UME calculation |
| 8 | 2.5.2.1 | P^HRES_h = P^D_h + P^ELZ_h | `optimization/dispatch_scheduler.py` | Supply-demand balance |
| 9 | 2.5.2.1 | P^HRES = {ℶ_0·(PV+WT), ℶ_a·(PV+WT+FC), ...} | `optimization/dispatch_scheduler.py` | Dispatch modes |
| 10 | 2.5.2.1 | ℶ_0, ℶ_a, ℶ_b, ℶ_c ∈ {0, 1} | `optimization/constraints.py` | Binary flags |
| 11 | 2.5.2.2 | P^PV = (PV_max·N_p·PV_df)·(G_h/G_STC)·(1+K_T·ΔT) | `components/solar_pv.py` | PV output |
| 12 | 2.5.2.2 | P^WT (cubic power curve) | `components/wind_turbine.py` | Wind output |
| 13 | 2.5.2.3 | Q^ELZ = (η_ELZ·P^ELZ)/(2F·V_rev) | `components/electrolyzer.py` | H2 production |
| 14 | 2.5.2.3 | P^FC = V_cell·I_cell·N_fc | `components/fuel_cell.py` | FC power |
| 15 | 2.5.2.3 | Q^FC = P^FC/(2F·V_cell·N_fc) | `components/fuel_cell.py` | H2 consumption |
| 16 | 2.5.2.3 | H_h = H_{h-1} + Q^ELZ - Q^FC - G^H | `components/hydrogen_storage.py` | Storage dynamics |
| 17 | 2.5.2.4 | C_xH_yO_z + O_2 → CO + H_2 + CO_2 + H_2O + Char | `components/biomass_generator.py` | Gasification |
| 18 | 2.5.2.4 | Syngas combustion | `components/biomass_generator.py` | Combustion |
| 19 | 2.5.2.4 | P^BM = Q^B · η_st | `components/biomass_generator.py` | Biomass power |
| 20 | 2.5.2.4 | Q^B = B_h · LHV · (1 - e_Ls) | `components/biomass_generator.py` | Heat transfer |
| 21 | 2.5.2.4 | e_Ls = e_fm + e_uc + e_dg + e_lh + e_ma + e_mfc | `components/biomass_generator.py` | Heat losses |
| 22-27 | 2.5.2.4 | Gibbs free energy minimization | `components/gibbs_minimization.py` | HHV calculation |
| 28 | 2.5.2.4 | LHV = HHV - l_v·[W_r·(1+8.94·C_H2)] | `components/biomass_generator.py` | LHV calculation |
| 29 | 2.5.2.5 | C_L = argmax_c(P_c·Π P(x_i|c)) | `data/fetchers/biomass_data.py` | Bayesian classification |
| 30 | 2.5.2.5 | A_F|R = ½Σ(x_i·y_{i+1} - x_{i+1}·y_i) | `data/fetchers/biomass_data.py` | Shoelace area |
| 31 | 2.5.2.5 | B_fdT = {(A_F·Y_F) + (A_R·Y_R)} | `data/fetchers/biomass_data.py` | Feedstock fortitude |
| 32 | 2.5.2.5 | Σ B_h ≤ B_fdT | `optimization/constraints.py` | Feedstock constraint |

---

## 13. Complete Table Mapping (Paper → Validation)

| Table # | Description | Data Points | Validation Use |
|---------|-------------|-------------|----------------|
| Table 2 | Component costs | PV: $900/kW, WT: $1200/kW, ELZ: $890/kW, FC: $1000/kW, H2 Tank: $1100/kW, BM: $600/kW | Input parameters |
| Table 3 | Biomass feedstock | Dry grass: 19,315,584 ton/yr, Wood: 1,622,350 ton/yr | Feedstock constraint |
| Table 4 | Land cover classification | 8 categories with areas | GIS validation |
| Table 5 | Optimal configuration | PV: 41.8kW, WT: 30.1kW, BM: 27.4kW, FC: 15.1kW, ELZ: 40.3kW | **PRIMARY VALIDATION** |
| Table 6 | 8 Scenarios | LHV × Irradiance × Wind combinations | Scenario testing |
| Table 7 | Config @ different H2 prices | H1=$6.6/kg vs H2=$9.9/kg | Sensitivity validation |
| Table 8 | Seasonal COE | Dry: $0.452-$0.398, Wet: $0.511-$0.442 | Seasonal validation |
| Table 9 | Literature comparison | 7 reference studies | Benchmarking |

---

## 14. Figure Mapping (Paper → Visualization)

| Figure # | Description | Implementation File | Validation Purpose |
|----------|-------------|---------------------|-------------------|
| Fig 1 | System schematic | Documentation only | Architecture reference |
| Fig 2 | Operation logic flow | `optimization/dispatch_scheduler.py` | Logic validation |
| Fig 3 | ε-constraint logic | `optimization/epsilon_constraint.py` | Algorithm validation |
| Fig 4 | Dispatch model + unit commitment | `optimization/dispatch_scheduler.py` | **CRITICAL** - Full dispatch logic |
| Fig 5 | LULC mapping model | `data/fetchers/biomass_data.py` | GIS methodology |
| Fig 6 | Annual solar/wind data | `visualization/dispatch_plots.py` | Data validation |
| Fig 7 | LULC map classification | Documentation | Spatial reference |
| Fig 8 | Rangeland/forest classification | Documentation | Feedstock reference |
| Fig 9 | Pareto curves (a,b,c) | `visualization/pareto_plots.py` | **PRIMARY VALIDATION** |
| Fig 10 | Optimal capacity pie charts | `visualization/pareto_plots.py` | Config visualization |
| Fig 11 | Demand-supply scenarios | `visualization/dispatch_plots.py` | Scenario validation |
| Fig 12 | H2 production/consumption | `visualization/dispatch_plots.py` | H2 balance validation |
| Fig 13 | Biomass power/feed-rate | `visualization/dispatch_plots.py` | Biomass validation |
| Fig 14 | H2 price sensitivity | `visualization/sensitivity_plots.py` | Sensitivity validation |

---

## 15. Supplementary Material (Paper S1, S2)

The paper references supplementary files S1 and S2 for:
- **S1:** Detailed fuel cell voltage calculation (V_cell)
- **S2:** Detailed electrolyzer efficiency calculation (η_ELZ)

These must be implemented in:
- `components/fuel_cell.py` - V_cell calculation
- `components/electrolyzer.py` - η_ELZ calculation (voltage, Faradaic, auxiliary efficiency)

---

## 16. 8 Scenario Definitions (Table 6 - Complete)

| SC | Month | LHV | Irradiance | Wind | Climate | LHV Value |
|----|-------|-----|------------|------|---------|-----------|
| 1 | January | High | High | High | Dry | 17.5 MJ/kg |
| 2 | February | High | High | Low | Dry | 17.5 MJ/kg |
| 3 | April | High | Low | High | Dry | 17.5 MJ/kg |
| 4 | July | High | Low | Low | Cold/Dry | 17.5 MJ/kg |
| 5 | December | Low | High | High | Rainy | 14.3 MJ/kg |
| 6 | May | Low | High | Low | Rainy | 14.3 MJ/kg |
| 7 | November | Low | Low | High | Rainy | 14.3 MJ/kg |
| 8 | May | Low | Low | Low | Cold/Rainy | 14.3 MJ/kg |

**LHV Relationship to Precipitation:**
- LHV = 17.5 MJ/kg when precipitation 0-12 mm (dry)
- LHV = 14.3 MJ/kg when precipitation ~120 mm (wet)
- Feedstock mix ratio: 1:10 (wood:grass)

---

## 17. VERIFICATION GUIDELINE

### 17.1 How to Know the Implementation is Correct

#### Step 1: Unit Test Validation (Component Level)
Each component must pass unit tests that verify equation implementation:

| Component | Test File | Validation Method |
|-----------|-----------|-------------------|
| Solar PV | `tests/unit/test_solar_pv.py` | Compare output with Eq 11 at known G_h, T values |
| Wind Turbine | `tests/unit/test_wind_turbine.py` | Verify cubic curve + cut-in/cut-out behavior |
| Electrolyzer | `tests/unit/test_electrolyzer.py` | H2 production rate at known power input |
| Fuel Cell | `tests/unit/test_fuel_cell.py` | Power output at known H2 consumption |
| H2 Storage | `tests/unit/test_h2_storage.py` | Mass balance: H_h = H_{h-1} + in - out |
| Biomass | `tests/unit/test_biomass.py` | Power output at known feedrate + LHV |
| Gibbs HHV | `tests/unit/test_gibbs.py` | HHV within literature range (15-20 MJ/kg) |

#### Step 2: Integration Test Validation (System Level)
```
tests/integration/
├── test_dispatch_logic.py      # Verify Fig 4 logic flow
├── test_supply_demand.py       # Eq 8 balance verification
├── test_hydrogen_balance.py    # Production = Consumption + Sales + Storage
└── test_cost_calculation.py    # TC aggregation per Eq 3-4
```

#### Step 3: Result Validation (Paper Comparison)

**PRIMARY VALIDATION - Table 5 Results:**
```python
# tests/validation/test_table5.py
EXPECTED_OPTIMAL_CONFIG = {
    "PV_kW": 41.8,      # ±5% → [39.71, 43.89]
    "WT_kW": 30.1,      # ±5% → [28.60, 31.61]
    "BM_kW": 27.4,      # ±5% → [26.03, 28.77]
    "FC_kW": 15.1,      # ±5% → [14.35, 15.86]
    "ELZ_kW": 40.3,     # ±5% → [38.29, 42.32]
}
```

**COE Validation:**
```python
# tests/validation/test_coe_results.py
EXPECTED_COE = {
    "with_H2_market_6.6": 0.494,    # ±3% → [0.479, 0.509]
    "without_H2_market": 0.668,     # ±3% → [0.648, 0.688]
    "with_H2_market_9.9": 0.405,    # ±3% → [0.393, 0.417]
}

EXPECTED_RELIABILITY = {
    "with_H2_market": 0.961,        # ±0.02 → [0.941, 0.981]
    "without_H2_market": 0.978,     # ±0.02 → [0.958, 0.998]
}
```

**Seasonal COE Validation (Table 8):**
```python
EXPECTED_SEASONAL_COE = {
    "dry_H1": 0.452,    # H2@$6.6/kg
    "dry_H2": 0.398,    # H2@$9.9/kg
    "wet_H1": 0.511,    # H2@$6.6/kg
    "wet_H2": 0.442,    # H2@$9.9/kg
}
```

### 17.2 Validation Checklist

```
[ ] 1. DATA VALIDATION
    [ ] Solar irradiance peak ~1290 W/m², avg ~479 W/m²
    [ ] Wind speed peak ~11.3 m/s, avg ~3.69 m/s
    [ ] Annual load = 127.8 MWh (127,800 kWh)
    [ ] Location coordinates: -1.3206°, 36.8939°

[ ] 2. COMPONENT VALIDATION
    [ ] PV follows Eq 11 temperature derating
    [ ] Wind follows Eq 12 cubic power curve
    [ ] Electrolyzer follows Eq 13 with Faraday constant
    [ ] Fuel cell follows Eq 14-15
    [ ] H2 storage follows Eq 16 mass balance
    [ ] Biomass follows Eq 19-21, 28 thermodynamics

[ ] 3. OPTIMIZATION VALIDATION
    [ ] ε-constraint generates Pareto front (Fig 9)
    [ ] Dispatch logic follows Fig 4 decision tree
    [ ] Binary flags (ℶ_0, ℶ_a, ℶ_b, ℶ_c) work correctly
    [ ] Supply-demand balance (Eq 8) satisfied every hour

[ ] 4. ECONOMIC VALIDATION
    [ ] Component costs match Table 2
    [ ] COE formula matches Eq 2 (includes H2 revenue)
    [ ] Discount rate = 12%
    [ ] H2 prices: $6.6/kg and $9.9/kg tested

[ ] 5. RESULT VALIDATION
    [ ] Optimal config within ±5% of Table 5
    [ ] COE with H2 market: $0.494 ±3%
    [ ] COE without H2 market: $0.668 ±3%
    [ ] Reliability with H2 market: 0.961 ±0.02
    [ ] Reliability without H2 market: 0.978 ±0.02
    [ ] Pareto front shape matches Fig 9

[ ] 6. SCENARIO VALIDATION
    [ ] All 8 scenarios from Table 6 run successfully
    [ ] Dry season shows higher H2 sales (SC 1-4)
    [ ] Wet season shows higher FC usage (SC 5-8)
    [ ] Seasonal COE matches Table 8

[ ] 7. SENSITIVITY VALIDATION
    [ ] H2@$9.9/kg reduces COE to ~$0.405
    [ ] Higher H2 price → more H2 sales, less FC use
    [ ] Pareto shift matches Fig 14
```

### 17.3 Running Validation Tests

```bash
# Run all validation tests
uv run pytest tests/validation/ -v

# Run specific validation
uv run pytest tests/validation/test_table5.py -v
uv run pytest tests/validation/test_coe_results.py -v
uv run pytest tests/validation/test_scenarios.py -v

# Generate validation report
uv run python -m simulation.scenario_runner --validate --output results/validation_report.md
```

### 17.4 Expected Output Comparison

When the implementation is correct, running the optimization should produce:

**Console Output:**
```
Optimization Results (With H2 Market @ $6.6/kg):
================================================
Optimal COE: $0.494/kWh (Paper: $0.494/kWh) ✓
Reliability Index: 0.961 (Paper: 0.961) ✓

Component Capacities:
- PV System: 41.8 kW (Paper: 41.8 kW) ✓
- Wind Turbines: 30.1 kW (Paper: 30.1 kW) ✓
- Biogenerator: 27.4 kW (Paper: 27.4 kW) ✓
- Fuel Cell: 15.1 kW (Paper: 15.1 kW) ✓
- Electrolyzer: 40.3 kW (Paper: 40.3 kW) ✓

Validation Status: PASSED
```

### 17.5 Troubleshooting Common Discrepancies

| Issue | Possible Cause | Solution |
|-------|---------------|----------|
| COE too high | H2 revenue not included | Check β activation in Eq 2 |
| COE too low | Missing O&M costs | Verify all λ_τ terms in Eq 4 |
| Wrong capacities | Incorrect constraints | Check dispatch binary flags |
| Low reliability | UME calculation error | Verify Eq 7 denominator |
| No Pareto front | Single-objective mode | Ensure ε-constraint loop active |
| Seasonal mismatch | LHV not varying | Update LHV by precipitation |

---

## 18. COMPLETENESS VERIFICATION

### All 32 Equations Implemented:
- [x] Eq 1-7: Objective functions (optimization/objectives.py)
- [x] Eq 8-10: Dispatch scheduling (optimization/dispatch_scheduler.py)
- [x] Eq 11-12: PV & Wind (components/solar_pv.py, wind_turbine.py)
- [x] Eq 13-16: H2 chain (components/electrolyzer.py, fuel_cell.py, hydrogen_storage.py)
- [x] Eq 17-21, 28: Biomass (components/biomass_generator.py)
- [x] Eq 22-27: Gibbs minimization (components/gibbs_minimization.py)
- [x] Eq 29-32: LULC/GIS (data/fetchers/biomass_data.py)

### All 9 Tables Referenced:
- [x] Table 2: Component costs → config/parameters.py
- [x] Table 3: Biomass feedstock → data/fetchers/biomass_data.py
- [x] Table 4: Land cover → data/fetchers/biomass_data.py
- [x] Table 5: Optimal config → tests/validation/test_table5.py
- [x] Table 6: 8 Scenarios → config/scenarios.py
- [x] Table 7: H2 price configs → config/scenarios.py
- [x] Table 8: Seasonal COE → tests/validation/test_scenarios.py
- [x] Table 9: Literature comparison → tests/validation/ (benchmarking)

### All Key Figures Reproducible:
- [x] Fig 9: Pareto curves → visualization/pareto_plots.py
- [x] Fig 10: Capacity pie charts → visualization/pareto_plots.py
- [x] Fig 11-13: Scenario plots → visualization/dispatch_plots.py
- [x] Fig 14: Sensitivity analysis → visualization/sensitivity_plots.py
