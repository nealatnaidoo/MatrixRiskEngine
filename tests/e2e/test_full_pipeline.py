"""End-to-End Test - Full Research Pipeline.

Tests the complete workflow:
1. Data Load
2. Factor Analysis
3. Backtest
4. Risk Calculation
5. (Optimization - if cvxpy available)
"""

import pytest
from datetime import date
from unittest.mock import Mock

import pandas as pd
import numpy as np

from tests.stubs.stub_data_adapter import StubDataAdapter
from src.core.domain.portfolio import Portfolio
from src.core.domain.backtest_result import BacktestResult, BacktestConfig
from src.core.services.factor_analysis_service import FactorAnalysisService
from src.core.services.backtest_engine import BacktestEngine, BacktestRequest
from src.core.services.risk_calculation_service import RiskCalculationService
from src.adapters.ore_adapter import OREAdapter


# Check if cvxpy is available
try:
    import cvxpy
    from src.adapters.optimizer_adapter import OptimizerAdapter
    HAS_CVXPY = True
except ImportError:
    HAS_CVXPY = False


class TestFullResearchPipeline:
    """End-to-end test of the complete research pipeline."""

    @pytest.fixture
    def universe(self) -> list[str]:
        """Define test universe."""
        return ["AAPL", "GOOGL", "MSFT", "AMZN", "META"]

    @pytest.fixture
    def market_data(self, universe: list[str]) -> pd.DataFrame:
        """Generate synthetic market data."""
        np.random.seed(42)
        num_days = 504  # 2 years

        dates = pd.date_range("2022-01-01", periods=num_days, freq="B")
        data = {}

        for symbol in universe:
            returns = np.random.randn(num_days) * 0.02
            prices = 100 * np.cumprod(1 + returns)
            data[symbol] = prices

        return pd.DataFrame(data, index=dates)

    @pytest.fixture
    def data_adapter(self, universe: list[str], market_data: pd.DataFrame) -> StubDataAdapter:
        """Create data adapter with seeded data."""
        adapter = StubDataAdapter()

        for symbol in universe:
            df = pd.DataFrame({
                "close": market_data[symbol],
                "volume": np.random.randint(1000000, 10000000, size=len(market_data)),
            }, index=market_data.index)
            adapter.seed_data(symbol=symbol, version="v1", data=df)

        return adapter

    @pytest.fixture
    def mock_backtest_port(self) -> Mock:
        """Create mock backtest port."""
        port = Mock()

        def simulate_fn(signals, prices, transaction_costs, rebalance_freq):
            returns = prices.pct_change().dropna()
            portfolio_returns = returns.mean(axis=1) if not returns.empty else pd.Series(dtype=float)

            config = BacktestConfig(
                data_version="v1",
                start_date=date(2022, 1, 3),
                end_date=date(2023, 12, 29),
                universe=tuple(prices.columns.tolist()),
                rebalance_freq=rebalance_freq,
            )

            return BacktestResult(
                returns=portfolio_returns,
                trades=pd.DataFrame(columns=["timestamp", "symbol", "quantity", "price", "cost"]),
                positions=pd.DataFrame(columns=["date", "symbol", "position"]),
                metrics={
                    "total_return": float(portfolio_returns.sum()) if len(portfolio_returns) > 0 else 0.0,
                    "sharpe_ratio": float(portfolio_returns.mean() / portfolio_returns.std() * np.sqrt(252)) if len(portfolio_returns) > 1 else 0.0,
                    "max_drawdown": -0.15,
                },
                config=config,
            )

        port.simulate.side_effect = simulate_fn
        return port

    def test_full_pipeline_data_to_risk(
        self,
        universe: list[str],
        market_data: pd.DataFrame,
        data_adapter: StubDataAdapter,
        mock_backtest_port: Mock,
    ) -> None:
        """Test complete pipeline from data load to risk calculation."""
        # ========== Step 1: Data Load ==========
        print("\n=== Step 1: Data Load ===")
        loaded_data = {}
        for symbol in universe:
            df = data_adapter.load(symbol=symbol, version="v1")
            loaded_data[symbol] = df["close"]
            print(f"  Loaded {symbol}: {len(df)} rows")

        prices_df = pd.DataFrame(loaded_data)
        assert len(prices_df) > 250, "Need at least 1 year of data"
        print(f"  Total: {prices_df.shape[0]} days x {prices_df.shape[1]} securities")

        # ========== Step 2: Factor Analysis ==========
        print("\n=== Step 2: Factor Analysis ===")
        returns = prices_df.pct_change().dropna()

        # Create a momentum factor
        momentum_12m = prices_df.pct_change(252)
        factor_signals = momentum_12m.rank(axis=1, pct=True)

        # Compute IC
        service = FactorAnalysisService()
        # Align signals with forward returns
        forward_returns = returns.shift(-1).dropna()
        aligned_signals = factor_signals.loc[forward_returns.index]

        analysis = service.analyze(
            factor_scores=aligned_signals,
            forward_returns=forward_returns,
        )

        print(f"  Mean IC: {analysis.ic_mean:.4f}")
        print(f"  IC t-stat: {analysis.t_statistic:.4f}")
        print(f"  Hit Rate: {analysis.hit_rate:.2%}")

        # ========== Step 3: Backtest ==========
        print("\n=== Step 3: Backtest ===")
        backtest_engine = BacktestEngine(
            data_port=data_adapter,
            backtest_port=mock_backtest_port,
            report_port=None,
        )

        def momentum_signal(prices: pd.DataFrame) -> pd.DataFrame:
            momentum = prices.pct_change(20)  # 1-month momentum
            ranks = momentum.rank(axis=1, pct=True)
            # Go long top half
            weights = (ranks > 0.5).astype(float)
            weights = weights.div(weights.sum(axis=1), axis=0).fillna(0)
            return weights

        request = BacktestRequest(
            universe=universe,
            start_date=date(2022, 1, 1),
            end_date=date(2023, 12, 31),
            data_version="v1",
            signal_generator=momentum_signal,
            rebalance_freq="monthly",
            transaction_costs={"spread_bps": 5, "commission_bps": 2},
            generate_tearsheet=False,
        )

        response = backtest_engine.run(request)
        print(f"  Total Return: {response.result.total_return:.2%}")
        print(f"  Sharpe Ratio: {response.result.sharpe_ratio:.2f}")
        print(f"  Max Drawdown: {response.result.max_drawdown:.2%}")

        assert response.result is not None, "Backtest should return result"

        # ========== Step 4: Create Portfolio from Backtest ==========
        print("\n=== Step 4: Portfolio Construction ===")
        nav = 10_000_000  # $10M portfolio

        # Equal weight portfolio
        weights = {symbol: 1.0 / len(universe) for symbol in universe}
        positions = {symbol: nav * weight for symbol, weight in weights.items()}

        portfolio = Portfolio(
            positions=positions,
            weights=weights,
            nav=nav,
            as_of_date=date.today(),
        )

        print(f"  NAV: ${portfolio.nav:,.0f}")
        print(f"  Positions: {portfolio.num_positions}")
        max_weight = max(portfolio.weights.values())
        print(f"  Max Weight: {max_weight:.2%}")

        total_weight = sum(portfolio.weights.values())
        assert abs(total_weight - 1.0) < 0.01, "Portfolio should be fully invested"

        # ========== Step 5: Risk Calculation ==========
        print("\n=== Step 5: Risk Calculation ===")
        risk_port = OREAdapter()

        var_results = risk_port.calculate_var(
            portfolio=portfolio,
            market_data=market_data,
            method="historical",
            confidence_levels=[0.95, 0.99],
            window_days=250,
        )

        print(f"  95% VaR: ${abs(var_results['95%']):,.0f}")
        print(f"  99% VaR: ${abs(var_results['99%']):,.0f}")

        cvar_results = risk_port.calculate_cvar(
            portfolio=portfolio,
            market_data=market_data,
            var_params={
                "method": "historical",
                "confidence_levels": [0.95, 0.99],
                "window_days": 250,
            },
        )

        print(f"  95% CVaR: ${abs(cvar_results['95%']):,.0f}")
        print(f"  99% CVaR: ${abs(cvar_results['99%']):,.0f}")

        # Verify CVaR >= VaR
        assert abs(cvar_results["95%"]) >= abs(var_results["95%"]), "CVaR should exceed VaR"
        assert abs(cvar_results["99%"]) >= abs(var_results["99%"]), "CVaR should exceed VaR"

        # Compute Greeks
        greeks = risk_port.compute_greeks(
            portfolio=portfolio,
            market_data=market_data,
        )

        print(f"  Portfolio Beta: {greeks.get('beta', 'N/A')}")
        print(f"  Portfolio Delta: {greeks.get('delta', 'N/A')}")

        print("\n=== Pipeline Complete ===")

    @pytest.mark.skipif(not HAS_CVXPY, reason="cvxpy not installed")
    def test_full_pipeline_with_optimization(
        self,
        universe: list[str],
        market_data: pd.DataFrame,
    ) -> None:
        """Test pipeline including optimization step."""
        print("\n=== Pipeline with Optimization ===")

        # Create alpha signals from momentum
        returns = market_data.pct_change().dropna()
        alpha = returns.mean() * 252  # Annualized expected returns

        # Create covariance matrix
        cov_matrix = returns.cov() * 252  # Annualized

        # ========== Optimization ==========
        print("\n=== Optimization ===")
        optimizer = OptimizerAdapter(timeout_seconds=30.0)

        portfolio = optimizer.optimize(
            alpha=alpha,
            risk_model=cov_matrix,
            constraints=[],
            objective="max_sharpe",
        )

        print(f"  Optimal Weights:")
        for symbol, weight in sorted(portfolio.weights.items(), key=lambda x: -x[1]):
            if weight > 0.001:
                print(f"    {symbol}: {weight:.2%}")

        print(f"  Total Weight: {sum(portfolio.weights.values()):.4f}")

        # Verify valid portfolio
        assert abs(sum(portfolio.weights.values()) - 1.0) < 0.01, "Weights should sum to 1"
        assert all(w >= -0.001 for w in portfolio.weights.values()), "No short positions"

        print("\n=== Optimization Pipeline Complete ===")

    def test_stress_testing_integration(
        self,
        universe: list[str],
        market_data: pd.DataFrame,
    ) -> None:
        """Test stress testing as part of the pipeline."""
        from src.core.domain.stress_scenario import StressScenario

        print("\n=== Stress Testing ===")

        # Create portfolio
        nav = 10_000_000
        weights = {symbol: 1.0 / len(universe) for symbol in universe}
        positions = {symbol: nav * weight for symbol, weight in weights.items()}

        portfolio = Portfolio(
            positions=positions,
            weights=weights,
            nav=nav,
            as_of_date=date.today(),
        )

        # Define stress scenarios
        scenarios = [
            StressScenario(
                name="Market Crash",
                shocks={"equity_all": -0.20},
                description="20% equity market decline",
                date_calibrated=date.today(),
            ),
            StressScenario(
                name="Tech Selloff",
                shocks={"tech_sector": -0.30},
                description="30% tech sector decline",
                date_calibrated=date.today(),
            ),
            StressScenario(
                name="Mild Correction",
                shocks={"equity_all": -0.10},
                description="10% market correction",
                date_calibrated=date.today(),
            ),
        ]

        # Run stress tests
        risk_port = OREAdapter()
        results = risk_port.stress_test(
            portfolio=portfolio,
            market_data=market_data,
            scenarios=scenarios,
        )

        print(f"  Stress Test Results:")
        for _, row in results.iterrows():
            print(f"    {row['scenario']}: P&L ${row['pnl']:,.0f} ({row['pct_change']:.2%})")

        # Verify results structure
        assert len(results) == len(scenarios), "Should have result for each scenario"
        assert all(results["pnl"] <= 0), "Negative shocks should produce losses"

        print("\n=== Stress Testing Complete ===")
