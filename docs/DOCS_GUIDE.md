# Documentation Guide: H2-HRES Codebase

Welcome! This guide helps you navigate the documentation in the correct order based on your needs.

---

## Quick Start: Choose Your Path

### Path A: "I want to run the code"
1. **USER_GUIDE.md** - Installation and basic usage
2. **DATA_GUIDE.md** - Data sources and fetching
3. **VALIDATION_GUIDE.md** - Verify results

### Path B: "I want to understand the algorithm"
1. **MILP_ALGORITHM.md** - Algorithm explanation for beginners
2. **IMPLEMENTATION_PLAN.md** - Original design document
3. **IMPLEMENTATION_AUDIT.md** - Paper compliance details

### Path C: "I want to present this to my supervisor"
1. **PRESENTATION_GUIDE.md** - Tips and talking points
2. **USER_GUIDE.md** - Demo commands
3. **VALIDATION_GUIDE.md** - Results to show

### Path D: "I want to understand all modifications"
1. **IMPLEMENTATION_AUDIT.md** - Full paper compliance audit
2. **OPTIMIZER_FIX_LOG.md** - MILP bug fixes explained
3. **SESSION_LOG.md** - Development history

---

## Complete Reading Order (Recommended)

| Order | Document | Purpose | Time |
|-------|----------|---------|------|
| 1 | **DOCS_GUIDE.md** | This file - start here | 2 min |
| 2 | **USER_GUIDE.md** | How to install and run | 10 min |
| 3 | **MILP_ALGORITHM.md** | Core algorithm explained simply | 15 min |
| 4 | **DATA_GUIDE.md** | NASA API and data handling | 8 min |
| 5 | **IMPLEMENTATION_PLAN.md** | Original design & equations | 20 min |
| 6 | **VALIDATION_GUIDE.md** | How to verify paper results | 10 min |
| 7 | **IMPLEMENTATION_AUDIT.md** | Paper compliance check | 15 min |
| 8 | **OPTIMIZER_FIX_LOG.md** | Bug fixes applied | 10 min |
| 9 | **SESSION_LOG.md** | Development history | 5 min |
| 10 | **PRESENTATION_GUIDE.md** | For supervisor meetings | 15 min |

**Total reading time: ~110 minutes**

---

## Document Summaries

### Core Documentation

#### USER_GUIDE.md
- Installation with `uv`
- Running simulations
- Command-line options
- Quick start examples

#### MILP_ALGORITHM.md
- Epsilon-constraint method explained
- Multi-objective optimization basics
- How COE and reliability trade off
- No math background required

#### IMPLEMENTATION_PLAN.md
- Original 32-file design
- All 32 equations from paper
- Table and figure mappings
- Validation criteria

### Data & Validation

#### DATA_GUIDE.md
- NASA POWER API usage
- Location coordinates (Nairobi)
- Data caching strategy
- Synthetic data generation

#### VALIDATION_GUIDE.md
- Expected paper results (Table 5)
- How to verify COE and reliability
- Troubleshooting discrepancies
- Validation commands

### Technical Details

#### IMPLEMENTATION_AUDIT.md
- Paper compliance summary (95%)
- 7 modifications documented
- File-by-file status
- Backpropagation instructions

#### OPTIMIZER_FIX_LOG.md
- MILP bug analysis
- Why COE was negative
- Each fix explained
- Before/after comparison

#### SESSION_LOG.md
- Commands run during development
- Test results
- Figures generated
- Known differences from paper

### Presentation

#### PRESENTATION_GUIDE.md
- Slide outline (15-20 slides)
- Key talking points
- Demo walkthrough
- Anticipated questions & answers

---

## Key Commands Reference

```bash
# Install dependencies
uv sync

# Run validation (quick check)
uv run python main.py --validate

# Run all 8 scenarios
uv run python main.py --scenarios

# Generate figures
uv run python main.py --figures

# Run MILP optimization (slow)
uv run python main.py --optimize --pareto-points 5
```

---

## Key Results to Know

| Metric | Paper Value | Implementation |
|--------|-------------|----------------|
| COE (with H2) | $0.494/kWh | $0.287/kWh* |
| Reliability | 96.1% | 95.9% |
| PV Capacity | 41.8 kW | Optimal varies |
| Wind Capacity | 30.1 kW | Optimal varies |

*COE differs due to different meteorological data source (NASA 2023 vs paper)

---

## Glossary

| Term | Meaning |
|------|---------|
| COE | Cost of Energy ($/kWh) |
| UME | Unmet Energy (reliability metric) |
| MILP | Mixed-Integer Linear Programming |
| H2 | Hydrogen |
| FC | Fuel Cell |
| ELZ | Electrolyzer |
| BM | Biomass Generator |
| PV | Photovoltaic (Solar) |
| WT | Wind Turbine |

---

## Need Help?

1. Check **USER_GUIDE.md** for basic issues
2. Check **VALIDATION_GUIDE.md** for result discrepancies
3. Check **OPTIMIZER_FIX_LOG.md** for MILP problems
4. Review **IMPLEMENTATION_AUDIT.md** for paper compliance questions
