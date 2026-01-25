#!/usr/bin/env python3
"""Backtest Runner CLI - Execute backtests from configuration.

Usage:
    python backtest_runner.py --config backtest_config.yaml
    python backtest_runner.py --universe AAPL,MSFT,GOOGL --start 2020-01-01 --end 2020-12-31

Examples:
    # Run backtest from config file
    python backtest_runner.py --config config/momentum_strategy.yaml

    # Run backtest with inline parameters
    python backtest_runner.py --universe AAPL,MSFT --start 2020-01-01 --end 2020-12-31 --strategy momentum

    # Generate tearsheet
    python backtest_runner.py --config config/strategy.yaml --tearsheet
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description="Run backtests from configuration or command line",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--config", "-c",
        type=str,
        help="Path to YAML configuration file",
    )

    parser.add_argument(
        "--universe", "-u",
        type=str,
        help="Comma-separated list of symbols (e.g., AAPL,MSFT,GOOGL)",
    )

    parser.add_argument(
        "--start", "-s",
        type=str,
        help="Start date (YYYY-MM-DD)",
    )

    parser.add_argument(
        "--end", "-e",
        type=str,
        help="End date (YYYY-MM-DD)",
    )

    parser.add_argument(
        "--strategy",
        type=str,
        choices=["equal_weight", "momentum", "mean_reversion"],
        default="equal_weight",
        help="Strategy type (default: equal_weight)",
    )

    parser.add_argument(
        "--rebalance",
        type=str,
        choices=["daily", "weekly", "monthly", "quarterly"],
        default="monthly",
        help="Rebalancing frequency (default: monthly)",
    )

    parser.add_argument(
        "--data-version",
        type=str,
        default="latest",
        help="Data version to use (default: latest)",
    )

    parser.add_argument(
        "--spread-bps",
        type=float,
        default=5.0,
        help="Spread cost in basis points (default: 5)",
    )

    parser.add_argument(
        "--commission-bps",
        type=float,
        default=2.0,
        help="Commission cost in basis points (default: 2)",
    )

    parser.add_argument(
        "--tearsheet", "-t",
        action="store_true",
        help="Generate HTML tearsheet",
    )

    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="artifacts/backtests",
        help="Output directory for results (default: artifacts/backtests)",
    )

    parser.add_argument(
        "--connection",
        type=str,
        default="lmdb://./arctic_data",
        help="ArcticDB connection string",
    )

    return parser


def load_config(config_path: str) -> dict[str, Any]:
    """Load configuration from YAML file."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def create_signal_generator(strategy: str):
    """Create signal generator function based on strategy type."""
    def equal_weight(prices: pd.DataFrame) -> pd.DataFrame:
        """Equal weight all assets."""
        n = len(prices.columns)
        return pd.DataFrame(1.0 / n, index=prices.index, columns=prices.columns)

    def momentum(prices: pd.DataFrame) -> pd.DataFrame:
        """12-month momentum strategy."""
        returns = prices.pct_change(periods=252).fillna(0)
        ranks = returns.rank(axis=1, pct=True)
        # Long top half, short bottom half
        signals = (ranks - 0.5) * 2
        return signals

    def mean_reversion(prices: pd.DataFrame) -> pd.DataFrame:
        """Mean reversion (contrarian) strategy."""
        returns = prices.pct_change(periods=21).fillna(0)
        ranks = returns.rank(axis=1, pct=True)
        # Short recent winners, long recent losers
        signals = (0.5 - ranks) * 2
        return signals

    strategies = {
        "equal_weight": equal_weight,
        "momentum": momentum,
        "mean_reversion": mean_reversion,
    }

    return strategies.get(strategy, equal_weight)


def main(args: list[str] | None = None) -> int:
    """Main entry point.

    Args:
        args: Command line arguments

    Returns:
        Exit code (0 for success)
    """
    parser = create_parser()
    parsed = parser.parse_args(args)

    # Load config if provided
    config: dict[str, Any] = {}
    if parsed.config:
        config_path = Path(parsed.config)
        if not config_path.exists():
            print(f"Error: Config file not found: {parsed.config}", file=sys.stderr)
            return 1
        config = load_config(parsed.config)

    # Override config with command line args
    universe = parsed.universe.split(",") if parsed.universe else config.get("universe", [])
    start_date_str = parsed.start or config.get("start_date")
    end_date_str = parsed.end or config.get("end_date")
    strategy = parsed.strategy or config.get("strategy", "equal_weight")
    rebalance_freq = parsed.rebalance or config.get("rebalance_freq", "monthly")
    data_version = parsed.data_version or config.get("data_version", "latest")

    # Validate required parameters
    if not universe:
        parser.error("--universe is required (or specify in config)")
    if not start_date_str:
        parser.error("--start is required (or specify in config)")
    if not end_date_str:
        parser.error("--end is required (or specify in config)")

    # Parse dates
    start_date = date.fromisoformat(start_date_str)
    end_date = date.fromisoformat(end_date_str)

    print(f"Running backtest:")
    print(f"  Universe: {', '.join(universe)}")
    print(f"  Period: {start_date} to {end_date}")
    print(f"  Strategy: {strategy}")
    print(f"  Rebalance: {rebalance_freq}")

    # Lazy imports
    from src.adapters.arcticdb_adapter import ArcticDBAdapter
    from src.adapters.vectorbt_adapter import VectorBTAdapter
    from src.core.services.backtest_engine import BacktestEngine, BacktestRequest

    # Create adapters
    data_adapter = ArcticDBAdapter(parsed.connection)
    backtest_adapter = VectorBTAdapter()

    # Create report adapter if tearsheet requested
    report_adapter = None
    if parsed.tearsheet:
        try:
            from src.adapters.quantstats_adapter import QuantStatsAdapter
            report_adapter = QuantStatsAdapter()
        except ImportError:
            print("Warning: quantstats not installed, tearsheet disabled", file=sys.stderr)

    # Create engine
    engine = BacktestEngine(data_adapter, backtest_adapter, report_adapter)

    # Create request
    signal_generator = create_signal_generator(strategy)

    request = BacktestRequest(
        universe=universe,
        start_date=start_date,
        end_date=end_date,
        data_version=data_version if data_version != "latest" else None,
        signal_generator=signal_generator,
        rebalance_freq=rebalance_freq,
        transaction_costs={
            "spread_bps": parsed.spread_bps,
            "commission_bps": parsed.commission_bps,
        },
        generate_tearsheet=parsed.tearsheet and report_adapter is not None,
        output_dir=parsed.output_dir,
    )

    # Run backtest
    print("\nRunning simulation...")
    try:
        response = engine.run(request)
    except Exception as e:
        print(f"Error running backtest: {e}", file=sys.stderr)
        return 1

    # Print results
    print("\nBacktest Results:")
    print("-" * 40)
    for metric, value in response.metrics_summary.items():
        if isinstance(value, float):
            if "return" in metric or "drawdown" in metric or "rate" in metric:
                print(f"  {metric}: {value:.2%}")
            else:
                print(f"  {metric}: {value:.4f}")
        else:
            print(f"  {metric}: {value}")

    if response.tearsheet_path:
        print(f"\nTearsheet generated: {response.tearsheet_path}")

    # Save results
    output_dir = Path(parsed.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = output_dir / f"backtest_{timestamp}.json"

    import json
    results = {
        "config": {
            "universe": universe,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "strategy": strategy,
            "rebalance_freq": rebalance_freq,
        },
        "metrics": response.metrics_summary,
        "tearsheet_path": response.tearsheet_path,
    }

    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Results saved to: {results_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
