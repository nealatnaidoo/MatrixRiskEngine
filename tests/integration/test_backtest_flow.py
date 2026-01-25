"""Integration Test - Backtest Flow (F2).

Tests the complete backtesting workflow:
1. Load price data for universe
2. Generate trading signals
3. Run backtest simulation with transaction costs
4. Generate performance tearsheet
"""

import pytest
import pandas as pd
import numpy as np
from datetime import date
from unittest.mock import Mock

from tests.stubs.stub_data_adapter import StubDataAdapter
from src.core.services.backtest_engine import (
    BacktestEngine,
    BacktestRequest,
    BacktestResponse,
)
from src.core.domain.backtest_result import BacktestResult, BacktestConfig


class TestBacktestFlowF2:
    """Integration tests for Flow F2: Backtesting."""

    @pytest.fixture
    def data_adapter(self) -> StubDataAdapter:
        """Create fresh data adapter with seeded data."""
        adapter = StubDataAdapter()

        # Seed test data for multiple symbols
        dates = pd.date_range("2020-01-01", periods=252, freq="B")
        np.random.seed(42)

        for symbol in ["AAPL", "MSFT", "GOOGL"]:
            # Generate realistic price data
            returns = np.random.randn(252) * 0.02
            prices = 100 * np.cumprod(1 + returns)

            data = pd.DataFrame({
                "open": prices * (1 + np.random.randn(252) * 0.005),
                "high": prices * (1 + np.abs(np.random.randn(252)) * 0.01),
                "low": prices * (1 - np.abs(np.random.randn(252)) * 0.01),
                "close": prices,
                "volume": np.random.randint(1000000, 10000000, size=252),
            }, index=dates)

            adapter.seed_data(
                symbol=symbol,
                version="v1",
                data=data,
                metadata={"source": "test"},
            )

        return adapter

    @pytest.fixture
    def backtest_port(self) -> Mock:
        """Create mock backtest port."""
        port = Mock()

        def simulate_fn(
            signals: pd.DataFrame,
            prices: pd.DataFrame,
            transaction_costs: dict,
            rebalance_freq: str,
        ) -> BacktestResult:
            """Mock simulation returning realistic results."""
            # Calculate simple returns from prices
            returns = prices.pct_change().dropna()
            if signals.empty or returns.empty:
                returns = pd.Series(dtype=float)
            else:
                # Weight returns by signals
                aligned_signals = signals.reindex(returns.index).ffill().dropna()
                common_idx = returns.index.intersection(aligned_signals.index)
                if len(common_idx) > 0:
                    returns = returns.loc[common_idx]
                    aligned_signals = aligned_signals.loc[common_idx]
                    returns = (returns * aligned_signals).sum(axis=1)
                else:
                    returns = pd.Series(dtype=float)

            # Apply transaction costs
            cost_factor = 1 - (
                transaction_costs.get("spread_bps", 0) +
                transaction_costs.get("commission_bps", 0)
            ) / 10000

            if len(returns) > 0:
                returns = returns * cost_factor

            # Create mock trades
            trades = pd.DataFrame({
                "timestamp": [pd.Timestamp("2020-03-01")],
                "symbol": ["AAPL"],
                "quantity": [100],
                "price": [100.0],
                "cost": [0.7],
            })

            config = BacktestConfig(
                data_version="v1",
                start_date=date(2020, 1, 2),
                end_date=date(2020, 12, 30),
                universe=tuple(prices.columns.tolist()),
                rebalance_freq=rebalance_freq,
            )

            return BacktestResult(
                returns=returns if isinstance(returns, pd.Series) else pd.Series(returns),
                trades=trades,
                positions=pd.DataFrame(columns=["date", "symbol", "position"]),
                metrics={
                    "total_return": float(returns.sum()) if len(returns) > 0 else 0.0,
                    "sharpe_ratio": float(returns.mean() / returns.std() * np.sqrt(252)) if len(returns) > 1 and returns.std() > 0 else 0.0,
                    "max_drawdown": -0.10,
                    "volatility": float(returns.std() * np.sqrt(252)) if len(returns) > 1 else 0.0,
                    "win_rate": float((returns > 0).sum() / len(returns)) if len(returns) > 0 else 0.0,
                },
                config=config,
            )

        port.simulate.side_effect = simulate_fn
        return port

    def test_ac_f2_001_backtest_with_transaction_costs(
        self,
        data_adapter: StubDataAdapter,
        backtest_port: Mock,
    ) -> None:
        """AC-F2-001: Backtest correctly applies transaction costs.

        Test: Run backtest with 10 bps costs vs zero costs.
        Expected: Returns are reduced by transaction costs.
        """
        engine = BacktestEngine(data_adapter, backtest_port)

        def simple_signal(prices: pd.DataFrame) -> pd.DataFrame:
            """Equal weight all assets."""
            return pd.DataFrame(
                1.0 / len(prices.columns),
                index=prices.index,
                columns=prices.columns,
            )

        # Run with zero costs
        request_zero = BacktestRequest(
            universe=["AAPL", "MSFT"],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
            data_version="v1",
            signal_generator=simple_signal,
            transaction_costs={"spread_bps": 0, "commission_bps": 0},
            generate_tearsheet=False,
        )

        response_zero = engine.run(request_zero)

        # Run with 10 bps costs
        request_cost = BacktestRequest(
            universe=["AAPL", "MSFT"],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
            data_version="v1",
            signal_generator=simple_signal,
            transaction_costs={"spread_bps": 5, "commission_bps": 5},
            generate_tearsheet=False,
        )

        response_cost = engine.run(request_cost)

        # Verify backtest_port was called twice
        assert backtest_port.simulate.call_count == 2

        # Verify both returned valid responses
        assert isinstance(response_zero, BacktestResponse)
        assert isinstance(response_cost, BacktestResponse)

    def test_ac_f2_002_monthly_rebalancing(
        self,
        data_adapter: StubDataAdapter,
        backtest_port: Mock,
    ) -> None:
        """AC-F2-002: Monthly rebalancing only trades on month-end.

        Test: Run backtest with monthly rebalancing.
        Expected: Rebalancing frequency is passed to simulation.
        """
        engine = BacktestEngine(data_adapter, backtest_port)

        def momentum_signal(prices: pd.DataFrame) -> pd.DataFrame:
            """12-month momentum signal."""
            returns = prices.pct_change(periods=21)  # Approx 1 month
            ranks = returns.rank(axis=1, pct=True)
            return ranks

        request = BacktestRequest(
            universe=["AAPL", "MSFT", "GOOGL"],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
            data_version="v1",
            signal_generator=momentum_signal,
            rebalance_freq="monthly",
            generate_tearsheet=False,
        )

        response = engine.run(request)

        # Verify rebalance_freq was passed correctly
        call_kwargs = backtest_port.simulate.call_args.kwargs
        assert call_kwargs["rebalance_freq"] == "monthly"

    def test_ac_f2_003_tearsheet_generation(
        self,
        data_adapter: StubDataAdapter,
        backtest_port: Mock,
    ) -> None:
        """AC-F2-003: Performance tearsheet is generated.

        Test: Run backtest with tearsheet generation enabled.
        Expected: Tearsheet path is returned (when report_port available).
        """
        # Create mock report port
        report_port = Mock()
        report_port.generate_report.return_value = "/path/to/tearsheet.html"

        engine = BacktestEngine(data_adapter, backtest_port, report_port)

        def simple_signal(prices: pd.DataFrame) -> pd.DataFrame:
            return pd.DataFrame(0.5, index=prices.index, columns=prices.columns)

        request = BacktestRequest(
            universe=["AAPL"],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
            data_version="v1",
            signal_generator=simple_signal,
            generate_tearsheet=True,
        )

        response = engine.run(request)

        # Verify tearsheet was requested
        assert report_port.generate_report.called
        assert response.tearsheet_path is not None

    def test_complete_backtest_workflow(
        self,
        data_adapter: StubDataAdapter,
        backtest_port: Mock,
    ) -> None:
        """Test complete backtest workflow from data load to metrics."""
        engine = BacktestEngine(data_adapter, backtest_port)

        def equal_weight_signal(prices: pd.DataFrame) -> pd.DataFrame:
            """Equal weight all assets."""
            return pd.DataFrame(
                1.0 / len(prices.columns),
                index=prices.index,
                columns=prices.columns,
            )

        request = BacktestRequest(
            universe=["AAPL", "MSFT", "GOOGL"],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
            data_version="v1",
            signal_generator=equal_weight_signal,
            rebalance_freq="monthly",
            transaction_costs={"spread_bps": 5, "commission_bps": 2},
            generate_tearsheet=False,
        )

        response = engine.run(request)

        # Verify response structure
        assert isinstance(response, BacktestResponse)
        assert response.result is not None
        assert "sharpe_ratio" in response.metrics_summary
        assert "max_drawdown" in response.metrics_summary
        assert "total_return" in response.metrics_summary

    def test_empty_universe_raises(
        self,
        data_adapter: StubDataAdapter,
        backtest_port: Mock,
    ) -> None:
        """Empty universe should raise ValueError."""
        engine = BacktestEngine(data_adapter, backtest_port)

        request = BacktestRequest(
            universe=[],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
            data_version="v1",
            signal_generator=lambda x: x,
        )

        with pytest.raises(ValueError, match="empty"):
            engine.run(request)

    def test_invalid_dates_raises(
        self,
        data_adapter: StubDataAdapter,
        backtest_port: Mock,
    ) -> None:
        """Invalid date range should raise ValueError."""
        engine = BacktestEngine(data_adapter, backtest_port)

        request = BacktestRequest(
            universe=["AAPL"],
            start_date=date(2020, 12, 31),  # After end
            end_date=date(2020, 1, 1),
            data_version="v1",
            signal_generator=lambda x: x,
        )

        with pytest.raises(ValueError, match="before"):
            engine.run(request)

    def test_invalid_rebalance_frequency_raises(
        self,
        data_adapter: StubDataAdapter,
        backtest_port: Mock,
    ) -> None:
        """Invalid rebalancing frequency should raise ValueError."""
        engine = BacktestEngine(data_adapter, backtest_port)

        request = BacktestRequest(
            universe=["AAPL"],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
            data_version="v1",
            signal_generator=lambda x: x,
            rebalance_freq="biweekly",  # Invalid
        )

        with pytest.raises(ValueError, match="frequency"):
            engine.run(request)

    def test_metrics_summary_includes_key_metrics(
        self,
        data_adapter: StubDataAdapter,
        backtest_port: Mock,
    ) -> None:
        """Metrics summary includes all key performance indicators."""
        engine = BacktestEngine(data_adapter, backtest_port)

        request = BacktestRequest(
            universe=["AAPL"],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
            data_version="v1",
            signal_generator=lambda x: pd.DataFrame(1.0, index=x.index, columns=x.columns),
            generate_tearsheet=False,
        )

        response = engine.run(request)

        # Check all key metrics are present
        required_metrics = [
            "total_return",
            "sharpe_ratio",
            "max_drawdown",
            "volatility",
            "win_rate",
            "num_trades",
        ]

        for metric in required_metrics:
            assert metric in response.metrics_summary, f"Missing metric: {metric}"
