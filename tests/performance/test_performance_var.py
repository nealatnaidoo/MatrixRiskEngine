"""Performance Test - VaR Computation.

Benchmark: Full portfolio VaR in <15 minutes.
"""

import pytest
import time
import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import numpy as np

from src.adapters.ore_adapter import OREAdapter
from src.core.domain.portfolio import Portfolio


class TestPerformanceVaR:
    """Performance tests for VaR computation."""

    @pytest.fixture
    def large_portfolio(self) -> Portfolio:
        """Create portfolio with 2000 securities."""
        num_securities = 2000

        positions = {}
        weights = {}

        for i in range(num_securities):
            symbol = f"SEC{i:04d}"
            weight = 1.0 / num_securities
            positions[symbol] = weight * 10000000  # $10M portfolio
            weights[symbol] = weight

        return Portfolio(
            positions=positions,
            weights=weights,
            nav=10000000.0,
            as_of_date=date.today(),
        )

    @pytest.fixture
    def large_market_data(self) -> pd.DataFrame:
        """Create 2 years of market data for 2000 securities."""
        num_securities = 2000
        num_days = 504  # 2 years

        dates = pd.date_range("2022-01-01", periods=num_days, freq="B")
        np.random.seed(42)

        data = {}
        for i in range(num_securities):
            symbol = f"SEC{i:04d}"
            returns = np.random.randn(num_days) * 0.02
            prices = 100 * np.cumprod(1 + returns)
            data[symbol] = prices

        return pd.DataFrame(data, index=dates)

    def test_var_computation_2000_securities(
        self,
        large_portfolio: Portfolio,
        large_market_data: pd.DataFrame,
    ) -> None:
        """VaR for 2000 securities should complete in <15 minutes."""
        adapter = OREAdapter()

        start_time = time.perf_counter()

        var_results = adapter.calculate_var(
            portfolio=large_portfolio,
            market_data=large_market_data,
            method="historical",
            confidence_levels=[0.95, 0.99],
            window_days=250,
        )

        elapsed = time.perf_counter() - start_time

        print(f"\nVaR computation: {elapsed:.2f} seconds")
        print(f"Portfolio: {len(large_portfolio.positions)} securities")
        print(f"95% VaR: ${abs(var_results['95%']):,.0f}")
        print(f"99% VaR: ${abs(var_results['99%']):,.0f}")

        # 15 minutes = 900 seconds
        assert elapsed < 900, f"VaR took {elapsed:.2f}s, expected <900s (15 min)"

    def test_cvar_computation_performance(
        self,
        large_portfolio: Portfolio,
        large_market_data: pd.DataFrame,
    ) -> None:
        """CVaR computation should add minimal overhead."""
        adapter = OREAdapter()

        # VaR only
        start = time.perf_counter()
        var_results = adapter.calculate_var(
            portfolio=large_portfolio,
            market_data=large_market_data,
            method="historical",
            confidence_levels=[0.95, 0.99],
            window_days=250,
        )
        var_time = time.perf_counter() - start

        # CVaR
        start = time.perf_counter()
        cvar_results = adapter.calculate_cvar(
            portfolio=large_portfolio,
            market_data=large_market_data,
            var_params={
                "method": "historical",
                "confidence_levels": [0.95, 0.99],
                "window_days": 250,
            },
        )
        cvar_time = time.perf_counter() - start

        print(f"\nVaR time: {var_time:.2f}s")
        print(f"CVaR time: {cvar_time:.2f}s")
        print(f"Overhead: {(cvar_time / var_time - 1) * 100:.1f}%")

    def test_parametric_var_performance(
        self,
        large_portfolio: Portfolio,
        large_market_data: pd.DataFrame,
    ) -> None:
        """Parametric VaR should be faster than historical."""
        adapter = OREAdapter()

        # Historical
        start = time.perf_counter()
        adapter.calculate_var(
            portfolio=large_portfolio,
            market_data=large_market_data,
            method="historical",
            confidence_levels=[0.95, 0.99],
            window_days=250,
        )
        hist_time = time.perf_counter() - start

        # Parametric
        start = time.perf_counter()
        adapter.calculate_var(
            portfolio=large_portfolio,
            market_data=large_market_data,
            method="parametric",
            confidence_levels=[0.95, 0.99],
            window_days=250,
        )
        param_time = time.perf_counter() - start

        print(f"\nHistorical VaR: {hist_time:.2f}s")
        print(f"Parametric VaR: {param_time:.2f}s")
        print(f"Speedup: {hist_time / param_time:.1f}x")

    def test_stress_test_performance(
        self,
        large_portfolio: Portfolio,
        large_market_data: pd.DataFrame,
    ) -> None:
        """Stress testing 10 scenarios should be fast."""
        from src.core.domain.stress_scenario import StressScenario

        adapter = OREAdapter()

        scenarios = []
        for i in range(10):
            shock = -0.05 * (i + 1)  # -5% to -50%
            scenarios.append(
                StressScenario(
                    name=f"Scenario {i+1} ({shock:.0%})",
                    shocks={"equity_all": shock},
                    description=f"{abs(shock):.0%} equity decline",
                    date_calibrated=date.today(),
                )
            )

        start_time = time.perf_counter()
        results = adapter.stress_test(
            portfolio=large_portfolio,
            market_data=large_market_data,
            scenarios=scenarios,
        )
        elapsed = time.perf_counter() - start_time

        print(f"\nStress test: {elapsed:.2f} seconds")
        print(f"Scenarios: {len(scenarios)}")
        print(f"Per scenario: {elapsed / len(scenarios) * 1000:.2f}ms")

        assert elapsed < 60, f"Stress test took {elapsed:.2f}s, expected <60s"

    def test_generate_performance_artifact(
        self,
        large_portfolio: Portfolio,
        large_market_data: pd.DataFrame,
        tmp_path: Path,
    ) -> None:
        """Generate performance artifact JSON."""
        adapter = OREAdapter()

        start_time = time.perf_counter()
        var_results = adapter.calculate_var(
            portfolio=large_portfolio,
            market_data=large_market_data,
            method="historical",
            confidence_levels=[0.95, 0.99],
            window_days=250,
        )
        elapsed = time.perf_counter() - start_time

        artifact = {
            "test_name": "var_performance",
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {
                "num_securities": len(large_portfolio.positions),
                "num_days": len(large_market_data),
                "elapsed_seconds": elapsed,
                "var_95": var_results["95%"],
                "var_99": var_results["99%"],
            },
            "thresholds": {
                "max_seconds": 900.0,  # 15 minutes
            },
            "passed": elapsed < 900,
        }

        artifact_path = tmp_path / "performance_test_var.json"
        with open(artifact_path, "w") as f:
            json.dump(artifact, f, indent=2)

        print(f"\nArtifact saved to: {artifact_path}")
