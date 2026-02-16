"""Scenario definitions from the paper.

Reference: Mulumba & Farzaneh (2025) - Table 6, Table 7
International Journal of Hydrogen Energy 178 (2025) 151474

8 scenarios based on combinations of:
- LHV (High/Low based on precipitation)
- Solar Irradiance (High/Low)
- Wind Speed (High/Low)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class LHVLevel(Enum):
    """LHV level based on precipitation/moisture content."""

    HIGH = "high"  # 17.5 MJ/kg (dry season, 0-12 mm precipitation)
    LOW = "low"  # 14.3 MJ/kg (wet season, ~120 mm precipitation)


class IrradianceLevel(Enum):
    """Solar irradiance level."""

    HIGH = "high"
    LOW = "low"


class WindLevel(Enum):
    """Wind speed level."""

    HIGH = "high"
    LOW = "low"


class Climate(Enum):
    """Climate condition."""

    DRY = "dry"
    RAINY = "rainy"
    COLD_DRY = "cold_dry"
    COLD_RAINY = "cold_rainy"


@dataclass
class ScenarioConfig:
    """Configuration for a single scenario."""

    id: int
    name: str
    month: str
    lhv_level: LHVLevel
    irradiance_level: IrradianceLevel
    wind_level: WindLevel
    climate: Climate
    lhv_value: float  # MJ/kg
    description: str

    @property
    def is_dry_season(self) -> bool:
        """Check if scenario is in dry season."""
        return self.climate in [Climate.DRY, Climate.COLD_DRY]

    @property
    def is_high_renewable(self) -> bool:
        """Check if scenario has high renewable potential."""
        return (
            self.irradiance_level == IrradianceLevel.HIGH
            and self.wind_level == WindLevel.HIGH
        )


class Scenarios:
    """Collection of all 8 scenarios from Table 6."""

    # Scenario 1: High LHV, High Irradiance, High Wind (Dry season - January)
    SC1 = ScenarioConfig(
        id=1,
        name="SC1",
        month="January",
        lhv_level=LHVLevel.HIGH,
        irradiance_level=IrradianceLevel.HIGH,
        wind_level=WindLevel.HIGH,
        climate=Climate.DRY,
        lhv_value=17.5,
        description="Dry season with high solar and wind - optimal for H2 production",
    )

    # Scenario 2: High LHV, High Irradiance, Low Wind (Dry season - February)
    SC2 = ScenarioConfig(
        id=2,
        name="SC2",
        month="February",
        lhv_level=LHVLevel.HIGH,
        irradiance_level=IrradianceLevel.HIGH,
        wind_level=WindLevel.LOW,
        climate=Climate.DRY,
        lhv_value=17.5,
        description="Dry season with high solar, low wind - solar dominant",
    )

    # Scenario 3: High LHV, Low Irradiance, High Wind (Dry season - April)
    SC3 = ScenarioConfig(
        id=3,
        name="SC3",
        month="April",
        lhv_level=LHVLevel.HIGH,
        irradiance_level=IrradianceLevel.LOW,
        wind_level=WindLevel.HIGH,
        climate=Climate.DRY,
        lhv_value=17.5,
        description="Dry season with low solar, high wind - wind dominant",
    )

    # Scenario 4: High LHV, Low Irradiance, Low Wind (Cold/Dry season - July)
    SC4 = ScenarioConfig(
        id=4,
        name="SC4",
        month="July",
        lhv_level=LHVLevel.HIGH,
        irradiance_level=IrradianceLevel.LOW,
        wind_level=WindLevel.LOW,
        climate=Climate.COLD_DRY,
        lhv_value=17.5,
        description="Cold dry season with low renewables - biomass backup needed",
    )

    # Scenario 5: Low LHV, High Irradiance, High Wind (Rainy season - December)
    SC5 = ScenarioConfig(
        id=5,
        name="SC5",
        month="December",
        lhv_level=LHVLevel.LOW,
        irradiance_level=IrradianceLevel.HIGH,
        wind_level=WindLevel.HIGH,
        climate=Climate.RAINY,
        lhv_value=14.3,
        description="Rainy season with high renewables - fuel cell backup",
    )

    # Scenario 6: Low LHV, High Irradiance, Low Wind (Rainy season - May)
    SC6 = ScenarioConfig(
        id=6,
        name="SC6",
        month="May",
        lhv_level=LHVLevel.LOW,
        irradiance_level=IrradianceLevel.HIGH,
        wind_level=WindLevel.LOW,
        climate=Climate.RAINY,
        lhv_value=14.3,
        description="Rainy season with high solar, low wind",
    )

    # Scenario 7: Low LHV, Low Irradiance, High Wind (Rainy season - November)
    SC7 = ScenarioConfig(
        id=7,
        name="SC7",
        month="November",
        lhv_level=LHVLevel.LOW,
        irradiance_level=IrradianceLevel.LOW,
        wind_level=WindLevel.HIGH,
        climate=Climate.RAINY,
        lhv_value=14.3,
        description="Rainy season with low solar, high wind",
    )

    # Scenario 8: Low LHV, Low Irradiance, Low Wind (Cold/Rainy season - May)
    SC8 = ScenarioConfig(
        id=8,
        name="SC8",
        month="May",
        lhv_level=LHVLevel.LOW,
        irradiance_level=IrradianceLevel.LOW,
        wind_level=WindLevel.LOW,
        climate=Climate.COLD_RAINY,
        lhv_value=14.3,
        description="Cold rainy season with low renewables - highest FC usage",
    )

    @classmethod
    def all(cls) -> List[ScenarioConfig]:
        """Get all scenarios as a list."""
        return [cls.SC1, cls.SC2, cls.SC3, cls.SC4, cls.SC5, cls.SC6, cls.SC7, cls.SC8]

    @classmethod
    def dry_season(cls) -> List[ScenarioConfig]:
        """Get dry season scenarios (SC1-SC4)."""
        return [cls.SC1, cls.SC2, cls.SC3, cls.SC4]

    @classmethod
    def wet_season(cls) -> List[ScenarioConfig]:
        """Get wet/rainy season scenarios (SC5-SC8)."""
        return [cls.SC5, cls.SC6, cls.SC7, cls.SC8]

    @classmethod
    def by_id(cls, scenario_id: int) -> Optional[ScenarioConfig]:
        """Get scenario by ID (1-8)."""
        scenarios = {s.id: s for s in cls.all()}
        return scenarios.get(scenario_id)

    @classmethod
    def by_month(cls, month: str) -> List[ScenarioConfig]:
        """Get scenarios for a given month."""
        return [s for s in cls.all() if s.month.lower() == month.lower()]


@dataclass
class HydrogenPriceScenario:
    """Hydrogen price scenarios from Table 7."""

    name: str
    price: float  # $/kg
    description: str


class H2PriceScenarios:
    """Hydrogen market price scenarios."""

    BASE = HydrogenPriceScenario(
        name="H1",
        price=6.6,
        description="Base case hydrogen price",
    )

    HIGH = HydrogenPriceScenario(
        name="H2",
        price=9.9,
        description="High hydrogen price (sensitivity analysis)",
    )

    @classmethod
    def all(cls) -> List[HydrogenPriceScenario]:
        """Get all price scenarios."""
        return [cls.BASE, cls.HIGH]


# Month to scenario mapping for hourly simulation
MONTH_SCENARIO_MAP: Dict[int, int] = {
    1: 1,  # January -> SC1
    2: 2,  # February -> SC2
    3: 3,  # March -> SC3 (similar to April)
    4: 3,  # April -> SC3
    5: 6,  # May -> SC6 (or SC8 for late May)
    6: 4,  # June -> SC4 (cold/dry)
    7: 4,  # July -> SC4
    8: 4,  # August -> SC4
    9: 2,  # September -> SC2 (dry, high irradiance)
    10: 7,  # October -> SC7 (start of short rains)
    11: 7,  # November -> SC7
    12: 5,  # December -> SC5
}
