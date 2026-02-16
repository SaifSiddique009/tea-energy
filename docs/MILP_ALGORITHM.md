# MILP Algorithm Explanation

A beginner-friendly guide to understanding the Multi-Objective Optimization with Epsilon-Constraint method used in this project.

---

## Table of Contents

1. [What is MILP?](#1-what-is-milp)
2. [The Multi-Objective Problem](#2-the-multi-objective-problem)
3. [Epsilon-Constraint Method](#3-epsilon-constraint-method)
4. [How the Algorithm Works](#4-how-the-algorithm-works)
5. [Decision Variables](#5-decision-variables)
6. [Constraints](#6-constraints)
7. [The Dispatch Logic](#7-the-dispatch-logic)
8. [Why Not HOMER?](#8-why-not-homer)
9. [Solver Explanation](#9-solver-explanation)

---

## 1. What is MILP?

### Mixed-Integer Linear Programming

**MILP** = Mixed-Integer Linear Programming

- **Mixed**: Uses both continuous (e.g., 41.8 kW) and integer/binary (e.g., on/off) variables
- **Integer**: Some variables must be whole numbers (0 or 1 for on/off)
- **Linear**: All relationships are linear (y = mx + b form)
- **Programming**: Mathematical optimization (not computer programming)

### Simple Example

Imagine choosing how many solar panels and wind turbines to buy:

```
Minimize: Cost = 900*PV + 1200*Wind    (minimize total cost)

Subject to:
  PV + Wind >= 50 kW                    (meet demand)
  PV <= 100 kW                          (space constraint)
  Wind <= 80 kW                         (space constraint)
  PV, Wind >= 0                         (can't have negative)
```

This is a **Linear Program (LP)**. MILP adds integer constraints:

```
Add: Wind_on = {0, 1}                   (binary: on or off)
     Wind <= 80 * Wind_on               (wind only if turned on)
```

---

## 2. The Multi-Objective Problem

### Two Competing Goals

The paper optimizes for TWO objectives simultaneously:

1. **Minimize COE (Cost of Energy)**: Lower electricity cost = good
2. **Minimize UME (Unmet Energy)**: Less blackouts = good

**The Problem**: These goals conflict!
- Cheaper systems have more blackouts
- Reliable systems cost more

### Pareto Front

We can't minimize both perfectly, so we find the **Pareto Front**: the set of "best trade-off" solutions where you can't improve one objective without hurting the other.

```
         UME (Unmet Energy)
          ^
     0.05 |    *                    <- Expensive but reliable
          |      *
     0.04 |        * <- "Knee point" (best trade-off)
          |          *
     0.03 |            *
          |              *
     0.02 |                *        <- Cheap but unreliable
          +----+----+----+----+---> COE ($/kWh)
              0.40 0.45 0.50 0.55
```

Each `*` is a valid solution. The "knee point" is typically chosen as the optimal balance.

---

## 3. Epsilon-Constraint Method

### How to Handle Two Objectives

The **Epsilon-Constraint Method** converts a multi-objective problem into a series of single-objective problems:

1. **Choose one objective to minimize** (COE)
2. **Constrain the other** (UME <= epsilon)
3. **Vary epsilon** to trace out the Pareto front

### Algorithm Steps

```
Step 1: Minimize COE alone
        → Get COE* (best possible COE), and UME at this point

Step 2: Minimize UME alone
        → Get UME* (best possible UME), and COE at this point

Step 3: Divide [UME*, UME_at_COE*] into intervals
        → Create 20 epsilon values: e1, e2, ..., e20

Step 4: For each epsilon:
        → Solve: Minimize COE subject to UME <= epsilon
        → Record the solution (COE, UME, capacities)

Step 5: Filter dominated solutions
        → Remove any solution that's worse on both objectives

Step 6: Find knee point
        → Choose solution with best trade-off
```

### Visual Representation

```
           Minimize COE (no UME constraint)
                    ↓
              COE* = $0.494/kWh
              UME  = 0.039
                    ↓
    ┌───────────────────────────────────┐
    │   For each epsilon in [0.022, 0.039]:  │
    │     Solve: min COE s.t. UME <= eps    │
    │     → Get one Pareto point            │
    └───────────────────────────────────┘
                    ↓
              20 Pareto points
                    ↓
              Select knee point
                    ↓
           Optimal Configuration
```

---

## 4. How the Algorithm Works

### The Objective Function (Equation 1-2)

```
Minimize COE = (Total_Cost - H2_Revenue) / Total_Energy

Where:
  Total_Cost = Capital + O&M + Replacement
  H2_Revenue = H2_sold * H2_price
  Total_Energy = sum of all power generated
```

### In Python Terms

```python
# Objective function (simplified)
total_cost = sum(
    pv_capital * pv_capacity +
    wind_capital * wind_capacity +
    ... +
    om_costs
)

h2_revenue = sum(h2_sold[h] * h2_price for h in hours)

total_energy = sum(
    pv_power[h] + wind_power[h] + fc_power[h] + bm_power[h]
    for h in hours
)

coe = (total_cost - h2_revenue) / total_energy
```

### The Full Problem

```
MINIMIZE:
    COE = f1(x)

SUBJECT TO:
    UME <= epsilon                      (epsilon-constraint)
    Supply >= Demand at each hour       (power balance)
    H2_storage[h] = H2_storage[h-1] + produced - consumed
    0 <= PV_power <= PV_capacity * irradiance
    0 <= Wind_power <= Wind_capacity * f(wind_speed)
    0.3*BM_cap*y_bm <= BM_power <= BM_cap*y_bm
    ... (many more constraints)

VARIABLES:
    PV_capacity, Wind_capacity, ... (continuous)
    y_bm, y_fc, y_elz (binary: on/off)
```

---

## 5. Decision Variables

### Continuous Variables (Real Numbers)

| Variable | Meaning | Units |
|----------|---------|-------|
| P_pv[h] | PV power at hour h | kW |
| P_wind[h] | Wind power at hour h | kW |
| P_fc[h] | Fuel cell power at hour h | kW |
| P_bm[h] | Biomass power at hour h | kW |
| P_elz[h] | Electrolyzer power at hour h | kW |
| H2_produced[h] | H2 production rate | kg/h |
| H2_consumed[h] | H2 consumption rate | kg/h |
| H2_sold[h] | H2 sold to market | kg/h |
| H2_storage[h] | H2 tank level | kg |
| UME[h] | Unmet energy at hour h | kW |

### Binary Variables (0 or 1)

| Variable | Meaning |
|----------|---------|
| y_bm[h] | Biomass generator ON (1) or OFF (0) |
| y_fc[h] | Fuel cell ON (1) or OFF (0) |
| y_elz[h] | Electrolyzer ON (1) or OFF (0) |

### Why Binary Variables?

Biomass generators have a **minimum load** (can't run below 30% capacity):

```
Either: Biomass is OFF → P_bm = 0
Or:     Biomass is ON  → 0.3 * capacity <= P_bm <= capacity
```

This is modeled as:
```
0.3 * BM_capacity * y_bm <= P_bm <= BM_capacity * y_bm

If y_bm = 0: 0 <= P_bm <= 0 (must be zero)
If y_bm = 1: 0.3*cap <= P_bm <= cap (normal operation)
```

---

## 6. Constraints

### Power Balance (Equation 8)

Every hour, supply must meet demand (plus electrolyzer):

```
PV_power[h] + Wind_power[h] + FC_power[h] + BM_power[h]
    >= Demand[h] + ELZ_power[h] - UME[h]
```

### H2 Storage (Equation 16)

Mass balance every hour:

```
H2_storage[h] = H2_storage[h-1] + H2_produced[h] - H2_consumed[h] - H2_sold[h]

Subject to:
  H2_min <= H2_storage[h] <= H2_max  (tank limits)
```

### Component Limits

```
0 <= PV_power[h] <= PV_capacity * (irradiance[h] / 1000)
0 <= Wind_power[h] <= Wind_capacity * f(wind_speed[h])
```

### Biomass Minimum Load

```
0.3 * BM_capacity * y_bm[h] <= BM_power[h] <= BM_capacity * y_bm[h]
```

### Feedstock Constraint (Equation 32)

```
sum(Feedstock_consumed[h] for h in year) <= Available_feedstock
```

---

## 7. The Dispatch Logic

### Figure 4: Decision Tree

The paper uses a hierarchical dispatch strategy:

```
                  Is Renewable (PV+Wind) >= Demand?
                            /            \
                          YES            NO
                           |              |
                    MODE 0: Surplus    Is H2 available?
                           |           /        \
                    Store excess     YES        NO
                    as H2            |           |
                                 MODE A:    Is Biomass on?
                                 Use FC     /        \
                                          YES       NO
                                           |         |
                                       MODE B:    MODE C:
                                       Use BM     Use BM + FC
```

### Dispatch Modes (Equations 9-10)

| Mode | Condition | Action |
|------|-----------|--------|
| Mode 0 | PV+Wind >= Demand | Excess to electrolyzer |
| Mode A | Deficit + H2 available | Activate fuel cell |
| Mode B | Deficit + No H2 | Activate biomass |
| Mode C | Deficit + Both needed | Activate both |

These are modeled with binary flags:
```
mode_0, mode_a, mode_b, mode_c in {0, 1}
mode_0 + mode_a + mode_b + mode_c = 1  (exactly one mode active)
```

---

## 8. Why Not HOMER?

### HOMER (Industry Tool)

HOMER is a widely-used software for hybrid system optimization. However:

| Feature | HOMER | This Implementation |
|---------|-------|---------------------|
| Multi-objective | Limited | Full Pareto front |
| Customization | Limited | Full control |
| Algorithm | Proprietary | Transparent MILP |
| Cost | Commercial license | Free/open-source |
| Research use | Results hard to explain | Full mathematical formulation |

### Why Epsilon-Constraint MILP?

1. **Academic rigor**: Full mathematical formulation in the paper
2. **Transparency**: Every equation is visible and explainable
3. **Reproducibility**: Can be exactly replicated
4. **Flexibility**: Easy to add/modify constraints
5. **Multi-objective**: True Pareto front generation

---

## 9. Solver Explanation

### What is a Solver?

A **solver** is software that finds the optimal values for decision variables. We use:

- **PuLP**: Python library for formulating MILP problems
- **CBC**: Coin-or Branch and Cut solver (does the actual solving)

### How CBC Works (Simplified)

1. **Relax integers**: Solve as continuous LP (fast)
2. **Branch**: Split into sub-problems for integer variables
3. **Bound**: Calculate bounds on objective
4. **Cut**: Add constraints to tighten bounds
5. **Repeat**: Until optimal integer solution found

### Problem Size

For 8760 hours:
- ~150,000 variables
- ~130,000 constraints
- Solve time: 5-30 minutes per epsilon point

### Running the Solver

```python
import pulp

# Create problem
prob = pulp.LpProblem("H2_HRES", pulp.LpMinimize)

# Add variables
pv_cap = pulp.LpVariable("PV_capacity", lowBound=0, upBound=100)

# Add objective
prob += coe_expression  # Minimize COE

# Add constraints
prob += supply >= demand

# Solve
prob.solve(pulp.PULP_CBC_CMD(msg=1, timeLimit=600))

# Get results
print(f"Status: {pulp.LpStatus[prob.status]}")
print(f"PV Capacity: {pv_cap.varValue} kW")
```

---

## Summary: The Big Picture

```
┌─────────────────────────────────────────────────────────────┐
│                    INPUT DATA                                │
│  - 8760 hours of solar, wind, temperature                   │
│  - 8760 hours of demand                                     │
│  - Component costs (Table 2)                                │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│               EPSILON-CONSTRAINT OPTIMIZER                   │
│                                                             │
│  For each epsilon (UME limit):                              │
│    ┌─────────────────────────────────────────────┐         │
│    │  MILP Solver (CBC)                          │         │
│    │  - Decision variables (capacities, power)   │         │
│    │  - Constraints (balance, storage, limits)   │         │
│    │  - Objective: Minimize COE                  │         │
│    │  - Subject to: UME <= epsilon               │         │
│    └───────────────────┬─────────────────────────┘         │
│                        │                                    │
│                        ▼                                    │
│    One Pareto point (COE, UME, configuration)              │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    PARETO FRONT                              │
│  20 optimal trade-off solutions                             │
│                                                             │
│  Select "knee point" = best balance of cost vs reliability  │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  OPTIMAL CONFIGURATION                       │
│  PV: 41.8 kW, Wind: 30.1 kW, Biomass: 27.4 kW              │
│  Fuel Cell: 15.1 kW, Electrolyzer: 40.3 kW                 │
│  COE: $0.494/kWh, Reliability: 96.1%                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Takeaways

1. **MILP** = Optimization with continuous + binary variables
2. **Epsilon-constraint** converts multi-objective → single-objective series
3. **Pareto front** = Set of best trade-off solutions
4. **Knee point** = Selected optimal solution
5. **Dispatch logic** = Rules for which component runs when
6. **CBC solver** = The engine that finds optimal values

---

## Further Reading

- Paper Section 2.5: Full mathematical formulation
- [PuLP Documentation](https://coin-or.github.io/pulp/)
- [Epsilon-Constraint Method](https://en.wikipedia.org/wiki/Multi-objective_optimization#Scalarizing)
- docs/IMPLEMENTATION_PLAN.md: Complete equation mapping
