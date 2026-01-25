"""BacktestResult Domain Object - Backtest output with metrics.

Represents the complete output of a backtest simulation including:
- Returns time series
- Trade history
- Position history
- Performance metrics
- Configuration for reproducibility
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd


@dataclass(frozen=True)
class BacktestConfig:
    """Configuration used to run the backtest.

    Stored with results for reproducibility.

    Attributes:
        data_version: ArcticDB version tag used
        start_date: Backtest start date
        end_date: Backtest end date
        universe: List of symbols in universe
        rebalance_freq: Rebalancing frequency (daily, weekly, monthly, quarterly)
        transaction_costs: Cost model parameters
        random_seed: Random seed for any stochastic elements
    """

    data_version: str
    start_date: date
    end_date: date
    universe: tuple[str, ...]
    rebalance_freq: str
    transaction_costs: dict[str, float] = field(default_factory=dict)
    random_seed: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "data_version": self.data_version,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "universe": list(self.universe),
            "rebalance_freq": self.rebalance_freq,
            "transaction_costs": dict(self.transaction_costs),
            "random_seed": self.random_seed,
        }


@dataclass
class BacktestResult:
    """Complete backtest output with metrics and reproducibility info.

    Attributes:
        returns: Date to portfolio return time series
        trades: Trade history DataFrame (timestamp, symbol, quantity, price, cost)
        positions: Position history DataFrame (date, symbol, position_size)
        metrics: Performance metrics dict (Sharpe, max_dd, Calmar, etc.)
        config: Backtest configuration for reproducibility

    Invariants:
        - returns.index aligns with trading calendar
        - trades have valid timestamps within backtest period
        - metrics are derived from returns (not independent)

    Source of Truth: Backtest run output (persisted to disk)
    """

    returns: "pd.Series"
    trades: "pd.DataFrame"
    positions: "pd.DataFrame"
    metrics: dict[str, float]
    config: BacktestConfig

    def __post_init__(self) -> None:
        """Validate invariants after initialization."""
        self._validate_invariants()

    def _validate_invariants(self) -> None:
        """Validate all domain invariants.

        Raises:
            ValueError: If any invariant is violated
        """
        import pandas as pd

        # Invariant 1: returns must have DatetimeIndex
        if not isinstance(self.returns.index, pd.DatetimeIndex):
            raise ValueError("BacktestResult returns must have DatetimeIndex")

        # Invariant 2: returns index must be sorted
        if not self.returns.index.is_monotonic_increasing:
            raise ValueError("BacktestResult returns index must be sorted ascending")

        # Invariant 3: trades must have required columns
        required_trade_cols = {"timestamp", "symbol", "quantity", "price"}
        if not required_trade_cols.issubset(set(self.trades.columns)):
            missing = required_trade_cols - set(self.trades.columns)
            raise ValueError(f"BacktestResult trades missing columns: {missing}")

        # Invariant 4: trade timestamps within backtest period
        if len(self.trades) > 0:
            trade_dates = pd.to_datetime(self.trades["timestamp"]).dt.date
            min_trade = trade_dates.min()
            max_trade = trade_dates.max()

            if min_trade < self.config.start_date:
                raise ValueError(
                    f"Trade date {min_trade} before backtest start {self.config.start_date}"
                )
            if max_trade > self.config.end_date:
                raise ValueError(
                    f"Trade date {max_trade} after backtest end {self.config.end_date}"
                )

    @property
    def total_return(self) -> float:
        """Calculate total cumulative return."""
        return float((1 + self.returns).prod() - 1)

    @property
    def num_trades(self) -> int:
        """Return total number of trades."""
        return len(self.trades)

    @property
    def sharpe_ratio(self) -> float | None:
        """Return Sharpe ratio from metrics."""
        return self.metrics.get("sharpe_ratio")

    @property
    def max_drawdown(self) -> float | None:
        """Return maximum drawdown from metrics."""
        return self.metrics.get("max_drawdown")

    @property
    def win_rate(self) -> float | None:
        """Return win rate from metrics."""
        return self.metrics.get("win_rate")

    def get_metric(self, name: str) -> float | None:
        """Get a specific metric by name.

        Args:
            name: Metric name (e.g., 'sharpe_ratio', 'sortino_ratio')

        Returns:
            Metric value or None if not found
        """
        return self.metrics.get(name)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization (excluding large DataFrames)."""
        return {
            "total_return": self.total_return,
            "num_trades": self.num_trades,
            "metrics": dict(self.metrics),
            "config": self.config.to_dict(),
            "returns_start": self.returns.index[0].isoformat(),
            "returns_end": self.returns.index[-1].isoformat(),
            "returns_count": len(self.returns),
        }

    @classmethod
    def create_empty(cls, config: BacktestConfig) -> "BacktestResult":
        """Create an empty backtest result.

        Useful for cases where no trades were generated.

        Args:
            config: Backtest configuration

        Returns:
            Empty BacktestResult with zero returns and no trades
        """
        import pandas as pd

        date_range = pd.date_range(
            start=config.start_date,
            end=config.end_date,
            freq="B",  # Business days
        )

        return cls(
            returns=pd.Series(0.0, index=date_range, name="returns"),
            trades=pd.DataFrame(columns=["timestamp", "symbol", "quantity", "price", "cost"]),
            positions=pd.DataFrame(columns=["date", "symbol", "position"]),
            metrics={"sharpe_ratio": 0.0, "max_drawdown": 0.0, "total_return": 0.0},
            config=config,
        )
