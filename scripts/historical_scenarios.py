#!/usr/bin/env python3
"""Historical Scenario Replay - Test against known market events.

This script replays historical market crashes and validates that the
stress testing framework produces expected results.

Usage:
    python scripts/historical_scenarios.py --portfolio 10000000
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from src.adapters.ore_adapter import OREAdapter
from src.core.domain.portfolio import Portfolio
from src.core.domain.stress_scenario import StressScenario


# Historical market events with documented drawdowns
HISTORICAL_EVENTS = {
    "Black Monday 1987": {
        "date": "1987-10-19",
        "spx_drawdown": -0.226,
        "description": "Single-day crash, program trading",
        "duration": "1 day",
    },
    "Dot-com Crash 2000-2002": {
        "date": "2000-03-24 to 2002-10-09",
        "spx_drawdown": -0.49,
        "description": "Tech bubble burst",
        "duration": "31 months",
    },
    "2008 Financial Crisis": {
        "date": "2007-10-09 to 2009-03-09",
        "spx_drawdown": -0.57,
        "description": "Lehman collapse, credit freeze, GFC",
        "duration": "17 months",
    },
    "Flash Crash 2010": {
        "date": "2010-05-06",
        "spx_drawdown": -0.09,
        "description": "Intraday algorithmic crash",
        "duration": "36 minutes",
    },
    "European Debt Crisis 2011": {
        "date": "2011-04-29 to 2011-10-03",
        "spx_drawdown": -0.19,
        "description": "Greek debt crisis contagion",
        "duration": "5 months",
    },
    "COVID Crash 2020": {
        "date": "2020-02-19 to 2020-03-23",
        "spx_drawdown": -0.34,
        "description": "Pandemic market crash",
        "duration": "33 days",
    },
    "2022 Bear Market": {
        "date": "2022-01-03 to 2022-10-12",
        "spx_drawdown": -0.25,
        "description": "Fed rate hikes, inflation fears",
        "duration": "9 months",
    },
}

# Sector-specific events
SECTOR_EVENTS = {
    "Tech Selloff 2022": {
        "shocks": {"AAPL": -0.28, "GOOGL": -0.39, "MSFT": -0.29, "AMZN": -0.50, "META": -0.64},
        "description": "Tech sector drawdown in 2022",
    },
    "Bank Crisis 2023": {
        "shocks": {"JPM": -0.10, "BAC": -0.25, "WFC": -0.20, "GS": -0.15},
        "description": "Regional bank failures",
    },
    "Energy Crash 2020": {
        "shocks": {"XOM": -0.45, "CVX": -0.40, "COP": -0.55},
        "description": "Oil price collapse",
    },
}


def create_historical_scenarios() -> list[StressScenario]:
    """Create stress scenarios from historical events."""
    scenarios = []

    for name, event in HISTORICAL_EVENTS.items():
        scenarios.append(
            StressScenario(
                name=name,
                shocks={"equity_all": event["spx_drawdown"]},
                description=f"{event['description']} ({event['duration']})",
                date_calibrated=date.today(),
            )
        )

    return scenarios


def run_historical_replay(
    portfolio: Portfolio,
    market_data: pd.DataFrame,
) -> pd.DataFrame:
    """Run stress tests for all historical scenarios."""
    risk_adapter = OREAdapter()
    scenarios = create_historical_scenarios()

    print(f"Running {len(scenarios)} historical scenarios...")

    results = risk_adapter.stress_test(
        portfolio=portfolio,
        market_data=market_data,
        scenarios=scenarios,
    )

    return results


def validate_results(
    results: pd.DataFrame,
    portfolio_nav: float,
) -> list[dict]:
    """Validate stress test results against expected losses."""
    validation = []

    for scenario_name, event in HISTORICAL_EVENTS.items():
        scenario_result = results[results["scenario"] == scenario_name]

        if len(scenario_result) == 0:
            validation.append({
                "scenario": scenario_name,
                "status": "MISSING",
                "message": "Scenario not found in results",
            })
            continue

        row = scenario_result.iloc[0]
        expected_loss = portfolio_nav * event["spx_drawdown"]
        actual_loss = row["pnl"]
        pct_change = row["pct_change"]

        # Check if the computed loss matches expected (within 1% tolerance)
        tolerance = 0.01
        matches = abs(pct_change - event["spx_drawdown"]) < tolerance

        validation.append({
            "scenario": scenario_name,
            "historical_drawdown": f"{event['spx_drawdown']:.1%}",
            "computed_drawdown": f"{pct_change:.1%}",
            "expected_loss": expected_loss,
            "computed_loss": actual_loss,
            "matches": matches,
            "status": "PASS" if matches else "FAIL",
            "description": event["description"],
        })

    return validation


def print_report(
    validation: list[dict],
    portfolio_nav: float,
) -> None:
    """Print formatted validation report."""
    print("\n" + "=" * 80)
    print("HISTORICAL SCENARIO REPLAY REPORT")
    print("=" * 80)
    print(f"\nPortfolio NAV: ${portfolio_nav:,.0f}")
    print()

    # Summary table
    print(f"{'Scenario':<30} {'Historical':<12} {'Computed':<12} {'Loss':<15} {'Status':<8}")
    print("-" * 80)

    passed = 0
    for v in validation:
        if v["status"] == "PASS":
            passed += 1
            status_str = "✓ PASS"
        elif v["status"] == "FAIL":
            status_str = "✗ FAIL"
        else:
            status_str = "? " + v["status"]

        loss_str = f"${v.get('computed_loss', 0):,.0f}" if "computed_loss" in v else "N/A"

        print(
            f"{v['scenario']:<30} "
            f"{v.get('historical_drawdown', 'N/A'):<12} "
            f"{v.get('computed_drawdown', 'N/A'):<12} "
            f"{loss_str:<15} "
            f"{status_str:<8}"
        )

    print("-" * 80)
    print(f"\nValidation Summary: {passed}/{len(validation)} scenarios passed")

    # Detailed findings
    print("\nScenario Details:")
    for v in validation:
        print(f"\n  {v['scenario']}:")
        print(f"    {v.get('description', 'No description')}")
        if v["status"] == "PASS":
            print(f"    ✓ Stress test correctly replicates historical drawdown")
        elif v["status"] == "FAIL":
            print(f"    ✗ Mismatch: expected {v.get('historical_drawdown')}, got {v.get('computed_drawdown')}")

    print("\n" + "=" * 80)


def run_sector_scenarios(
    symbols: list[str],
    nav: float,
    market_data: pd.DataFrame,
) -> None:
    """Run sector-specific stress scenarios."""
    risk_adapter = OREAdapter()

    print("\n" + "=" * 80)
    print("SECTOR STRESS SCENARIOS")
    print("=" * 80)

    for event_name, event in SECTOR_EVENTS.items():
        # Check if portfolio has any of the affected symbols
        affected_symbols = [s for s in symbols if s in event["shocks"]]

        if not affected_symbols:
            print(f"\n{event_name}: No affected positions")
            continue

        # Create portfolio with affected symbols
        weights = {s: 1 / len(affected_symbols) for s in affected_symbols}
        positions = {s: nav * w for s, w in weights.items()}

        portfolio = Portfolio(
            positions=positions,
            weights=weights,
            nav=sum(positions.values()),
            as_of_date=date.today(),
        )

        # Create scenario with only relevant shocks
        relevant_shocks = {s: event["shocks"][s] for s in affected_symbols}
        scenario = StressScenario(
            name=event_name,
            shocks=relevant_shocks,
            description=event["description"],
            date_calibrated=date.today(),
        )

        results = risk_adapter.stress_test(
            portfolio=portfolio,
            market_data=market_data,
            scenarios=[scenario],
        )

        row = results.iloc[0]
        print(f"\n{event_name}:")
        print(f"  Description: {event['description']}")
        print(f"  Affected positions: {', '.join(affected_symbols)}")
        print(f"  Portfolio exposure: ${portfolio.nav:,.0f}")
        print(f"  Estimated loss: ${row['pnl']:,.0f} ({row['pct_change']:.1%})")


def main(args: list[str] | None = None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Replay historical market scenarios"
    )
    parser.add_argument(
        "--portfolio",
        type=float,
        default=10_000_000,
        help="Portfolio NAV (default: 10,000,000)",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default="AAPL,GOOGL,MSFT,AMZN,META",
        help="Comma-separated list of symbols",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file for results (JSON)",
    )
    parser.add_argument(
        "--sector-scenarios",
        action="store_true",
        help="Also run sector-specific scenarios",
    )

    parsed = parser.parse_args(args)

    symbols = parsed.symbols.split(",")
    nav = parsed.portfolio

    # Create portfolio
    weights = {s: 1 / len(symbols) for s in symbols}
    positions = {s: nav * w for s, w in weights.items()}

    portfolio = Portfolio(
        positions=positions,
        weights=weights,
        nav=nav,
        as_of_date=date.today(),
    )

    # Generate sample market data
    np.random.seed(42)
    dates = pd.date_range(end=date.today(), periods=252, freq="B")
    market_data = pd.DataFrame({
        symbol: 100 * np.cumprod(1 + np.random.randn(len(dates)) * 0.02)
        for symbol in symbols
    }, index=dates)

    # Run historical scenarios
    results = run_historical_replay(portfolio, market_data)

    # Validate results
    validation = validate_results(results, nav)

    # Print report
    print_report(validation, nav)

    # Run sector scenarios if requested
    if parsed.sector_scenarios:
        run_sector_scenarios(symbols, nav, market_data)

    # Save results if requested
    if parsed.output:
        output_data = {
            "portfolio_nav": nav,
            "symbols": symbols,
            "historical_events": HISTORICAL_EVENTS,
            "stress_results": results.to_dict(orient="records"),
            "validation": validation,
        }

        parsed.output.parent.mkdir(parents=True, exist_ok=True)
        with open(parsed.output, "w") as f:
            json.dump(output_data, f, indent=2, default=str)

        print(f"\nResults saved to: {parsed.output}")

    # Return exit code based on validation
    all_passed = all(v["status"] == "PASS" for v in validation)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
