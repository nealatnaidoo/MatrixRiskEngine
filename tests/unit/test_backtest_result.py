"""Unit tests for BacktestResult domain object."""

import pytest
import pandas as pd
from datetime import date

from src.core.domain.backtest_result import BacktestResult, BacktestConfig


class TestBacktestConfig:
    """Test BacktestConfig dataclass."""

    def test_config_creation(self) -> None:
        """BacktestConfig should be created with required fields."""
        config = BacktestConfig(
            data_version="v20200101_test",
            start_date=date(2015, 1, 1),
            end_date=date(2020, 1, 1),
            universe=("AAPL", "MSFT", "GOOGL"),
            rebalance_freq="monthly",
            transaction_costs={"spread_bps": 5, "commission_bps": 2},
            random_seed=42,
        )

        assert config.data_version == "v20200101_test"
        assert len(config.universe) == 3
        assert config.random_seed == 42

    def test_config_to_dict(self) -> None:
        """to_dict should return serializable dictionary."""
        config = BacktestConfig(
            data_version="v20200101_test",
            start_date=date(2015, 1, 1),
            end_date=date(2020, 1, 1),
            universe=("AAPL",),
            rebalance_freq="monthly",
        )

        result = config.to_dict()

        assert result["data_version"] == "v20200101_test"
        assert result["start_date"] == "2015-01-01"
        assert result["universe"] == ["AAPL"]


class TestBacktestResultInvariants:
    """Test BacktestResult invariant enforcement."""

    @pytest.fixture
    def valid_config(self) -> BacktestConfig:
        """Create valid config for testing."""
        return BacktestConfig(
            data_version="v20200101_test",
            start_date=date(2020, 1, 1),
            end_date=date(2020, 1, 31),
            universe=("AAPL",),
            rebalance_freq="daily",
        )

    def test_valid_backtest_result_creation(self, valid_config: BacktestConfig) -> None:
        """Valid BacktestResult should be created without errors."""
        dates = pd.date_range("2020-01-02", periods=22, freq="B")
        returns = pd.Series([0.01] * 22, index=dates, name="returns")
        trades = pd.DataFrame({
            "timestamp": ["2020-01-02"],
            "symbol": ["AAPL"],
            "quantity": [100],
            "price": [300.0],
            "cost": [3.0],
        })
        positions = pd.DataFrame({
            "date": ["2020-01-02"],
            "symbol": ["AAPL"],
            "position": [100],
        })

        result = BacktestResult(
            returns=returns,
            trades=trades,
            positions=positions,
            metrics={"sharpe_ratio": 1.5, "max_drawdown": -0.10},
            config=valid_config,
        )

        assert result.num_trades == 1
        assert result.sharpe_ratio == 1.5

    def test_non_datetime_index_raises(self, valid_config: BacktestConfig) -> None:
        """Returns without DatetimeIndex should raise ValueError."""
        returns = pd.Series([0.01, 0.02], index=[0, 1])  # Integer index

        with pytest.raises(ValueError, match="DatetimeIndex"):
            BacktestResult(
                returns=returns,
                trades=pd.DataFrame(columns=["timestamp", "symbol", "quantity", "price"]),
                positions=pd.DataFrame(),
                metrics={},
                config=valid_config,
            )

    def test_unsorted_returns_raises(self, valid_config: BacktestConfig) -> None:
        """Unsorted returns index should raise ValueError."""
        dates = pd.DatetimeIndex(["2020-01-03", "2020-01-02", "2020-01-04"])
        returns = pd.Series([0.01, 0.02, 0.03], index=dates)

        with pytest.raises(ValueError, match="sorted"):
            BacktestResult(
                returns=returns,
                trades=pd.DataFrame(columns=["timestamp", "symbol", "quantity", "price"]),
                positions=pd.DataFrame(),
                metrics={},
                config=valid_config,
            )

    def test_missing_trade_columns_raises(self, valid_config: BacktestConfig) -> None:
        """Trades missing required columns should raise ValueError."""
        dates = pd.date_range("2020-01-02", periods=5, freq="B")
        returns = pd.Series([0.01] * 5, index=dates)
        trades = pd.DataFrame({"timestamp": [], "symbol": []})  # Missing quantity, price

        with pytest.raises(ValueError, match="missing columns"):
            BacktestResult(
                returns=returns,
                trades=trades,
                positions=pd.DataFrame(),
                metrics={},
                config=valid_config,
            )

    def test_trade_before_backtest_start_raises(self, valid_config: BacktestConfig) -> None:
        """Trade before backtest start should raise ValueError."""
        dates = pd.date_range("2020-01-02", periods=5, freq="B")
        returns = pd.Series([0.01] * 5, index=dates)
        trades = pd.DataFrame({
            "timestamp": ["2019-12-15"],  # Before start
            "symbol": ["AAPL"],
            "quantity": [100],
            "price": [300.0],
        })

        with pytest.raises(ValueError, match="before backtest start"):
            BacktestResult(
                returns=returns,
                trades=trades,
                positions=pd.DataFrame(),
                metrics={},
                config=valid_config,
            )


class TestBacktestResultMethods:
    """Test BacktestResult methods."""

    @pytest.fixture
    def sample_result(self) -> BacktestResult:
        """Create sample BacktestResult for testing."""
        config = BacktestConfig(
            data_version="v20200101_test",
            start_date=date(2020, 1, 1),
            end_date=date(2020, 1, 31),
            universe=("AAPL",),
            rebalance_freq="daily",
        )

        dates = pd.date_range("2020-01-02", periods=22, freq="B")
        returns = pd.Series([0.01] * 22, index=dates, name="returns")
        trades = pd.DataFrame({
            "timestamp": ["2020-01-02", "2020-01-15"],
            "symbol": ["AAPL", "AAPL"],
            "quantity": [100, -50],
            "price": [300.0, 310.0],
            "cost": [3.0, 1.5],
        })

        return BacktestResult(
            returns=returns,
            trades=trades,
            positions=pd.DataFrame(columns=["date", "symbol", "position"]),
            metrics={
                "sharpe_ratio": 1.5,
                "max_drawdown": -0.10,
                "win_rate": 0.55,
                "total_return": 0.22,
            },
            config=config,
        )

    def test_total_return(self, sample_result: BacktestResult) -> None:
        """total_return should calculate cumulative return."""
        # 22 days of 1% return: (1.01)^22 - 1 ≈ 0.245
        assert sample_result.total_return > 0.24

    def test_num_trades(self, sample_result: BacktestResult) -> None:
        """num_trades should return trade count."""
        assert sample_result.num_trades == 2

    def test_sharpe_ratio(self, sample_result: BacktestResult) -> None:
        """sharpe_ratio property should return metric."""
        assert sample_result.sharpe_ratio == 1.5

    def test_max_drawdown(self, sample_result: BacktestResult) -> None:
        """max_drawdown property should return metric."""
        assert sample_result.max_drawdown == -0.10

    def test_get_metric(self, sample_result: BacktestResult) -> None:
        """get_metric should return metric by name."""
        assert sample_result.get_metric("win_rate") == 0.55
        assert sample_result.get_metric("unknown") is None

    def test_to_dict(self, sample_result: BacktestResult) -> None:
        """to_dict should return serializable dictionary."""
        result = sample_result.to_dict()

        assert result["num_trades"] == 2
        assert result["metrics"]["sharpe_ratio"] == 1.5
        assert "config" in result

    def test_create_empty(self) -> None:
        """create_empty should return empty result with zero returns."""
        config = BacktestConfig(
            data_version="v20200101_test",
            start_date=date(2020, 1, 1),
            end_date=date(2020, 1, 31),
            universe=("AAPL",),
            rebalance_freq="daily",
        )

        result = BacktestResult.create_empty(config)

        assert result.num_trades == 0
        assert result.total_return == 0.0
        assert len(result.returns) > 0  # Has business days
