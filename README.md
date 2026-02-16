# H2-HRES: Hydrogen-Based Hybrid Renewable Energy System

**Techno-Economic Analysis for Off-Grid Power Supply in Kenya**

Implementation of the epsilon-constraint MILP optimization model from:
> Mulumba & Farzaneh (2025). "Techno-economic analysis of a hydrogen-based hybrid renewable energy system for off-grid power supply in Kenya's urban area." *International Journal of Hydrogen Energy*, 178, 151474.

## Quick Start

### Prerequisites
- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager

### Installation

```bash
# Clone/navigate to the project
cd samin_research

# Install dependencies with uv
uv sync

# Verify installation
uv run python -c "import pulp; print('PuLP version:', pulp.__version__)"
```

### Run Basic Test (Synthetic Data)

```bash
# Quick validation with optimal config from paper
uv run python main.py --validate
```

Expected output:
```
Running validation with optimal configuration...
Reliability: 0.992 (Target: 0.961)
COE: $0.XX/kWh (Target: $0.494/kWh)
```

### Run Full Simulation

```bash
# Run hourly simulation (8760 hours)
uv run python main.py --scenarios

# Generate all figures
uv run python main.py --figures

# Run full optimization (takes 30+ minutes)
uv run python main.py --optimize
```

## System Components

| Component | Optimal Capacity | Paper Reference |
|-----------|------------------|-----------------|
| Solar PV | 41.8 kW | Table 5 |
| Wind Turbine | 30.1 kW | Table 5 |
| Biomass Generator | 27.4 kW | Table 5 |
| PEM Fuel Cell | 15.1 kW | Table 5 |
| PEM Electrolyzer | 40.3 kW | Table 5 |
| H2 Storage Tank | 100 kg | Section 3.1 |

## Key Results

| Metric | With H2 Market | Without H2 Market |
|--------|----------------|-------------------|
| COE ($/kWh) | 0.494 | 0.668 |
| Reliability | 96.1% | 97.8% |
| H2 Price | $6.6/kg | N/A |

## Project Structure

```
samin_research/
├── config/           # Parameters, scenarios, constants
├── components/       # PV, Wind, FC, ELZ, Biomass models
├── data/fetchers/    # NASA POWER API, load profiles
├── economics/        # Cost & COE calculations
├── optimization/     # MILP epsilon-constraint solver
├── simulation/       # 8760-hour dispatch engine
├── visualization/    # Pareto, dispatch, sensitivity plots
├── tests/            # Unit & validation tests
├── docs/             # Detailed documentation
└── main.py           # CLI entry point
```

## Documentation

| Document | Purpose |
|----------|---------|
| [USER_GUIDE.md](docs/USER_GUIDE.md) | Complete usage instructions |
| [DATA_GUIDE.md](docs/DATA_GUIDE.md) | NASA POWER API & data caching |
| [VALIDATION_GUIDE.md](docs/VALIDATION_GUIDE.md) | Paper results verification |
| [MILP_ALGORITHM.md](docs/MILP_ALGORITHM.md) | Algorithm explanation |
| [PRESENTATION_GUIDE.md](docs/PRESENTATION_GUIDE.md) | Supervisor presentation tips |
| [IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) | Full technical specification |

## Common Commands

```bash
# Test with synthetic data (fast)
uv run python main.py --validate

# Fetch real NASA POWER data and cache
uv run python -c "from data.fetchers.nasa_power import NASAPowerClient; c = NASAPowerClient(); c.fetch_year(2023)"

# Run 8 scenarios (Table 6)
uv run python main.py --scenarios

# Generate Pareto front (Figure 9)
uv run python main.py --optimize --pareto

# Generate dispatch plots (Figures 11-13)
uv run python main.py --figures
```

## License

Research/Educational use only.

## Citation

```bibtex
@article{mulumba2025techno,
  title={Techno-economic analysis of a hydrogen-based hybrid renewable energy system for off-grid power supply in Kenya's urban area},
  author={Mulumba, ... and Farzaneh, H.},
  journal={International Journal of Hydrogen Energy},
  volume={178},
  pages={151474},
  year={2025}
}
```
