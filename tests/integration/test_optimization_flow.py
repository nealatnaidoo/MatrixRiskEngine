"""Integration Test - Optimization Flow (F3).

Tests the complete portfolio optimization workflow:
1. Load alpha signals and risk model
2. Apply constraints
3. Run optimization
4. Generate trade list
"""

import pytest
import pandas as pd
import numpy as np
from datetime import date
from unittest.mock import Mock

from tests.stubs.stub_data_adapter import StubDataAdapter
from src.core.services.optimization_service import (
    OptimizationService,
    OptimizationRequest,
)
from src.core.domain.portfolio import Portfolio, PortfolioMetadata
from src.core.domain.constraint import Constraint, ConstraintType, Bounds

# Check if cvxpy is available
try:
    import cvxpy
    from src.adapters.optimizer_adapter import OptimizerAdapter
    HAS_CVXPY = True
except ImportError:
    HAS_CVXPY = False


@pytest.mark.skipif(not HAS_CVXPY, reason="cvxpy not installed")
class TestOptimizationFlowF3:
    """Integration tests for Flow F3: Portfolio Optimization."""

    @pytest.fixture
    def data_adapter(self) -> StubDataAdapter:
        """Create data adapter with seeded alpha and risk model."""
        adapter = StubDataAdapter()

        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
        dates = pd.date_range("2020-01-01", periods=252, freq="B")

        # Seed alpha signals
        np.random.seed(42)
        alpha_data = pd.DataFrame(
            {s: np.random.randn(252) * 0.01 + 0.001 for s in symbols},
            index=dates,
        )
        adapter.seed_data(
            symbol="alpha_signals",
            version="v1",
            data=alpha_data,
            metadata={"source": "test"},
        )

        # Seed risk model (covariance matrix)
        n = len(symbols)
        random_matrix = np.random.randn(n, n)
        cov_matrix = random_matrix @ random_matrix.T / n * 0.04

        risk_model = pd.DataFrame(
            cov_matrix,
            index=symbols,
            columns=symbols,
        )

        # Store as a single-row DataFrame for simplicity
        risk_df = pd.DataFrame(
            cov_matrix,
            index=symbols,
            columns=symbols,
        )
        # Convert to time series format
        risk_df_ts = pd.DataFrame(index=dates[-1:])
        for sym in symbols:
            risk_df_ts[sym] = risk_model.loc[sym].values.tolist()

        adapter.seed_data(
            symbol="risk_model_v1",
            version="v1",
            data=risk_df_ts,
            metadata={"source": "test"},
        )

        return adapter

    @pytest.fixture
    def optimizer(self) -> "OptimizerAdapter":
        """Create optimizer adapter."""
        return OptimizerAdapter()

    @pytest.fixture
    def current_portfolio(self) -> Portfolio:
        """Create current portfolio."""
        return Portfolio(
            positions={"AAPL": 0.3, "MSFT": 0.3, "GOOGL": 0.2, "AMZN": 0.1, "META": 0.1},
            weights={"AAPL": 0.3, "MSFT": 0.3, "GOOGL": 0.2, "AMZN": 0.1, "META": 0.1},
            nav=1000000.0,
            as_of_date=date(2020, 12, 31),
        )

    def test_ac_f3_001_optimization_produces_valid_weights(
        self,
        data_adapter: StubDataAdapter,
        optimizer: "OptimizerAdapter",
        current_portfolio: Portfolio,
    ) -> None:
        """AC-F3-001: Optimization produces valid portfolio weights.

        Test: Run optimization and verify weights sum to 1.
        """
        service = OptimizationService(data_adapter, optimizer)

        request = OptimizationRequest(
            universe=["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
            alpha_source="alpha_signals",
            risk_model_version="v1",
            constraints=[],
            objective="max_sharpe",
        )

        response = service.optimize(request)

        # Weights should sum to 1
        total_weight = sum(response.target_portfolio.weights.values())
        assert abs(total_weight - 1.0) < 1e-4

    def test_ac_f3_002_constraints_respected(
        self,
        data_adapter: StubDataAdapter,
        optimizer: "OptimizerAdapter",
    ) -> None:
        """AC-F3-002: Constraints are respected in solution.

        Test: Apply 20% position limit and verify.
        """
        service = OptimizationService(data_adapter, optimizer)

        constraints = [
            Constraint(
                type=ConstraintType.POSITION_LIMIT,
                bounds=Bounds(lower=0.0, upper=0.25),
                securities=["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
                name="Max 25% per position",
            ),
        ]

        request = OptimizationRequest(
            universe=["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
            alpha_source="alpha_signals",
            risk_model_version="v1",
            constraints=constraints,
            objective="max_sharpe",
        )

        response = service.optimize(request)

        # All weights should be <= 25%
        for symbol, weight in response.target_portfolio.weights.items():
            assert weight <= 0.25 + 1e-4, f"{symbol} weight {weight} exceeds 25%"

    def test_ac_f3_003_trades_generated(
        self,
        data_adapter: StubDataAdapter,
        optimizer: "OptimizerAdapter",
        current_portfolio: Portfolio,
    ) -> None:
        """AC-F3-003: Trade list is generated from current to target.

        Test: Generate trades with current portfolio.
        """
        service = OptimizationService(data_adapter, optimizer)

        request = OptimizationRequest(
            universe=["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
            alpha_source="alpha_signals",
            risk_model_version="v1",
            constraints=[],
            objective="max_sharpe",
            current_portfolio=current_portfolio,
        )

        response = service.optimize(request)

        # Should have trades
        assert len(response.trades) > 0

        # Trades should have valid structure
        for trade in response.trades:
            assert trade.symbol in ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
            assert trade.side in ("buy", "sell")
            assert trade.quantity > 0
            assert trade.estimated_cost >= 0

    def test_sector_constraint(
        self,
        data_adapter: StubDataAdapter,
        optimizer: "OptimizerAdapter",
    ) -> None:
        """Sector constraints should limit combined weights."""
        service = OptimizationService(data_adapter, optimizer)

        # Limit "tech" sector (AAPL, MSFT, GOOGL) to 50%
        constraints = [
            Constraint(
                type=ConstraintType.SECTOR_LIMIT,
                bounds=Bounds(lower=0.0, upper=0.50),
                securities=["AAPL", "MSFT", "GOOGL"],
                name="Tech max 50%",
            ),
        ]

        request = OptimizationRequest(
            universe=["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
            alpha_source="alpha_signals",
            risk_model_version="v1",
            constraints=constraints,
            objective="max_sharpe",
        )

        response = service.optimize(request)

        tech_weight = sum(
            response.target_portfolio.weights.get(s, 0)
            for s in ["AAPL", "MSFT", "GOOGL"]
        )
        assert tech_weight <= 0.50 + 1e-4

    def test_min_variance_objective(
        self,
        data_adapter: StubDataAdapter,
        optimizer: "OptimizerAdapter",
    ) -> None:
        """Min variance objective should produce valid solution."""
        service = OptimizationService(data_adapter, optimizer)

        request = OptimizationRequest(
            universe=["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
            alpha_source="alpha_signals",
            risk_model_version="v1",
            constraints=[],
            objective="min_variance",
        )

        response = service.optimize(request)

        # Should have valid weights
        total_weight = sum(response.target_portfolio.weights.values())
        assert abs(total_weight - 1.0) < 1e-4

    def test_transaction_cost_estimation(
        self,
        data_adapter: StubDataAdapter,
        optimizer: "OptimizerAdapter",
        current_portfolio: Portfolio,
    ) -> None:
        """Transaction costs should be estimated for trades."""
        service = OptimizationService(data_adapter, optimizer)

        request = OptimizationRequest(
            universe=["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
            alpha_source="alpha_signals",
            risk_model_version="v1",
            constraints=[],
            objective="max_sharpe",
            current_portfolio=current_portfolio,
            transaction_costs={"spread_bps": 10, "commission_bps": 5},
        )

        response = service.optimize(request)

        # Total estimated cost should be positive
        assert response.estimated_cost > 0

    def test_optimization_metadata(
        self,
        data_adapter: StubDataAdapter,
        optimizer: "OptimizerAdapter",
    ) -> None:
        """Optimization should return metadata about the run."""
        service = OptimizationService(data_adapter, optimizer)

        request = OptimizationRequest(
            universe=["AAPL", "MSFT", "GOOGL"],
            alpha_source="alpha_signals",
            risk_model_version="v1",
            constraints=[],
            objective="max_sharpe",
        )

        response = service.optimize(request)

        assert response.optimization_metadata is not None
        assert response.optimization_metadata["objective"] == "max_sharpe"
        assert response.optimization_metadata["universe_size"] == 3
