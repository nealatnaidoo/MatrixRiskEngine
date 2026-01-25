"""BacktestPort Protocol - Abstract interface for backtesting and optimization.

This port defines the contract for strategy simulation and portfolio optimization.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import pandas as pd

    from src.core.domain.backtest_result import BacktestResult
    from src.core.domain.constraint import Constraint
    from src.core.domain.portfolio import Portfolio


@runtime_checkable
class BacktestPort(Protocol):
    """Abstract interface for backtesting and portfolio optimization.

    Implementations:
    - VectorBTAdapter: Production implementation using VectorBT
    - OptimizerAdapter: Optimization-focused implementation using cvxpy
    - StubBacktestAdapter: Test stub for unit testing
    """

    def simulate(
        self,
        signals: "pd.DataFrame",
        prices: "pd.DataFrame",
        transaction_costs: dict[str, float],
        rebalance_freq: str,
    ) -> "BacktestResult":
        """Execute backtest simulation.

        Args:
            signals: DataFrame with entry/exit signals (symbol columns, date index)
            prices: DataFrame with price data (symbol columns, date index)
            transaction_costs: Cost parameters
                - spread_bps: Bid-ask spread in basis points
                - commission_bps: Commission in basis points
            rebalance_freq: Rebalancing frequency
                - "daily", "weekly", "monthly", "quarterly"

        Returns:
            BacktestResult with returns, trades, positions, metrics

        Raises:
            BacktestError: If simulation fails
            ValueError: If signals and prices are not aligned

        Pre-conditions:
            - signals and prices must have aligned date index
            - signals values must be numeric (position sizes or weights)

        Post-conditions:
            - Returns complete BacktestResult
            - Results are deterministic for same inputs
        """
        ...

    def optimize(
        self,
        alpha: "pd.Series",
        risk_model: "pd.DataFrame",
        constraints: list["Constraint"],
        objective: str,
    ) -> "Portfolio":
        """Optimize portfolio weights.

        Args:
            alpha: Expected returns by symbol
            risk_model: Covariance matrix (symbols x symbols)
            constraints: List of optimization constraints
            objective: Objective function
                - "max_sharpe": Maximize Sharpe ratio
                - "min_variance": Minimum variance portfolio
                - "max_return": Maximize return (risk-adjusted)
                - "risk_parity": Risk parity allocation

        Returns:
            Portfolio with optimal weights

        Raises:
            InfeasibleError: If constraints cannot be satisfied
            OptimizationTimeoutError: If optimization exceeds timeout

        Pre-conditions:
            - risk_model must be positive semi-definite
            - alpha and risk_model must reference same symbols

        Post-conditions:
            - Returned Portfolio satisfies all constraints
            - OR raises InfeasibleError (no "best effort" solutions)
        """
        ...


class BacktestError(Exception):
    """Raised when backtest simulation fails."""

    def __init__(self, message: str, details: dict[str, object] | None = None) -> None:
        self.details = details or {}
        super().__init__(message)


class InfeasibleError(Exception):
    """Raised when optimization constraints are infeasible."""

    def __init__(
        self,
        constraints: list[str] | None = None,
        message: str = "Optimization constraints are infeasible",
    ) -> None:
        self.constraints = constraints or []
        super().__init__(message)


class OptimizationTimeoutError(Exception):
    """Raised when optimization exceeds timeout."""

    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Optimization timed out after {timeout_seconds} seconds")
