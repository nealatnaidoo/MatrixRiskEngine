"""Unit tests for StubDataAdapter."""

import pytest
import pandas as pd
from datetime import date, datetime, timezone

from tests.stubs.stub_data_adapter import StubDataAdapter
from src.core.ports.data_port import DataNotFoundError, VersionExistsError, DataQualityError


class TestStubDataAdapterSave:
    """Test save functionality."""

    def test_save_valid_data(self) -> None:
        """Valid data should be saved successfully."""
        adapter = StubDataAdapter()
        dates = pd.date_range("2020-01-01", periods=5, freq="D")
        data = pd.DataFrame({"close": [100.0, 101.0, 102.0, 101.5, 103.0]}, index=dates)

        adapter.save("AAPL", data, "v20200106_test", {"source": "test"})

        versions = adapter.query_versions("AAPL")
        assert "v20200106_test" in versions

    def test_save_duplicate_version_raises(self) -> None:
        """Saving duplicate version should raise VersionExistsError."""
        adapter = StubDataAdapter()
        dates = pd.date_range("2020-01-01", periods=5, freq="D")
        data = pd.DataFrame({"close": [100.0, 101.0, 102.0, 101.5, 103.0]}, index=dates)

        adapter.save("AAPL", data, "v1", {"source": "test"})

        with pytest.raises(VersionExistsError):
            adapter.save("AAPL", data, "v1", {"source": "test"})

    def test_save_bad_quality_raises(self) -> None:
        """Data with quality issues should raise DataQualityError."""
        adapter = StubDataAdapter()
        dates = pd.date_range("2020-01-01", periods=5, freq="D")
        data = pd.DataFrame({"close": [-100.0, 101.0, 102.0, 101.5, 103.0]}, index=dates)

        with pytest.raises(DataQualityError):
            adapter.save("AAPL", data, "v1", {"source": "test"})


class TestStubDataAdapterLoad:
    """Test load functionality."""

    @pytest.fixture
    def seeded_adapter(self) -> StubDataAdapter:
        """Create adapter with seeded test data."""
        adapter = StubDataAdapter()
        dates = pd.date_range("2020-01-01", periods=10, freq="D")
        data = pd.DataFrame(
            {"close": list(range(100, 110))},
            index=dates,
        )

        adapter.seed_data("AAPL", "v1", data, {"published_date": "2020-01-11T00:00:00+00:00"})
        adapter.seed_data("AAPL", "v2", data * 1.1, {"published_date": "2020-01-12T00:00:00+00:00"})

        return adapter

    def test_load_latest_version(self, seeded_adapter: StubDataAdapter) -> None:
        """Loading without version should return latest."""
        data = seeded_adapter.load("AAPL")

        assert len(data) == 10
        # v2 has 10% higher values
        assert data["close"].iloc[0] > 105

    def test_load_specific_version(self, seeded_adapter: StubDataAdapter) -> None:
        """Loading specific version should return that version."""
        data = seeded_adapter.load("AAPL", version="v1")

        assert data["close"].iloc[0] == 100

    def test_load_with_date_range(self, seeded_adapter: StubDataAdapter) -> None:
        """Date range filter should work correctly."""
        data = seeded_adapter.load(
            "AAPL",
            version="v1",
            start_date=date(2020, 1, 3),
            end_date=date(2020, 1, 7),
        )

        assert len(data) == 5
        assert data.index[0].date() == date(2020, 1, 3)
        assert data.index[-1].date() == date(2020, 1, 7)

    def test_load_with_as_of_date(self, seeded_adapter: StubDataAdapter) -> None:
        """Point-in-time filter should work correctly."""
        # Query with as_of_date after published_date (Jan 11) but filter data to Jan 5
        # This tests that data rows after as_of_date are excluded
        data = seeded_adapter.load(
            "AAPL",
            version="v1",
            as_of_date=date(2020, 1, 15),  # After published_date
        )

        # Should return all 10 rows since as_of_date >= all data dates and >= published_date
        assert len(data) == 10

    def test_load_with_as_of_date_filters_data(self) -> None:
        """as_of_date should filter out data rows after that date."""
        adapter = StubDataAdapter()
        dates = pd.date_range("2020-01-01", periods=10, freq="D")
        data = pd.DataFrame({"close": list(range(100, 110))}, index=dates)

        # Published early so we can query any date
        adapter.seed_data("TEST", "v1", data, {"published_date": "2020-01-01T00:00:00+00:00"})

        # Query with as_of_date in the middle of data range
        result = adapter.load("TEST", version="v1", as_of_date=date(2020, 1, 5))

        # Should only return data up to Jan 5
        assert len(result) == 5
        assert all(d.date() <= date(2020, 1, 5) for d in result.index)

    def test_load_with_as_of_before_published_returns_empty(self, seeded_adapter: StubDataAdapter) -> None:
        """Querying before published_date should return empty."""
        # v1 published on Jan 11
        data = seeded_adapter.load(
            "AAPL",
            version="v1",
            as_of_date=date(2020, 1, 5),  # Before published_date
        )

        # Should be empty since data wasn't published yet
        assert len(data) == 0

    def test_load_nonexistent_symbol_raises(self, seeded_adapter: StubDataAdapter) -> None:
        """Loading nonexistent symbol should raise DataNotFoundError."""
        with pytest.raises(DataNotFoundError):
            seeded_adapter.load("NONEXISTENT")

    def test_load_nonexistent_version_raises(self, seeded_adapter: StubDataAdapter) -> None:
        """Loading nonexistent version should raise DataNotFoundError."""
        with pytest.raises(DataNotFoundError):
            seeded_adapter.load("AAPL", version="v999")


class TestStubDataAdapterQueryVersions:
    """Test query_versions functionality."""

    def test_query_versions_returns_sorted(self) -> None:
        """Versions should be returned in sorted order."""
        adapter = StubDataAdapter()
        dates = pd.date_range("2020-01-01", periods=5, freq="D")
        data = pd.DataFrame({"close": [100.0, 101.0, 102.0, 101.5, 103.0]}, index=dates)

        adapter.seed_data("AAPL", "v3", data)
        adapter.seed_data("AAPL", "v1", data)
        adapter.seed_data("AAPL", "v2", data)

        versions = adapter.query_versions("AAPL")

        assert versions == ["v1", "v2", "v3"]

    def test_query_versions_empty_for_unknown(self) -> None:
        """Unknown symbol should return empty list."""
        adapter = StubDataAdapter()

        versions = adapter.query_versions("UNKNOWN")

        assert versions == []


class TestStubDataAdapterValidation:
    """Test data quality validation."""

    def test_validate_clean_data(self) -> None:
        """Clean data should pass validation."""
        adapter = StubDataAdapter()
        dates = pd.date_range("2020-01-01", periods=100, freq="D")
        data = pd.DataFrame(
            {
                "close": [100 + i * 0.1 for i in range(100)],
                "volume": [1000000] * 100,
            },
            index=dates,
        )

        report = adapter.validate_data_quality(data)

        assert report["passed"] is True
        assert report["negative_prices"] is False

    def test_validate_negative_prices_fails(self) -> None:
        """Negative prices should fail validation."""
        adapter = StubDataAdapter()
        dates = pd.date_range("2020-01-01", periods=5, freq="D")
        data = pd.DataFrame({"close": [-100.0, 101.0, 102.0, 101.5, 103.0]}, index=dates)

        report = adapter.validate_data_quality(data)

        assert report["passed"] is False
        assert report["negative_prices"] is True

    def test_validate_missing_data_fails(self) -> None:
        """Too much missing data should fail validation."""
        adapter = StubDataAdapter()
        dates = pd.date_range("2020-01-01", periods=100, freq="D")
        data = pd.DataFrame(
            {"close": [100.0 if i % 5 != 0 else None for i in range(100)]},
            index=dates,
        )

        report = adapter.validate_data_quality(data)

        assert report["passed"] is False
        assert report["missing_pct"] > 0.001
