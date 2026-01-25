"""Unit tests for QuantStatsAdapter."""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path

from src.adapters.quantstats_adapter import QuantStatsAdapter
from src.core.ports.report_port import ReportGenerationError

# Check if quantstats is available
try:
    import quantstats
    HAS_QUANTSTATS = True
except ImportError:
    HAS_QUANTSTATS = False


class TestQuantStatsAdapterMetrics:
    """Test metrics calculation."""

    @pytest.fixture
    def sample_returns(self) -> pd.Series:
        """Create sample returns series."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=252, freq="B")
        returns = pd.Series(
            np.random.normal(0.0005, 0.02, 252),
            index=dates,
            name="returns",
        )
        return returns

    def test_calculate_metrics_basic(self, sample_returns: pd.Series) -> None:
        """calculate_metrics should return expected metrics."""
        adapter = QuantStatsAdapter()

        metrics = adapter.calculate_metrics(sample_returns)

        # Check basic metrics exist
        assert "total_return" in metrics
        assert "sharpe_ratio" in metrics
        assert "max_drawdown" in metrics
        assert "volatility" in metrics
        assert "win_rate" in metrics

    def test_calculate_metrics_empty_returns(self) -> None:
        """Empty returns should return zero metrics."""
        adapter = QuantStatsAdapter()

        empty_returns = pd.Series([], dtype=float, index=pd.DatetimeIndex([]))
        metrics = adapter.calculate_metrics(empty_returns)

        assert metrics["total_return"] == 0.0
        assert metrics["sharpe_ratio"] == 0.0

    def test_metrics_are_numeric(self, sample_returns: pd.Series) -> None:
        """All metrics should be numeric (no NaN/Inf)."""
        adapter = QuantStatsAdapter()

        metrics = adapter.calculate_metrics(sample_returns)

        for key, value in metrics.items():
            if isinstance(value, float):
                assert not np.isnan(value), f"{key} is NaN"
                assert not np.isinf(value), f"{key} is Inf"

    def test_win_rate_bounds(self, sample_returns: pd.Series) -> None:
        """Win rate should be between 0 and 1."""
        adapter = QuantStatsAdapter()

        metrics = adapter.calculate_metrics(sample_returns)

        assert 0 <= metrics["win_rate"] <= 1


class TestQuantStatsAdapterReports:
    """Test report generation."""

    @pytest.fixture
    def sample_returns(self) -> pd.Series:
        """Create sample returns series."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=252, freq="B")
        returns = pd.Series(
            np.random.normal(0.0005, 0.02, 252),
            index=dates,
            name="returns",
        )
        return returns

    @pytest.mark.skipif(not HAS_QUANTSTATS, reason="quantstats not installed")
    def test_generate_summary_report(
        self,
        sample_returns: pd.Series,
        tmp_path: Path,
    ) -> None:
        """Summary report should be generated."""
        adapter = QuantStatsAdapter(output_dir=tmp_path)

        output_file = tmp_path / "summary.html"
        result = adapter.generate_report(
            returns=sample_returns,
            benchmark=None,
            template="summary",
            output_path=str(output_file),
        )

        assert Path(result).exists()
        content = output_file.read_text()
        assert "Performance Summary" in content

    @pytest.mark.skipif(not HAS_QUANTSTATS, reason="quantstats not installed")
    def test_generate_risk_report(
        self,
        sample_returns: pd.Series,
        tmp_path: Path,
    ) -> None:
        """Risk report should be generated."""
        adapter = QuantStatsAdapter(output_dir=tmp_path)

        output_file = tmp_path / "risk.html"
        result = adapter.generate_report(
            returns=sample_returns,
            benchmark=None,
            template="risk",
            output_path=str(output_file),
        )

        assert Path(result).exists()
        content = output_file.read_text()
        assert "Risk Report" in content

    @pytest.mark.skipif(not HAS_QUANTSTATS, reason="quantstats not installed")
    def test_invalid_template_raises(
        self,
        sample_returns: pd.Series,
        tmp_path: Path,
    ) -> None:
        """Unknown template should raise ReportGenerationError."""
        adapter = QuantStatsAdapter(output_dir=tmp_path)

        with pytest.raises(ReportGenerationError, match="Unknown template"):
            adapter.generate_report(
                returns=sample_returns,
                benchmark=None,
                template="unknown_template",
                output_path=str(tmp_path / "output.html"),
            )

    def test_non_datetime_index_raises(self, tmp_path: Path) -> None:
        """Non-DatetimeIndex should raise ReportGenerationError."""
        adapter = QuantStatsAdapter(output_dir=tmp_path)

        bad_returns = pd.Series([0.01, 0.02, -0.01], index=[0, 1, 2])

        with pytest.raises(ReportGenerationError, match="DatetimeIndex"):
            adapter.generate_report(
                returns=bad_returns,
                benchmark=None,
                template="summary",
                output_path=str(tmp_path / "output.html"),
            )

    def test_empty_returns_raises(self, tmp_path: Path) -> None:
        """Empty returns should raise ReportGenerationError."""
        adapter = QuantStatsAdapter(output_dir=tmp_path)

        empty_returns = pd.Series([], dtype=float, index=pd.DatetimeIndex([]))

        with pytest.raises(ReportGenerationError, match="empty"):
            adapter.generate_report(
                returns=empty_returns,
                benchmark=None,
                template="summary",
                output_path=str(tmp_path / "output.html"),
            )

    @pytest.mark.skipif(not HAS_QUANTSTATS, reason="quantstats not installed")
    def test_creates_output_directory(
        self,
        sample_returns: pd.Series,
        tmp_path: Path,
    ) -> None:
        """Should create output directory if it doesn't exist."""
        adapter = QuantStatsAdapter(output_dir=tmp_path)

        output_file = tmp_path / "nested" / "dir" / "report.html"
        result = adapter.generate_report(
            returns=sample_returns,
            benchmark=None,
            template="summary",
            output_path=str(output_file),
        )

        assert Path(result).exists()
