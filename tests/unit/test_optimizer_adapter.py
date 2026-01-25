"""Unit tests for OptimizerAdapter."""

import pytest
import pandas as pd
import numpy as np

from src.adapters.optimizer_adapter import OptimizerAdapter
from src.core.domain.constraint import Constraint, ConstraintType, Bounds
from src.core.ports.backtest_port import InfeasibleError

# Check if cvxpy is available
try:
    import cvxpy
    HAS_CVXPY = True
except ImportError:
    HAS_CVXPY = False


@pytest.mark.skipif(not HAS_CVXPY, reason="cvxpy not installed")
class TestOptimizerAdapterBasic:
    """Test basic optimization functionality."""

    @pytest.fixture
    def sample_inputs(self) -> tuple[pd.Series, pd.DataFrame]:
        """Create sample alpha and risk model."""
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

        # Expected returns
        alpha = pd.Series(
            [0.10, 0.08, 0.12, 0.09, 0.11],
            index=symbols,
        )

        # Covariance matrix (must be positive semi-definite)
        np.random.seed(42)
        n = len(symbols)
        random_matrix = np.random.randn(n, n)
        cov_matrix = random_matrix @ random_matrix.T / n  # Guaranteed PSD
        cov_matrix = cov_matrix * 0.04  # Scale to reasonable volatility

        risk_model = pd.DataFrame(
            cov_matrix,
            index=symbols,
            columns=symbols,
        )

        return alpha, risk_model

    def test_optimize_max_sharpe(
        self,
        sample_inputs: tuple[pd.Series, pd.DataFrame],
    ) -> None:
        """max_sharpe optimization should produce valid portfolio."""
        alpha, risk_model = sample_inputs
        optimizer = OptimizerAdapter()

        portfolio = optimizer.optimize(
            alpha=alpha,
            risk_model=risk_model,
            constraints=[],
            objective="max_sharpe",
        )

        # Weights should sum to 1
        assert abs(sum(portfolio.weights.values()) - 1.0) < 1e-4

        # All weights should be in portfolio
        assert set(portfolio.weights.keys()) == set(alpha.index)

    def test_optimize_min_variance(
        self,
        sample_inputs: tuple[pd.Series, pd.DataFrame],
    ) -> None:
        """min_variance optimization should produce valid portfolio."""
        alpha, risk_model = sample_inputs
        optimizer = OptimizerAdapter()

        portfolio = optimizer.optimize(
            alpha=alpha,
            risk_model=risk_model,
            constraints=[],
            objective="min_variance",
        )

        assert abs(sum(portfolio.weights.values()) - 1.0) < 1e-4

    def test_optimize_with_position_constraints(
        self,
        sample_inputs: tuple[pd.Series, pd.DataFrame],
    ) -> None:
        """Position constraints should be respected."""
        alpha, risk_model = sample_inputs
        optimizer = OptimizerAdapter()

        constraints = [
            Constraint(
                type=ConstraintType.POSITION_LIMIT,
                bounds=Bounds(lower=0.0, upper=0.30),
                securities=["AAPL"],
                name="AAPL max 30%",
            ),
        ]

        portfolio = optimizer.optimize(
            alpha=alpha,
            risk_model=risk_model,
            constraints=constraints,
            objective="max_sharpe",
        )

        assert portfolio.weights["AAPL"] <= 0.30 + 1e-4

    def test_optimize_with_sector_constraints(
        self,
        sample_inputs: tuple[pd.Series, pd.DataFrame],
    ) -> None:
        """Sector constraints should be respected."""
        alpha, risk_model = sample_inputs
        optimizer = OptimizerAdapter()

        # Limit tech sector (AAPL, MSFT, GOOGL) to 50%
        constraints = [
            Constraint(
                type=ConstraintType.SECTOR_LIMIT,
                bounds=Bounds(lower=0.0, upper=0.50),
                securities=["AAPL", "MSFT", "GOOGL"],
                name="Tech max 50%",
            ),
        ]

        portfolio = optimizer.optimize(
            alpha=alpha,
            risk_model=risk_model,
            constraints=constraints,
            objective="max_sharpe",
        )

        tech_weight = sum(
            portfolio.weights[s] for s in ["AAPL", "MSFT", "GOOGL"]
        )
        assert tech_weight <= 0.50 + 1e-4


@pytest.mark.skipif(not HAS_CVXPY, reason="cvxpy not installed")
class TestOptimizerAdapterValidation:
    """Test input validation."""

    def test_empty_alpha_raises(self) -> None:
        """Empty alpha should raise ValueError."""
        optimizer = OptimizerAdapter()

        with pytest.raises(ValueError, match="empty"):
            optimizer.optimize(
                alpha=pd.Series(dtype=float),
                risk_model=pd.DataFrame(),
                constraints=[],
                objective="max_sharpe",
            )

    def test_non_psd_matrix_raises(self) -> None:
        """Non-PSD covariance matrix should raise ValueError."""
        optimizer = OptimizerAdapter()

        alpha = pd.Series([0.1, 0.1], index=["A", "B"])
        # Create non-PSD matrix
        risk_model = pd.DataFrame(
            [[1.0, 2.0], [2.0, 1.0]],  # Not PSD (eigenvalues: 3, -1)
            index=["A", "B"],
            columns=["A", "B"],
        )

        with pytest.raises(ValueError, match="PSD"):
            optimizer.optimize(
                alpha=alpha,
                risk_model=risk_model,
                constraints=[],
                objective="max_sharpe",
            )

    def test_unknown_objective_raises(self) -> None:
        """Unknown objective should raise ValueError."""
        optimizer = OptimizerAdapter()

        symbols = ["A", "B"]
        alpha = pd.Series([0.1, 0.1], index=symbols)
        risk_model = pd.DataFrame(
            np.eye(2) * 0.04,
            index=symbols,
            columns=symbols,
        )

        with pytest.raises(ValueError, match="Unknown objective"):
            optimizer.optimize(
                alpha=alpha,
                risk_model=risk_model,
                constraints=[],
                objective="unknown_objective",
            )


@pytest.mark.skipif(not HAS_CVXPY, reason="cvxpy not installed")
class TestOptimizerAdapterInfeasible:
    """Test infeasibility handling."""

    def test_infeasible_constraints_raises(self) -> None:
        """Infeasible constraints should raise InfeasibleError."""
        optimizer = OptimizerAdapter()

        symbols = ["A", "B"]
        alpha = pd.Series([0.1, 0.1], index=symbols)
        risk_model = pd.DataFrame(
            np.eye(2) * 0.04,
            index=symbols,
            columns=symbols,
        )

        # Impossible constraints: each position >= 60%, but sum = 100%
        constraints = [
            Constraint(
                type=ConstraintType.POSITION_LIMIT,
                bounds=Bounds(lower=0.60, upper=1.0),
                securities=["A"],
                name="A min 60%",
            ),
            Constraint(
                type=ConstraintType.POSITION_LIMIT,
                bounds=Bounds(lower=0.60, upper=1.0),
                securities=["B"],
                name="B min 60%",
            ),
        ]

        with pytest.raises(InfeasibleError):
            optimizer.optimize(
                alpha=alpha,
                risk_model=risk_model,
                constraints=constraints,
                objective="max_sharpe",
            )
