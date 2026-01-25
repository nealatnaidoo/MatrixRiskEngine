"""TimeSeries Domain Object - Versioned time series data with invariants.

Represents a single time series (e.g., OHLCV for a security) with:
- Immutable version tagging
- Monotonically increasing date index
- Quality metadata
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


@dataclass(frozen=True)
class TimeSeriesMetadata:
    """Metadata associated with a time series version.

    Attributes:
        source: Data source identifier (e.g., "bloomberg", "refinitiv")
        published_date: When this data was published/available
        quality_flags: Quality validation results
        created_at: When this version was created in the system
    """

    source: str
    published_date: datetime
    quality_flags: dict[str, object] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TimeSeries:
    """Time series data with versioning and invariants.

    A TimeSeries represents historical data for a single symbol, stored
    with an immutable version tag for reproducibility.

    Attributes:
        symbol: Asset identifier (e.g., "AAPL", "equity_SPY")
        date_index: Sorted, unique DatetimeIndex
        values: DataFrame with columns like open, high, low, close, volume
        version: Immutable version tag (format: vYYYYMMDD_label)
        metadata: Source, quality flags, timestamps

    Invariants:
        - date_index must be monotonically increasing (no duplicates)
        - version is immutable once written (enforced by data store)
        - values must align with date_index (no missing index entries)

    Source of Truth: ArcticDB library + symbol
    """

    symbol: str
    date_index: "pd.DatetimeIndex"
    values: "pd.DataFrame"
    version: str
    metadata: TimeSeriesMetadata

    def __post_init__(self) -> None:
        """Validate invariants after initialization."""
        self._validate_invariants()

    def _validate_invariants(self) -> None:
        """Validate all domain invariants.

        Raises:
            ValueError: If any invariant is violated
        """
        # Invariant 1: date_index must be monotonically increasing
        if not self.date_index.is_monotonic_increasing:
            raise ValueError(
                f"TimeSeries '{self.symbol}' date_index must be monotonically increasing. "
                "Found duplicates or out-of-order dates."
            )

        # Invariant 2: date_index must not have duplicates
        if self.date_index.has_duplicates:
            raise ValueError(
                f"TimeSeries '{self.symbol}' date_index must have unique values. "
                f"Found {self.date_index.duplicated().sum()} duplicates."
            )

        # Invariant 3: values must align with date_index
        if len(self.values) != len(self.date_index):
            raise ValueError(
                f"TimeSeries '{self.symbol}' values length ({len(self.values)}) "
                f"must match date_index length ({len(self.date_index)})."
            )

        # Invariant 4: values index must equal date_index
        if not self.values.index.equals(self.date_index):
            raise ValueError(
                f"TimeSeries '{self.symbol}' values index must equal date_index."
            )

        # Invariant 5: version format validation
        if not self.version.startswith("v"):
            raise ValueError(
                f"TimeSeries version must start with 'v'. Got: '{self.version}'"
            )

    @property
    def start_date(self) -> datetime:
        """Return the first date in the time series."""
        return self.date_index[0].to_pydatetime()

    @property
    def end_date(self) -> datetime:
        """Return the last date in the time series."""
        return self.date_index[-1].to_pydatetime()

    @property
    def row_count(self) -> int:
        """Return the number of observations."""
        return len(self.date_index)

    def filter_date_range(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> "TimeSeries":
        """Return a new TimeSeries filtered to the specified date range.

        Args:
            start_date: Start of range (inclusive)
            end_date: End of range (inclusive)

        Returns:
            New TimeSeries with filtered data (same version and metadata)
        """
        import pandas as pd

        mask = pd.Series(True, index=self.date_index)

        if start_date is not None:
            mask &= self.date_index >= pd.Timestamp(start_date)
        if end_date is not None:
            mask &= self.date_index <= pd.Timestamp(end_date)

        filtered_index = self.date_index[mask]
        filtered_values = self.values.loc[filtered_index]

        return TimeSeries(
            symbol=self.symbol,
            date_index=filtered_index,
            values=filtered_values,
            version=self.version,
            metadata=self.metadata,
        )

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "version": self.version,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "row_count": self.row_count,
            "columns": list(self.values.columns),
            "metadata": {
                "source": self.metadata.source,
                "published_date": self.metadata.published_date.isoformat(),
                "quality_flags": self.metadata.quality_flags,
            },
        }
