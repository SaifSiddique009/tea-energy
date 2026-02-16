"""Load profile generator for the residential community.

Reference: Section 3.1 - Case Study
- Total annual demand: 127.8 MWh (127,800 kWh)
- 70 households in three 7-story buildings
- Peak hours: 8-11 AM (morning), 8-10 PM (evening)
"""

import numpy as np
import pandas as pd
from typing import Optional, Tuple

from config.parameters import LoadParameters


class LoadProfileGenerator:
    """Generator for hourly electrical load profiles."""

    def __init__(self, params: Optional[LoadParameters] = None):
        """Initialize load profile generator.

        Args:
            params: Load parameters (uses defaults if not provided)
        """
        self.params = params or LoadParameters()

    def generate_annual_profile(
        self,
        year: int = 2023,
        seed: Optional[int] = 42,
    ) -> pd.DataFrame:
        """Generate hourly load profile for a full year.

        The profile accounts for:
        - Daily patterns (morning and evening peaks)
        - Weekly patterns (higher weekend usage)
        - Seasonal variations (slight increase in dry/cold season)
        - Random variations for realism

        Args:
            year: Year for the profile
            seed: Random seed for reproducibility

        Returns:
            DataFrame with hourly load in kW (8760 rows)
        """
        if seed is not None:
            np.random.seed(seed)

        # Create hourly timestamps
        dates = pd.date_range(start=f"{year}-01-01", periods=8760, freq="h")

        # Extract time components
        hours = dates.hour
        day_of_week = dates.dayofweek  # 0=Monday, 6=Sunday
        day_of_year = dates.dayofyear
        month = dates.month

        # Calculate base load (average hourly load to achieve annual demand)
        # Annual demand = 127,800 kWh, so average hourly = 127,800 / 8760 = 14.59 kW
        base_load = self.params.annual_demand / 8760

        # Daily load pattern (normalized to 1.0 average)
        daily_pattern = self._get_daily_pattern(hours)

        # Weekly pattern (weekends have ~10% higher usage)
        weekly_pattern = np.where(day_of_week >= 5, 1.10, 1.0)

        # Seasonal pattern (cold/dry months have slightly higher usage)
        # Kenya's cold season: June-August
        seasonal_pattern = self._get_seasonal_pattern(month)

        # Combine patterns
        load = base_load * daily_pattern * weekly_pattern * seasonal_pattern

        # Add random variation (±10%)
        noise = 1 + np.random.uniform(-0.10, 0.10, 8760)
        load = load * noise

        # Ensure load is positive
        load = np.maximum(load, 0.1)

        # Scale to match exact annual demand
        current_total = load.sum()
        load = load * (self.params.annual_demand / current_total)

        # Create DataFrame
        df = pd.DataFrame({"load_kw": load}, index=dates)

        return df

    def _get_daily_pattern(self, hours: np.ndarray) -> np.ndarray:
        """Generate daily load pattern with morning and evening peaks.

        Pattern based on typical residential usage:
        - Low overnight (0-6 AM): 0.5-0.7
        - Morning peak (8-11 AM): 1.3-1.5
        - Midday moderate (12-17): 0.9-1.1
        - Evening peak (20-22): 1.4-1.6
        - Late evening decline (23): 1.0
        """
        pattern = np.ones_like(hours, dtype=float)

        # Overnight low (0-5 AM)
        mask = hours < 6
        pattern[mask] = 0.6

        # Early morning ramp-up (6-7 AM)
        mask = (hours >= 6) & (hours < 8)
        pattern[mask] = 0.9

        # Morning peak (8-11 AM)
        mask = (hours >= self.params.morning_peak_start) & (
            hours <= self.params.morning_peak_end
        )
        pattern[mask] = 1.4

        # Midday (12-17)
        mask = (hours >= 12) & (hours < 18)
        pattern[mask] = 1.0

        # Pre-evening (18-19)
        mask = (hours >= 18) & (hours < 20)
        pattern[mask] = 1.2

        # Evening peak (20-22)
        mask = (hours >= self.params.evening_peak_start) & (
            hours <= self.params.evening_peak_end
        )
        pattern[mask] = 1.5

        # Late evening (23)
        mask = hours == 23
        pattern[mask] = 1.0

        return pattern

    def _get_seasonal_pattern(self, month: np.ndarray) -> np.ndarray:
        """Generate seasonal pattern.

        Kenya has two rainy seasons (March-May, October-December)
        and cold/dry season (June-August) with slightly higher electricity use.
        """
        pattern = np.ones_like(month, dtype=float)

        # Cold/dry season - slightly higher usage (heating, lighting)
        cold_months = [6, 7, 8]
        for m in cold_months:
            pattern[month == m] = 1.05

        # Hot dry season - moderate (January-February)
        hot_dry_months = [1, 2]
        for m in hot_dry_months:
            pattern[month == m] = 1.02

        # Rainy seasons - baseline
        # March-May, October-December already at 1.0

        return pattern

    def get_peak_demand(self, df: pd.DataFrame) -> float:
        """Get peak demand from load profile."""
        return df["load_kw"].max()

    def get_average_demand(self, df: pd.DataFrame) -> float:
        """Get average demand from load profile."""
        return df["load_kw"].mean()

    def get_load_factor(self, df: pd.DataFrame) -> float:
        """Calculate load factor (average/peak)."""
        return self.get_average_demand(df) / self.get_peak_demand(df)

    def get_monthly_summary(self, df: pd.DataFrame) -> pd.DataFrame:
        """Get monthly load summary."""
        monthly = df.resample("ME").agg(
            {
                "load_kw": ["sum", "mean", "max", "min"],
            }
        )
        monthly.columns = ["total_kwh", "avg_kw", "peak_kw", "min_kw"]
        return monthly

    def validate_profile(self, df: pd.DataFrame) -> Tuple[bool, dict]:
        """Validate load profile against expected values.

        Expected:
        - Annual demand: 127,800 kWh
        - Peak to average ratio: ~2.5
        """
        annual_demand = df["load_kw"].sum()
        peak_demand = df["load_kw"].max()
        avg_demand = df["load_kw"].mean()
        peak_to_avg = peak_demand / avg_demand

        validation = {
            "annual_demand_kwh": annual_demand,
            "expected_annual_kwh": self.params.annual_demand,
            "annual_error_pct": abs(annual_demand - self.params.annual_demand)
            / self.params.annual_demand
            * 100,
            "peak_demand_kw": peak_demand,
            "avg_demand_kw": avg_demand,
            "peak_to_avg_ratio": peak_to_avg,
            "expected_peak_to_avg": self.params.peak_to_base_ratio,
            "load_factor": avg_demand / peak_demand,
        }

        # Check if within tolerances
        annual_ok = validation["annual_error_pct"] < 1.0  # Within 1%
        ratio_ok = abs(peak_to_avg - self.params.peak_to_base_ratio) < 0.5

        is_valid = annual_ok and ratio_ok
        validation["is_valid"] = is_valid

        return is_valid, validation
