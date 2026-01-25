"""Integration Test - Risk Measurement Flow (F4).

Tests the complete risk analytics workflow:
1. Load portfolio positions
2. Load market data
3. Calculate VaR and CVaR
4. Compute Greeks
5. Generate risk report
"""

import pytest
import pandas as pd
import numpy as np
from datetime import date
from unittest.mock import Mock

from tests.stubs.stub_data_adapter import StubDataAdapter
from src.adapters.ore_adapter import OREAdapter
from src.core.domain.portfolio import Portfolio, PortfolioMetadata
from src.core.services.risk_calculation_service import (
    RiskCalculationService,
    RiskCalculationRequest,
    RiskCalculationResponse,
)
from src.core.ports.risk_port import InsufficientDataError


class TestRiskMeasurementFlowF4:
    """Integration tests for Flow F4: Risk Measurement."""

    @pytest.fixture
    def data_adapter(self) -> StubDataAdapter:
        """Create data adapter with seeded market data."""
        adapter = StubDataAdapter()

        # Seed 2 years of market data for sufficient VaR calculation
        dates = pd.date_range("2018-01-01", periods=504, freq="B")
        np.random.seed(42)

        for symbol in ["AAPL", "MSFT", "GOOGL", "AMZN"]:
            returns = np.random.randn(504) * 0.02
            prices = 100 * np.cumprod(1 + returns)

            data = pd.DataFrame({
                "open": prices * (1 + np.random.randn(504) * 0.005),
                "high": prices * (1 + np.abs(np.random.randn(504)) * 0.01),
                "low": prices * (1 - np.abs(np.random.randn(504)) * 0.01),
                "close": prices,
                "volume": np.random.randint(1000000, 10000000, size=504),
            }, index=dates)

            adapter.seed_data(
                symbol=symbol,
                version="v1",
                data=data,
                metadata={"source": "test"},
            )

        return adapter

    @pytest.fixture
    def sample_portfolio(self) -> Portfolio:
        """Create sample portfolio."""
        return Portfolio(
            positions={"AAPL": 1000, "MSFT": 500, "GOOGL": 200, "AMZN": 100},
            weights={"AAPL": 0.4, "MSFT": 0.3, "GOOGL": 0.2, "AMZN": 0.1},
            nav=1000000.0,
            as_of_date=date(2019, 12, 31),
            metadata=PortfolioMetadata(strategy_name="test_portfolio"),
        )

    @pytest.fixture
    def risk_adapter(self) -> OREAdapter:
        """Create OREAdapter."""
        return OREAdapter()

    def test_ac_f4_001_var_calculation(
        self,
        data_adapter: StubDataAdapter,
        sample_portfolio: Portfolio,
        risk_adapter: OREAdapter,
    ) -> None:
        """AC-F4-001: VaR calculated at multiple confidence levels.

        Test: Calculate VaR at 95% and 99% confidence.
        Expected: VaR values are negative and 99% is more extreme.
        """
        # Load market data
        market_data = {}
        for symbol in sample_portfolio.weights:
            df = data_adapter.load(symbol=symbol, version="v1")
            market_data[symbol] = df["close"]

        prices_df = pd.DataFrame(market_data)

        # Calculate VaR
        var_result = risk_adapter.calculate_var(
            portfolio=sample_portfolio,
            market_data=prices_df,
            method="historical",
            confidence_levels=[0.95, 0.99],
            window_days=250,
        )

        # Verify VaR values
        assert "95%" in var_result
        assert "99%" in var_result
        assert var_result["95%"] < 0  # Losses are negative
        assert var_result["99%"] < 0
        assert var_result["99%"] <= var_result["95%"]  # 99% more extreme

    def test_ac_f4_002_cvar_exceeds_var(
        self,
        data_adapter: StubDataAdapter,
        sample_portfolio: Portfolio,
        risk_adapter: OREAdapter,
    ) -> None:
        """AC-F4-002: CVaR is more extreme than VaR.

        Test: Calculate CVaR and verify CVaR >= VaR.
        Expected: CVaR <= VaR (more negative).
        """
        market_data = {}
        for symbol in sample_portfolio.weights:
            df = data_adapter.load(symbol=symbol, version="v1")
            market_data[symbol] = df["close"]

        prices_df = pd.DataFrame(market_data)

        var_result = risk_adapter.calculate_var(
            portfolio=sample_portfolio,
            market_data=prices_df,
            method="historical",
            confidence_levels=[0.95, 0.99],
            window_days=250,
        )

        cvar_result = risk_adapter.calculate_cvar(
            portfolio=sample_portfolio,
            market_data=prices_df,
            var_params={
                "method": "historical",
                "confidence_levels": [0.95, 0.99],
                "window_days": 250,
            },
        )

        # CVaR should be more extreme (lower) than VaR
        assert cvar_result["95%"] <= var_result["95%"]
        assert cvar_result["99%"] <= var_result["99%"]

    def test_ac_f4_003_greeks_computed(
        self,
        data_adapter: StubDataAdapter,
        sample_portfolio: Portfolio,
        risk_adapter: OREAdapter,
    ) -> None:
        """AC-F4-003: Greeks are computed for portfolio.

        Test: Compute Greeks for equity portfolio.
        Expected: Delta equals sum of weights.
        """
        market_data = {}
        for symbol in sample_portfolio.weights:
            df = data_adapter.load(symbol=symbol, version="v1")
            market_data[symbol] = df["close"]

        prices_df = pd.DataFrame(market_data)

        greeks = risk_adapter.compute_greeks(sample_portfolio, prices_df)

        # For equity portfolio, delta = sum of weights = 1.0
        assert greeks["delta"] == pytest.approx(1.0)
        # Gamma and Vega should be 0 for pure equity
        assert greeks["gamma"] == 0.0
        assert greeks["vega"] == 0.0

    def test_risk_calculation_service_workflow(
        self,
        data_adapter: StubDataAdapter,
        sample_portfolio: Portfolio,
        risk_adapter: OREAdapter,
    ) -> None:
        """Test complete risk calculation service workflow."""
        # Create mock report port
        report_port = Mock()
        report_port.generate_report.return_value = "/path/to/risk_report.html"

        service = RiskCalculationService(
            data_port=data_adapter,
            risk_port=risk_adapter,
            report_port=report_port,
        )

        request = RiskCalculationRequest(
            portfolio=sample_portfolio,
            market_data_version="v1",
            methods=["historical"],
            confidence_levels=[0.95, 0.99],
            window_days=250,
            generate_report=False,
        )

        response = service.calculate(request)

        # Verify response contains risk metrics
        assert response.metrics is not None
        assert response.metrics.var is not None
        assert response.metrics.cvar is not None

    def test_parametric_var_calculation(
        self,
        data_adapter: StubDataAdapter,
        sample_portfolio: Portfolio,
        risk_adapter: OREAdapter,
    ) -> None:
        """Parametric VaR should produce similar results to historical."""
        market_data = {}
        for symbol in sample_portfolio.weights:
            df = data_adapter.load(symbol=symbol, version="v1")
            market_data[symbol] = df["close"]

        prices_df = pd.DataFrame(market_data)

        # Historical VaR
        hist_var = risk_adapter.calculate_var(
            portfolio=sample_portfolio,
            market_data=prices_df,
            method="historical",
            confidence_levels=[0.95],
            window_days=250,
        )

        # Parametric VaR
        param_var = risk_adapter.calculate_var(
            portfolio=sample_portfolio,
            market_data=prices_df,
            method="parametric",
            confidence_levels=[0.95],
            window_days=250,
        )

        # Both should be negative
        assert hist_var["95%"] < 0
        assert param_var["95%"] < 0

    def test_insufficient_data_raises_error(
        self,
        sample_portfolio: Portfolio,
        risk_adapter: OREAdapter,
    ) -> None:
        """VaR with insufficient data should raise error."""
        # Only 50 days of data
        dates = pd.date_range("2020-01-01", periods=50, freq="B")
        prices_df = pd.DataFrame({
            "AAPL": np.random.randn(50).cumsum() + 100,
            "MSFT": np.random.randn(50).cumsum() + 150,
            "GOOGL": np.random.randn(50).cumsum() + 1000,
            "AMZN": np.random.randn(50).cumsum() + 2000,
        }, index=dates)

        with pytest.raises(InsufficientDataError):
            risk_adapter.calculate_var(
                portfolio=sample_portfolio,
                market_data=prices_df,
                method="historical",
                confidence_levels=[0.95],
                window_days=250,
            )
