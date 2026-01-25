#!/usr/bin/env python3
"""Risk Calculator CLI - Calculate VaR, CVaR, and Greeks.

Usage:
    python risk_calculator.py --portfolio portfolio.csv --date 2026-01-25
    python risk_calculator.py --portfolio portfolio.csv --scenarios scenarios.yaml

Examples:
    # Calculate VaR for a portfolio
    python risk_calculator.py --portfolio holdings.csv --date 2026-01-25

    # Run stress tests
    python risk_calculator.py --portfolio holdings.csv --scenarios stress_scenarios.yaml

    # Full risk report
    python risk_calculator.py --portfolio holdings.csv --date 2026-01-25 --report
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description="Calculate risk metrics for a portfolio",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--portfolio", "-p",
        type=str,
        required=True,
        help="Path to portfolio CSV file (columns: symbol, position, weight)",
    )

    parser.add_argument(
        "--date", "-d",
        type=str,
        default=str(date.today()),
        help="As-of date for calculations (default: today)",
    )

    parser.add_argument(
        "--data-version",
        type=str,
        default="latest",
        help="Data version to use (default: latest)",
    )

    parser.add_argument(
        "--var-method",
        type=str,
        choices=["historical", "parametric"],
        default="historical",
        help="VaR calculation method (default: historical)",
    )

    parser.add_argument(
        "--confidence",
        type=str,
        default="95,99",
        help="Confidence levels for VaR (default: 95,99)",
    )

    parser.add_argument(
        "--window",
        type=int,
        default=250,
        help="Lookback window in days (default: 250)",
    )

    parser.add_argument(
        "--scenarios", "-s",
        type=str,
        help="Path to stress scenarios YAML file",
    )

    parser.add_argument(
        "--report", "-r",
        action="store_true",
        help="Generate HTML risk report",
    )

    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="artifacts/risk",
        help="Output directory for results (default: artifacts/risk)",
    )

    parser.add_argument(
        "--connection",
        type=str,
        default="lmdb://./arctic_data",
        help="ArcticDB connection string",
    )

    parser.add_argument(
        "--nav",
        type=float,
        default=1000000.0,
        help="Portfolio NAV for scaling (default: 1000000)",
    )

    return parser


def load_portfolio(filepath: str, nav: float) -> "Portfolio":
    """Load portfolio from CSV file.

    Expected columns: symbol, position (or weight)
    """
    from src.core.domain.portfolio import Portfolio

    df = pd.read_csv(filepath)

    if "symbol" not in df.columns:
        raise ValueError("Portfolio CSV must have 'symbol' column")

    # Build positions and weights
    positions = {}
    weights = {}

    if "position" in df.columns:
        for _, row in df.iterrows():
            positions[row["symbol"]] = float(row["position"])
    elif "weight" in df.columns:
        for _, row in df.iterrows():
            weight = float(row["weight"])
            weights[row["symbol"]] = weight
            positions[row["symbol"]] = weight * nav
    else:
        raise ValueError("Portfolio CSV must have 'position' or 'weight' column")

    # Calculate weights if not provided
    if not weights:
        total = sum(abs(p) for p in positions.values())
        weights = {s: abs(p) / total for s, p in positions.items()}

    return Portfolio(
        positions=positions,
        weights=weights,
        nav=nav,
        as_of_date=date.today(),
    )


def load_scenarios(filepath: str) -> list:
    """Load stress scenarios from YAML file."""
    from src.core.domain.stress_scenario import StressScenario

    with open(filepath, "r") as f:
        data = yaml.safe_load(f)

    scenarios = []
    for item in data.get("scenarios", []):
        scenarios.append(
            StressScenario(
                name=item["name"],
                shocks=item["shocks"],
                description=item.get("description", ""),
                date_calibrated=date.today(),
            )
        )

    return scenarios


def main(args: list[str] | None = None) -> int:
    """Main entry point.

    Args:
        args: Command line arguments

    Returns:
        Exit code (0 for success)
    """
    parser = create_parser()
    parsed = parser.parse_args(args)

    # Load portfolio
    portfolio_path = Path(parsed.portfolio)
    if not portfolio_path.exists():
        print(f"Error: Portfolio file not found: {parsed.portfolio}", file=sys.stderr)
        return 1

    print(f"Loading portfolio from {parsed.portfolio}...")
    try:
        portfolio = load_portfolio(parsed.portfolio, parsed.nav)
    except Exception as e:
        print(f"Error loading portfolio: {e}", file=sys.stderr)
        return 1

    print(f"Portfolio loaded: {len(portfolio.positions)} positions, NAV=${portfolio.nav:,.0f}")

    # Parse parameters
    as_of = date.fromisoformat(parsed.date)
    confidence_levels = [float(c) / 100 for c in parsed.confidence.split(",")]

    # Lazy imports
    from src.adapters.arcticdb_adapter import ArcticDBAdapter
    from src.adapters.ore_adapter import OREAdapter
    from src.core.services.risk_calculation_service import (
        RiskCalculationService,
        RiskCalculationRequest,
    )

    # Create adapters
    data_adapter = ArcticDBAdapter(parsed.connection)
    risk_adapter = OREAdapter()

    # Create service
    service = RiskCalculationService(
        data_port=data_adapter,
        risk_port=risk_adapter,
        report_port=None,
    )

    # Load market data
    print(f"\nLoading market data...")
    try:
        request = RiskCalculationRequest(
            portfolio=portfolio,
            market_data_version=parsed.data_version if parsed.data_version != "latest" else "v1",
            methods=[parsed.var_method],
            confidence_levels=confidence_levels,
            window_days=parsed.window,
            generate_report=parsed.report,
        )

        response = service.calculate(request)
    except Exception as e:
        print(f"Error calculating risk: {e}", file=sys.stderr)
        return 1

    # Print VaR results
    print("\n" + "=" * 50)
    print("VALUE AT RISK (VaR)")
    print("=" * 50)
    for level, value in response.metrics.var.items():
        print(f"  {level} VaR: ${abs(value):,.0f} ({abs(value/portfolio.nav)*100:.2f}%)")

    # Print CVaR results
    print("\n" + "=" * 50)
    print("CONDITIONAL VaR (CVaR / Expected Shortfall)")
    print("=" * 50)
    for level, value in response.metrics.cvar.items():
        print(f"  {level} CVaR: ${abs(value):,.0f} ({abs(value/portfolio.nav)*100:.2f}%)")

    # Print Greeks
    print("\n" + "=" * 50)
    print("GREEKS")
    print("=" * 50)
    greeks_dict = response.metrics.greeks.to_dict()
    for greek, value in greeks_dict.items():
        if value is not None:
            print(f"  {greek}: {value:.4f}")

    # Run stress tests if scenarios provided
    if parsed.scenarios:
        scenarios_path = Path(parsed.scenarios)
        if not scenarios_path.exists():
            print(f"Warning: Scenarios file not found: {parsed.scenarios}", file=sys.stderr)
        else:
            print(f"\nLoading stress scenarios from {parsed.scenarios}...")
            scenarios = load_scenarios(parsed.scenarios)

            from src.core.services.stress_testing_service import (
                StressTestingService,
                StressTestRequest,
            )

            stress_service = StressTestingService(
                data_port=data_adapter,
                risk_port=risk_adapter,
                report_port=None,
            )

            stress_request = StressTestRequest(
                portfolio=portfolio,
                scenarios=scenarios,
                data_version=parsed.data_version if parsed.data_version != "latest" else None,
                generate_report=False,
            )

            stress_response = stress_service.run(stress_request)

            print("\n" + "=" * 50)
            print("STRESS TEST RESULTS")
            print("=" * 50)
            print(f"{'Scenario':<30} {'P&L':>15} {'% Change':>12}")
            print("-" * 57)
            for _, row in stress_response.results.iterrows():
                print(f"{row['scenario']:<30} ${row['pnl']:>14,.0f} {row['pct_change']*100:>11.2f}%")

            print("-" * 57)
            print(f"{'Worst Case:':<30} ${stress_response.max_loss:>14,.0f}")

    # Save results
    output_dir = Path(parsed.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = output_dir / f"risk_{timestamp}.json"

    results = {
        "portfolio": {
            "positions": list(portfolio.positions.keys()),
            "nav": portfolio.nav,
            "as_of_date": str(as_of),
        },
        "var": {k: float(v) for k, v in response.metrics.var.items()},
        "cvar": {k: float(v) for k, v in response.metrics.cvar.items()},
        "greeks": response.metrics.greeks.to_dict(),
        "parameters": {
            "method": parsed.var_method,
            "confidence_levels": confidence_levels,
            "window_days": parsed.window,
        },
    }

    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {results_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
