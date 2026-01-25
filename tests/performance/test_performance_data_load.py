"""Performance Test - Data Load.

Benchmark: 1M rows in <5 seconds.
"""

import pytest
import time
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np

from tests.stubs.stub_data_adapter import StubDataAdapter


class TestPerformanceDataLoad:
    """Performance tests for data loading."""

    @pytest.fixture
    def adapter_with_large_data(self) -> tuple[StubDataAdapter, pd.DataFrame]:
        """Create adapter with 1M rows of data."""
        adapter = StubDataAdapter()

        # Generate 1M rows (approx 4000 days * 250 symbols)
        # For testing, we'll use 10000 days * 100 symbols = 1M rows conceptually
        # Actually generate 10000 rows per symbol for 100 symbols
        num_days = 10000
        num_symbols = 100

        dates = pd.date_range("2000-01-01", periods=num_days, freq="D")
        np.random.seed(42)

        total_rows = 0
        for i in range(num_symbols):
            symbol = f"SYM{i:04d}"
            prices = 100 + np.cumsum(np.random.randn(num_days) * 0.5)

            data = pd.DataFrame({
                "close": prices,
                "volume": np.random.randint(1000, 10000, size=num_days),
            }, index=dates)

            adapter.seed_data(symbol=symbol, version="v1", data=data)
            total_rows += len(data)

        return adapter, dates

    def test_data_load_performance(
        self,
        adapter_with_large_data: tuple[StubDataAdapter, pd.DataFrame],
    ) -> None:
        """Loading large dataset should complete in <5 seconds."""
        adapter, dates = adapter_with_large_data

        # Measure time to load all symbols
        start_time = time.perf_counter()

        loaded_rows = 0
        for i in range(100):
            symbol = f"SYM{i:04d}"
            df = adapter.load(symbol=symbol, version="v1")
            loaded_rows += len(df)

        elapsed = time.perf_counter() - start_time

        print(f"\nLoaded {loaded_rows:,} rows in {elapsed:.3f} seconds")
        print(f"Throughput: {loaded_rows / elapsed:,.0f} rows/second")

        # Performance assertion
        assert elapsed < 5.0, f"Data load took {elapsed:.2f}s, expected <5s"

    def test_single_symbol_load_performance(
        self,
        adapter_with_large_data: tuple[StubDataAdapter, pd.DataFrame],
    ) -> None:
        """Single symbol load should be <100ms."""
        adapter, _ = adapter_with_large_data

        # Warm up
        adapter.load(symbol="SYM0000", version="v1")

        # Measure
        times = []
        for i in range(10):
            symbol = f"SYM{i:04d}"
            start = time.perf_counter()
            adapter.load(symbol=symbol, version="v1")
            times.append(time.perf_counter() - start)

        avg_time = sum(times) / len(times)
        print(f"\nAverage single symbol load: {avg_time*1000:.2f}ms")

        assert avg_time < 0.1, f"Single load took {avg_time*1000:.2f}ms, expected <100ms"

    def test_date_range_filter_performance(
        self,
        adapter_with_large_data: tuple[StubDataAdapter, pd.DataFrame],
    ) -> None:
        """Date range filtering should add minimal overhead."""
        adapter, dates = adapter_with_large_data
        from datetime import date

        start_date = date(2005, 1, 1)
        end_date = date(2010, 12, 31)

        # Measure without filter
        start = time.perf_counter()
        for i in range(10):
            adapter.load(symbol=f"SYM{i:04d}", version="v1")
        time_no_filter = time.perf_counter() - start

        # Measure with filter
        start = time.perf_counter()
        for i in range(10):
            adapter.load(
                symbol=f"SYM{i:04d}",
                version="v1",
                start_date=start_date,
                end_date=end_date,
            )
        time_with_filter = time.perf_counter() - start

        overhead_ms = (time_with_filter - time_no_filter) * 1000
        print(f"\nWithout filter: {time_no_filter*1000:.2f}ms")
        print(f"With filter: {time_with_filter*1000:.2f}ms")
        print(f"Overhead: {overhead_ms:.2f}ms")

        # Filter should add <50ms overhead for 10 loads (5ms per load)
        # Using absolute time since percentage is misleading for fast operations
        assert overhead_ms < 50, f"Filter overhead {overhead_ms:.2f}ms exceeds 50ms"
        # Also ensure filtered operation is still fast in absolute terms
        assert time_with_filter < 1.0, f"Filtered load took {time_with_filter:.2f}s, expected <1s"

    def test_generate_performance_artifact(
        self,
        adapter_with_large_data: tuple[StubDataAdapter, pd.DataFrame],
        tmp_path: Path,
    ) -> None:
        """Generate performance artifact JSON."""
        adapter, _ = adapter_with_large_data

        # Run full test
        start_time = time.perf_counter()

        loaded_rows = 0
        for i in range(100):
            df = adapter.load(symbol=f"SYM{i:04d}", version="v1")
            loaded_rows += len(df)

        elapsed = time.perf_counter() - start_time

        # Generate artifact
        artifact = {
            "test_name": "data_load_performance",
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {
                "total_rows": loaded_rows,
                "num_symbols": 100,
                "elapsed_seconds": elapsed,
                "rows_per_second": loaded_rows / elapsed,
            },
            "thresholds": {
                "max_seconds": 5.0,
            },
            "passed": elapsed < 5.0,
        }

        # Save artifact
        artifact_path = tmp_path / "performance_test_data_load.json"
        with open(artifact_path, "w") as f:
            json.dump(artifact, f, indent=2)

        print(f"\nArtifact saved to: {artifact_path}")
        print(json.dumps(artifact, indent=2))
