"""Dispatch scheduler implementing the operational logic.

Reference: Section 2.5.2.1, Equations 8-10, Figure 4

Dispatch modes (Eq 9):
- Mode 0 (ℶ_0): P^HRES = PV + WT (excess to electrolyzer)
- Mode A (ℶ_a): P^HRES = PV + WT + FC (fuel cell backup)
- Mode B (ℶ_b): P^HRES = PV + WT + BM (biomass backup)
- Mode C (ℶ_c): P^HRES = PV + WT + BM + FC (both backups)

Dispatch logic (Figure 4):
IF P_PV + P_WT >= P_D:
    Excess → Electrolyzer → H2 storage/sales
ELSE (deficit):
    IF H2_available > H_min:
        Activate Fuel Cell
    ELIF Biomass_available:
        Activate Biomass
    ELSE:
        Both FC + Biomass
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple 

import numpy as np 

from components import (
    SolarPV,
    WindTurbine,
    Electrolyzer,
    FuelCell, 
    HydrogenStorage,
    BiomassGenerator,
) 


class DispatchMode(Enum):
    """Dispatch modes from Equation 9."""

    MODE_0 = auto()  # Renewables only
    MODE_A = auto()  # Renewables + Fuel Cell
    MODE_B = auto()  # Renewables + Biomass
    MODE_C = auto()  # Renewables + FC + Biomass


@dataclass
class HourlyDispatch:
    """Dispatch result for a single hour."""

    mode: DispatchMode
    p_pv: float  # kW
    p_wind: float  # kW
    p_fc: float  # kW
    p_bm: float  # kW
    p_elz: float  # kW (consumption)
    p_ume: float  # kW (unmet)
    h2_produced: float  # kg
    h2_consumed: float  # kg
    h2_sold: float  # kg
    h2_level: float  # kg
    feedstock_used: float  # kg


@dataclass
class DispatchResult:
    """Complete dispatch result over simulation period."""

    hourly: List[HourlyDispatch]
    mode_counts: Dict[DispatchMode, int]
    total_energy_served: float
    total_unmet_energy: float
    total_h2_produced: float
    total_h2_consumed: float
    total_h2_sold: float
    total_feedstock_used: float


class DispatchScheduler:
    """Scheduler implementing dispatch logic from Figure 4."""

    def __init__(
        self,
        pv: SolarPV,
        wind: WindTurbine,
        electrolyzer: Electrolyzer,
        fuel_cell: FuelCell,
        h2_storage: HydrogenStorage,
        biomass: BiomassGenerator,
    ):
        """Initialize dispatch scheduler.

        Args:
            All component instances
        """
        self.pv = pv
        self.wind = wind
        self.electrolyzer = electrolyzer
        self.fuel_cell = fuel_cell
        self.h2_storage = h2_storage
        self.biomass = biomass

    def determine_mode(
        self,
        renewable_power: float,
        demand: float,
        h2_available: float,
        feedstock_available: float,
    ) -> DispatchMode:
        """Determine dispatch mode based on Figure 4 logic.

        Args:
            renewable_power: Available PV + Wind power (kW)
            demand: Load demand (kW)
            h2_available: H2 available above minimum SOC (kg)
            feedstock_available: Biomass feedstock available (kg)

        Returns:
            DispatchMode for this hour
        """
        if renewable_power >= demand:
            # Surplus - use Mode 0, excess to electrolyzer
            return DispatchMode.MODE_0

        # Deficit - need backup
        deficit = demand - renewable_power

        # Check H2 availability for fuel cell
        h2_min_threshold = 0.5  # Minimum H2 to consider FC (kg)
        fc_can_help = h2_available > h2_min_threshold

        # Check biomass availability
        bm_can_help = feedstock_available > 0 and self.biomass.capacity > 0

        if fc_can_help and not bm_can_help:
            return DispatchMode.MODE_A
        elif bm_can_help and not fc_can_help:
            return DispatchMode.MODE_B
        elif fc_can_help and bm_can_help:
            # Both available - check which is more appropriate
            # Prioritize FC if deficit is small, BM if large
            if deficit <= self.fuel_cell.capacity * 0.7:
                return DispatchMode.MODE_A
            elif deficit <= self.biomass.capacity * 0.7:
                return DispatchMode.MODE_B
            else:
                return DispatchMode.MODE_C
        else:
            # Neither available - will have unmet demand
            return DispatchMode.MODE_0

    def dispatch_hour(
        self,
        demand: float,
        irradiance: float,
        temperature: float,
        wind_speed: float,
        lhv_mj_kg: float,
        feedstock_available: float = float("inf"),
    ) -> HourlyDispatch:
        """Dispatch power for a single hour.

        Strategy: 
        1. Biomass runs as Baseload (Max Capacity) to maximize reliable power and H2 production.
        2. Renewables add to supply.
        3. If Surplus -> Electrolyzer (H2).
        4. If Deficit -> Fuel Cell (Backup).
        """
        # 1. Biomass Baseload Dispatch
        target_bm = self.biomass.capacity
        bm_output = self.biomass.calculate_output(target_bm, lhv_mj_kg, feedstock_available)
        p_bm = float(np.atleast_1d(bm_output.power_kw)[0])
        feedstock_used = float(
            np.atleast_1d(bm_output.details["feed_rate_kg_h"])[0]
        )

        # 2. Renewable Generation
        pv_output = self.pv.calculate_output(irradiance, temperature)
        p_pv = float(np.atleast_1d(pv_output.power_kw)[0])

        wind_output = self.wind.calculate_output(wind_speed)
        p_wind = float(np.atleast_1d(wind_output.power_kw)[0])

        renewable_power = p_pv + p_wind

        # available H2
        h2_available = self.h2_storage.available_to_discharge

        # 3. Net Load Calculation
        total_gen = p_bm + renewable_power
        
        p_fc = 0.0
        p_elz = 0.0
        p_ume = 0.0
        h2_produced = 0.0
        h2_consumed = 0.0
        h2_sold = 0.0
        
        mode = DispatchMode.MODE_B # Default to Biomass active

        if total_gen >= demand:
            # Surplus case
            mode = DispatchMode.MODE_0 # Effectively Surplus Mode
            excess = total_gen - demand
            
            if excess > 0:
                elz_power = min(excess, self.electrolyzer.capacity)
                # Check min load
                if elz_power >= self.electrolyzer.capacity * self.electrolyzer.params.min_load_fraction:
                    p_elz = elz_power
                    elz_output = self.electrolyzer.calculate_output(p_elz)
                    h2_produced = float(
                        np.atleast_1d(elz_output.details["h2_production_kg_h"])[0]
                    )
                    
                    _, storable_amount = self.h2_storage.can_charge(h2_produced)
                    h2_sold = h2_produced - storable_amount
        
        else:
            # Deficit case - Need Fuel Cell
            mode = DispatchMode.MODE_C # Biomass + FC (since BM is already running)
            deficit = demand - total_gen
            
            # Use FC
            target_fc = min(deficit, self.fuel_cell.capacity)
            fc_output = self.fuel_cell.calculate_output(target_fc, h2_available)
            p_fc = float(np.atleast_1d(fc_output.power_kw)[0])
            h2_consumed = float(
                np.atleast_1d(fc_output.details["h2_consumption_kg_h"])[0]
            )
            
            remaining = deficit - p_fc
            if remaining > 0:
                p_ume = remaining

        # Update H2 storage
        storage_result = self.h2_storage.simulate_hour(
            h2_from_elz=h2_produced,
            h2_to_fc=h2_consumed,
            h2_to_market=h2_sold,
        )
        h2_level = self.h2_storage.h2_stored_kg

        return HourlyDispatch(
            mode=mode,
            p_pv=p_pv,
            p_wind=p_wind,
            p_fc=p_fc,
            p_bm=p_bm,
            p_elz=p_elz,
            p_ume=p_ume,
            h2_produced=h2_produced,
            h2_consumed=h2_consumed,
            h2_sold=storage_result["h2_to_market_kg"],
            h2_level=h2_level,
            feedstock_used=feedstock_used,
        )

    def simulate_year(
        self,
        demand_profile: np.ndarray,
        irradiance_profile: np.ndarray,
        temperature_profile: np.ndarray,
        wind_speed_profile: np.ndarray,
        lhv_profile: np.ndarray,
        annual_feedstock_kg: float = float("inf"),
    ) -> DispatchResult:
        """Simulate dispatch for a full year.

        Args:
            demand_profile: Hourly demand (8760 values, kW)
            irradiance_profile: Hourly irradiance (W/m²)
            temperature_profile: Hourly temperature (°C)
            wind_speed_profile: Hourly wind speed (m/s)
            lhv_profile: Hourly LHV values (MJ/kg)
            annual_feedstock_kg: Total feedstock available for year

        Returns:
            DispatchResult with all hourly results and totals
        """
        # Reset storage to initial state
        self.h2_storage.reset()

        # Track feedstock consumption
        feedstock_remaining = annual_feedstock_kg

        hourly_results = []
        mode_counts = {mode: 0 for mode in DispatchMode}

        for h in range(len(demand_profile)):
            result = self.dispatch_hour(
                demand=demand_profile[h],
                irradiance=irradiance_profile[h],
                temperature=temperature_profile[h],
                wind_speed=wind_speed_profile[h],
                lhv_mj_kg=lhv_profile[h],
                feedstock_available=feedstock_remaining,
            )

            hourly_results.append(result)
            mode_counts[result.mode] += 1
            feedstock_remaining -= result.feedstock_used

        # Calculate totals
        total_energy_served = sum(
            r.p_pv + r.p_wind + r.p_fc + r.p_bm - r.p_elz for r in hourly_results
        )
        total_unmet = sum(r.p_ume for r in hourly_results)
        total_h2_produced = sum(r.h2_produced for r in hourly_results)
        total_h2_consumed = sum(r.h2_consumed for r in hourly_results)
        total_h2_sold = sum(r.h2_sold for r in hourly_results)
        total_feedstock = sum(r.feedstock_used for r in hourly_results)

        return DispatchResult(
            hourly=hourly_results,
            mode_counts=mode_counts,
            total_energy_served=total_energy_served,
            total_unmet_energy=total_unmet,
            total_h2_produced=total_h2_produced,
            total_h2_consumed=total_h2_consumed,
            total_h2_sold=total_h2_sold,
            total_feedstock_used=total_feedstock,
        )

    def get_mode_statistics(
        self,
        result: DispatchResult,
    ) -> Dict[str, float]:
        """Get statistics about dispatch mode usage.

        Args:
            result: DispatchResult from simulation

        Returns:
            Dict with mode usage statistics
        """
        total_hours = len(result.hourly)

        return {
            "mode_0_hours": result.mode_counts[DispatchMode.MODE_0],
            "mode_0_pct": result.mode_counts[DispatchMode.MODE_0] / total_hours * 100,
            "mode_a_hours": result.mode_counts[DispatchMode.MODE_A],
            "mode_a_pct": result.mode_counts[DispatchMode.MODE_A] / total_hours * 100,
            "mode_b_hours": result.mode_counts[DispatchMode.MODE_B],
            "mode_b_pct": result.mode_counts[DispatchMode.MODE_B] / total_hours * 100,
            "mode_c_hours": result.mode_counts[DispatchMode.MODE_C],
            "mode_c_pct": result.mode_counts[DispatchMode.MODE_C] / total_hours * 100,
        }
