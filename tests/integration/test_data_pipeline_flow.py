"""Integration Test - Data Pipeline Flow (F1).

Tests the complete data pipeline workflow:
1. Data ingestion from CSV/raw data
2. Versioned storage in ArcticDB (or stub)
3. Point-in-time queries
4. Data quality validation
"""

import pytest
import pandas as pd
import numpy as np
from datetime import date, datetime, timezone, timedelta

from tests.stubs.stub_data_adapter import StubDataAdapter
from src.core.ports.data_port import (
    DataNotFoundError,
    DataQualityError,
    VersionExistsError,
)


class TestDataPipelineFlowF1:
    """Integration tests for Flow F1: Data Ingestion and Versioning."""

    @pytest.fixture
    def data_adapter(self) -> StubDataAdapter:
        """Create fresh data adapter for each test."""
        return StubDataAdapter()

    @pytest.fixture
    def sample_ohlcv_data(self) -> pd.DataFrame:
        """Create sample OHLCV data for testing."""
        dates = pd.date_range("2020-01-01", periods=252, freq="B")
        np.random.seed(42)

        # Generate realistic price data
        close = 100 * np.cumprod(1 + np.random.randn(252) * 0.02)
        high = close * (1 + np.abs(np.random.randn(252)) * 0.01)
        low = close * (1 - np.abs(np.random.randn(252)) * 0.01)
        open_price = close * (1 + np.random.randn(252) * 0.005)
        volume = np.random.randint(1000000, 10000000, size=252)

        return pd.DataFrame({
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }, index=dates)

    def test_ac_f1_001_version_immutability(
        self,
        data_adapter: StubDataAdapter,
        sample_ohlcv_data: pd.DataFrame,
    ) -> None:
        """AC-F1-001: Data versions are immutable once saved.

        Test: Save version v1, attempt to save v1 again with different data.
        Expected: VersionExistsError raised.
        """
        # Save version 1
        data_adapter.save(
            symbol="AAPL",
            data=sample_ohlcv_data,
            version="v1",
            metadata={"source": "test"},
        )

        # Attempt to overwrite with different data
        modified_data = sample_ohlcv_data.copy()
        modified_data["close"] = modified_data["close"] * 1.1

        with pytest.raises(VersionExistsError):
            data_adapter.save(
                symbol="AAPL",
                data=modified_data,
                version="v1",
                metadata={"source": "test_modified"},
            )

    def test_ac_f1_002_version_retrieval(
        self,
        data_adapter: StubDataAdapter,
        sample_ohlcv_data: pd.DataFrame,
    ) -> None:
        """AC-F1-002: Specific versions can be retrieved accurately.

        Test: Save v1, save v2, retrieve v1.
        Expected: v1 data is unchanged.
        """
        # Save version 1
        data_adapter.save(
            symbol="AAPL",
            data=sample_ohlcv_data,
            version="v1",
            metadata={"source": "test"},
        )

        # Create v2 with different data
        v2_data = sample_ohlcv_data.copy()
        v2_data["close"] = v2_data["close"] * 1.1

        data_adapter.save(
            symbol="AAPL",
            data=v2_data,
            version="v2",
            metadata={"source": "test_v2"},
        )

        # Retrieve v1 - should be unchanged
        retrieved_v1 = data_adapter.load(symbol="AAPL", version="v1")

        # Compare data
        pd.testing.assert_frame_equal(
            retrieved_v1,
            sample_ohlcv_data,
            check_exact=False,
            rtol=1e-10,
        )

    def test_ac_f1_003_point_in_time_query(
        self,
        data_adapter: StubDataAdapter,
    ) -> None:
        """AC-F1-003: Point-in-time queries filter out future data.

        Test: Query data as of 2020-06-15 should not include post-June data.
        """
        # Create data spanning full year
        dates = pd.date_range("2020-01-01", "2020-12-31", freq="B")
        data = pd.DataFrame({
            "close": 100 + np.arange(len(dates)) * 0.1,
        }, index=dates)

        # Save with published date in January
        data_adapter.seed_data(
            symbol="AAPL",
            version="v1",
            data=data,
            metadata={"published_date": "2020-01-15T00:00:00+00:00"},
        )

        # Query as of June 15
        as_of = date(2020, 6, 15)
        result = data_adapter.load(symbol="AAPL", as_of_date=as_of)

        # Should only have data up to June 15
        assert result.index.max().date() <= as_of

    def test_ac_f1_003_published_date_filtering(
        self,
        data_adapter: StubDataAdapter,
        sample_ohlcv_data: pd.DataFrame,
    ) -> None:
        """AC-F1-003: Data published after as_of_date is excluded.

        Test: Data published on 2020-07-01, queried as of 2020-06-15.
        Expected: Empty result.
        """
        # Save data with future published date
        data_adapter.seed_data(
            symbol="AAPL",
            version="v1",
            data=sample_ohlcv_data,
            metadata={"published_date": "2020-07-01T00:00:00+00:00"},
        )

        # Query before published date
        result = data_adapter.load(
            symbol="AAPL",
            as_of_date=date(2020, 6, 15),
        )

        # Should be empty - data wasn't published yet
        assert len(result) == 0

    def test_data_quality_validation_passes(
        self,
        data_adapter: StubDataAdapter,
        sample_ohlcv_data: pd.DataFrame,
    ) -> None:
        """Valid data passes quality validation."""
        # Clean data should pass
        data_adapter.save(
            symbol="AAPL",
            data=sample_ohlcv_data,
            version="v1",
            metadata={},
        )

        # Load and verify
        result = data_adapter.load(symbol="AAPL")
        assert len(result) > 0

    def test_data_quality_validation_fails_negative_prices(
        self,
        data_adapter: StubDataAdapter,
        sample_ohlcv_data: pd.DataFrame,
    ) -> None:
        """Negative prices fail quality validation."""
        bad_data = sample_ohlcv_data.copy()
        bad_data.loc[bad_data.index[10], "close"] = -100

        with pytest.raises(DataQualityError):
            data_adapter.save(
                symbol="AAPL",
                data=bad_data,
                version="v1",
                metadata={},
            )

    def test_data_quality_validation_fails_missing_data(
        self,
        data_adapter: StubDataAdapter,
        sample_ohlcv_data: pd.DataFrame,
    ) -> None:
        """Excessive missing data fails quality validation."""
        bad_data = sample_ohlcv_data.copy()
        # Set 10% of data to NaN (exceeds 0.1% threshold)
        mask = np.random.random(len(bad_data)) < 0.1
        bad_data.loc[mask, "close"] = np.nan

        with pytest.raises(DataQualityError):
            data_adapter.save(
                symbol="AAPL",
                data=bad_data,
                version="v1",
                metadata={},
            )

    def test_date_range_filtering(
        self,
        data_adapter: StubDataAdapter,
        sample_ohlcv_data: pd.DataFrame,
    ) -> None:
        """Date range filtering returns correct subset."""
        data_adapter.save(
            symbol="AAPL",
            data=sample_ohlcv_data,
            version="v1",
            metadata={},
        )

        # Load with date range
        result = data_adapter.load(
            symbol="AAPL",
            start_date=date(2020, 3, 1),
            end_date=date(2020, 6, 30),
        )

        # Verify date range
        assert result.index.min() >= pd.Timestamp("2020-03-01")
        assert result.index.max() <= pd.Timestamp("2020-06-30")

    def test_multiple_symbols(
        self,
        data_adapter: StubDataAdapter,
    ) -> None:
        """Multiple symbols can be stored and retrieved independently."""
        dates = pd.date_range("2020-01-01", periods=100, freq="B")

        for symbol in ["AAPL", "MSFT", "GOOGL"]:
            data = pd.DataFrame({
                "close": 100 + np.random.randn(100).cumsum(),
            }, index=dates)

            data_adapter.save(
                symbol=symbol,
                data=data,
                version="v1",
                metadata={"symbol": symbol},
            )

        # Verify each symbol can be retrieved
        for symbol in ["AAPL", "MSFT", "GOOGL"]:
            result = data_adapter.load(symbol=symbol)
            assert len(result) == 100

    def test_version_listing(
        self,
        data_adapter: StubDataAdapter,
        sample_ohlcv_data: pd.DataFrame,
    ) -> None:
        """All versions for a symbol are listed correctly."""
        # Save multiple versions
        for version in ["v1", "v2", "v3"]:
            data_adapter.save(
                symbol="AAPL",
                data=sample_ohlcv_data,
                version=version,
                metadata={},
            )

        versions = data_adapter.query_versions("AAPL")

        assert versions == ["v1", "v2", "v3"]

    def test_latest_version_default(
        self,
        data_adapter: StubDataAdapter,
        sample_ohlcv_data: pd.DataFrame,
    ) -> None:
        """Loading without version returns latest."""
        # Save v1
        v1_data = sample_ohlcv_data.copy()
        v1_data["close"] = 100.0

        data_adapter.save(
            symbol="AAPL",
            data=v1_data,
            version="v1",
            metadata={},
        )

        # Save v2 with different prices
        v2_data = sample_ohlcv_data.copy()
        v2_data["close"] = 200.0

        data_adapter.save(
            symbol="AAPL",
            data=v2_data,
            version="v2",
            metadata={},
        )

        # Load without specifying version
        result = data_adapter.load(symbol="AAPL")

        # Should get v2 (latest)
        assert result["close"].iloc[0] == 200.0

    def test_nonexistent_symbol_raises(
        self,
        data_adapter: StubDataAdapter,
    ) -> None:
        """Loading nonexistent symbol raises error."""
        with pytest.raises(DataNotFoundError):
            data_adapter.load(symbol="UNKNOWN")

    def test_nonexistent_version_raises(
        self,
        data_adapter: StubDataAdapter,
        sample_ohlcv_data: pd.DataFrame,
    ) -> None:
        """Loading nonexistent version raises error."""
        data_adapter.save(
            symbol="AAPL",
            data=sample_ohlcv_data,
            version="v1",
            metadata={},
        )

        with pytest.raises(DataNotFoundError):
            data_adapter.load(symbol="AAPL", version="v999")
