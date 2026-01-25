#!/usr/bin/env python3
"""Data Loader CLI - Ingest and version time series data.

Usage:
    python data_loader.py --input data.csv --symbol AAPL --version v20260125
    python data_loader.py --input data.csv --symbol AAPL --version v1 --connection lmdb://./arctic_data

Examples:
    # Load CSV data into ArcticDB
    python data_loader.py --input prices.csv --symbol AAPL --version v1

    # Load with custom metadata
    python data_loader.py --input prices.csv --symbol AAPL --version v1 --source bloomberg

    # List versions for a symbol
    python data_loader.py --symbol AAPL --list-versions
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description="Load and version time series data into ArcticDB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--input", "-i",
        type=str,
        help="Path to input CSV file",
    )

    parser.add_argument(
        "--symbol", "-s",
        type=str,
        required=True,
        help="Symbol identifier (e.g., AAPL)",
    )

    parser.add_argument(
        "--version", "-v",
        type=str,
        help="Version tag (e.g., v20260125)",
    )

    parser.add_argument(
        "--connection", "-c",
        type=str,
        default="lmdb://./arctic_data",
        help="ArcticDB connection string (default: lmdb://./arctic_data)",
    )

    parser.add_argument(
        "--source",
        type=str,
        default="manual",
        help="Data source identifier (default: manual)",
    )

    parser.add_argument(
        "--list-versions", "-l",
        action="store_true",
        help="List available versions for symbol",
    )

    parser.add_argument(
        "--date-column",
        type=str,
        default="date",
        help="Name of date column in CSV (default: date)",
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate data, don't save",
    )

    return parser


def load_csv(filepath: str, date_column: str) -> pd.DataFrame:
    """Load CSV file and parse dates.

    Args:
        filepath: Path to CSV file
        date_column: Name of date column

    Returns:
        DataFrame with DatetimeIndex
    """
    df = pd.read_csv(filepath, parse_dates=[date_column])
    df = df.set_index(date_column)
    df.index = pd.DatetimeIndex(df.index)
    df = df.sort_index()
    return df


def main(args: list[str] | None = None) -> int:
    """Main entry point.

    Args:
        args: Command line arguments (defaults to sys.argv)

    Returns:
        Exit code (0 for success)
    """
    parser = create_parser()
    parsed = parser.parse_args(args)

    # Lazy import to avoid loading arcticdb if not needed
    from src.adapters.arcticdb_adapter import ArcticDBAdapter

    adapter = ArcticDBAdapter(parsed.connection)

    # List versions mode
    if parsed.list_versions:
        versions = adapter.query_versions(parsed.symbol)
        if versions:
            print(f"Available versions for {parsed.symbol}:")
            for v in versions:
                print(f"  - {v}")
        else:
            print(f"No versions found for {parsed.symbol}")
        return 0

    # Load mode - require input and version
    if not parsed.input:
        parser.error("--input is required when not using --list-versions")
    if not parsed.version:
        parser.error("--version is required when not using --list-versions")

    input_path = Path(parsed.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {parsed.input}", file=sys.stderr)
        return 1

    # Load data
    print(f"Loading data from {parsed.input}...")
    try:
        data = load_csv(parsed.input, parsed.date_column)
    except Exception as e:
        print(f"Error loading CSV: {e}", file=sys.stderr)
        return 1

    print(f"Loaded {len(data)} rows from {data.index.min()} to {data.index.max()}")

    # Validate data
    print("Validating data quality...")
    quality_report = adapter.validate_data_quality(data)

    if not quality_report["passed"]:
        print("Data quality validation FAILED:", file=sys.stderr)
        for error in quality_report.get("errors", []):
            print(f"  - {error}", file=sys.stderr)
        return 1

    print("Data quality validation passed:")
    print(f"  - Missing: {quality_report['missing_pct']:.4%}")
    print(f"  - Outliers: {quality_report['outlier_count']}")

    if parsed.validate_only:
        print("Validation only mode - not saving")
        return 0

    # Save data
    print(f"Saving as {parsed.symbol} version {parsed.version}...")

    metadata = {
        "source": parsed.source,
        "input_file": str(input_path.absolute()),
        "loaded_at": datetime.now(timezone.utc).isoformat(),
        "row_count": len(data),
    }

    try:
        adapter.save(
            symbol=parsed.symbol,
            data=data,
            version=parsed.version,
            metadata=metadata,
        )
        print(f"Successfully saved {parsed.symbol} version {parsed.version}")
        return 0

    except Exception as e:
        print(f"Error saving data: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
