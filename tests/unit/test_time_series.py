"""Unit tests for TimeSeries domain object."""

import pytest
import pandas as pd
from datetime import datetime

from src.core.domain.time_series import TimeSeries, TimeSeriesMetadata


class TestTimeSeriesInvariants:
    """Test TimeSeries invariant enforcement."""

    def test_valid_time_series_creation(self) -> None:
        """Valid TimeSeries should be created without errors."""
        dates = pd.date_range("2020-01-01", periods=5, freq="D")
        values = pd.DataFrame(
            {"close": [100.0, 101.0, 102.0, 101.5, 103.0]},
            index=dates,
        )
        metadata = TimeSeriesMetadata(
            source="test",
            published_date=datetime(2020, 1, 6),
        )

        ts = TimeSeries(
            symbol="AAPL",
            date_index=dates,
            values=values,
            version="v20200106_test",
            metadata=metadata,
        )

        assert ts.symbol == "AAPL"
        assert ts.row_count == 5
        assert ts.version == "v20200106_test"

    def test_non_monotonic_date_index_raises(self) -> None:
        """Non-monotonic date index should raise ValueError."""
        dates = pd.DatetimeIndex(["2020-01-01", "2020-01-03", "2020-01-02"])
        values = pd.DataFrame({"close": [100.0, 101.0, 102.0]}, index=dates)
        metadata = TimeSeriesMetadata(source="test", published_date=datetime(2020, 1, 4))

        with pytest.raises(ValueError, match="monotonically increasing"):
            TimeSeries(
                symbol="AAPL",
                date_index=dates,
                values=values,
                version="v20200104_test",
                metadata=metadata,
            )

    def test_duplicate_dates_raises(self) -> None:
        """Duplicate dates in index should raise ValueError."""
        dates = pd.DatetimeIndex(["2020-01-01", "2020-01-02", "2020-01-02"])
        values = pd.DataFrame({"close": [100.0, 101.0, 102.0]}, index=dates)
        metadata = TimeSeriesMetadata(source="test", published_date=datetime(2020, 1, 4))

        with pytest.raises(ValueError, match="duplicates"):
            TimeSeries(
                symbol="AAPL",
                date_index=dates,
                values=values,
                version="v20200104_test",
                metadata=metadata,
            )

    def test_mismatched_lengths_raises(self) -> None:
        """Mismatched index and values lengths should raise ValueError."""
        dates = pd.date_range("2020-01-01", periods=5, freq="D")
        values = pd.DataFrame(
            {"close": [100.0, 101.0, 102.0]},  # Only 3 values
            index=pd.date_range("2020-01-01", periods=3, freq="D"),
        )
        metadata = TimeSeriesMetadata(source="test", published_date=datetime(2020, 1, 6))

        with pytest.raises(ValueError, match="length"):
            TimeSeries(
                symbol="AAPL",
                date_index=dates,
                values=values,
                version="v20200106_test",
                metadata=metadata,
            )

    def test_invalid_version_format_raises(self) -> None:
        """Version not starting with 'v' should raise ValueError."""
        dates = pd.date_range("2020-01-01", periods=5, freq="D")
        values = pd.DataFrame({"close": [100.0, 101.0, 102.0, 101.5, 103.0]}, index=dates)
        metadata = TimeSeriesMetadata(source="test", published_date=datetime(2020, 1, 6))

        with pytest.raises(ValueError, match="must start with 'v'"):
            TimeSeries(
                symbol="AAPL",
                date_index=dates,
                values=values,
                version="20200106_test",  # Missing 'v' prefix
                metadata=metadata,
            )


class TestTimeSeriesMethods:
    """Test TimeSeries methods."""

    @pytest.fixture
    def sample_time_series(self) -> TimeSeries:
        """Create a sample TimeSeries for testing."""
        dates = pd.date_range("2020-01-01", periods=10, freq="D")
        values = pd.DataFrame(
            {"close": list(range(100, 110))},
            index=dates,
        )
        metadata = TimeSeriesMetadata(
            source="test",
            published_date=datetime(2020, 1, 11),
        )
        return TimeSeries(
            symbol="AAPL",
            date_index=dates,
            values=values,
            version="v20200111_test",
            metadata=metadata,
        )

    def test_start_date(self, sample_time_series: TimeSeries) -> None:
        """start_date should return first date."""
        assert sample_time_series.start_date == datetime(2020, 1, 1)

    def test_end_date(self, sample_time_series: TimeSeries) -> None:
        """end_date should return last date."""
        assert sample_time_series.end_date == datetime(2020, 1, 10)

    def test_row_count(self, sample_time_series: TimeSeries) -> None:
        """row_count should return number of observations."""
        assert sample_time_series.row_count == 10

    def test_filter_date_range(self, sample_time_series: TimeSeries) -> None:
        """filter_date_range should return filtered TimeSeries."""
        filtered = sample_time_series.filter_date_range(
            start_date=datetime(2020, 1, 3),
            end_date=datetime(2020, 1, 7),
        )

        assert filtered.row_count == 5
        assert filtered.start_date == datetime(2020, 1, 3)
        assert filtered.end_date == datetime(2020, 1, 7)
        assert filtered.version == sample_time_series.version

    def test_to_dict(self, sample_time_series: TimeSeries) -> None:
        """to_dict should return serializable dictionary."""
        result = sample_time_series.to_dict()

        assert result["symbol"] == "AAPL"
        assert result["version"] == "v20200111_test"
        assert result["row_count"] == 10
        assert "close" in result["columns"]
