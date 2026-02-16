# Data Guide: NASA POWER API & Data Management

Complete guide to fetching, caching, and using meteorological data for H2-HRES simulations.

---

## Table of Contents

1. [Data Requirements](#1-data-requirements)
2. [NASA POWER API](#2-nasa-power-api)
3. [Fetching Real Data](#3-fetching-real-data)
4. [Caching System](#4-caching-system)
5. [Data Validation](#5-data-validation)
6. [Load Profile Data](#6-load-profile-data)
7. [Biomass Data](#7-biomass-data)

---

## 1. Data Requirements

### 1.1 Meteorological Data (from NASA POWER)

| Parameter | API Name | Unit | Paper Value |
|-----------|----------|------|-------------|
| Solar Irradiance | ALLSKY_SFC_SW_DWN | W/m^2 | Peak: 1290, Avg: 479 |
| Temperature | T2M | C | 15-35 range |
| Wind Speed (10m) | WS10M | m/s | - |
| Wind Speed (50m) | WS50M | m/s | Peak: 11.3, Avg: 3.69 |
| Precipitation | PRECTOTCORR | mm/hour | Varies by season |
| Relative Humidity | RH2M | % | 30-100% |

### 1.2 Location

**Embakasi Pipeline Estate, Nairobi, Kenya**
- Latitude: -1.3206 (1 19'14.33"S)
- Longitude: 36.8939 (36 53'38.1"E)

### 1.3 Time Resolution

- **Hourly data** for 1 full year (8760 hours)
- Recommended years: 2022, 2023

---

## 2. NASA POWER API

### 2.1 API Endpoint

```
https://power.larc.nasa.gov/api/temporal/hourly/point
```

### 2.2 Parameters

```
parameters: ALLSKY_SFC_SW_DWN,T2M,WS10M,WS50M,PRECTOTCORR,RH2M
community: RE (Renewable Energy)
longitude: 36.8939
latitude: -1.3206
start: 20230101
end: 20231231
format: JSON
```

### 2.3 API Limits

- **Rate limit:** ~30 requests per minute
- **Data range:** 1984-present (hourly data from 2001)
- **Max request:** 1 year of hourly data per request

### 2.4 Manual API Test

Test the API directly in browser:
```
https://power.larc.nasa.gov/api/temporal/hourly/point?parameters=ALLSKY_SFC_SW_DWN,T2M,WS10M,WS50M,PRECTOTCORR,RH2M&community=RE&longitude=36.8939&latitude=-1.3206&start=20230101&end=20231231&format=JSON
```

---

## 3. Fetching Real Data

### 3.1 Using NASAPowerClient

```python
from data.fetchers.nasa_power import NASAPowerClient

# Initialize client (uses paper location by default)
client = NASAPowerClient()

# Fetch 2023 data (takes ~30-60 seconds)
print("Fetching NASA POWER data for 2023...")
df = client.fetch_year(2023, use_cache=True)

# Check data
print(f"Data shape: {df.shape}")
print(f"Columns: {df.columns.tolist()}")
print(f"Date range: {df.index.min()} to {df.index.max()}")
print(df.head())
```

### 3.2 Expected Output

```
Fetching NASA POWER data for 2023...
Data shape: (8760, 6)
Columns: ['irradiance', 'temperature', 'wind_speed_10m', 'wind_speed_50m', 'precipitation', 'relative_humidity']
Date range: 2023-01-01 00:00:00 to 2023-12-31 23:00:00

                      irradiance  temperature  wind_speed_10m  wind_speed_50m  precipitation  relative_humidity
2023-01-01 00:00:00         0.0         22.5            2.1             3.5           0.0               65.0
2023-01-01 01:00:00         0.0         21.8            1.9             3.2           0.0               68.0
...
```

### 3.3 Custom Location

```python
# Fetch data for different location
client = NASAPowerClient(
    latitude=-1.2921,    # Custom latitude
    longitude=36.8219,   # Custom longitude
)
df = client.fetch_year(2023)
```

### 3.4 Multiple Years

```python
# Fetch multiple years
years_data = {}
for year in [2021, 2022, 2023]:
    print(f"Fetching {year}...")
    years_data[year] = client.fetch_year(year, use_cache=True)

# Concatenate for multi-year analysis
import pandas as pd
all_data = pd.concat(years_data.values())
print(f"Total hours: {len(all_data)}")
```

### 3.5 Handling API Failures

The client automatically falls back to synthetic data if API fails:

```python
# If API fails, synthetic data is generated
df = client.fetch_year(2023, use_cache=True, show_progress=True)

# Check if data is real or synthetic
stats = client.get_statistics(df)
print(f"Irradiance max: {stats['irradiance']['max']:.1f} W/m^2")
print(f"Wind max: {stats['wind_speed_50m']['max']:.1f} m/s")

# Paper values: Irradiance ~1290, Wind ~11.3
# If close to these values, data is working correctly
```

---

## 4. Caching System

### 4.1 Cache Location

Data is cached in `data/cache/`:
```
data/
  cache/
    nasa_power_<hash>.parquet    # One file per year/location
```

### 4.2 Cache File Naming

Files are named using MD5 hash of `latitude_longitude_year`:
```python
# Example: -1.3206_36.8939_2023 -> hash
cache_file = "nasa_power_a1b2c3d4e5f6.parquet"
```

### 4.3 Forcing Fresh Fetch

```python
# Skip cache and fetch fresh data
df = client.fetch_year(2023, use_cache=False)
```

### 4.4 Clear Cache

```bash
# Remove all cached data
rm -rf data/cache/*.parquet
```

Or programmatically:
```python
import os
from pathlib import Path

cache_dir = Path("data/cache")
for f in cache_dir.glob("*.parquet"):
    f.unlink()
    print(f"Deleted: {f.name}")
```

### 4.5 Pre-populate Cache

```python
# Pre-fetch data for common years
from data.fetchers.nasa_power import NASAPowerClient

client = NASAPowerClient()
for year in [2020, 2021, 2022, 2023]:
    print(f"Caching {year}...")
    client.fetch_year(year, use_cache=True)

print("Cache populated!")
```

---

## 5. Data Validation

### 5.1 Validate Against Paper Values

```python
from data.fetchers.nasa_power import NASAPowerClient

client = NASAPowerClient()
df = client.fetch_year(2023)

# Get statistics
stats = client.get_statistics(df)

# Paper reference values (Section 3.1)
paper_values = {
    "irradiance": {"peak": 1290, "avg": 479},
    "wind_speed_50m": {"peak": 11.3, "avg": 3.69},
}

# Compare
print("Irradiance Validation:")
print(f"  Peak: {stats['irradiance']['max']:.1f} W/m^2 (Paper: 1290)")
print(f"  Avg:  {stats['irradiance']['mean']:.1f} W/m^2 (Paper: 479)")

print("\nWind Speed (50m) Validation:")
print(f"  Peak: {stats['wind_speed_50m']['max']:.1f} m/s (Paper: 11.3)")
print(f"  Avg:  {stats['wind_speed_50m']['mean']:.2f} m/s (Paper: 3.69)")
```

### 5.2 Built-in Validation

```python
# Use built-in validation
is_valid = client.validate_data(df)

if is_valid:
    print("Data matches expected paper values")
else:
    print("Warning: Data may differ from paper values")
    # This is expected if using different year or location
```

### 5.3 Data Quality Checks

```python
import numpy as np

# Check for missing values
print(f"Missing values: {df.isnull().sum().sum()}")

# Check for negative irradiance (invalid)
neg_irr = (df['irradiance'] < 0).sum()
print(f"Negative irradiance hours: {neg_irr}")

# Check for nighttime irradiance (should be 0)
night_hours = df[df['irradiance'] == 0]
print(f"Nighttime hours: {len(night_hours)} (expected ~4380)")

# Check wind speed range
print(f"Wind speed range: {df['wind_speed_50m'].min():.2f} - {df['wind_speed_50m'].max():.2f} m/s")
```

---

## 6. Load Profile Data

### 6.1 Generate Load Profile

```python
from data.fetchers.load_profile import LoadProfileGenerator

generator = LoadProfileGenerator()
load_df = generator.generate_annual_profile(year=2023)

print(f"Annual demand: {load_df['load_kw'].sum():.0f} kWh")
print(f"Peak demand: {load_df['load_kw'].max():.1f} kW")
print(f"Average demand: {load_df['load_kw'].mean():.1f} kW")
```

### 6.2 Paper Values

| Metric | Value |
|--------|-------|
| Annual demand | 127,800 kWh |
| Households | 70 |
| Peak hours | 8-11 AM, 8-10 PM |

### 6.3 Validate Load Profile

```python
is_valid, validation = generator.validate_profile(load_df)

print(f"Annual demand: {validation['annual_demand_kwh']:.0f} kWh")
print(f"Expected: {validation['expected_annual_kwh']:.0f} kWh")
print(f"Error: {validation['annual_error_pct']:.2f}%")
print(f"Valid: {is_valid}")
```

---

## 7. Biomass Data

### 7.1 Feedstock Availability

```python
from data.fetchers.biomass_data import BiomassDataProvider

provider = BiomassDataProvider()
feedstock = provider.calculate_feedstock_availability()

print(f"Grass available: {feedstock.grass_available_ton_year:,.0f} ton/year")
print(f"Wood available: {feedstock.wood_available_ton_year:,.0f} ton/year")
print(f"Mix ratio (wood:grass): {feedstock.mix_ratio_wood:.3f}:{feedstock.mix_ratio_grass:.3f}")
```

### 7.2 LHV by Season

```python
# Get monthly LHV values
monthly_lhv = provider.get_monthly_lhv(2023)
print(monthly_lhv)

# Get hourly LHV for simulation
hourly_lhv = provider.get_hourly_lhv(2023)
print(f"LHV range: {hourly_lhv.min():.1f} - {hourly_lhv.max():.1f} MJ/kg")
```

### 7.3 Paper Reference Values (Table 3-4)

| Feedstock | Availability (ton/year) |
|-----------|------------------------|
| Dry grass pellets | 19,315,584 |
| Wood pellets | 1,622,350 |
| **Mix ratio** | **1:10 (wood:grass)** |

| Season | LHV (MJ/kg) |
|--------|-------------|
| Dry (0-12mm precip) | 17.5 |
| Wet (~120mm precip) | 14.3 |

---

## Quick Data Commands

```bash
# Fetch and cache 2023 data
uv run python -c "
from data.fetchers.nasa_power import NASAPowerClient
c = NASAPowerClient()
df = c.fetch_year(2023, use_cache=True)
print(f'Data cached: {len(df)} hours')
s = c.get_statistics(df)
print(f'Irradiance: avg={s[\"irradiance\"][\"mean\"]:.0f}, max={s[\"irradiance\"][\"max\"]:.0f}')
print(f'Wind: avg={s[\"wind_speed_50m\"][\"mean\"]:.2f}, max={s[\"wind_speed_50m\"][\"max\"]:.1f}')
"

# Check cache contents
ls -la data/cache/

# Generate load profile
uv run python -c "
from data.fetchers.load_profile import LoadProfileGenerator
g = LoadProfileGenerator()
df = g.generate_annual_profile(2023)
print(f'Annual demand: {df[\"load_kw\"].sum():.0f} kWh (Paper: 127,800)')
"
```

---

## Using Cached Data in Simulations

```python
from simulation.hourly_simulation import HourlySimulator, SimulationConfig
from data.fetchers.nasa_power import NASAPowerClient
from data.fetchers.load_profile import LoadProfileGenerator

# Step 1: Get meteorological data (from cache if available)
met_client = NASAPowerClient()
met_data = met_client.fetch_year(2023, use_cache=True)

# Step 2: Generate load profile
load_gen = LoadProfileGenerator()
demand_data = load_gen.generate_annual_profile(2023)

# Step 3: Run simulation with real data
from config.parameters import DEFAULT_PARAMS
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

result = simulator.run_simulation(config, met_data, demand_data)
print(f"Reliability: {result.metrics['reliability']:.3f}")
print(f"COE: ${result.metrics['coe']:.3f}/kWh")
```

---

## Next Steps

- [VALIDATION_GUIDE.md](VALIDATION_GUIDE.md) - Validate results against paper
- [USER_GUIDE.md](USER_GUIDE.md) - Full usage instructions
