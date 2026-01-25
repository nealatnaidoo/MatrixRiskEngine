"""ArcticDBAdapter - Production implementation of DataPort using ArcticDB.

This adapter provides versioned time series storage with:
- Immutable version tagging
- Point-in-time queries
- Data quality validation
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from src.core.ports.data_port import (
    DataNotFoundError,
    DataPort,
    DataQualityError,
    VersionExistsError,
)

# Quality gate thresholds
MAX_MISSING_PCT = 0.001  # 0.1%
OUTLIER_SIGMA = 5.0


class ArcticDBAdapter:
    """ArcticDB implementation of DataPort.

    Provides versioned time series storage with point-in-time query support.
    """

    def __init__(self, connection_string: str = "lmdb://./arctic_data") -> None:
        """Initialize ArcticDB adapter.

        Args:
            connection_string: ArcticDB connection string
                - lmdb://./path for local storage
                - s3://bucket/path for S3 storage
        """
        self._connection_string = connection_string
        self._ac: Any = None  # Lazy initialization to avoid import errors in tests

    def _get_arctic(self) -> Any:
        """Get or create ArcticDB connection (lazy initialization)."""
        if self._ac is None:
            import arcticdb as adb

            self._ac = adb.Arctic(self._connection_string)
        return self._ac

    def _get_library(self, library_name: str = "market_data") -> Any:
        """Get or create library."""
        ac = self._get_arctic()
        if library_name not in ac.list_libraries():
            ac.create_library(library_name)
        return ac[library_name]

    def _make_versioned_symbol(self, symbol: str, version: str) -> str:
        """Create versioned symbol name."""
        return f"{symbol}__{version}"

    def load(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
        as_of_date: date | None = None,
        version: str | None = None,
    ) -> pd.DataFrame:
        """Load time series data with optional point-in-time filtering.

        Args:
            symbol: Asset identifier
            start_date: Start of date range filter
            end_date: End of date range filter
            as_of_date: Point-in-time filter
            version: Specific version (defaults to latest)

        Returns:
            DataFrame with time series data

        Raises:
            DataNotFoundError: If symbol/version not found
        """
        lib = self._get_library()

        # Get version to load
        if version is None:
            versions = self.query_versions(symbol)
            if not versions:
                raise DataNotFoundError(symbol)
            version = versions[-1]  # Latest version

        versioned_symbol = self._make_versioned_symbol(symbol, version)

        if not lib.has_symbol(versioned_symbol):
            raise DataNotFoundError(symbol, version)

        # Read data
        result = lib.read(versioned_symbol)
        df = result.data

        # Apply date range filter
        if start_date is not None:
            df = df[df.index >= pd.Timestamp(start_date)]
        if end_date is not None:
            df = df[df.index <= pd.Timestamp(end_date)]

        # Apply point-in-time filter using metadata
        if as_of_date is not None:
            metadata = result.metadata or {}
            published_date_str = metadata.get("published_date")
            if published_date_str:
                published_date = datetime.fromisoformat(published_date_str).date()
                if as_of_date < published_date:
                    # Data was published after as_of_date, return empty
                    return df.iloc[0:0]

            # Filter out data points after as_of_date
            df = df[df.index.date <= as_of_date]

        return df

    def save(
        self,
        symbol: str,
        data: pd.DataFrame,
        version: str,
        metadata: dict[str, object],
    ) -> None:
        """Save versioned time series data.

        Args:
            symbol: Asset identifier
            data: DataFrame with DatetimeIndex
            version: Version tag (must be unique for symbol)
            metadata: Additional metadata

        Raises:
            VersionExistsError: If version already exists
            DataQualityError: If data fails validation
            ValueError: If data index is invalid
        """
        # Validate data has DatetimeIndex
        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("Data must have DatetimeIndex")

        # Validate monotonically increasing
        if not data.index.is_monotonic_increasing:
            raise ValueError("Data index must be monotonically increasing")

        # Run quality validation
        quality_report = self.validate_data_quality(data)
        if not quality_report["passed"]:
            raise DataQualityError(quality_report)

        lib = self._get_library()
        versioned_symbol = self._make_versioned_symbol(symbol, version)

        # Check version doesn't exist
        if lib.has_symbol(versioned_symbol):
            raise VersionExistsError(symbol, version)

        # Add published_date to metadata if not present
        if "published_date" not in metadata:
            metadata["published_date"] = datetime.now(timezone.utc).isoformat()

        # Add quality report to metadata
        metadata["quality_report"] = quality_report

        # Write to ArcticDB
        lib.write(versioned_symbol, data, metadata=metadata)

    def query_versions(self, symbol: str) -> list[str]:
        """List available versions for a symbol.

        Args:
            symbol: Asset identifier

        Returns:
            List of version tags sorted by creation time
        """
        lib = self._get_library()
        prefix = f"{symbol}__"

        versions = []
        for sym in lib.list_symbols():
            if sym.startswith(prefix):
                version = sym[len(prefix) :]
                versions.append(version)

        return sorted(versions)

    def validate_data_quality(self, data: pd.DataFrame) -> dict[str, object]:
        """Validate data quality and return report.

        Args:
            data: DataFrame to validate

        Returns:
            Validation report with pass/fail status
        """
        errors: list[str] = []

        # Check for missing data
        missing_pct = data.isnull().sum().sum() / data.size if data.size > 0 else 0.0

        if missing_pct > MAX_MISSING_PCT:
            errors.append(f"Missing data {missing_pct:.2%} exceeds threshold {MAX_MISSING_PCT:.2%}")

        # Check for outliers (numeric columns only)
        outlier_count = 0
        numeric_cols = data.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            series = data[col].dropna()
            if len(series) > 1:
                mean = series.mean()
                std = series.std()
                if std > 0:
                    z_scores = np.abs((series - mean) / std)
                    outlier_count += (z_scores > OUTLIER_SIGMA).sum()

        # Check for negative prices (if price columns exist)
        negative_prices = False
        price_cols = [c for c in data.columns if c in ("close", "open", "high", "low", "price")]

        for col in price_cols:
            if (data[col] < 0).any():
                negative_prices = True
                errors.append(f"Negative prices found in column '{col}'")

        # Check for zero volume
        zero_volume_count = 0
        if "volume" in data.columns:
            zero_volume_count = int((data["volume"] == 0).sum())

        passed = len(errors) == 0

        return {
            "passed": passed,
            "missing_pct": float(missing_pct),
            "outlier_count": int(outlier_count),
            "negative_prices": negative_prices,
            "zero_volume_count": zero_volume_count,
            "errors": errors,
        }

    def delete_version(self, symbol: str, version: str) -> None:
        """Delete a specific version (use with caution - breaks immutability).

        This method exists for cleanup/testing purposes only.
        Production systems should not delete versions.

        Args:
            symbol: Asset identifier
            version: Version to delete

        Raises:
            DataNotFoundError: If version doesn't exist
        """
        lib = self._get_library()
        versioned_symbol = self._make_versioned_symbol(symbol, version)

        if not lib.has_symbol(versioned_symbol):
            raise DataNotFoundError(symbol, version)

        lib.delete(versioned_symbol)

    def save_corporate_action(
        self,
        symbol: str,
        action_type: str,
        effective_date: date,
        adjustment_factor: float,
        metadata: dict[str, object] | None = None,
    ) -> None:
        """Save a corporate action for a symbol.

        Args:
            symbol: Asset identifier
            action_type: Type of action ("split", "dividend")
            effective_date: Date the action becomes effective
            adjustment_factor: Adjustment factor (e.g., 2.0 for 2:1 split)
            metadata: Additional metadata

        Raises:
            ValueError: If action_type is invalid
        """
        if action_type not in ("split", "dividend"):
            raise ValueError(f"Invalid action type: {action_type}")

        lib = self._get_library("corporate_actions")
        action_symbol = f"{symbol}__ca__{effective_date.isoformat()}"

        action_data = pd.DataFrame({
            "action_type": [action_type],
            "adjustment_factor": [adjustment_factor],
        }, index=pd.DatetimeIndex([pd.Timestamp(effective_date)]))

        meta = metadata or {}
        meta["symbol"] = symbol
        meta["action_type"] = action_type
        meta["effective_date"] = effective_date.isoformat()

        lib.write(action_symbol, action_data, metadata=meta)

    def load_corporate_actions(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Load corporate actions for a symbol.

        Args:
            symbol: Asset identifier
            start_date: Start of date range
            end_date: End of date range

        Returns:
            DataFrame with corporate actions
        """
        lib = self._get_library("corporate_actions")
        prefix = f"{symbol}__ca__"

        actions = []
        for sym in lib.list_symbols():
            if sym.startswith(prefix):
                result = lib.read(sym)
                df = result.data
                meta = result.metadata or {}

                # Apply date filters
                if start_date is not None:
                    df = df[df.index >= pd.Timestamp(start_date)]
                if end_date is not None:
                    df = df[df.index <= pd.Timestamp(end_date)]

                if not df.empty:
                    actions.append(df)

        if not actions:
            return pd.DataFrame(columns=["action_type", "adjustment_factor"])

        return pd.concat(actions).sort_index()

    def apply_corporate_actions(
        self,
        data: pd.DataFrame,
        symbol: str,
        as_of_date: date | None = None,
    ) -> pd.DataFrame:
        """Apply corporate actions to price data.

        Only applies actions where effective_date <= as_of_date.

        Args:
            data: Price DataFrame with DatetimeIndex
            symbol: Asset identifier
            as_of_date: Point-in-time date for filtering actions

        Returns:
            Adjusted price DataFrame
        """
        # Load applicable corporate actions
        actions = self.load_corporate_actions(symbol)

        if actions.empty:
            return data

        adjusted = data.copy()
        price_cols = [c for c in adjusted.columns if c in ("close", "open", "high", "low", "price")]

        for action_date, row in actions.iterrows():
            action_effective = action_date.date() if hasattr(action_date, "date") else action_date

            # Only apply if action was known as of as_of_date
            if as_of_date is not None and action_effective > as_of_date:
                continue

            # Apply adjustment to historical prices before effective date
            mask = adjusted.index < action_date
            factor = row["adjustment_factor"]

            if row["action_type"] == "split":
                # Adjust prices by dividing by split factor
                for col in price_cols:
                    if col in adjusted.columns:
                        adjusted.loc[mask, col] = adjusted.loc[mask, col] / factor
                # Adjust volume by multiplying
                if "volume" in adjusted.columns:
                    adjusted.loc[mask, "volume"] = adjusted.loc[mask, "volume"] * factor

            elif row["action_type"] == "dividend":
                # Adjust prices for dividend
                for col in price_cols:
                    if col in adjusted.columns:
                        adjusted.loc[mask, col] = adjusted.loc[mask, col] - factor

        return adjusted


# Type assertion for Protocol compliance
_: DataPort = ArcticDBAdapter()  # type: ignore[assignment]
