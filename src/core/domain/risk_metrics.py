"""RiskMetrics Domain Object - VaR, CVaR, Greeks with invariants.

Represents risk metrics calculated for a portfolio at a specific point in time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class Greeks:
    """Collection of Greek risk sensitivities.

    Attributes:
        delta: First-order price sensitivity
        gamma: Second-order price sensitivity
        vega: Volatility sensitivity
        theta: Time decay
        rho: Interest rate sensitivity
        duration: Bond price sensitivity to yield
        convexity: Second-order bond price sensitivity
    """

    delta: float | None = None
    gamma: float | None = None
    vega: float | None = None
    theta: float | None = None
    rho: float | None = None
    duration: float | None = None
    convexity: float | None = None

    def to_dict(self) -> dict[str, float | None]:
        """Convert to dictionary."""
        return {
            "delta": self.delta,
            "gamma": self.gamma,
            "vega": self.vega,
            "theta": self.theta,
            "rho": self.rho,
            "duration": self.duration,
            "convexity": self.convexity,
        }


@dataclass
class RiskMetrics:
    """Risk metrics for a portfolio snapshot.

    Represents VaR, CVaR, and Greeks calculated at a specific valuation point.

    Attributes:
        var: Value at Risk by confidence level (e.g., {"95%": -1500000, "99%": -2200000})
        cvar: Conditional VaR (Expected Shortfall) by confidence level
        greeks: Greek sensitivities (aggregated at portfolio level)
        as_of_date: Valuation date for these metrics
        portfolio_id: Links to the Portfolio this was calculated for

    Invariants:
        - CVaR[c] >= VaR[c] for all confidence levels c (CVaR is always worse/more negative)
        - All Greeks computed at same valuation point
        - as_of_date matches market data snapshot date

    Source of Truth: Risk calculation output (may be cached)
    """

    var: dict[str, float]
    cvar: dict[str, float]
    greeks: Greeks
    as_of_date: date
    portfolio_id: str
    calculation_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate invariants after initialization."""
        self._validate_invariants()

    def _validate_invariants(self) -> None:
        """Validate all domain invariants.

        Raises:
            ValueError: If any invariant is violated
        """
        # Invariant 1: CVaR and VaR must have same confidence levels
        var_levels = set(self.var.keys())
        cvar_levels = set(self.cvar.keys())

        if var_levels != cvar_levels:
            raise ValueError(
                f"RiskMetrics VaR and CVaR must have same confidence levels. "
                f"VaR levels: {var_levels}, CVaR levels: {cvar_levels}"
            )

        # Invariant 2: CVaR >= VaR for all confidence levels
        # Note: For losses, both values are negative, and CVaR should be more negative
        # So we check |CVaR| >= |VaR| which means CVaR <= VaR (both negative)
        for level in var_levels:
            var_val = self.var[level]
            cvar_val = self.cvar[level]

            # CVaR represents expected loss beyond VaR, so it should be more extreme
            # For negative values (losses): CVaR <= VaR (more negative)
            # Allow small tolerance for floating point
            tolerance = 1e-6 * max(abs(var_val), abs(cvar_val), 1.0)

            if cvar_val > var_val + tolerance:
                raise ValueError(
                    f"RiskMetrics invariant violated: CVaR must be <= VaR (more extreme). "
                    f"At {level}: VaR={var_val}, CVaR={cvar_val}"
                )

    def get_var(self, confidence_level: str) -> float | None:
        """Get VaR at a specific confidence level.

        Args:
            confidence_level: e.g., "95%", "99%"

        Returns:
            VaR value or None if level not calculated
        """
        return self.var.get(confidence_level)

    def get_cvar(self, confidence_level: str) -> float | None:
        """Get CVaR at a specific confidence level.

        Args:
            confidence_level: e.g., "95%", "99%"

        Returns:
            CVaR value or None if level not calculated
        """
        return self.cvar.get(confidence_level)

    @property
    def confidence_levels(self) -> list[str]:
        """Return list of confidence levels calculated."""
        return list(self.var.keys())

    @property
    def has_greeks(self) -> bool:
        """Return True if any Greeks are populated."""
        greeks_dict = self.greeks.to_dict()
        return any(v is not None for v in greeks_dict.values())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "var": dict(self.var),
            "cvar": dict(self.cvar),
            "greeks": self.greeks.to_dict(),
            "as_of_date": self.as_of_date.isoformat(),
            "portfolio_id": self.portfolio_id,
            "calculation_metadata": self.calculation_metadata,
        }

    @classmethod
    def create_with_var_only(
        cls,
        var: dict[str, float],
        cvar: dict[str, float],
        as_of_date: date,
        portfolio_id: str,
    ) -> "RiskMetrics":
        """Create RiskMetrics with only VaR/CVaR (no Greeks).

        Args:
            var: VaR by confidence level
            cvar: CVaR by confidence level
            as_of_date: Valuation date
            portfolio_id: Portfolio identifier

        Returns:
            RiskMetrics with empty Greeks
        """
        return cls(
            var=var,
            cvar=cvar,
            greeks=Greeks(),
            as_of_date=as_of_date,
            portfolio_id=portfolio_id,
        )
