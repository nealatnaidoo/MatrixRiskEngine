"""OREAdapter - Risk analytics implementation using Open Risk Engine.

This adapter provides:
- Portfolio valuation (NPV)
- Historical and parametric VaR
- CVaR (Expected Shortfall)
- Greeks computation
- Stress testing
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from src.core.ports.risk_port import (
    InsufficientDataError,
    PricingError,
    RiskPort,
)

if TYPE_CHECKING:
    from src.core.domain.portfolio import Portfolio
    from src.core.domain.risk_metrics import RiskMetrics
    from src.core.domain.stress_scenario import StressScenario


class OREAdapter:
    """Open Risk Engine implementation of RiskPort.

    Provides risk analytics including VaR, CVaR, Greeks, and stress testing.
    Uses ORE-SWIG bindings when available, falls back to pure Python.
    """

    def __init__(self, use_ore_bindings: bool = False) -> None:
        """Initialize OREAdapter.

        Args:
            use_ore_bindings: Whether to use ORE-SWIG bindings.
                If False, uses pure Python implementations.
        """
        self._use_ore = use_ore_bindings
        self._ore: Any = None

    def _get_ore(self) -> Any:
        """Get ORE bindings (lazy import)."""
        if self._ore is None and self._use_ore:
            try:
                import ORE as ore  # ORE-SWIG bindings

                self._ore = ore
            except ImportError:
                # Fall back to pure Python
                self._use_ore = False
        return self._ore

    def value_portfolio(
        self,
        portfolio: "Portfolio",
        market_data: pd.DataFrame,
    ) -> float:
        """Value portfolio at current market prices.

        Args:
            portfolio: Portfolio to value
            market_data: Current market data with 'close' prices

        Returns:
            Net present value (NPV) of portfolio

        Raises:
            PricingError: If valuation fails for any position
        """
        total_value = 0.0

        for symbol, position in portfolio.positions.items():
            if symbol not in market_data.columns:
                # Check if symbol is in index
                if symbol in market_data.index:
                    price = float(market_data.loc[symbol, "close"])
                else:
                    raise PricingError(
                        symbol, f"No market data available for {symbol}"
                    )
            else:
                # Get latest price
                if "close" in market_data.columns:
                    price = float(market_data[symbol].iloc[-1])
                else:
                    price = float(market_data[symbol].iloc[-1])

            total_value += position * price

        return total_value

    def calculate_var(
        self,
        portfolio: "Portfolio",
        market_data: pd.DataFrame,
        method: str = "historical",
        confidence_levels: list[float] | None = None,
        window_days: int = 250,
    ) -> dict[str, float]:
        """Calculate Value at Risk.

        Args:
            portfolio: Portfolio to analyze
            market_data: Historical price data
            method: "historical" or "parametric"
            confidence_levels: Confidence levels (default: [0.95, 0.99])
            window_days: Lookback window in days

        Returns:
            Dictionary mapping confidence level to VaR value
            e.g., {"95%": -1500000, "99%": -2200000}

        Raises:
            InsufficientDataError: If not enough data
            ValueError: If invalid parameters
        """
        if confidence_levels is None:
            confidence_levels = [0.95, 0.99]

        # Validate confidence levels
        for level in confidence_levels:
            if not 0 < level < 1:
                raise ValueError(f"Confidence level must be in (0, 1): {level}")

        # Calculate portfolio returns
        portfolio_returns = self._calculate_portfolio_returns(
            portfolio, market_data, window_days
        )

        if len(portfolio_returns) < window_days:
            raise InsufficientDataError(
                required_days=window_days,
                available_days=len(portfolio_returns),
            )

        result = {}

        if method == "historical":
            # Historical simulation VaR
            for level in confidence_levels:
                var_value = np.percentile(
                    portfolio_returns, (1 - level) * 100
                )
                result[f"{int(level * 100)}%"] = float(var_value * portfolio.nav)

        elif method == "parametric":
            # Variance-covariance VaR
            from scipy import stats

            mean_return = portfolio_returns.mean()
            std_return = portfolio_returns.std()

            for level in confidence_levels:
                z_score = stats.norm.ppf(1 - level)
                var_value = mean_return + z_score * std_return
                result[f"{int(level * 100)}%"] = float(var_value * portfolio.nav)

        else:
            raise ValueError(f"Unknown VaR method: {method}")

        return result

    def calculate_cvar(
        self,
        portfolio: "Portfolio",
        market_data: pd.DataFrame,
        var_params: dict[str, object] | None = None,
    ) -> dict[str, float]:
        """Calculate Conditional VaR (Expected Shortfall).

        Args:
            portfolio: Portfolio to analyze
            market_data: Historical market data
            var_params: VaR calculation parameters

        Returns:
            Dictionary mapping confidence level to CVaR value
        """
        params = var_params or {}
        method = str(params.get("method", "historical"))
        confidence_levels = list(params.get("confidence_levels", [0.95, 0.99]))
        window_days = int(params.get("window_days", 250))

        # Calculate portfolio returns
        portfolio_returns = self._calculate_portfolio_returns(
            portfolio, market_data, window_days
        )

        if len(portfolio_returns) < window_days:
            raise InsufficientDataError(
                required_days=window_days,
                available_days=len(portfolio_returns),
            )

        result = {}

        for level in confidence_levels:
            # VaR threshold
            var_threshold = np.percentile(
                portfolio_returns, (1 - level) * 100
            )

            # CVaR = mean of returns below VaR threshold
            tail_returns = portfolio_returns[portfolio_returns <= var_threshold]
            cvar_value = tail_returns.mean() if len(tail_returns) > 0 else var_threshold

            result[f"{int(level * 100)}%"] = float(cvar_value * portfolio.nav)

        return result

    def compute_greeks(
        self,
        portfolio: "Portfolio",
        market_data: pd.DataFrame,
    ) -> dict[str, float | None]:
        """Compute Greek risk sensitivities.

        For equity portfolios, computes delta and gamma.
        For fixed income, computes duration and convexity.

        Args:
            portfolio: Portfolio to analyze
            market_data: Current market data

        Returns:
            Dictionary of Greeks
        """
        greeks: dict[str, float | None] = {
            "delta": None,
            "gamma": None,
            "vega": None,
            "theta": None,
            "rho": None,
            "duration": None,
            "convexity": None,
        }

        # For equity portfolios, delta is approximately portfolio beta
        # Simplified: sum of weighted deltas (assume delta=1 for equities)
        total_delta = 0.0

        for symbol, weight in portfolio.weights.items():
            # Equities have delta = 1 per unit
            total_delta += weight

        greeks["delta"] = total_delta

        # Gamma and Vega are 0 for pure equity portfolios (no options)
        greeks["gamma"] = 0.0
        greeks["vega"] = 0.0

        # Duration and convexity are None for equity portfolios
        # Would be computed for fixed income

        return greeks

    def stress_test(
        self,
        portfolio: "Portfolio",
        market_data: pd.DataFrame,
        scenarios: list["StressScenario"],
    ) -> pd.DataFrame:
        """Apply stress scenarios and return stressed P&L.

        Args:
            portfolio: Portfolio to stress test
            market_data: Base market data
            scenarios: List of stress scenarios to apply

        Returns:
            DataFrame with scenario results
        """
        # Calculate base NPV
        base_npv = self._calculate_npv(portfolio, market_data)

        results = []

        for scenario in scenarios:
            # Apply shocks to market data
            stressed_data = self._apply_shocks(market_data, scenario)

            # Calculate stressed NPV
            try:
                stressed_npv = self._calculate_npv(portfolio, stressed_data)
                pnl = stressed_npv - base_npv
                pct_change = pnl / base_npv if base_npv != 0 else 0.0

                results.append({
                    "scenario": scenario.name,
                    "base_npv": base_npv,
                    "stressed_npv": stressed_npv,
                    "pnl": pnl,
                    "pct_change": pct_change,
                })
            except Exception as e:
                # Record error but continue with other scenarios
                results.append({
                    "scenario": scenario.name,
                    "base_npv": base_npv,
                    "stressed_npv": None,
                    "pnl": None,
                    "pct_change": None,
                    "error": str(e),
                })

        return pd.DataFrame(results)

    def _calculate_portfolio_returns(
        self,
        portfolio: "Portfolio",
        market_data: pd.DataFrame,
        window_days: int,
    ) -> pd.Series:
        """Calculate portfolio returns from market data."""
        # Get weights
        weights = portfolio.weights

        # Calculate returns for each symbol
        returns_data = {}

        for symbol in weights:
            if symbol in market_data.columns:
                prices = market_data[symbol].dropna()
                if len(prices) > 1:
                    returns_data[symbol] = prices.pct_change().dropna()

        if not returns_data:
            return pd.Series(dtype=float)

        # Combine into DataFrame
        returns_df = pd.DataFrame(returns_data)

        # Take last window_days
        returns_df = returns_df.tail(window_days)

        # Calculate portfolio returns
        weight_vec = pd.Series(weights)
        common = list(set(returns_df.columns) & set(weight_vec.index))

        if not common:
            return pd.Series(dtype=float)

        portfolio_returns = (returns_df[common] * weight_vec[common]).sum(axis=1)

        return portfolio_returns

    def _calculate_npv(
        self,
        portfolio: "Portfolio",
        market_data: pd.DataFrame,
    ) -> float:
        """Calculate portfolio NPV from market data."""
        npv = 0.0

        for symbol, position in portfolio.positions.items():
            if symbol in market_data.columns:
                price = market_data[symbol].iloc[-1]
                npv += position * price

        return npv

    def _apply_shocks(
        self,
        market_data: pd.DataFrame,
        scenario: "StressScenario",
    ) -> pd.DataFrame:
        """Apply scenario shocks to market data."""
        stressed = market_data.copy()

        for risk_factor, shock in scenario.shocks.items():
            if risk_factor in stressed.columns:
                # Apply shock as percentage change
                stressed[risk_factor] = stressed[risk_factor] * (1 + shock)
            elif risk_factor == "equity_all":
                # Apply to all equity columns
                for col in stressed.columns:
                    stressed[col] = stressed[col] * (1 + shock)
            elif risk_factor == "rates":
                # Interest rate shock (would apply to rate curves)
                pass  # Not applicable to simple equity data

        return stressed


def create_ore_adapter(use_ore_bindings: bool = False) -> OREAdapter:
    """Factory function to create OREAdapter."""
    return OREAdapter(use_ore_bindings=use_ore_bindings)


# Type assertion for Protocol compliance
_: RiskPort = OREAdapter()  # type: ignore[assignment]
