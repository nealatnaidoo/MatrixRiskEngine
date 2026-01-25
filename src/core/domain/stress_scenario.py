"""StressScenario Domain Object - Market shock scenarios.

Represents a stress testing scenario with risk factor shocks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

# Maximum reasonable shock magnitude (500% = 5.0)
MAX_SHOCK_MAGNITUDE = 5.0


@dataclass
class StressScenario:
    """Stress testing scenario definition.

    Represents a named scenario with shocks to various risk factors,
    used for stress testing portfolio resilience.

    Attributes:
        name: Scenario name (e.g., "2008 Financial Crisis", "COVID Crash")
        shocks: Risk factor to shock mapping (e.g., {"SPX": -0.40, "VIX": 2.0})
        description: Narrative description of the scenario
        date_calibrated: When this scenario was defined/calibrated

    Invariants:
        - shocks must specify all required risk factors (completeness check in service)
        - shock magnitudes must be reasonable: abs(shock) < 5.0 for most factors

    Source of Truth: YAML configuration file (scenarios.yaml)
    """

    name: str
    shocks: dict[str, float]
    description: str
    date_calibrated: date

    def __post_init__(self) -> None:
        """Validate invariants after initialization."""
        self._validate_invariants()

    def _validate_invariants(self) -> None:
        """Validate all domain invariants.

        Raises:
            ValueError: If any invariant is violated
        """
        # Invariant 1: name must not be empty
        if not self.name or not self.name.strip():
            raise ValueError("StressScenario name must not be empty")

        # Invariant 2: shocks must not be empty
        if not self.shocks:
            raise ValueError(
                f"StressScenario '{self.name}' must have at least one shock defined"
            )

        # Invariant 3: shock magnitudes must be reasonable
        extreme_shocks = []
        for factor, shock in self.shocks.items():
            if abs(shock) > MAX_SHOCK_MAGNITUDE:
                extreme_shocks.append((factor, shock))

        if extreme_shocks:
            raise ValueError(
                f"StressScenario '{self.name}' has extreme shocks (|shock| > {MAX_SHOCK_MAGNITUDE}): "
                f"{extreme_shocks}. If intentional, adjust MAX_SHOCK_MAGNITUDE."
            )

    def get_shock(self, risk_factor: str) -> float | None:
        """Get shock for a specific risk factor.

        Args:
            risk_factor: Risk factor identifier (e.g., "SPX", "VIX")

        Returns:
            Shock value or None if not defined
        """
        return self.shocks.get(risk_factor)

    @property
    def risk_factors(self) -> list[str]:
        """Return list of risk factors with defined shocks."""
        return list(self.shocks.keys())

    @property
    def num_shocks(self) -> int:
        """Return number of risk factor shocks."""
        return len(self.shocks)

    def has_shock(self, risk_factor: str) -> bool:
        """Check if scenario defines a shock for a risk factor.

        Args:
            risk_factor: Risk factor identifier

        Returns:
            True if shock is defined
        """
        return risk_factor in self.shocks

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "shocks": dict(self.shocks),
            "description": self.description,
            "date_calibrated": self.date_calibrated.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StressScenario":
        """Create StressScenario from dictionary.

        Args:
            data: Dictionary with scenario data

        Returns:
            StressScenario instance
        """
        return cls(
            name=data["name"],
            shocks=data["shocks"],
            description=data.get("description", ""),
            date_calibrated=(
                date.fromisoformat(data["date_calibrated"])
                if isinstance(data["date_calibrated"], str)
                else data["date_calibrated"]
            ),
        )


# Pre-defined scenarios for common stress tests
SCENARIO_2008_CRISIS = StressScenario(
    name="2008 Financial Crisis",
    shocks={
        "SPX": -0.40,      # Equity down 40%
        "VIX": 2.0,        # Vol up 200%
        "US10Y": -0.015,   # Rates down 150 bps
        "USDEUR": 0.10,    # USD up 10%
        "CreditHY": 0.08,  # HY spreads up 800 bps
    },
    description="Lehman Brothers collapse scenario - severe credit crisis",
    date_calibrated=date(2008, 9, 15),
)

SCENARIO_COVID_CRASH = StressScenario(
    name="COVID Crash",
    shocks={
        "SPX": -0.35,      # Equity down 35%
        "VIX": 1.5,        # Vol up 150%
        "US10Y": -0.010,   # Rates down 100 bps
        "CreditIG": 0.015, # IG spreads up 150 bps
    },
    description="March 2020 pandemic shock - rapid liquidity crisis",
    date_calibrated=date(2020, 3, 16),
)
