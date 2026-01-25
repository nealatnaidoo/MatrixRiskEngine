"""DataPort Protocol - Abstract interface for time series data storage and retrieval.

This port defines the contract for versioned time series storage, supporting:
- Point-in-time queries with as_of_date filtering
- Immutable version tagging
- Data quality validation
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import pandas as pd


@runtime_checkable
class DataPort(Protocol):
    """Abstract interface for versioned time series data storage.

    Implementations:
    - ArcticDBAdapter: Production implementation using ArcticDB
    - StubDataAdapter: Test stub for unit testing

    All implementations must enforce:
    - Version immutability (no overwrites)
    - Point-in-time correctness (no future data in past queries)
    - Data quality validation on write
    """

    def load(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
        as_of_date: date | None = None,
        version: str | None = None,
    ) -> "pd.DataFrame":
        """Load time series data with optional point-in-time filtering.

        Args:
            symbol: Asset identifier (e.g., "AAPL", "SPY")
            start_date: Start of date range filter (inclusive)
            end_date: End of date range filter (inclusive)
            as_of_date: Point-in-time filter - excludes data with published_date > as_of_date
            version: Specific version tag to retrieve (defaults to latest)

        Returns:
            DataFrame with DatetimeIndex and time series values

        Raises:
            DataNotFoundError: If symbol or version not found
            ValueError: If as_of_date is in the future relative to data availability

        Pre-conditions:
            - symbol must exist in data store

        Post-conditions:
            - Returns DataFrame with date index
            - If as_of_date specified, no records with published_date > as_of_date
        """
        ...

    def save(
        self,
        symbol: str,
        data: "pd.DataFrame",
        version: str,
        metadata: dict[str, object],
    ) -> None:
        """Save versioned time series data.

        Args:
            symbol: Asset identifier
            data: DataFrame with DatetimeIndex containing time series values
            version: Immutable version tag (format: vYYYYMMDD_label)
            metadata: Additional metadata (source, quality_flags, published_date)

        Raises:
            VersionExistsError: If version already exists for symbol
            DataQualityError: If data fails quality validation
            ValueError: If data index is not monotonically increasing

        Pre-conditions:
            - data must have DatetimeIndex
            - version must not exist for symbol

        Post-conditions:
            - Data persisted with version tag
            - Metadata stored with data
            - Quality validation executed
        """
        ...

    def query_versions(self, symbol: str) -> list[str]:
        """List available versions for a symbol.

        Args:
            symbol: Asset identifier

        Returns:
            List of version tags sorted by creation time (oldest first)

        Raises:
            DataNotFoundError: If symbol not found
        """
        ...

    def validate_data_quality(self, data: "pd.DataFrame") -> dict[str, object]:
        """Validate data quality and return report.

        Validation gates:
        - Missing data: <0.1% threshold
        - Outliers: Beyond 5 sigma flagged
        - Negative prices: Rejected (except spreads/yields)
        - Zero volume: Flagged as suspicious

        Args:
            data: DataFrame to validate

        Returns:
            Dict with keys:
            - passed: bool - overall pass/fail
            - missing_pct: float - percentage of missing values
            - outlier_count: int - number of outliers detected
            - negative_prices: bool - whether negative prices found
            - zero_volume_count: int - count of zero volume observations
            - errors: list[str] - list of validation errors

        Post-conditions:
            - Returns complete validation report
            - Does not modify input data
        """
        ...


class DataNotFoundError(Exception):
    """Raised when requested symbol or version is not found."""

    def __init__(self, symbol: str, version: str | None = None) -> None:
        self.symbol = symbol
        self.version = version
        msg = f"Data not found for symbol '{symbol}'"
        if version:
            msg += f" version '{version}'"
        super().__init__(msg)


class VersionExistsError(Exception):
    """Raised when attempting to overwrite an existing version."""

    def __init__(self, symbol: str, version: str) -> None:
        self.symbol = symbol
        self.version = version
        super().__init__(
            f"Version '{version}' already exists for symbol '{symbol}'. "
            "Versions are immutable and cannot be overwritten."
        )


class DataQualityError(Exception):
    """Raised when data fails quality validation gates."""

    def __init__(self, validation_report: dict[str, object]) -> None:
        self.validation_report = validation_report
        errors = validation_report.get("errors", [])
        super().__init__(f"Data quality validation failed: {errors}")
