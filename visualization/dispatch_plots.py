"""Dispatch visualization plots.

Reference: Figures 11-13
- Figure 11: Demand-supply for different scenarios
- Figure 12: H2 production/consumption
- Figure 13: Biomass power/feed-rate
"""

from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from simulation.hourly_simulation import SimulationResult
from simulation.scenario_runner import ScenarioResult, AllScenariosResult
from config.scenarios import Scenarios


class DispatchPlotter:
    """Plotter for dispatch visualization (Figures 11-13)."""

    def __init__(
        self,
        output_dir: Optional[Path] = None,
    ):
        """Initialize plotter.

        Args:
            output_dir: Directory for saving figures
        """
        self.output_dir = output_dir or Path("results/figures")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def plot_hourly_dispatch(
        self,
        result: SimulationResult,
        hours: Optional[range] = None,
        title: str = "Hourly Power Dispatch",
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        """Plot hourly power dispatch.

        Args:
            result: Simulation result
            hours: Range of hours to plot (default: first week)
            title: Plot title
            save_path: Path to save figure

        Returns:
            Matplotlib figure
        """
        if hours is None:
            hours = range(0, 168)  # First week

        fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

        x = list(hours)

        # Panel 1: Generation sources
        ax1 = axes[0]
        ax1.stackplot(
            x,
            result.pv_power[hours],
            result.wind_power[hours],
            result.fc_power[hours],
            result.bm_power[hours],
            labels=["PV", "Wind", "Fuel Cell", "Biomass"],
            colors=["gold", "lightblue", "coral", "lightgreen"],
            alpha=0.8,
        )
        ax1.set_ylabel("Power (kW)")
        ax1.set_title("Power Generation by Source")
        ax1.legend(loc="upper right")
        ax1.grid(True, alpha=0.3)

        # Panel 2: Demand vs Supply
        ax2 = axes[1]
        total_supply = (
            result.pv_power[hours]
            + result.wind_power[hours]
            + result.fc_power[hours]
            + result.bm_power[hours]
        )
        demand = total_supply + result.unmet_power[hours] - result.elz_power[hours]

        ax2.plot(x, demand, "k-", linewidth=1.5, label="Demand + ELZ")
        ax2.plot(x, total_supply, "b--", linewidth=1.5, label="Supply")
        ax2.fill_between(
            x,
            0,
            result.unmet_power[hours],
            color="red",
            alpha=0.5,
            label="Unmet",
        )
        ax2.set_ylabel("Power (kW)")
        ax2.set_title("Demand vs Supply")
        ax2.legend(loc="upper right")
        ax2.grid(True, alpha=0.3)

        # Panel 3: Electrolyzer consumption
        ax3 = axes[2]
        ax3.fill_between(
            x,
            0,
            result.elz_power[hours],
            color="plum",
            alpha=0.7,
            label="Electrolyzer",
        )
        ax3.set_xlabel("Hour")
        ax3.set_ylabel("Power (kW)")
        ax3.set_title("Electrolyzer Consumption")
        ax3.legend(loc="upper right")
        ax3.grid(True, alpha=0.3)

        plt.suptitle(title, fontsize=14)
        plt.tight_layout()

        if save_path:
            fig.savefig(self.output_dir / save_path, dpi=300, bbox_inches="tight")

        return fig

    def plot_h2_dynamics(
        self,
        result: SimulationResult,
        hours: Optional[range] = None,
        title: str = "Hydrogen Dynamics",
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        """Plot H2 production, consumption, and storage (Figure 12).

        Args:
            result: Simulation result
            hours: Range of hours to plot
            title: Plot title
            save_path: Path to save figure

        Returns:
            Matplotlib figure
        """
        if hours is None:
            hours = range(0, 168)

        fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

        x = list(hours)

        # Panel 1: H2 Production vs Consumption
        ax1 = axes[0]
        ax1.bar(
            x,
            result.h2_produced[hours],
            color="green",
            alpha=0.7,
            label="H2 Produced",
        )
        ax1.bar(
            x,
            -result.h2_consumed[hours],
            color="red",
            alpha=0.7,
            label="H2 Consumed",
        )
        ax1.axhline(y=0, color="black", linewidth=0.5)
        ax1.set_ylabel("H2 (kg/h)")
        ax1.set_title("H2 Production and Consumption")
        ax1.legend(loc="upper right")
        ax1.grid(True, alpha=0.3)

        # Panel 2: H2 Sales
        ax2 = axes[1]
        ax2.bar(
            x,
            result.h2_sold[hours],
            color="purple",
            alpha=0.7,
            label="H2 Sold",
        )
        ax2.set_ylabel("H2 (kg/h)")
        ax2.set_title("H2 Market Sales")
        ax2.legend(loc="upper right")
        ax2.grid(True, alpha=0.3)

        # Panel 3: H2 Storage Level
        ax3 = axes[2]
        ax3.fill_between(
            x,
            0,
            result.h2_level[hours],
            color="blue",
            alpha=0.5,
        )
        ax3.plot(x, result.h2_level[hours], "b-", linewidth=1.5, label="H2 Level")
        ax3.axhline(
            y=result.config.h2_storage_capacity_kg * 0.1,
            color="red",
            linestyle="--",
            label="Min SOC",
        )
        ax3.axhline(
            y=result.config.h2_storage_capacity_kg * 0.95,
            color="orange",
            linestyle="--",
            label="Max SOC",
        )
        ax3.set_xlabel("Hour")
        ax3.set_ylabel("H2 Storage (kg)")
        ax3.set_title("H2 Storage Level")
        ax3.legend(loc="upper right")
        ax3.grid(True, alpha=0.3)

        plt.suptitle(title, fontsize=14)
        plt.tight_layout()

        if save_path:
            fig.savefig(self.output_dir / save_path, dpi=300, bbox_inches="tight")

        return fig

    def plot_biomass_operation(
        self,
        result: SimulationResult,
        hours: Optional[range] = None,
        title: str = "Biomass Generator Operation",
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        """Plot biomass power and feedstock consumption (Figure 13).

        Args:
            result: Simulation result
            hours: Range of hours to plot
            title: Plot title
            save_path: Path to save figure

        Returns:
            Matplotlib figure
        """
        if hours is None:
            hours = range(0, 168)

        fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

        x = list(hours)

        # Calculate feedstock rate from power (approximate)
        feedstock_rate = result.bm_power[hours] * 0.5  # Simplified: 0.5 kg/kWh

        # Panel 1: Biomass Power Output
        ax1 = axes[0]
        ax1.fill_between(
            x,
            0,
            result.bm_power[hours],
            color="lightgreen",
            alpha=0.7,
        )
        ax1.plot(x, result.bm_power[hours], "g-", linewidth=1.5, label="Power Output")
        ax1.axhline(
            y=result.config.biomass_capacity_kw,
            color="red",
            linestyle="--",
            label="Rated Capacity",
        )
        ax1.axhline(
            y=result.config.biomass_capacity_kw * 0.3,
            color="orange",
            linestyle="--",
            label="Min Load",
        )
        ax1.set_ylabel("Power (kW)")
        ax1.set_title("Biomass Power Output")
        ax1.legend(loc="upper right")
        ax1.grid(True, alpha=0.3)

        # Panel 2: Feedstock Consumption
        ax2 = axes[1]
        ax2.bar(
            x,
            feedstock_rate,
            color="brown",
            alpha=0.7,
            label="Feedstock Rate",
        )
        ax2.set_xlabel("Hour")
        ax2.set_ylabel("Feedstock (kg/h)")
        ax2.set_title("Feedstock Consumption Rate")
        ax2.legend(loc="upper right")
        ax2.grid(True, alpha=0.3)

        plt.suptitle(title, fontsize=14)
        plt.tight_layout()

        if save_path:
            fig.savefig(self.output_dir / save_path, dpi=300, bbox_inches="tight")

        return fig

    def plot_scenario_comparison(
        self,
        results: AllScenariosResult,
        title: str = "Scenario Comparison",
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        """Plot comparison across all 8 scenarios (Figure 11).

        Args:
            results: All scenarios result
            title: Plot title
            save_path: Path to save figure

        Returns:
            Matplotlib figure
        """
        fig, axes = plt.subplots(2, 4, figsize=(16, 8))
        axes = axes.flatten()

        for i, scenario in enumerate(Scenarios.all()):
            ax = axes[i]
            result = results.scenarios[scenario.name]
            sim = result.simulation

            # Get representative day (first 24 hours of the scenario month)
            hours = range(24)

            supply = (
                sim.pv_power[hours]
                + sim.wind_power[hours]
                + sim.fc_power[hours]
                + sim.bm_power[hours]
            )
            demand = supply + sim.unmet_power[hours] - sim.elz_power[hours]

            ax.stackplot(
                hours,
                sim.pv_power[hours],
                sim.wind_power[hours],
                sim.fc_power[hours],
                sim.bm_power[hours],
                colors=["gold", "lightblue", "coral", "lightgreen"],
                alpha=0.8,
            )
            ax.plot(hours, demand, "k--", linewidth=1.5, label="Demand")
            ax.set_title(
                f"{scenario.name}: {scenario.month}\n"
                f"LHV={scenario.lhv_value}, {scenario.climate.value}",
                fontsize=10,
            )
            ax.set_xlabel("Hour")
            ax.set_ylabel("kW")
            ax.grid(True, alpha=0.3)

        # Add legend to last subplot
        axes[-1].legend(
            ["PV", "Wind", "FC", "Biomass", "Demand"],
            loc="upper right",
            fontsize=8,
        )

        plt.suptitle(title, fontsize=14)
        plt.tight_layout()

        if save_path:
            fig.savefig(self.output_dir / save_path, dpi=300, bbox_inches="tight")

        return fig

    def plot_annual_energy_breakdown(
        self,
        result: SimulationResult,
        title: str = "Annual Energy Breakdown",
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        """Plot annual energy breakdown by source.

        Args:
            result: Simulation result
            title: Plot title
            save_path: Path to save figure

        Returns:
            Matplotlib figure
        """
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        # Energy by source
        energy_sources = {
            "PV": np.sum(result.pv_power),
            "Wind": np.sum(result.wind_power),
            "Fuel Cell": np.sum(result.fc_power),
            "Biomass": np.sum(result.bm_power),
        }

        labels = list(energy_sources.keys())
        values = list(energy_sources.values())
        colors = ["gold", "lightblue", "coral", "lightgreen"]

        axes[0].pie(
            values,
            labels=[f"{l}\n{v/1000:.1f} MWh" for l, v in zip(labels, values)],
            colors=colors,
            autopct="%1.1f%%",
            startangle=90,
        )
        axes[0].set_title("Generation by Source")

        # Monthly breakdown
        months = range(1, 13)
        monthly_totals = {m: 0 for m in months}
        dates = pd.date_range(
            start=f"{result.config.year}-01-01", periods=8760, freq="h"
        )

        total_supply = (
            result.pv_power + result.wind_power + result.fc_power + result.bm_power
        )

        for m in months:
            mask = dates.month == m
            monthly_totals[m] = np.sum(total_supply[mask])

        axes[1].bar(
            list(monthly_totals.keys()),
            [v / 1000 for v in monthly_totals.values()],
            color="steelblue",
            alpha=0.8,
        )
        axes[1].set_xlabel("Month")
        axes[1].set_ylabel("Energy (MWh)")
        axes[1].set_title("Monthly Generation")
        axes[1].set_xticks(list(months))
        axes[1].grid(True, alpha=0.3, axis="y")

        plt.suptitle(title, fontsize=14)
        plt.tight_layout()

        if save_path:
            fig.savefig(self.output_dir / save_path, dpi=300, bbox_inches="tight")

        return fig

    def create_figure_11(
        self,
        results: AllScenariosResult,
        save_path: str = "figure_11_scenarios.png",
    ) -> plt.Figure:
        """Reproduce Figure 11 from the paper.

        Shows demand-supply for all 8 scenarios.

        Args:
            results: All scenarios result
            save_path: Path to save figure

        Returns:
            Matplotlib figure
        """
        return self.plot_scenario_comparison(
            results,
            title="Figure 11: Demand-Supply Scenarios",
            save_path=save_path,
        )
