"""RiskPort Protocol - Abstract interface for risk analytics.

This port defines the contract for VaR, CVaR, Greeks, and stress testing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import pandas as pd

    from src.core.domain.portfolio import Portfolio
    from src.core.domain.risk_metrics import RiskMetrics
    from src.core.domain.stress_scenario import StressScenario


@runtime_checkable
class RiskPort(Protocol):
    """Abstract interface for risk analytics.

    Implementations:
    - OREAdapter: Production implementation using Open Risk Engine
    - StubRiskAdapter: Test stub for unit testing
    """

    def calculate_var(
        self,
        portfolio: "Portfolio",
        market_data: "pd.DataFrame",
        method: str,
        confidence_levels: list[float],
        window_days: int,
    ) -> dict[str, float]:
        """Calculate Value at Risk.

        Args:
            portfolio: Portfolio to analyze
            market_data: Historical market data (prices/returns)
            method: VaR calculation method
                - "historical": Historical simulation
                - "parametric": Variance-covariance method
            confidence_levels: Confidence levels (e.g., [0.95, 0.99])
            window_days: Lookback window for historical data

        Returns:
            Dictionary mapping confidence level string to VaR value
            e.g., {"95%": -1500000, "99%": -2200000}
            Values are negative (representing losses)

        Raises:
            InsufficientDataError: If window_days > available data
            ValueError: If confidence_levels outside (0, 1)

        Pre-conditions:
            - market_data.as_of_date matches portfolio.as_of_date
            - market_data contains all portfolio symbols

        Post-conditions:
            - Returns VaR for each confidence level
            - VaR values are negative (loss amounts)
        """
        ...

    def calculate_cvar(
        self,
        portfolio: "Portfolio",
        market_data: "pd.DataFrame",
        var_params: dict[str, object],
    ) -> dict[str, float]:
        """Calculate Conditional VaR (Expected Shortfall).

        Args:
            portfolio: Portfolio to analyze
            market_data: Historical market data
            var_params: Parameters from calculate_var
                - method: Same method as VaR
                - confidence_levels: Same levels as VaR
                - window_days: Same window as VaR

        Returns:
            Dictionary mapping confidence level to CVaR value
            CVaR is always <= VaR (more extreme/negative)

        Post-conditions:
            - CVaR[level] <= VaR[level] for all levels
        """
        ...

    def compute_greeks(
        self,
        portfolio: "Portfolio",
        market_data: "pd.DataFrame",
    ) -> dict[str, float | None]:
        """Compute Greek risk sensitivities.

        Args:
            portfolio: Portfolio to analyze
            market_data: Current market data (prices, curves, vols)

        Returns:
            Dictionary of Greeks:
            - delta: First-order price sensitivity
            - gamma: Second-order price sensitivity
            - vega: Volatility sensitivity
            - theta: Time decay
            - rho: Interest rate sensitivity
            - duration: Bond price sensitivity (fixed income)
            - convexity: Second-order bond sensitivity

            None for Greeks not applicable to portfolio

        Raises:
            PricingError: If instrument valuation fails

        Post-conditions:
            - All Greeks computed at same valuation point
            - Greeks match analytical formulas within 1%
        """
        ...

    def stress_test(
        self,
        portfolio: "Portfolio",
        market_data: "pd.DataFrame",
        scenarios: list["StressScenario"],
    ) -> "pd.DataFrame":
        """Apply stress scenarios and return stressed P&L.

        Args:
            portfolio: Portfolio to stress test
            market_data: Base market data
            scenarios: List of stress scenarios to apply

        Returns:
            DataFrame with columns:
            - scenario: Scenario name
            - base_npv: Base portfolio value
            - stressed_npv: Stressed portfolio value
            - pnl: Profit/loss (stressed - base)
            - pct_change: Percentage change

        Raises:
            PricingError: If stressed valuation fails

        Post-conditions:
            - One row per scenario
            - P&L calculated for all scenarios
        """
        ...

    def value_portfolio(
        self,
        portfolio: "Portfolio",
        market_data: "pd.DataFrame",
    ) -> float:
        """Value portfolio at current market prices.

        Args:
            portfolio: Portfolio to value
            market_data: Current market data

        Returns:
            Net present value (NPV) of portfolio

        Raises:
            PricingError: If valuation fails
        """
        ...


class InsufficientDataError(Exception):
    """Raised when not enough historical data for calculation."""

    def __init__(self, required_days: int, available_days: int) -> None:
        self.required_days = required_days
        self.available_days = available_days
        super().__init__(
            f"Insufficient data: required {required_days} days, "
            f"only {available_days} available"
        )


class PricingError(Exception):
    """Raised when instrument valuation fails."""

    def __init__(self, symbol: str, message: str) -> None:
        self.symbol = symbol
        super().__init__(f"Pricing failed for '{symbol}': {message}")
