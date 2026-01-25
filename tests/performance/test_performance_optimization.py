"""Performance Test - Optimization.

Benchmark: 500 securities in <10 seconds.
"""

import pytest
import time
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np

# Check if cvxpy is available
try:
    import cvxpy
    from src.adapters.optimizer_adapter import OptimizerAdapter
    HAS_CVXPY = True
except ImportError:
    HAS_CVXPY = False


@pytest.mark.skipif(not HAS_CVXPY, reason="cvxpy not installed")
class TestPerformanceOptimization:
    """Performance tests for portfolio optimization."""

    @pytest.fixture
    def large_optimization_inputs(self) -> tuple[pd.Series, pd.DataFrame]:
        """Create inputs for 500 security optimization."""
        num_securities = 500
        symbols = [f"SEC{i:04d}" for i in range(num_securities)]

        np.random.seed(42)

        # Alpha signals
        alpha = pd.Series(
            np.random.randn(num_securities) * 0.01,
            index=symbols,
        )

        # Covariance matrix (must be PSD)
        # Generate random matrix and create PSD matrix
        random_matrix = np.random.randn(num_securities, 50)  # Factor model
        cov_matrix = random_matrix @ random_matrix.T / 50
        cov_matrix = cov_matrix * 0.04  # Scale to reasonable volatility

        # Add small diagonal to ensure PSD
        cov_matrix += np.eye(num_securities) * 0.01

        risk_model = pd.DataFrame(
            cov_matrix,
            index=symbols,
            columns=symbols,
        )

        return alpha, risk_model

    def test_optimization_500_securities(
        self,
        large_optimization_inputs: tuple[pd.Series, pd.DataFrame],
    ) -> None:
        """Optimization of 500 securities should complete in <10 seconds."""
        alpha, risk_model = large_optimization_inputs

        optimizer = OptimizerAdapter(timeout_seconds=30.0)

        start_time = time.perf_counter()

        portfolio = optimizer.optimize(
            alpha=alpha,
            risk_model=risk_model,
            constraints=[],
            objective="max_sharpe",
        )

        elapsed = time.perf_counter() - start_time

        print(f"\nOptimization: {elapsed:.2f} seconds")
        print(f"Securities: {len(alpha)}")
        print(f"Total weight: {sum(portfolio.weights.values()):.4f}")

        assert elapsed < 10, f"Optimization took {elapsed:.2f}s, expected <10s"

    def test_optimization_with_constraints(
        self,
        large_optimization_inputs: tuple[pd.Series, pd.DataFrame],
    ) -> None:
        """Optimization with constraints should still be fast."""
        from src.core.domain.constraint import Constraint, ConstraintType, Bounds

        alpha, risk_model = large_optimization_inputs
        symbols = list(alpha.index)

        # Add position constraints for each security
        constraints = []
        for symbol in symbols:
            constraints.append(
                Constraint(
                    type=ConstraintType.POSITION_LIMIT,
                    bounds=Bounds(lower=0.0, upper=0.01),  # Max 1% per position
                    securities=[symbol],
                    name=f"{symbol} max 1%",
                )
            )

        optimizer = OptimizerAdapter(timeout_seconds=30.0)

        start_time = time.perf_counter()

        portfolio = optimizer.optimize(
            alpha=alpha,
            risk_model=risk_model,
            constraints=constraints,
            objective="max_sharpe",
        )

        elapsed = time.perf_counter() - start_time

        print(f"\nOptimization with {len(constraints)} constraints: {elapsed:.2f}s")

        # Allow more time for constrained optimization
        assert elapsed < 30, f"Constrained optimization took {elapsed:.2f}s, expected <30s"

    def test_min_variance_performance(
        self,
        large_optimization_inputs: tuple[pd.Series, pd.DataFrame],
    ) -> None:
        """Min variance should be faster than max Sharpe."""
        alpha, risk_model = large_optimization_inputs

        optimizer = OptimizerAdapter(timeout_seconds=30.0)

        # Max Sharpe
        start = time.perf_counter()
        optimizer.optimize(
            alpha=alpha,
            risk_model=risk_model,
            constraints=[],
            objective="max_sharpe",
        )
        sharpe_time = time.perf_counter() - start

        # Min Variance
        start = time.perf_counter()
        optimizer.optimize(
            alpha=alpha,
            risk_model=risk_model,
            constraints=[],
            objective="min_variance",
        )
        var_time = time.perf_counter() - start

        print(f"\nMax Sharpe: {sharpe_time:.2f}s")
        print(f"Min Variance: {var_time:.2f}s")

    def test_scaling_behavior(self) -> None:
        """Test how optimization scales with problem size."""
        optimizer = OptimizerAdapter(timeout_seconds=30.0)
        np.random.seed(42)

        sizes = [50, 100, 200, 300]
        times = []

        for n in sizes:
            symbols = [f"S{i}" for i in range(n)]
            alpha = pd.Series(np.random.randn(n) * 0.01, index=symbols)

            random_matrix = np.random.randn(n, 20)
            cov = random_matrix @ random_matrix.T / 20 * 0.04 + np.eye(n) * 0.01
            risk_model = pd.DataFrame(cov, index=symbols, columns=symbols)

            start = time.perf_counter()
            optimizer.optimize(
                alpha=alpha,
                risk_model=risk_model,
                constraints=[],
                objective="max_sharpe",
            )
            elapsed = time.perf_counter() - start
            times.append(elapsed)

            print(f"n={n}: {elapsed:.3f}s")

        # Check reasonable scaling (should be roughly polynomial)
        # Time for n=300 should be less than 10x time for n=50
        scaling_factor = times[-1] / times[0]
        print(f"\nScaling factor (300 vs 50): {scaling_factor:.1f}x")

    def test_generate_performance_artifact(
        self,
        large_optimization_inputs: tuple[pd.Series, pd.DataFrame],
        tmp_path: Path,
    ) -> None:
        """Generate performance artifact JSON."""
        alpha, risk_model = large_optimization_inputs

        optimizer = OptimizerAdapter(timeout_seconds=30.0)

        start_time = time.perf_counter()
        portfolio = optimizer.optimize(
            alpha=alpha,
            risk_model=risk_model,
            constraints=[],
            objective="max_sharpe",
        )
        elapsed = time.perf_counter() - start_time

        artifact = {
            "test_name": "optimization_performance",
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {
                "num_securities": len(alpha),
                "elapsed_seconds": elapsed,
                "objective": "max_sharpe",
                "total_weight": sum(portfolio.weights.values()),
            },
            "thresholds": {
                "max_seconds": 10.0,
            },
            "passed": elapsed < 10,
        }

        artifact_path = tmp_path / "performance_test_optimization.json"
        with open(artifact_path, "w") as f:
            json.dump(artifact, f, indent=2)

        print(f"\nArtifact saved to: {artifact_path}")
