"""BacktestEngine - Domain service for orchestrating backtest workflows.

This service coordinates:
1. Data loading via DataPort
2. Backtest simulation via BacktestPort
3. Transaction cost application
4. Report generation via ReportPort
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import pandas as pd

if TYPE_CHECKING:
    from src.core.domain.backtest_result import BacktestResult
    from src.core.ports.backtest_port import BacktestPort
    from src.core.ports.data_port import DataPort
    from src.core.ports.report_port import ReportPort


@dataclass(frozen=True)
class BacktestRequest:
    """Request parameters for a backtest run.

    Attributes:
        universe: List of symbols to include
        start_date: Backtest start date
        end_date: Backtest end date
        data_version: ArcticDB version tag to use
        signal_generator: Function that generates signals from price data
        rebalance_freq: Rebalancing frequency
        transaction_costs: Cost parameters
        generate_tearsheet: Whether to generate HTML tearsheet
        output_dir: Directory for output files
    """

    universe: list[str]
    start_date: date
    end_date: date
    data_version: str
    signal_generator: Callable[[pd.DataFrame], pd.DataFrame]
    rebalance_freq: str = "monthly"
    transaction_costs: dict[str, float] | None = None
    generate_tearsheet: bool = True
    output_dir: str = "artifacts/tearsheets"


@dataclass
class BacktestResponse:
    """Response from a backtest run.

    Attributes:
        result: Complete backtest result
        tearsheet_path: Path to generated tearsheet (if requested)
        metrics_summary: Summary of key metrics
    """

    result: "BacktestResult"
    tearsheet_path: str | None
    metrics_summary: dict[str, float]


class BacktestEngine:
    """Orchestrates backtest workflow.

    Coordinates data loading, simulation, and reporting through ports.
    This is a domain service that contains no I/O logic itself.
    """

    def __init__(
        self,
        data_port: "DataPort",
        backtest_port: "BacktestPort",
        report_port: "ReportPort | None" = None,
    ) -> None:
        """Initialize BacktestEngine with required ports.

        Args:
            data_port: Port for loading market data
            backtest_port: Port for running simulations
            report_port: Optional port for generating reports
        """
        self._data_port = data_port
        self._backtest_port = backtest_port
        self._report_port = report_port

    def run(self, request: BacktestRequest) -> BacktestResponse:
        """Execute complete backtest workflow.

        Workflow:
        1. Load price data for universe
        2. Generate signals using provided function
        3. Run backtest simulation with transaction costs
        4. Generate tearsheet (if requested and report_port available)

        Args:
            request: Backtest request parameters

        Returns:
            BacktestResponse with results and optional tearsheet

        Raises:
            ValueError: If universe is empty or dates invalid
            DataNotFoundError: If data cannot be loaded
            BacktestError: If simulation fails
        """
        # Validate request
        self._validate_request(request)

        # Step 1: Load price data
        prices = self._load_prices(request)

        # Step 2: Generate signals
        signals = request.signal_generator(prices)

        # Validate signals
        if signals.empty:
            raise ValueError("Signal generator returned empty DataFrame")

        # Step 3: Run simulation
        transaction_costs = request.transaction_costs or {
            "spread_bps": 5,
            "commission_bps": 2,
        }

        result = self._backtest_port.simulate(
            signals=signals,
            prices=prices,
            transaction_costs=transaction_costs,
            rebalance_freq=request.rebalance_freq,
        )

        # Step 4: Generate tearsheet (optional)
        tearsheet_path = None
        if request.generate_tearsheet and self._report_port is not None:
            tearsheet_path = self._generate_tearsheet(
                result, request.output_dir
            )

        # Build summary
        metrics_summary = self._build_metrics_summary(result)

        return BacktestResponse(
            result=result,
            tearsheet_path=tearsheet_path,
            metrics_summary=metrics_summary,
        )

    def _validate_request(self, request: BacktestRequest) -> None:
        """Validate backtest request parameters."""
        if not request.universe:
            raise ValueError("Universe cannot be empty")

        if request.start_date >= request.end_date:
            raise ValueError(
                f"Start date ({request.start_date}) must be before "
                f"end date ({request.end_date})"
            )

        if request.rebalance_freq not in (
            "daily",
            "weekly",
            "monthly",
            "quarterly",
        ):
            raise ValueError(
                f"Invalid rebalance frequency: {request.rebalance_freq}"
            )

    def _load_prices(self, request: BacktestRequest) -> pd.DataFrame:
        """Load price data for all symbols in universe."""
        price_data: dict[str, pd.Series] = {}

        for symbol in request.universe:
            df = self._data_port.load(
                symbol=symbol,
                start_date=request.start_date,
                end_date=request.end_date,
                version=request.data_version,
            )

            # Extract close price (or first numeric column)
            if "close" in df.columns:
                price_data[symbol] = df["close"]
            elif len(df.columns) > 0:
                price_data[symbol] = df.iloc[:, 0]

        if not price_data:
            raise ValueError("No price data loaded for any symbol")

        # Combine into DataFrame
        prices = pd.DataFrame(price_data)

        # Forward fill missing values (holidays, etc.)
        prices = prices.ffill()

        return prices

    def _generate_tearsheet(
        self,
        result: "BacktestResult",
        output_dir: str,
    ) -> str:
        """Generate HTML tearsheet for backtest results."""
        if self._report_port is None:
            raise ValueError("Report port not configured")

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        from datetime import datetime, timezone

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"tearsheet_{timestamp}.html"
        filepath = output_path / filename

        return self._report_port.generate_report(
            returns=result.returns,
            benchmark=None,
            template="full",
            output_path=str(filepath),
        )

    def _build_metrics_summary(
        self,
        result: "BacktestResult",
    ) -> dict[str, float]:
        """Build summary of key metrics."""
        return {
            "total_return": result.metrics.get("total_return", 0.0),
            "sharpe_ratio": result.metrics.get("sharpe_ratio", 0.0),
            "max_drawdown": result.metrics.get("max_drawdown", 0.0),
            "volatility": result.metrics.get("volatility", 0.0),
            "win_rate": result.metrics.get("win_rate", 0.0),
            "num_trades": float(result.num_trades),
        }


# Factory function for common setups
def create_backtest_engine(
    data_port: "DataPort",
    backtest_port: "BacktestPort",
    report_port: "ReportPort | None" = None,
) -> BacktestEngine:
    """Create a BacktestEngine with the given ports.

    Args:
        data_port: Port for data access
        backtest_port: Port for simulation
        report_port: Optional port for reporting

    Returns:
        Configured BacktestEngine
    """
    return BacktestEngine(
        data_port=data_port,
        backtest_port=backtest_port,
        report_port=report_port,
    )
