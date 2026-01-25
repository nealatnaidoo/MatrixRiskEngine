#!/usr/bin/env python3
"""VaR Backtesting - Validate VaR model accuracy.

This script performs rolling VaR backtesting to validate the risk model.
A good VaR model should have breach rate ≈ (1 - confidence_level).
For 95% VaR, expect ~5% of days to breach.

Usage:
    python scripts/var_backtest.py --confidence 0.95 --lookback 252
"""

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from src.adapters.ore_adapter import OREAdapter
from src.core.domain.portfolio import Portfolio


def generate_sample_data(
    symbols: list[str],
    start_date: date,
    end_date: date,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic market data for testing."""
    np.random.seed(seed)
    dates = pd.date_range(start_date, end_date, freq="B")

    prices = {}
    for symbol in symbols:
        # Random walk with drift
        daily_returns = np.random.randn(len(dates)) * 0.02 + 0.0003
        prices[symbol] = 100 * np.cumprod(1 + daily_returns)

    return pd.DataFrame(prices, index=dates)


def backtest_var_model(
    market_data: pd.DataFrame,
    confidence_level: float = 0.95,
    lookback_days: int = 252,
    nav: float = 1_000_000,
) -> dict:
    """
    Backtest VaR predictions against actual losses.

    Args:
        market_data: DataFrame with price data
        confidence_level: VaR confidence level (e.g., 0.95)
        lookback_days: Historical window for VaR calculation
        nav: Portfolio NAV

    Returns:
        Dictionary with backtest results and statistics
    """
    risk_adapter = OREAdapter()
    symbols = list(market_data.columns)
    dates = market_data.index

    results = []

    print(f"Running VaR backtest...")
    print(f"  Confidence: {confidence_level:.0%}")
    print(f"  Lookback: {lookback_days} days")
    print(f"  Test period: {dates[lookback_days].date()} to {dates[-2].date()}")
    print()

    for i in range(lookback_days, len(dates) - 1):
        test_date = dates[i]

        # Create equal-weight portfolio
        weights = {s: 1 / len(symbols) for s in symbols}
        positions = {s: nav * w for s, w in weights.items()}

        portfolio = Portfolio(
            positions=positions,
            weights=weights,
            nav=nav,
            as_of_date=test_date.date(),
        )

        # Calculate VaR using historical data up to test_date
        historical_data = market_data.iloc[i - lookback_days : i]

        var_result = risk_adapter.calculate_var(
            portfolio=portfolio,
            market_data=historical_data,
            method="historical",
            confidence_levels=[confidence_level],
            window_days=lookback_days,
        )

        confidence_key = f"{int(confidence_level * 100)}%"
        predicted_var = var_result[confidence_key]

        # Calculate actual next-day P&L
        today_prices = market_data.iloc[i]
        tomorrow_prices = market_data.iloc[i + 1]
        daily_returns = tomorrow_prices / today_prices - 1

        # Portfolio return (equal weighted)
        portfolio_return = daily_returns.mean()
        actual_pnl = nav * portfolio_return

        # Check if VaR was breached (actual loss exceeded VaR)
        breached = actual_pnl < predicted_var

        results.append({
            "date": test_date.date(),
            "predicted_var": predicted_var,
            "actual_pnl": actual_pnl,
            "breached": breached,
        })

        # Progress indicator
        if (i - lookback_days) % 50 == 0:
            print(f"  Processed {i - lookback_days + 1} / {len(dates) - lookback_days - 1} days")

    results_df = pd.DataFrame(results)

    # Calculate statistics
    n = len(results_df)
    x = results_df["breached"].sum()
    breach_rate = x / n
    expected_breach_rate = 1 - confidence_level

    # Kupiec POF (Proportion of Failures) test
    p = expected_breach_rate
    if 0 < x < n:
        lr_pof = -2 * (
            x * np.log(p / (x / n)) + (n - x) * np.log((1 - p) / (1 - x / n))
        )
    else:
        lr_pof = np.nan

    # Christoffersen Independence test (simplified)
    # Check if breaches cluster
    breaches = results_df["breached"].values
    n00 = n01 = n10 = n11 = 0
    for i in range(1, len(breaches)):
        if not breaches[i - 1] and not breaches[i]:
            n00 += 1
        elif not breaches[i - 1] and breaches[i]:
            n01 += 1
        elif breaches[i - 1] and not breaches[i]:
            n10 += 1
        else:
            n11 += 1

    return {
        "test_parameters": {
            "confidence_level": confidence_level,
            "lookback_days": lookback_days,
            "nav": nav,
        },
        "statistics": {
            "total_days": n,
            "num_breaches": int(x),
            "breach_rate": breach_rate,
            "expected_breach_rate": expected_breach_rate,
            "breach_rate_ratio": breach_rate / expected_breach_rate if expected_breach_rate > 0 else np.nan,
        },
        "kupiec_test": {
            "lr_statistic": lr_pof,
            "critical_value_95": 3.84,  # Chi-squared(1) at 95%
            "critical_value_99": 6.63,  # Chi-squared(1) at 99%
            "reject_at_95": lr_pof > 3.84 if not np.isnan(lr_pof) else None,
            "model_valid_95": lr_pof <= 3.84 if not np.isnan(lr_pof) else None,
        },
        "independence_test": {
            "n00": n00,
            "n01": n01,
            "n10": n10,
            "n11": n11,
        },
        "results": results_df,
    }


def print_report(backtest_result: dict) -> None:
    """Print formatted backtest report."""
    stats = backtest_result["statistics"]
    kupiec = backtest_result["kupiec_test"]
    params = backtest_result["test_parameters"]

    print("\n" + "=" * 60)
    print("VAR BACKTEST REPORT")
    print("=" * 60)

    print(f"\nTest Parameters:")
    print(f"  Confidence Level: {params['confidence_level']:.0%}")
    print(f"  Lookback Window:  {params['lookback_days']} days")
    print(f"  Portfolio NAV:    ${params['nav']:,.0f}")

    print(f"\nBacktest Statistics:")
    print(f"  Total Test Days:    {stats['total_days']}")
    print(f"  Number of Breaches: {stats['num_breaches']}")
    print(f"  Breach Rate:        {stats['breach_rate']:.2%}")
    print(f"  Expected Rate:      {stats['expected_breach_rate']:.2%}")
    print(f"  Ratio (Actual/Exp): {stats['breach_rate_ratio']:.2f}")

    print(f"\nKupiec POF Test:")
    print(f"  LR Statistic:       {kupiec['lr_statistic']:.4f}")
    print(f"  Critical Value 95%: {kupiec['critical_value_95']}")
    print(f"  Critical Value 99%: {kupiec['critical_value_99']}")

    if kupiec["model_valid_95"]:
        print(f"  Result: ✓ MODEL VALID at 95% confidence")
    elif kupiec["model_valid_95"] is False:
        print(f"  Result: ✗ MODEL REJECTED at 95% confidence")
    else:
        print(f"  Result: Unable to compute (edge case)")

    # Interpretation
    print(f"\nInterpretation:")
    ratio = stats["breach_rate_ratio"]
    if 0.8 <= ratio <= 1.2:
        print("  VaR model is well-calibrated (breach rate within 20% of expected)")
    elif ratio < 0.8:
        print("  VaR model may be too conservative (fewer breaches than expected)")
    else:
        print("  VaR model may underestimate risk (more breaches than expected)")

    print("=" * 60)


def main(args: list[str] | None = None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backtest VaR model accuracy"
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.95,
        help="VaR confidence level (default: 0.95)",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=252,
        help="Lookback window in days (default: 252)",
    )
    parser.add_argument(
        "--nav",
        type=float,
        default=1_000_000,
        help="Portfolio NAV (default: 1,000,000)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file for detailed results (JSON)",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default="AAPL,GOOGL,MSFT,AMZN,META",
        help="Comma-separated list of symbols",
    )

    parsed = parser.parse_args(args)

    symbols = parsed.symbols.split(",")

    # Generate sample data (3 years)
    end_date = date.today()
    start_date = end_date - timedelta(days=3 * 365)

    print(f"Generating sample market data for {len(symbols)} symbols...")
    market_data = generate_sample_data(symbols, start_date, end_date)
    print(f"  Date range: {market_data.index[0].date()} to {market_data.index[-1].date()}")
    print(f"  Total days: {len(market_data)}")
    print()

    # Run backtest
    result = backtest_var_model(
        market_data=market_data,
        confidence_level=parsed.confidence,
        lookback_days=parsed.lookback,
        nav=parsed.nav,
    )

    # Print report
    print_report(result)

    # Save detailed results if requested
    if parsed.output:
        output_data = {
            "test_parameters": result["test_parameters"],
            "statistics": result["statistics"],
            "kupiec_test": result["kupiec_test"],
            "independence_test": result["independence_test"],
            "daily_results": result["results"].to_dict(orient="records"),
        }

        # Convert dates to strings for JSON
        for record in output_data["daily_results"]:
            record["date"] = str(record["date"])

        parsed.output.parent.mkdir(parents=True, exist_ok=True)
        with open(parsed.output, "w") as f:
            json.dump(output_data, f, indent=2, default=str)

        print(f"\nDetailed results saved to: {parsed.output}")

    # Return exit code based on model validity
    if result["kupiec_test"]["model_valid_95"]:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
