"""StubDataAdapter - Test stub implementation of DataPort.

This stub provides in-memory data storage for unit testing without
requiring ArcticDB to be installed or running.
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


class StubDataAdapter:
    """In-memory test stub for DataPort.

    Provides the same interface as ArcticDBAdapter but stores data
    in memory for fast unit testing.

    Signature must match ArcticDBAdapter exactly for test double synchronization.
    """

    def __init__(self) -> None:
        """Initialize stub with empty storage."""
        # Storage: {symbol: {version: (data, metadata)}}
        self._storage: dict[str, dict[str, tuple[pd.DataFrame, dict[str, Any]]]] = {}

    def load(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
        as_of_date: date | None = None,
        version: str | None = None,
    ) -> pd.DataFrame:
        """Load time series data from stub storage."""
        if symbol not in self._storage:
            raise DataNotFoundError(symbol)

        versions = self._storage[symbol]
        if not versions:
            raise DataNotFoundError(symbol)

        # Get version to load
        if version is None:
            version = sorted(versions.keys())[-1]  # Latest

        if version not in versions:
            raise DataNotFoundError(symbol, version)

        df, metadata = versions[version]
        df = df.copy()

        # Apply date range filter
        if start_date is not None:
            df = df[df.index >= pd.Timestamp(start_date)]
        if end_date is not None:
            df = df[df.index <= pd.Timestamp(end_date)]

        # Apply point-in-time filter
        if as_of_date is not None:
            published_date_str = metadata.get("published_date")
            if published_date_str:
                published_date = datetime.fromisoformat(published_date_str).date()
                if as_of_date < published_date:
                    return df.iloc[0:0]  # Empty

            df = df[df.index.date <= as_of_date]

        return df

    def save(
        self,
        symbol: str,
        data: pd.DataFrame,
        version: str,
        metadata: dict[str, object],
    ) -> None:
        """Save versioned time series data to stub storage."""
        # Validate data
        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("Data must have DatetimeIndex")

        if not data.index.is_monotonic_increasing:
            raise ValueError("Data index must be monotonically increasing")

        # Run quality validation
        quality_report = self.validate_data_quality(data)
        if not quality_report["passed"]:
            raise DataQualityError(quality_report)

        # Check version doesn't exist
        if symbol in self._storage and version in self._storage[symbol]:
            raise VersionExistsError(symbol, version)

        # Add metadata
        if "published_date" not in metadata:
            metadata["published_date"] = datetime.now(timezone.utc).isoformat()
        metadata["quality_report"] = quality_report

        # Store
        if symbol not in self._storage:
            self._storage[symbol] = {}

        self._storage[symbol][version] = (data.copy(), dict(metadata))

    def query_versions(self, symbol: str) -> list[str]:
        """List available versions for a symbol."""
        if symbol not in self._storage:
            return []
        return sorted(self._storage[symbol].keys())

    def validate_data_quality(self, data: pd.DataFrame) -> dict[str, object]:
        """Validate data quality and return report."""
        errors: list[str] = []

        # Check for missing data
        missing_pct = data.isnull().sum().sum() / data.size if data.size > 0 else 0.0

        if missing_pct > 0.001:  # 0.1%
            errors.append(f"Missing data {missing_pct:.2%} exceeds threshold")

        # Check for outliers
        outlier_count = 0
        numeric_cols = data.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            series = data[col].dropna()
            if len(series) > 1:
                mean = series.mean()
                std = series.std()
                if std > 0:
                    z_scores = np.abs((series - mean) / std)
                    outlier_count += int((z_scores > 5.0).sum())

        # Check for negative prices
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

        return {
            "passed": len(errors) == 0,
            "missing_pct": float(missing_pct),
            "outlier_count": outlier_count,
            "negative_prices": negative_prices,
            "zero_volume_count": zero_volume_count,
            "errors": errors,
        }

    def clear(self) -> None:
        """Clear all stored data (test helper)."""
        self._storage.clear()

    def seed_data(
        self,
        symbol: str,
        version: str,
        data: pd.DataFrame,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Seed test data bypassing validation (test helper).

        Use this to set up test fixtures without validation constraints.
        """
        if symbol not in self._storage:
            self._storage[symbol] = {}

        meta = metadata or {}
        if "published_date" not in meta:
            meta["published_date"] = datetime.now(timezone.utc).isoformat()

        self._storage[symbol][version] = (data.copy(), meta)

    # Corporate action methods
    def save_corporate_action(
        self,
        symbol: str,
        action_type: str,
        effective_date: date,
        adjustment_factor: float,
        metadata: dict[str, object] | None = None,
    ) -> None:
        """Save a corporate action for a symbol."""
        if action_type not in ("split", "dividend"):
            raise ValueError(f"Invalid action type: {action_type}")

        if not hasattr(self, "_corporate_actions"):
            self._corporate_actions: dict[str, list[dict[str, Any]]] = {}

        if symbol not in self._corporate_actions:
            self._corporate_actions[symbol] = []

        self._corporate_actions[symbol].append({
            "action_type": action_type,
            "effective_date": effective_date,
            "adjustment_factor": adjustment_factor,
            "metadata": metadata or {},
        })

    def load_corporate_actions(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Load corporate actions for a symbol."""
        if not hasattr(self, "_corporate_actions"):
            return pd.DataFrame(columns=["action_type", "adjustment_factor"])

        if symbol not in self._corporate_actions:
            return pd.DataFrame(columns=["action_type", "adjustment_factor"])

        actions = self._corporate_actions[symbol]
        rows = []

        for action in actions:
            eff_date = action["effective_date"]

            if start_date is not None and eff_date < start_date:
                continue
            if end_date is not None and eff_date > end_date:
                continue

            rows.append({
                "date": pd.Timestamp(eff_date),
                "action_type": action["action_type"],
                "adjustment_factor": action["adjustment_factor"],
            })

        if not rows:
            return pd.DataFrame(columns=["action_type", "adjustment_factor"])

        df = pd.DataFrame(rows)
        df = df.set_index("date")
        return df.sort_index()

    def apply_corporate_actions(
        self,
        data: pd.DataFrame,
        symbol: str,
        as_of_date: date | None = None,
    ) -> pd.DataFrame:
        """Apply corporate actions to price data."""
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
                for col in price_cols:
                    if col in adjusted.columns:
                        adjusted.loc[mask, col] = adjusted.loc[mask, col] / factor
                if "volume" in adjusted.columns:
                    adjusted.loc[mask, "volume"] = adjusted.loc[mask, "volume"] * factor

            elif row["action_type"] == "dividend":
                for col in price_cols:
                    if col in adjusted.columns:
                        adjusted.loc[mask, col] = adjusted.loc[mask, col] - factor

        return adjusted


# Type assertion for Protocol compliance
_: DataPort = StubDataAdapter()  # type: ignore[assignment]
