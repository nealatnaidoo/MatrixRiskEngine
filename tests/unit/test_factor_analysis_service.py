"""Unit tests for FactorAnalysisService."""

import pytest
import pandas as pd
import numpy as np

from src.core.services.factor_analysis_service import (
    FactorAnalysisService,
    FactorAnalysisResult,
)


class TestFactorAnalysisServiceIC:
    """Test Information Coefficient calculation."""

    @pytest.fixture
    def sample_data(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Create sample factor scores and returns."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=100, freq="B")
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

        # Factor scores with some predictive power
        factor_scores = pd.DataFrame(
            np.random.randn(100, 5),
            index=dates,
            columns=symbols,
        )

        # Forward returns correlated with factor scores
        noise = np.random.randn(100, 5) * 0.5
        forward_returns = pd.DataFrame(
            factor_scores.values * 0.01 + noise * 0.02,
            index=dates,
            columns=symbols,
        )

        return factor_scores, forward_returns

    def test_calculate_ic_basic(
        self,
        sample_data: tuple[pd.DataFrame, pd.DataFrame],
    ) -> None:
        """calculate_ic should return IC time series."""
        factor_scores, forward_returns = sample_data
        service = FactorAnalysisService()

        ic_series = service.calculate_ic(factor_scores, forward_returns)

        assert len(ic_series) == len(factor_scores)
        assert isinstance(ic_series, pd.Series)

    def test_calculate_ic_positive_for_predictive_factor(
        self,
        sample_data: tuple[pd.DataFrame, pd.DataFrame],
    ) -> None:
        """IC should be positive for predictive factor."""
        factor_scores, forward_returns = sample_data
        service = FactorAnalysisService()

        ic_series = service.calculate_ic(factor_scores, forward_returns)

        # Mean IC should be positive since returns are correlated with scores
        assert ic_series.mean() > 0

    def test_calculate_ic_empty_data(self) -> None:
        """Empty data should return empty series."""
        service = FactorAnalysisService()

        factor_scores = pd.DataFrame()
        forward_returns = pd.DataFrame()

        ic_series = service.calculate_ic(factor_scores, forward_returns)

        assert len(ic_series) == 0


class TestFactorAnalysisServiceTurnover:
    """Test turnover calculation."""

    def test_calculate_turnover_basic(self) -> None:
        """calculate_turnover should return turnover series."""
        dates = pd.date_range("2020-01-01", periods=10, freq="B")
        positions = pd.DataFrame(
            {
                "AAPL": [0.5, 0.5, 0.6, 0.6, 0.4, 0.4, 0.5, 0.5, 0.5, 0.5],
                "MSFT": [0.5, 0.5, 0.4, 0.4, 0.6, 0.6, 0.5, 0.5, 0.5, 0.5],
            },
            index=dates,
        )

        service = FactorAnalysisService()
        turnover = service.calculate_turnover(positions)

        # Turnover exists for dates after first
        assert len(turnover) == len(positions) - 1

    def test_calculate_turnover_static_portfolio(self) -> None:
        """Static portfolio should have zero turnover."""
        dates = pd.date_range("2020-01-01", periods=10, freq="B")
        positions = pd.DataFrame(
            {
                "AAPL": [0.5] * 10,
                "MSFT": [0.5] * 10,
            },
            index=dates,
        )

        service = FactorAnalysisService()
        turnover = service.calculate_turnover(positions)

        assert (turnover == 0).all()

    def test_calculate_turnover_full_rebalance(self) -> None:
        """Full rebalance should have 100% turnover."""
        dates = pd.date_range("2020-01-01", periods=2, freq="B")
        positions = pd.DataFrame(
            {
                "AAPL": [1.0, 0.0],
                "MSFT": [0.0, 1.0],
            },
            index=dates,
        )

        service = FactorAnalysisService()
        turnover = service.calculate_turnover(positions)

        # Full switch = 100% turnover
        assert turnover.iloc[0] == 1.0


class TestFactorAnalysisServiceStatisticalTests:
    """Test statistical significance tests."""

    def test_statistical_tests_significant(self) -> None:
        """High IC should be statistically significant."""
        # Create IC series with clear positive mean
        np.random.seed(42)
        ic_series = pd.Series(np.random.randn(100) * 0.1 + 0.05)

        service = FactorAnalysisService()
        results = service.statistical_tests(ic_series)

        assert results["t_statistic"] > 0
        assert results["p_value"] < 0.05  # Significant

    def test_statistical_tests_not_significant(self) -> None:
        """Zero-mean IC should not be significant."""
        np.random.seed(42)
        ic_series = pd.Series(np.random.randn(100) * 0.01)

        service = FactorAnalysisService()
        results = service.statistical_tests(ic_series)

        assert results["p_value"] > 0.05  # Not significant

    def test_hit_rate_bounds(self) -> None:
        """Hit rate should be between 0 and 1."""
        np.random.seed(42)
        ic_series = pd.Series(np.random.randn(100))

        service = FactorAnalysisService()
        results = service.statistical_tests(ic_series)

        assert 0 <= results["hit_rate"] <= 1


class TestFactorAnalysisServiceAnalyze:
    """Test complete analysis workflow."""

    def test_analyze_returns_complete_result(self) -> None:
        """analyze should return complete FactorAnalysisResult."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=50, freq="B")
        symbols = ["AAPL", "MSFT", "GOOGL"]

        factor_scores = pd.DataFrame(
            np.random.randn(50, 3),
            index=dates,
            columns=symbols,
        )
        forward_returns = pd.DataFrame(
            np.random.randn(50, 3) * 0.02,
            index=dates,
            columns=symbols,
        )

        service = FactorAnalysisService()
        result = service.analyze(factor_scores, forward_returns)

        assert isinstance(result, FactorAnalysisResult)
        assert len(result.ic_series) > 0
        assert len(result.turnover_series) > 0
        assert result.t_statistic is not None

    def test_analyze_to_dict(self) -> None:
        """to_dict should return serializable dictionary."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=50, freq="B")
        symbols = ["AAPL", "MSFT"]

        factor_scores = pd.DataFrame(
            np.random.randn(50, 2),
            index=dates,
            columns=symbols,
        )
        forward_returns = pd.DataFrame(
            np.random.randn(50, 2) * 0.02,
            index=dates,
            columns=symbols,
        )

        service = FactorAnalysisService()
        result = service.analyze(factor_scores, forward_returns)

        result_dict = result.to_dict()

        assert "ic_mean" in result_dict
        assert "sharpe_ratio" in result_dict
        assert "turnover_mean" in result_dict
