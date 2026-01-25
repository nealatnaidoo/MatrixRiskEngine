"""Unit tests for OREAdapter."""

import pytest
import pandas as pd
import numpy as np
from datetime import date

from src.adapters.ore_adapter import OREAdapter
from src.core.domain.portfolio import Portfolio, PortfolioMetadata
from src.core.domain.stress_scenario import StressScenario
from src.core.ports.risk_port import InsufficientDataError


class TestOREAdapterValuation:
    """Test portfolio valuation."""

    @pytest.fixture
    def sample_portfolio(self) -> Portfolio:
        """Create sample portfolio."""
        return Portfolio(
            positions={"AAPL": 100, "MSFT": 50, "GOOGL": 25},
            weights={"AAPL": 0.5, "MSFT": 0.3, "GOOGL": 0.2},
            nav=100000.0,
            as_of_date=date.today(),
        )

    @pytest.fixture
    def sample_market_data(self) -> pd.DataFrame:
        """Create sample market data."""
        dates = pd.date_range("2020-01-01", periods=252, freq="B")
        np.random.seed(42)

        data = {
            "AAPL": 100 + np.cumsum(np.random.randn(252) * 2),
            "MSFT": 200 + np.cumsum(np.random.randn(252) * 3),
            "GOOGL": 1500 + np.cumsum(np.random.randn(252) * 20),
        }

        return pd.DataFrame(data, index=dates)

    def test_value_portfolio_basic(
        self,
        sample_portfolio: Portfolio,
        sample_market_data: pd.DataFrame,
    ) -> None:
        """value_portfolio should calculate NPV correctly."""
        adapter = OREAdapter()

        npv = adapter.value_portfolio(sample_portfolio, sample_market_data)

        # NPV should be positive
        assert npv > 0

        # Manually calculate expected NPV
        expected = (
            100 * sample_market_data["AAPL"].iloc[-1] +
            50 * sample_market_data["MSFT"].iloc[-1] +
            25 * sample_market_data["GOOGL"].iloc[-1]
        )
        assert abs(npv - expected) < 1e-6


class TestOREAdapterVaR:
    """Test VaR calculations."""

    @pytest.fixture
    def sample_portfolio(self) -> Portfolio:
        """Create sample portfolio."""
        return Portfolio(
            positions={"AAPL": 100, "MSFT": 50},
            weights={"AAPL": 0.6, "MSFT": 0.4},
            nav=100000.0,
            as_of_date=date.today(),
        )

    @pytest.fixture
    def sample_market_data(self) -> pd.DataFrame:
        """Create sample market data with sufficient history."""
        dates = pd.date_range("2019-01-01", periods=500, freq="B")
        np.random.seed(42)

        data = {
            "AAPL": 100 * np.cumprod(1 + np.random.randn(500) * 0.02),
            "MSFT": 150 * np.cumprod(1 + np.random.randn(500) * 0.025),
        }

        return pd.DataFrame(data, index=dates)

    def test_calculate_var_historical(
        self,
        sample_portfolio: Portfolio,
        sample_market_data: pd.DataFrame,
    ) -> None:
        """Historical VaR should return negative values."""
        adapter = OREAdapter()

        var = adapter.calculate_var(
            portfolio=sample_portfolio,
            market_data=sample_market_data,
            method="historical",
            confidence_levels=[0.95, 0.99],
            window_days=250,
        )

        assert "95%" in var
        assert "99%" in var
        # VaR values should be negative (losses)
        assert var["95%"] < 0
        assert var["99%"] < 0
        # 99% VaR should be more extreme than 95%
        assert var["99%"] <= var["95%"]

    def test_calculate_var_parametric(
        self,
        sample_portfolio: Portfolio,
        sample_market_data: pd.DataFrame,
    ) -> None:
        """Parametric VaR should use variance-covariance method."""
        adapter = OREAdapter()

        var = adapter.calculate_var(
            portfolio=sample_portfolio,
            market_data=sample_market_data,
            method="parametric",
            confidence_levels=[0.95, 0.99],
            window_days=250,
        )

        assert "95%" in var
        assert "99%" in var

    def test_calculate_var_insufficient_data(
        self,
        sample_portfolio: Portfolio,
    ) -> None:
        """VaR with insufficient data should raise error."""
        adapter = OREAdapter()

        # Only 50 days of data
        dates = pd.date_range("2020-01-01", periods=50, freq="B")
        short_data = pd.DataFrame({
            "AAPL": np.random.randn(50),
            "MSFT": np.random.randn(50),
        }, index=dates)

        with pytest.raises(InsufficientDataError):
            adapter.calculate_var(
                portfolio=sample_portfolio,
                market_data=short_data,
                method="historical",
                confidence_levels=[0.95],
                window_days=250,
            )

    def test_calculate_var_invalid_confidence(
        self,
        sample_portfolio: Portfolio,
        sample_market_data: pd.DataFrame,
    ) -> None:
        """Invalid confidence level should raise ValueError."""
        adapter = OREAdapter()

        with pytest.raises(ValueError):
            adapter.calculate_var(
                portfolio=sample_portfolio,
                market_data=sample_market_data,
                method="historical",
                confidence_levels=[1.5],  # Invalid
                window_days=250,
            )


class TestOREAdapterCVaR:
    """Test CVaR calculations."""

    @pytest.fixture
    def sample_portfolio(self) -> Portfolio:
        """Create sample portfolio."""
        return Portfolio(
            positions={"AAPL": 100, "MSFT": 50},
            weights={"AAPL": 0.6, "MSFT": 0.4},
            nav=100000.0,
            as_of_date=date.today(),
        )

    @pytest.fixture
    def sample_market_data(self) -> pd.DataFrame:
        """Create sample market data."""
        dates = pd.date_range("2019-01-01", periods=500, freq="B")
        np.random.seed(42)

        data = {
            "AAPL": 100 * np.cumprod(1 + np.random.randn(500) * 0.02),
            "MSFT": 150 * np.cumprod(1 + np.random.randn(500) * 0.025),
        }

        return pd.DataFrame(data, index=dates)

    def test_cvar_more_extreme_than_var(
        self,
        sample_portfolio: Portfolio,
        sample_market_data: pd.DataFrame,
    ) -> None:
        """CVaR should be more extreme (lower) than VaR."""
        adapter = OREAdapter()

        var = adapter.calculate_var(
            portfolio=sample_portfolio,
            market_data=sample_market_data,
            method="historical",
            confidence_levels=[0.95, 0.99],
            window_days=250,
        )

        cvar = adapter.calculate_cvar(
            portfolio=sample_portfolio,
            market_data=sample_market_data,
            var_params={
                "method": "historical",
                "confidence_levels": [0.95, 0.99],
                "window_days": 250,
            },
        )

        # CVaR <= VaR (more negative)
        assert cvar["95%"] <= var["95%"]
        assert cvar["99%"] <= var["99%"]


class TestOREAdapterGreeks:
    """Test Greeks computation."""

    @pytest.fixture
    def sample_portfolio(self) -> Portfolio:
        """Create sample equity portfolio."""
        return Portfolio(
            positions={"AAPL": 100, "MSFT": 50},
            weights={"AAPL": 0.6, "MSFT": 0.4},
            nav=100000.0,
            as_of_date=date.today(),
        )

    @pytest.fixture
    def sample_market_data(self) -> pd.DataFrame:
        """Create sample market data."""
        dates = pd.date_range("2020-01-01", periods=10, freq="B")
        return pd.DataFrame({
            "AAPL": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            "MSFT": [200, 201, 202, 203, 204, 205, 206, 207, 208, 209],
        }, index=dates)

    def test_compute_greeks_equity(
        self,
        sample_portfolio: Portfolio,
        sample_market_data: pd.DataFrame,
    ) -> None:
        """Greeks for equity portfolio should have delta = sum of weights."""
        adapter = OREAdapter()

        greeks = adapter.compute_greeks(sample_portfolio, sample_market_data)

        # Delta should equal sum of weights (1.0 for fully invested)
        assert greeks["delta"] == 1.0

        # Gamma and Vega should be 0 for pure equity
        assert greeks["gamma"] == 0.0
        assert greeks["vega"] == 0.0

        # Duration/Convexity not applicable for equity
        assert greeks["duration"] is None
        assert greeks["convexity"] is None


class TestOREAdapterStressTest:
    """Test stress testing."""

    @pytest.fixture
    def sample_portfolio(self) -> Portfolio:
        """Create sample portfolio."""
        return Portfolio(
            positions={"AAPL": 100, "MSFT": 50, "GOOGL": 25},
            weights={"AAPL": 0.5, "MSFT": 0.3, "GOOGL": 0.2},
            nav=100000.0,
            as_of_date=date.today(),
        )

    @pytest.fixture
    def sample_market_data(self) -> pd.DataFrame:
        """Create sample market data."""
        dates = pd.date_range("2020-01-01", periods=10, freq="B")
        return pd.DataFrame({
            "AAPL": [100] * 10,
            "MSFT": [200] * 10,
            "GOOGL": [1500] * 10,
        }, index=dates)

    def test_stress_test_basic(
        self,
        sample_portfolio: Portfolio,
        sample_market_data: pd.DataFrame,
    ) -> None:
        """Stress test should apply scenarios correctly."""
        adapter = OREAdapter()

        scenarios = [
            StressScenario(
                name="10% Equity Drop",
                shocks={"equity_all": -0.10},
                description="Test scenario with 10% drop",
                date_calibrated=date.today(),
            ),
            StressScenario(
                name="20% Equity Drop",
                shocks={"equity_all": -0.20},
                description="Test scenario with 20% drop",
                date_calibrated=date.today(),
            ),
        ]

        results = adapter.stress_test(
            portfolio=sample_portfolio,
            market_data=sample_market_data,
            scenarios=scenarios,
        )

        assert len(results) == 2
        assert "scenario" in results.columns
        assert "base_npv" in results.columns
        assert "stressed_npv" in results.columns
        assert "pnl" in results.columns

    def test_stress_test_pnl_negative_for_drop(
        self,
        sample_portfolio: Portfolio,
        sample_market_data: pd.DataFrame,
    ) -> None:
        """Stress test with equity drop should show negative P&L."""
        adapter = OREAdapter()

        scenarios = [
            StressScenario(
                name="10% Drop",
                shocks={"equity_all": -0.10},
                description="Test 10% drop",
                date_calibrated=date.today(),
            ),
        ]

        results = adapter.stress_test(
            portfolio=sample_portfolio,
            market_data=sample_market_data,
            scenarios=scenarios,
        )

        # P&L should be negative for a drop
        assert results["pnl"].iloc[0] < 0

    def test_stress_test_multiple_scenarios(
        self,
        sample_portfolio: Portfolio,
        sample_market_data: pd.DataFrame,
    ) -> None:
        """Multiple scenarios should be processed."""
        adapter = OREAdapter()

        scenarios = [
            StressScenario(name="Scenario 1", shocks={"equity_all": -0.05}, description="S1", date_calibrated=date.today()),
            StressScenario(name="Scenario 2", shocks={"equity_all": -0.10}, description="S2", date_calibrated=date.today()),
            StressScenario(name="Scenario 3", shocks={"equity_all": -0.20}, description="S3", date_calibrated=date.today()),
        ]

        results = adapter.stress_test(
            portfolio=sample_portfolio,
            market_data=sample_market_data,
            scenarios=scenarios,
        )

        assert len(results) == 3
        assert list(results["scenario"]) == ["Scenario 1", "Scenario 2", "Scenario 3"]
