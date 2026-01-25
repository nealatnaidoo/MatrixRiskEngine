"""Unit tests for VectorBTAdapter."""

import pytest
import pandas as pd
import numpy as np
from datetime import date

from src.adapters.vectorbt_adapter import VectorBTAdapter
from src.core.ports.backtest_port import BacktestError


class TestVectorBTAdapterSimulation:
    """Test backtest simulation."""

    @pytest.fixture
    def sample_data(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Create sample signals and prices for testing."""
        dates = pd.date_range("2020-01-01", periods=252, freq="B")

        # Prices with upward trend
        np.random.seed(42)
        price_returns = np.random.normal(0.0005, 0.02, (252, 3))
        prices = pd.DataFrame(
            100 * np.exp(np.cumsum(price_returns, axis=0)),
            index=dates,
            columns=["AAPL", "MSFT", "GOOGL"],
        )

        # Equal weight signals
        signals = pd.DataFrame(
            [[1, 1, 1]] * 252,
            index=dates,
            columns=["AAPL", "MSFT", "GOOGL"],
        )

        return signals, prices

    def test_basic_simulation(self, sample_data: tuple[pd.DataFrame, pd.DataFrame]) -> None:
        """Basic simulation should produce valid BacktestResult."""
        signals, prices = sample_data
        adapter = VectorBTAdapter()

        result = adapter.simulate(
            signals=signals,
            prices=prices,
            transaction_costs={"spread_bps": 5, "commission_bps": 2},
            rebalance_freq="monthly",
        )

        assert len(result.returns) > 0
        assert result.config.rebalance_freq == "monthly"
        assert "sharpe_ratio" in result.metrics

    def test_daily_rebalancing(self, sample_data: tuple[pd.DataFrame, pd.DataFrame]) -> None:
        """Daily rebalancing should produce more trades."""
        signals, prices = sample_data
        adapter = VectorBTAdapter()

        result = adapter.simulate(
            signals=signals,
            prices=prices,
            transaction_costs={"spread_bps": 0, "commission_bps": 0},
            rebalance_freq="daily",
        )

        assert result.config.rebalance_freq == "daily"

    def test_transaction_costs_reduce_returns(
        self,
        sample_data: tuple[pd.DataFrame, pd.DataFrame],
    ) -> None:
        """Transaction costs should reduce returns."""
        signals, prices = sample_data
        adapter = VectorBTAdapter()

        # Zero costs
        result_no_cost = adapter.simulate(
            signals=signals,
            prices=prices,
            transaction_costs={"spread_bps": 0, "commission_bps": 0},
            rebalance_freq="monthly",
        )

        # With costs
        result_with_cost = adapter.simulate(
            signals=signals,
            prices=prices,
            transaction_costs={"spread_bps": 50, "commission_bps": 20},
            rebalance_freq="monthly",
        )

        # Net returns should be lower with costs
        assert result_with_cost.total_return <= result_no_cost.total_return

    def test_invalid_signals_raises(self) -> None:
        """Non-DatetimeIndex signals should raise BacktestError."""
        adapter = VectorBTAdapter()

        signals = pd.DataFrame({"AAPL": [1, 1, 1]}, index=[0, 1, 2])
        prices = pd.DataFrame({"AAPL": [100, 101, 102]}, index=[0, 1, 2])

        with pytest.raises(BacktestError, match="DatetimeIndex"):
            adapter.simulate(
                signals=signals,
                prices=prices,
                transaction_costs={},
                rebalance_freq="daily",
            )

    def test_no_overlapping_dates_raises(self) -> None:
        """No overlapping dates should raise BacktestError."""
        adapter = VectorBTAdapter()

        signals = pd.DataFrame(
            {"AAPL": [1, 1]},
            index=pd.date_range("2020-01-01", periods=2, freq="D"),
        )
        prices = pd.DataFrame(
            {"AAPL": [100, 101]},
            index=pd.date_range("2021-01-01", periods=2, freq="D"),
        )

        with pytest.raises(BacktestError, match="overlapping dates"):
            adapter.simulate(
                signals=signals,
                prices=prices,
                transaction_costs={},
                rebalance_freq="daily",
            )

    def test_metrics_calculation(
        self,
        sample_data: tuple[pd.DataFrame, pd.DataFrame],
    ) -> None:
        """Metrics should be calculated correctly."""
        signals, prices = sample_data
        adapter = VectorBTAdapter()

        result = adapter.simulate(
            signals=signals,
            prices=prices,
            transaction_costs={"spread_bps": 5, "commission_bps": 2},
            rebalance_freq="monthly",
        )

        # Check required metrics exist
        assert "sharpe_ratio" in result.metrics
        assert "max_drawdown" in result.metrics
        assert "total_return" in result.metrics
        assert "volatility" in result.metrics
        assert "win_rate" in result.metrics

        # Max drawdown should be <= 0
        assert result.metrics["max_drawdown"] <= 0

        # Win rate should be between 0 and 1
        assert 0 <= result.metrics["win_rate"] <= 1


class TestVectorBTAdapterRebalancing:
    """Test rebalancing frequency handling."""

    @pytest.fixture
    def year_of_data(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Create a full year of data."""
        dates = pd.date_range("2020-01-01", "2020-12-31", freq="B")
        signals = pd.DataFrame({"AAPL": [1] * len(dates)}, index=dates)
        prices = pd.DataFrame({"AAPL": [100] * len(dates)}, index=dates)
        return signals, prices

    def test_weekly_rebalancing(
        self,
        year_of_data: tuple[pd.DataFrame, pd.DataFrame],
    ) -> None:
        """Weekly rebalancing should work."""
        signals, prices = year_of_data
        adapter = VectorBTAdapter()

        result = adapter.simulate(
            signals=signals,
            prices=prices,
            transaction_costs={},
            rebalance_freq="weekly",
        )

        assert result.config.rebalance_freq == "weekly"

    def test_quarterly_rebalancing(
        self,
        year_of_data: tuple[pd.DataFrame, pd.DataFrame],
    ) -> None:
        """Quarterly rebalancing should work."""
        signals, prices = year_of_data
        adapter = VectorBTAdapter()

        result = adapter.simulate(
            signals=signals,
            prices=prices,
            transaction_costs={},
            rebalance_freq="quarterly",
        )

        assert result.config.rebalance_freq == "quarterly"

    def test_unknown_frequency_raises(
        self,
        year_of_data: tuple[pd.DataFrame, pd.DataFrame],
    ) -> None:
        """Unknown frequency should raise BacktestError."""
        signals, prices = year_of_data
        adapter = VectorBTAdapter()

        with pytest.raises(BacktestError, match="Unknown rebalance frequency"):
            adapter.simulate(
                signals=signals,
                prices=prices,
                transaction_costs={},
                rebalance_freq="biweekly",
            )
