"""Unit tests for BacktestEngine service."""

import pytest
import pandas as pd
import numpy as np
from datetime import date
from unittest.mock import Mock, MagicMock

from src.core.services.backtest_engine import (
    BacktestEngine,
    BacktestRequest,
    BacktestResponse,
)
from src.core.domain.backtest_result import BacktestConfig, BacktestResult


class TestBacktestEngineValidation:
    """Test request validation."""

    @pytest.fixture
    def mock_ports(self) -> tuple[Mock, Mock, Mock]:
        """Create mock ports for testing."""
        data_port = Mock()
        backtest_port = Mock()
        report_port = Mock()
        return data_port, backtest_port, report_port

    def test_empty_universe_raises(self, mock_ports: tuple[Mock, Mock, Mock]) -> None:
        """Empty universe should raise ValueError."""
        data_port, backtest_port, report_port = mock_ports
        engine = BacktestEngine(data_port, backtest_port, report_port)

        request = BacktestRequest(
            universe=[],  # Empty
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
            data_version="v1",
            signal_generator=lambda x: x,
        )

        with pytest.raises(ValueError, match="empty"):
            engine.run(request)

    def test_invalid_dates_raises(self, mock_ports: tuple[Mock, Mock, Mock]) -> None:
        """Start date >= end date should raise ValueError."""
        data_port, backtest_port, report_port = mock_ports
        engine = BacktestEngine(data_port, backtest_port, report_port)

        request = BacktestRequest(
            universe=["AAPL"],
            start_date=date(2020, 12, 31),
            end_date=date(2020, 1, 1),  # Before start
            data_version="v1",
            signal_generator=lambda x: x,
        )

        with pytest.raises(ValueError, match="before"):
            engine.run(request)

    def test_invalid_rebalance_freq_raises(
        self, mock_ports: tuple[Mock, Mock, Mock]
    ) -> None:
        """Invalid rebalance frequency should raise ValueError."""
        data_port, backtest_port, report_port = mock_ports
        engine = BacktestEngine(data_port, backtest_port, report_port)

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


class TestBacktestEngineWorkflow:
    """Test complete backtest workflow."""

    @pytest.fixture
    def configured_engine(self) -> tuple[BacktestEngine, Mock, Mock]:
        """Create engine with configured mock ports."""
        data_port = Mock()
        backtest_port = Mock()
        report_port = Mock()

        # Configure data port to return price data
        dates = pd.date_range("2020-01-01", periods=252, freq="B")
        price_df = pd.DataFrame(
            {"close": [100 + i * 0.1 for i in range(252)]},
            index=dates,
        )
        data_port.load.return_value = price_df

        # Configure backtest port to return result
        config = BacktestConfig(
            data_version="v1",
            start_date=date(2020, 1, 2),
            end_date=date(2020, 12, 30),
            universe=("AAPL",),
            rebalance_freq="monthly",
        )
        returns = pd.Series(
            np.random.randn(250) * 0.02,
            index=dates[2:],
        )
        trades = pd.DataFrame({
            "timestamp": [dates[10]],
            "symbol": ["AAPL"],
            "quantity": [100],
            "price": [101.0],
            "cost": [1.0],
        })
        result = BacktestResult(
            returns=returns,
            trades=trades,
            positions=pd.DataFrame(columns=["date", "symbol", "position"]),
            metrics={"sharpe_ratio": 1.5, "max_drawdown": -0.10},
            config=config,
        )
        backtest_port.simulate.return_value = result

        # Configure report port
        report_port.generate_report.return_value = "/path/to/tearsheet.html"

        engine = BacktestEngine(data_port, backtest_port, report_port)
        return engine, data_port, backtest_port

    def test_run_loads_data_for_each_symbol(
        self, configured_engine: tuple[BacktestEngine, Mock, Mock]
    ) -> None:
        """run should load data for each symbol in universe."""
        engine, data_port, _ = configured_engine

        request = BacktestRequest(
            universe=["AAPL", "MSFT"],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
            data_version="v1",
            signal_generator=lambda x: pd.DataFrame(1, index=x.index, columns=x.columns),
            generate_tearsheet=False,
        )

        engine.run(request)

        # Data port should be called for each symbol
        assert data_port.load.call_count == 2

    def test_run_calls_simulate_with_signals(
        self, configured_engine: tuple[BacktestEngine, Mock, Mock]
    ) -> None:
        """run should call simulate with generated signals."""
        engine, _, backtest_port = configured_engine

        def signal_generator(prices: pd.DataFrame) -> pd.DataFrame:
            return pd.DataFrame(1.0, index=prices.index, columns=prices.columns)

        request = BacktestRequest(
            universe=["AAPL"],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
            data_version="v1",
            signal_generator=signal_generator,
            generate_tearsheet=False,
        )

        engine.run(request)

        backtest_port.simulate.assert_called_once()

    def test_run_returns_response_with_metrics(
        self, configured_engine: tuple[BacktestEngine, Mock, Mock]
    ) -> None:
        """run should return response with metrics summary."""
        engine, _, _ = configured_engine

        request = BacktestRequest(
            universe=["AAPL"],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
            data_version="v1",
            signal_generator=lambda x: pd.DataFrame(1, index=x.index, columns=x.columns),
            generate_tearsheet=False,
        )

        response = engine.run(request)

        assert isinstance(response, BacktestResponse)
        assert "sharpe_ratio" in response.metrics_summary
        assert response.result is not None


class TestBacktestEngineSignalGenerator:
    """Test signal generator handling."""

    def test_empty_signals_raises(self) -> None:
        """Empty signals from generator should raise ValueError."""
        data_port = Mock()
        backtest_port = Mock()

        dates = pd.date_range("2020-01-01", periods=10, freq="B")
        data_port.load.return_value = pd.DataFrame(
            {"close": [100] * 10}, index=dates
        )

        engine = BacktestEngine(data_port, backtest_port)

        request = BacktestRequest(
            universe=["AAPL"],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
            data_version="v1",
            signal_generator=lambda x: pd.DataFrame(),  # Empty signals
        )

        with pytest.raises(ValueError, match="empty"):
            engine.run(request)
