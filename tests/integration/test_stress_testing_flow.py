"""Integration Test - Stress Testing Flow (F5).

Tests the complete stress testing workflow:
1. Load portfolio positions
2. Load stress scenarios
3. Apply shocks to market data
4. Calculate stressed P&L
5. Generate stress report
"""

import pytest
import pandas as pd
import numpy as np
from datetime import date
from unittest.mock import Mock

from tests.stubs.stub_data_adapter import StubDataAdapter
from src.adapters.ore_adapter import OREAdapter
from src.core.domain.portfolio import Portfolio, PortfolioMetadata
from src.core.domain.stress_scenario import StressScenario
from src.core.services.stress_testing_service import (
    StressTestingService,
    StressTestRequest,
    StressTestResponse,
)


class TestStressTestingFlowF5:
    """Integration tests for Flow F5: Stress Testing."""

    @pytest.fixture
    def data_adapter(self) -> StubDataAdapter:
        """Create data adapter with seeded market data."""
        adapter = StubDataAdapter()

        dates = pd.date_range("2020-01-01", periods=252, freq="B")
        np.random.seed(42)

        for symbol in ["AAPL", "MSFT", "GOOGL"]:
            prices = 100 + np.cumsum(np.random.randn(252) * 2)

            data = pd.DataFrame({
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
    def sample_portfolio(self) -> Portfolio:
        """Create sample portfolio."""
        return Portfolio(
            positions={"AAPL": 100, "MSFT": 50, "GOOGL": 25},
            weights={"AAPL": 0.5, "MSFT": 0.3, "GOOGL": 0.2},
            nav=100000.0,
            as_of_date=date(2020, 12, 31),
        )

    @pytest.fixture
    def stress_scenarios(self) -> list[StressScenario]:
        """Create standard stress scenarios."""
        return [
            StressScenario(
                name="2008 Financial Crisis",
                shocks={"equity_all": -0.40},
                description="40% equity market decline",
                date_calibrated=date(2008, 10, 1),
            ),
            StressScenario(
                name="COVID Crash",
                shocks={"equity_all": -0.35},
                description="35% rapid equity decline",
                date_calibrated=date(2020, 3, 1),
            ),
            StressScenario(
                name="Tech Correction",
                shocks={"AAPL": -0.20, "MSFT": -0.20, "GOOGL": -0.25},
                description="Tech sector correction",
                date_calibrated=date(2022, 1, 1),
            ),
            StressScenario(
                name="Mild Pullback",
                shocks={"equity_all": -0.10},
                description="10% market pullback",
                date_calibrated=date(2020, 1, 1),
            ),
        ]

    @pytest.fixture
    def risk_adapter(self) -> OREAdapter:
        """Create OREAdapter."""
        return OREAdapter()

    def test_ac_f5_001_scenarios_applied(
        self,
        data_adapter: StubDataAdapter,
        sample_portfolio: Portfolio,
        stress_scenarios: list[StressScenario],
        risk_adapter: OREAdapter,
    ) -> None:
        """AC-F5-001: All scenarios are applied correctly.

        Test: Apply 4 stress scenarios.
        Expected: 4 stress results returned.
        """
        # Load market data
        market_data = {}
        for symbol in sample_portfolio.weights:
            df = data_adapter.load(symbol=symbol, version="v1")
            market_data[symbol] = df["close"]

        prices_df = pd.DataFrame(market_data)

        results = risk_adapter.stress_test(
            portfolio=sample_portfolio,
            market_data=prices_df,
            scenarios=stress_scenarios,
        )

        # Should have one row per scenario
        assert len(results) == 4
        assert list(results["scenario"]) == [
            "2008 Financial Crisis",
            "COVID Crash",
            "Tech Correction",
            "Mild Pullback",
        ]

    def test_ac_f5_002_pnl_calculated(
        self,
        data_adapter: StubDataAdapter,
        sample_portfolio: Portfolio,
        stress_scenarios: list[StressScenario],
        risk_adapter: OREAdapter,
    ) -> None:
        """AC-F5-002: Stressed P&L is calculated for each scenario.

        Test: Calculate stressed P&L.
        Expected: P&L is negative for downside scenarios.
        """
        market_data = {}
        for symbol in sample_portfolio.weights:
            df = data_adapter.load(symbol=symbol, version="v1")
            market_data[symbol] = df["close"]

        prices_df = pd.DataFrame(market_data)

        results = risk_adapter.stress_test(
            portfolio=sample_portfolio,
            market_data=prices_df,
            scenarios=stress_scenarios,
        )

        # All scenarios are negative shocks, so P&L should be negative
        for _, row in results.iterrows():
            assert row["pnl"] < 0, f"Scenario {row['scenario']} should have negative P&L"

    def test_ac_f5_003_base_vs_stressed_npv(
        self,
        data_adapter: StubDataAdapter,
        sample_portfolio: Portfolio,
        stress_scenarios: list[StressScenario],
        risk_adapter: OREAdapter,
    ) -> None:
        """AC-F5-003: Base and stressed NPV are provided.

        Test: Verify base_npv and stressed_npv are calculated.
        Expected: stressed_npv < base_npv for downside scenarios.
        """
        market_data = {}
        for symbol in sample_portfolio.weights:
            df = data_adapter.load(symbol=symbol, version="v1")
            market_data[symbol] = df["close"]

        prices_df = pd.DataFrame(market_data)

        results = risk_adapter.stress_test(
            portfolio=sample_portfolio,
            market_data=prices_df,
            scenarios=stress_scenarios,
        )

        for _, row in results.iterrows():
            assert row["base_npv"] > 0
            assert row["stressed_npv"] < row["base_npv"]
            assert row["pnl"] == row["stressed_npv"] - row["base_npv"]

    def test_stress_testing_service_workflow(
        self,
        data_adapter: StubDataAdapter,
        sample_portfolio: Portfolio,
        stress_scenarios: list[StressScenario],
        risk_adapter: OREAdapter,
    ) -> None:
        """Test complete stress testing service workflow."""
        # Load market data
        market_data = {}
        for symbol in sample_portfolio.weights:
            df = data_adapter.load(symbol=symbol, version="v1")
            market_data[symbol] = df["close"]

        prices_df = pd.DataFrame(market_data)

        service = StressTestingService(
            risk_port=risk_adapter,
        )

        request = StressTestRequest(
            portfolio=sample_portfolio,
            scenarios=stress_scenarios,
            market_data=prices_df,
            generate_report=False,
        )

        response = service.run(request)

        # Verify response
        assert response.results is not None
        assert len(response.results) == 4

        # Find worst scenario
        worst_pnl = min(r.pnl for r in response.results)
        assert worst_pnl < 0

    def test_percentage_change_calculation(
        self,
        data_adapter: StubDataAdapter,
        sample_portfolio: Portfolio,
        risk_adapter: OREAdapter,
    ) -> None:
        """Percentage change should match shock magnitude."""
        market_data = {}
        for symbol in sample_portfolio.weights:
            df = data_adapter.load(symbol=symbol, version="v1")
            market_data[symbol] = df["close"]

        prices_df = pd.DataFrame(market_data)

        # Apply 10% drop scenario
        scenarios = [
            StressScenario(
                name="10% Drop",
                shocks={"equity_all": -0.10},
                description="10% drop",
                date_calibrated=date.today(),
            ),
        ]

        results = risk_adapter.stress_test(
            portfolio=sample_portfolio,
            market_data=prices_df,
            scenarios=scenarios,
        )

        # Percentage change should be approximately -10%
        pct_change = results["pct_change"].iloc[0]
        assert pct_change == pytest.approx(-0.10, rel=0.01)

    def test_individual_stock_shocks(
        self,
        data_adapter: StubDataAdapter,
        sample_portfolio: Portfolio,
        risk_adapter: OREAdapter,
    ) -> None:
        """Individual stock shocks should only affect that stock."""
        market_data = {}
        for symbol in sample_portfolio.weights:
            df = data_adapter.load(symbol=symbol, version="v1")
            market_data[symbol] = df["close"]

        prices_df = pd.DataFrame(market_data)

        # Only shock AAPL
        scenarios = [
            StressScenario(
                name="AAPL Only",
                shocks={"AAPL": -0.50},
                description="50% AAPL drop",
                date_calibrated=date.today(),
            ),
        ]

        results = risk_adapter.stress_test(
            portfolio=sample_portfolio,
            market_data=prices_df,
            scenarios=scenarios,
        )

        # P&L should be negative but less than 50% (AAPL is 50% of portfolio)
        pct_change = results["pct_change"].iloc[0]
        assert pct_change < 0
        # AAPL is 50% weight with 50% shock = -25% portfolio impact
        assert pct_change == pytest.approx(-0.25, rel=0.1)
