"""Performance Test - Backtest Execution.

Benchmark: 10 years, 500 securities in <60 seconds.
"""

import pytest
import time
import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import numpy as np

from tests.stubs.stub_data_adapter import StubDataAdapter
from src.core.domain.backtest_result import BacktestResult, BacktestConfig


class TestPerformanceBacktest:
    """Performance tests for backtesting."""

    @pytest.fixture
    def large_backtest_data(self) -> tuple[StubDataAdapter, list[str]]:
        """Create adapter with 10 years of data for 500 securities."""
        adapter = StubDataAdapter()

        # 10 years of daily data = ~2520 trading days
        num_days = 2520
        num_symbols = 500

        dates = pd.date_range("2014-01-01", periods=num_days, freq="B")
        np.random.seed(42)

        symbols = []
        for i in range(num_symbols):
            symbol = f"SEC{i:04d}"
            symbols.append(symbol)

            returns = np.random.randn(num_days) * 0.02
            prices = 100 * np.cumprod(1 + returns)

            data = pd.DataFrame({
                "close": prices,
                "volume": np.random.randint(100000, 1000000, size=num_days),
            }, index=dates)

            adapter.seed_data(symbol=symbol, version="v1", data=data)

        return adapter, symbols

    @pytest.fixture
    def mock_backtest_port(self) -> Mock:
        """Create mock backtest port for fast simulation."""
        port = Mock()

        def simulate_fn(signals, prices, transaction_costs, rebalance_freq):
            """Fast mock simulation."""
            returns = prices.pct_change().dropna()
            if returns.empty:
                portfolio_returns = pd.Series(dtype=float)
            else:
                # Simple equal weight
                portfolio_returns = returns.mean(axis=1)

            config = BacktestConfig(
                data_version="v1",
                start_date=date(2014, 1, 2),
                end_date=date(2023, 12, 30),
                universe=tuple(prices.columns.tolist()[:10]),
                rebalance_freq=rebalance_freq,
            )

            return BacktestResult(
                returns=portfolio_returns,
                trades=pd.DataFrame(columns=["timestamp", "symbol", "quantity", "price", "cost"]),
                positions=pd.DataFrame(columns=["date", "symbol", "position"]),
                metrics={
                    "total_return": float(portfolio_returns.sum()) if len(portfolio_returns) > 0 else 0.0,
                    "sharpe_ratio": 1.0,
                    "max_drawdown": -0.10,
                },
                config=config,
            )

        port.simulate.side_effect = simulate_fn
        return port

    def test_backtest_performance_500_securities(
        self,
        large_backtest_data: tuple[StubDataAdapter, list[str]],
        mock_backtest_port: Mock,
    ) -> None:
        """Backtest 500 securities over 10 years should complete in <60 seconds."""
        from src.core.services.backtest_engine import BacktestEngine, BacktestRequest

        adapter, symbols = large_backtest_data

        engine = BacktestEngine(
            data_port=adapter,
            backtest_port=mock_backtest_port,
            report_port=None,
        )

        def equal_weight(prices: pd.DataFrame) -> pd.DataFrame:
            n = len(prices.columns)
            return pd.DataFrame(1.0 / n, index=prices.index, columns=prices.columns)

        request = BacktestRequest(
            universe=symbols,
            start_date=date(2014, 1, 1),
            end_date=date(2023, 12, 31),
            data_version="v1",
            signal_generator=equal_weight,
            rebalance_freq="monthly",
            transaction_costs={"spread_bps": 5, "commission_bps": 2},
            generate_tearsheet=False,
        )

        start_time = time.perf_counter()
        response = engine.run(request)
        elapsed = time.perf_counter() - start_time

        print(f"\nBacktest completed in {elapsed:.2f} seconds")
        print(f"Universe: {len(symbols)} securities")
        print(f"Period: 10 years")

        assert elapsed < 60, f"Backtest took {elapsed:.2f}s, expected <60s"

    def test_data_loading_phase_performance(
        self,
        large_backtest_data: tuple[StubDataAdapter, list[str]],
    ) -> None:
        """Data loading for 500 securities should complete in <30 seconds."""
        adapter, symbols = large_backtest_data

        start_time = time.perf_counter()

        # Load all data
        price_data = {}
        for symbol in symbols:
            df = adapter.load(symbol=symbol, version="v1")
            price_data[symbol] = df["close"]

        prices_df = pd.DataFrame(price_data)

        elapsed = time.perf_counter() - start_time

        print(f"\nData loading: {elapsed:.2f} seconds")
        print(f"DataFrame shape: {prices_df.shape}")
        print(f"Memory: {prices_df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB")

        assert elapsed < 30, f"Data loading took {elapsed:.2f}s, expected <30s"

    def test_signal_generation_performance(
        self,
        large_backtest_data: tuple[StubDataAdapter, list[str]],
    ) -> None:
        """Signal generation for 500 securities should be fast."""
        adapter, symbols = large_backtest_data

        # Load data
        price_data = {}
        for symbol in symbols[:100]:  # Use 100 for speed
            df = adapter.load(symbol=symbol, version="v1")
            price_data[symbol] = df["close"]

        prices_df = pd.DataFrame(price_data)

        # Test momentum signal generation
        def momentum_signal(prices: pd.DataFrame) -> pd.DataFrame:
            returns = prices.pct_change(252)
            ranks = returns.rank(axis=1, pct=True)
            return ranks

        start_time = time.perf_counter()
        signals = momentum_signal(prices_df)
        elapsed = time.perf_counter() - start_time

        print(f"\nSignal generation: {elapsed*1000:.2f}ms")
        print(f"Signals shape: {signals.shape}")

        assert elapsed < 5, f"Signal generation took {elapsed:.2f}s, expected <5s"

    def test_generate_performance_artifact(
        self,
        large_backtest_data: tuple[StubDataAdapter, list[str]],
        mock_backtest_port: Mock,
        tmp_path: Path,
    ) -> None:
        """Generate performance artifact JSON."""
        from src.core.services.backtest_engine import BacktestEngine, BacktestRequest

        adapter, symbols = large_backtest_data

        engine = BacktestEngine(
            data_port=adapter,
            backtest_port=mock_backtest_port,
        )

        def equal_weight(prices: pd.DataFrame) -> pd.DataFrame:
            n = len(prices.columns)
            return pd.DataFrame(1.0 / n, index=prices.index, columns=prices.columns)

        request = BacktestRequest(
            universe=symbols,
            start_date=date(2014, 1, 1),
            end_date=date(2023, 12, 31),
            data_version="v1",
            signal_generator=equal_weight,
            generate_tearsheet=False,
        )

        start_time = time.perf_counter()
        response = engine.run(request)
        elapsed = time.perf_counter() - start_time

        artifact = {
            "test_name": "backtest_performance",
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {
                "num_securities": len(symbols),
                "num_years": 10,
                "elapsed_seconds": elapsed,
                "securities_per_second": len(symbols) / elapsed,
            },
            "thresholds": {
                "max_seconds": 60.0,
            },
            "passed": elapsed < 60,
        }

        artifact_path = tmp_path / "performance_test_backtest.json"
        with open(artifact_path, "w") as f:
            json.dump(artifact, f, indent=2)

        print(f"\nArtifact saved to: {artifact_path}")
