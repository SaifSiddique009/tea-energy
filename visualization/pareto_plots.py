"""Pareto front visualization.

Reference: Figure 9 - Pareto curves for different H2 market scenarios
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np

from optimization.epsilon_constraint import ParetoResult, OptimizationResult


class ParetoPlotter:
    """Plotter for Pareto front visualization (Figure 9)."""

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        style: str = "seaborn-v0_8-whitegrid",
    ):
        """Initialize plotter.

        Args:
            output_dir: Directory for saving figures
            style: Matplotlib style
        """
        self.output_dir = output_dir or Path("results/figures")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        try:
            plt.style.use(style)
        except OSError:
            plt.style.use("seaborn-whitegrid")

    def plot_pareto_front(
        self,
        result: ParetoResult,
        title: str = "Pareto Front: COE vs Reliability",
        save_path: Optional[str] = None,
        show_knee: bool = True,
    ) -> plt.Figure:
        """Plot Pareto front.

        Args:
            result: ParetoResult from optimization
            title: Plot title
            save_path: Path to save figure
            show_knee: Whether to highlight knee point

        Returns:
            Matplotlib figure
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        # Extract data
        coes = [s.coe for s in result.solutions]
        reliabilities = [s.reliability for s in result.solutions]

        # Plot Pareto front
        ax.plot(coes, reliabilities, "b-o", markersize=6, label="Pareto Front")

        # Highlight knee point
        if show_knee:
            knee = result.knee_point
            ax.scatter(
                [knee.coe],
                [knee.reliability],
                s=150,
                c="red",
                marker="*",
                zorder=5,
                label=f"Knee Point (COE=${knee.coe:.3f}, Rel={knee.reliability:.3f})",
            )

        # Mark anchor points
        ax.scatter(
            [result.f1_anchor.coe],
            [result.f1_anchor.reliability],
            s=100,
            c="green",
            marker="^",
            zorder=5,
            label="Min COE",
        )
        ax.scatter(
            [result.f2_anchor.coe],
            [result.f2_anchor.reliability],
            s=100,
            c="orange",
            marker="v",
            zorder=5,
            label="Max Reliability",
        )

        ax.set_xlabel("Cost of Energy ($/kWh)", fontsize=12)
        ax.set_ylabel("Reliability Index", fontsize=12)
        ax.set_title(title, fontsize=14)
        ax.legend(loc="best")
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            fig.savefig(self.output_dir / save_path, dpi=300, bbox_inches="tight")

        return fig

    def plot_multiple_pareto(
        self,
        results: Dict[str, ParetoResult],
        title: str = "Pareto Fronts Comparison",
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        """Plot multiple Pareto fronts (e.g., different H2 prices).

        Args:
            results: Dict mapping scenario name to ParetoResult
            title: Plot title
            save_path: Path to save figure

        Returns:
            Matplotlib figure
        """
        fig, ax = plt.subplots(figsize=(12, 7))

        colors = ["blue", "red", "green", "orange", "purple"]
        markers = ["o", "s", "^", "v", "D"]

        for i, (name, result) in enumerate(results.items()):
            color = colors[i % len(colors)]
            marker = markers[i % len(markers)]

            coes = [s.coe for s in result.solutions]
            reliabilities = [s.reliability for s in result.solutions]

            ax.plot(
                coes,
                reliabilities,
                f"{color}-{marker}",
                markersize=5,
                label=name,
            )

            # Mark knee point
            knee = result.knee_point
            ax.scatter(
                [knee.coe],
                [knee.reliability],
                s=100,
                c=color,
                marker="*",
                zorder=5,
            )

        ax.set_xlabel("Cost of Energy ($/kWh)", fontsize=12)
        ax.set_ylabel("Reliability Index", fontsize=12)
        ax.set_title(title, fontsize=14)
        ax.legend(loc="best")
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            fig.savefig(self.output_dir / save_path, dpi=300, bbox_inches="tight")

        return fig

    def plot_capacity_pie(
        self,
        result: OptimizationResult,
        title: str = "Optimal System Configuration",
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        """Plot capacity distribution as pie chart (Figure 10).

        Args:
            result: OptimizationResult with optimal capacities
            title: Plot title
            save_path: Path to save figure

        Returns:
            Matplotlib figure
        """
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        # Power capacities
        power_caps = {
            "PV": result.pv_capacity,
            "Wind": result.wind_capacity,
            "Biomass": result.biomass_capacity,
            "Fuel Cell": result.fuel_cell_capacity,
            "Electrolyzer": result.electrolyzer_capacity,
        }

        labels1 = [f"{k}\n{v:.1f} kW" for k, v in power_caps.items()]
        sizes1 = list(power_caps.values())
        colors1 = ["gold", "lightblue", "lightgreen", "coral", "plum"]

        axes[0].pie(
            sizes1,
            labels=labels1,
            colors=colors1,
            autopct="%1.1f%%",
            startangle=90,
        )
        axes[0].set_title("Power Capacity Distribution", fontsize=12)

        # Cost breakdown (simplified)
        costs = {
            "PV": result.pv_capacity * 900,
            "Wind": result.wind_capacity * 1200,
            "Electrolyzer": result.electrolyzer_capacity * 890,
            "Fuel Cell": result.fuel_cell_capacity * 1000,
            "H2 Storage": result.h2_storage_capacity * 1100,
            "Biomass": result.biomass_capacity * 600,
        }

        labels2 = [f"{k}\n${v/1000:.1f}k" for k, v in costs.items()]
        sizes2 = list(costs.values())
        colors2 = ["gold", "lightblue", "plum", "coral", "lightyellow", "lightgreen"]

        axes[1].pie(
            sizes2,
            labels=labels2,
            colors=colors2,
            autopct="%1.1f%%",
            startangle=90,
        )
        axes[1].set_title("Capital Cost Distribution", fontsize=12)

        plt.suptitle(title, fontsize=14, y=1.02)
        plt.tight_layout()

        if save_path:
            fig.savefig(self.output_dir / save_path, dpi=300, bbox_inches="tight")

        return fig

    def plot_pareto_3d(
        self,
        results: List[OptimizationResult],
        title: str = "3D Pareto Front",
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        """Plot 3D Pareto front (COE vs UME vs H2 Revenue).

        Args:
            results: List of optimization results
            title: Plot title
            save_path: Path to save figure

        Returns:
            Matplotlib figure
        """
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection="3d")

        coes = [r.coe for r in results]
        umes = [r.ume for r in results]
        h2_revenues = [r.h2_revenue for r in results]

        scatter = ax.scatter(
            coes,
            umes,
            h2_revenues,
            c=coes,
            cmap="viridis",
            s=50,
        )

        ax.set_xlabel("COE ($/kWh)")
        ax.set_ylabel("UME")
        ax.set_zlabel("H2 Revenue ($)")
        ax.set_title(title)

        plt.colorbar(scatter, label="COE ($/kWh)")
        plt.tight_layout()

        if save_path:
            fig.savefig(self.output_dir / save_path, dpi=300, bbox_inches="tight")

        return fig

    def create_figure_9(
        self,
        pareto_with_h2_base: ParetoResult,
        pareto_with_h2_high: ParetoResult,
        pareto_without_h2: ParetoResult,
        save_path: str = "figure_9_pareto.png",
    ) -> plt.Figure:
        """Reproduce Figure 9 from the paper.

        Shows three Pareto curves:
        (a) With H2 market @ $6.6/kg
        (b) With H2 market @ $9.9/kg
        (c) Without H2 market

        Args:
            pareto_with_h2_base: Pareto result at $6.6/kg
            pareto_with_h2_high: Pareto result at $9.9/kg
            pareto_without_h2: Pareto result without H2 market
            save_path: Path to save figure

        Returns:
            Matplotlib figure
        """
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))

        scenarios = [
            (pareto_with_h2_base, "H2 @ $6.6/kg", "blue"),
            (pareto_with_h2_high, "H2 @ $9.9/kg", "green"),
            (pareto_without_h2, "No H2 Market", "red"),
        ]

        for ax, (result, label, color) in zip(axes, scenarios):
            coes = [s.coe for s in result.solutions]
            rels = [s.reliability for s in result.solutions]

            ax.plot(coes, rels, f"{color}-o", markersize=5)

            # Mark knee
            knee = result.knee_point
            ax.scatter([knee.coe], [knee.reliability], s=150, c="orange", marker="*")

            ax.set_xlabel("COE ($/kWh)")
            ax.set_ylabel("Reliability")
            ax.set_title(f"({chr(97+scenarios.index((result, label, color)))}) {label}")
            ax.grid(True, alpha=0.3)

            # Add annotation for knee point
            ax.annotate(
                f"COE=${knee.coe:.3f}\nRel={knee.reliability:.3f}",
                xy=(knee.coe, knee.reliability),
                xytext=(10, -20),
                textcoords="offset points",
                fontsize=8,
            )

        plt.suptitle("Figure 9: Pareto Curves for Different Market Scenarios", fontsize=14)
        plt.tight_layout()

        fig.savefig(self.output_dir / save_path, dpi=300, bbox_inches="tight")

        return fig
