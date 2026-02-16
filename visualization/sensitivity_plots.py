"""Sensitivity analysis visualization.

Reference: Figure 14 - H2 price sensitivity analysis
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np

from optimization.epsilon_constraint import ParetoResult
from simulation.scenario_runner import AllScenariosResult


class SensitivityPlotter:
    """Plotter for sensitivity analysis (Figure 14)."""

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

    def plot_h2_price_sensitivity(
        self,
        price_results: Dict[float, AllScenariosResult],
        title: str = "H2 Price Sensitivity Analysis",
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        """Plot COE sensitivity to H2 price (Figure 14).

        Args:
            price_results: Dict mapping H2 price to scenario results
            title: Plot title
            save_path: Path to save figure

        Returns:
            Matplotlib figure
        """
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        prices = sorted(price_results.keys())
        dry_coes = [price_results[p].dry_season_avg_coe for p in prices]
        wet_coes = [price_results[p].wet_season_avg_coe for p in prices]
        overall_coes = [price_results[p].overall_avg_coe for p in prices]

        # Panel 1: COE vs H2 Price
        ax1 = axes[0]
        ax1.plot(prices, dry_coes, "b-o", markersize=8, label="Dry Season")
        ax1.plot(prices, wet_coes, "r-s", markersize=8, label="Wet Season")
        ax1.plot(prices, overall_coes, "g-^", markersize=8, label="Overall")

        ax1.set_xlabel("H2 Price ($/kg)", fontsize=12)
        ax1.set_ylabel("COE ($/kWh)", fontsize=12)
        ax1.set_title("COE vs H2 Price")
        ax1.legend(loc="best")
        ax1.grid(True, alpha=0.3)

        # Panel 2: COE Reduction
        if len(prices) >= 2:
            base_price = prices[0]
            reductions = {}

            for p in prices:
                dry_red = (price_results[base_price].dry_season_avg_coe -
                          price_results[p].dry_season_avg_coe) / price_results[base_price].dry_season_avg_coe * 100
                wet_red = (price_results[base_price].wet_season_avg_coe -
                          price_results[p].wet_season_avg_coe) / price_results[base_price].wet_season_avg_coe * 100
                reductions[p] = {"dry": dry_red, "wet": wet_red}

            ax2 = axes[1]
            x = np.arange(len(prices))
            width = 0.35

            dry_reds = [reductions[p]["dry"] for p in prices]
            wet_reds = [reductions[p]["wet"] for p in prices]

            ax2.bar(x - width/2, dry_reds, width, label="Dry Season", color="blue", alpha=0.7)
            ax2.bar(x + width/2, wet_reds, width, label="Wet Season", color="red", alpha=0.7)

            ax2.set_xlabel("H2 Price ($/kg)", fontsize=12)
            ax2.set_ylabel("COE Reduction (%)", fontsize=12)
            ax2.set_title(f"COE Reduction from ${base_price}/kg Baseline")
            ax2.set_xticks(x)
            ax2.set_xticklabels([f"${p}" for p in prices])
            ax2.legend(loc="best")
            ax2.grid(True, alpha=0.3, axis="y")
            ax2.axhline(y=0, color="black", linewidth=0.5)

        plt.suptitle(title, fontsize=14)
        plt.tight_layout()

        if save_path:
            fig.savefig(self.output_dir / save_path, dpi=300, bbox_inches="tight")

        return fig

    def plot_pareto_shift(
        self,
        pareto_base: ParetoResult,
        pareto_high: ParetoResult,
        title: str = "Pareto Front Shift with H2 Price",
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        """Plot Pareto front shift between H2 price scenarios.

        Args:
            pareto_base: Pareto result at base H2 price
            pareto_high: Pareto result at high H2 price
            title: Plot title
            save_path: Path to save figure

        Returns:
            Matplotlib figure
        """
        fig, ax = plt.subplots(figsize=(10, 7))

        # Base price Pareto
        coe_base = [s.coe for s in pareto_base.solutions]
        rel_base = [s.reliability for s in pareto_base.solutions]
        ax.plot(coe_base, rel_base, "b-o", markersize=5, label="H2 @ $6.6/kg")

        # High price Pareto
        coe_high = [s.coe for s in pareto_high.solutions]
        rel_high = [s.reliability for s in pareto_high.solutions]
        ax.plot(coe_high, rel_high, "r-s", markersize=5, label="H2 @ $9.9/kg")

        # Mark knee points
        knee_base = pareto_base.knee_point
        knee_high = pareto_high.knee_point

        ax.scatter([knee_base.coe], [knee_base.reliability], s=150, c="blue", marker="*", zorder=5)
        ax.scatter([knee_high.coe], [knee_high.reliability], s=150, c="red", marker="*", zorder=5)

        # Draw arrow showing shift
        ax.annotate(
            "",
            xy=(knee_high.coe, knee_high.reliability),
            xytext=(knee_base.coe, knee_base.reliability),
            arrowprops=dict(arrowstyle="->", color="green", lw=2),
        )

        # Add improvement text
        coe_improvement = (knee_base.coe - knee_high.coe) / knee_base.coe * 100
        ax.text(
            (knee_base.coe + knee_high.coe) / 2,
            (knee_base.reliability + knee_high.reliability) / 2 + 0.02,
            f"COE reduction: {coe_improvement:.1f}%",
            fontsize=10,
            color="green",
        )

        ax.set_xlabel("COE ($/kWh)", fontsize=12)
        ax.set_ylabel("Reliability", fontsize=12)
        ax.set_title(title, fontsize=14)
        ax.legend(loc="best")
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            fig.savefig(self.output_dir / save_path, dpi=300, bbox_inches="tight")

        return fig

    def plot_parameter_sensitivity(
        self,
        parameter_name: str,
        parameter_values: List[float],
        coe_values: List[float],
        reliability_values: List[float],
        title: Optional[str] = None,
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        """Plot general parameter sensitivity.

        Args:
            parameter_name: Name of parameter being varied
            parameter_values: Parameter values tested
            coe_values: Corresponding COE values
            reliability_values: Corresponding reliability values
            title: Plot title
            save_path: Path to save figure

        Returns:
            Matplotlib figure
        """
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        # COE sensitivity
        ax1 = axes[0]
        ax1.plot(parameter_values, coe_values, "b-o", markersize=8)
        ax1.set_xlabel(parameter_name, fontsize=12)
        ax1.set_ylabel("COE ($/kWh)", fontsize=12)
        ax1.set_title(f"COE Sensitivity to {parameter_name}")
        ax1.grid(True, alpha=0.3)

        # Reliability sensitivity
        ax2 = axes[1]
        ax2.plot(parameter_values, reliability_values, "r-s", markersize=8)
        ax2.set_xlabel(parameter_name, fontsize=12)
        ax2.set_ylabel("Reliability", fontsize=12)
        ax2.set_title(f"Reliability Sensitivity to {parameter_name}")
        ax2.grid(True, alpha=0.3)

        if title:
            plt.suptitle(title, fontsize=14)

        plt.tight_layout()

        if save_path:
            fig.savefig(self.output_dir / save_path, dpi=300, bbox_inches="tight")

        return fig

    def plot_seasonal_comparison(
        self,
        results: AllScenariosResult,
        title: str = "Seasonal Performance Comparison",
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        """Plot seasonal comparison of COE and reliability.

        Args:
            results: All scenarios result
            title: Plot title
            save_path: Path to save figure

        Returns:
            Matplotlib figure
        """
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        # Data
        categories = ["Dry Season", "Wet Season", "Overall"]
        coes = [results.dry_season_avg_coe, results.wet_season_avg_coe, results.overall_avg_coe]
        reliabilities = [
            np.mean([results.scenarios[s.name].monthly_reliability
                    for s in [results.scenarios["SC1"].scenario,
                             results.scenarios["SC2"].scenario,
                             results.scenarios["SC3"].scenario,
                             results.scenarios["SC4"].scenario]]),
            np.mean([results.scenarios[s.name].monthly_reliability
                    for s in [results.scenarios["SC5"].scenario,
                             results.scenarios["SC6"].scenario,
                             results.scenarios["SC7"].scenario,
                             results.scenarios["SC8"].scenario]]),
            results.overall_reliability,
        ]

        x = np.arange(len(categories))
        width = 0.5

        # COE comparison
        bars1 = axes[0].bar(x, coes, width, color=["blue", "red", "green"], alpha=0.7)
        axes[0].set_ylabel("COE ($/kWh)", fontsize=12)
        axes[0].set_title("Seasonal COE Comparison")
        axes[0].set_xticks(x)
        axes[0].set_xticklabels(categories)
        axes[0].grid(True, alpha=0.3, axis="y")

        # Add value labels
        for bar, val in zip(bars1, coes):
            axes[0].text(
                bar.get_x() + bar.get_width()/2,
                bar.get_height() + 0.01,
                f"${val:.3f}",
                ha="center",
                fontsize=10,
            )

        # Reliability comparison
        bars2 = axes[1].bar(x, reliabilities, width, color=["blue", "red", "green"], alpha=0.7)
        axes[1].set_ylabel("Reliability", fontsize=12)
        axes[1].set_title("Seasonal Reliability Comparison")
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(categories)
        axes[1].set_ylim([0.9, 1.0])
        axes[1].grid(True, alpha=0.3, axis="y")

        # Add value labels
        for bar, val in zip(bars2, reliabilities):
            axes[1].text(
                bar.get_x() + bar.get_width()/2,
                bar.get_height() + 0.002,
                f"{val:.3f}",
                ha="center",
                fontsize=10,
            )

        plt.suptitle(title, fontsize=14)
        plt.tight_layout()

        if save_path:
            fig.savefig(self.output_dir / save_path, dpi=300, bbox_inches="tight")

        return fig

    def create_figure_14(
        self,
        price_results: Dict[float, AllScenariosResult],
        pareto_base: Optional[ParetoResult] = None,
        pareto_high: Optional[ParetoResult] = None,
        save_path: str = "figure_14_sensitivity.png",
    ) -> plt.Figure:
        """Reproduce Figure 14 from the paper.

        Shows H2 price sensitivity analysis.

        Args:
            price_results: Dict mapping H2 price to scenario results
            pareto_base: Optional Pareto result at base price
            pareto_high: Optional Pareto result at high price
            save_path: Path to save figure

        Returns:
            Matplotlib figure
        """
        if pareto_base and pareto_high:
            # Create combined figure
            fig, axes = plt.subplots(1, 2, figsize=(14, 6))

            # Left: COE sensitivity
            prices = sorted(price_results.keys())
            dry_coes = [price_results[p].dry_season_avg_coe for p in prices]
            wet_coes = [price_results[p].wet_season_avg_coe for p in prices]

            axes[0].plot(prices, dry_coes, "b-o", markersize=8, label="Dry Season")
            axes[0].plot(prices, wet_coes, "r-s", markersize=8, label="Wet Season")
            axes[0].set_xlabel("H2 Price ($/kg)")
            axes[0].set_ylabel("COE ($/kWh)")
            axes[0].set_title("(a) COE vs H2 Price")
            axes[0].legend()
            axes[0].grid(True, alpha=0.3)

            # Right: Pareto shift
            coe_base = [s.coe for s in pareto_base.solutions]
            rel_base = [s.reliability for s in pareto_base.solutions]
            coe_high = [s.coe for s in pareto_high.solutions]
            rel_high = [s.reliability for s in pareto_high.solutions]

            axes[1].plot(coe_base, rel_base, "b-o", markersize=5, label="H2 @ $6.6/kg")
            axes[1].plot(coe_high, rel_high, "r-s", markersize=5, label="H2 @ $9.9/kg")
            axes[1].set_xlabel("COE ($/kWh)")
            axes[1].set_ylabel("Reliability")
            axes[1].set_title("(b) Pareto Front Shift")
            axes[1].legend()
            axes[1].grid(True, alpha=0.3)

            plt.suptitle("Figure 14: H2 Price Sensitivity Analysis", fontsize=14)
            plt.tight_layout()

            fig.savefig(self.output_dir / save_path, dpi=300, bbox_inches="tight")
            return fig

        else:
            return self.plot_h2_price_sensitivity(
                price_results,
                title="Figure 14: H2 Price Sensitivity Analysis",
                save_path=save_path,
            )
