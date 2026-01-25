#!/usr/bin/env python3
"""Optimizer Runner CLI - Run portfolio optimization.

Usage:
    python optimizer_runner.py --alpha alpha.csv --constraints constraints.yaml
    python optimizer_runner.py --universe AAPL,MSFT,GOOGL --objective max_sharpe

Examples:
    # Run optimization with alpha signals
    python optimizer_runner.py --alpha alpha.csv --objective max_sharpe

    # Run with constraints
    python optimizer_runner.py --alpha alpha.csv --constraints constraints.yaml

    # Generate trades from current portfolio
    python optimizer_runner.py --alpha alpha.csv --current-portfolio current.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description="Run portfolio optimization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--alpha", "-a",
        type=str,
        help="Path to alpha signals CSV (columns: symbol, alpha)",
    )

    parser.add_argument(
        "--universe", "-u",
        type=str,
        help="Comma-separated list of symbols (if no alpha file)",
    )

    parser.add_argument(
        "--constraints", "-c",
        type=str,
        help="Path to constraints YAML file",
    )

    parser.add_argument(
        "--current-portfolio", "-p",
        type=str,
        help="Path to current portfolio CSV for trade generation",
    )

    parser.add_argument(
        "--objective", "-o",
        type=str,
        choices=["max_sharpe", "min_variance", "max_return"],
        default="max_sharpe",
        help="Optimization objective (default: max_sharpe)",
    )

    parser.add_argument(
        "--risk-model",
        type=str,
        help="Path to risk model (covariance matrix) CSV",
    )

    parser.add_argument(
        "--max-position",
        type=float,
        default=0.10,
        help="Maximum position size (default: 0.10 = 10%%)",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Optimization timeout in seconds (default: 30)",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="artifacts/optimization",
        help="Output directory (default: artifacts/optimization)",
    )

    parser.add_argument(
        "--nav",
        type=float,
        default=1000000.0,
        help="Portfolio NAV for trade sizing (default: 1000000)",
    )

    return parser


def load_alpha(filepath: str) -> pd.Series:
    """Load alpha signals from CSV."""
    df = pd.read_csv(filepath)
    if "symbol" not in df.columns:
        raise ValueError("Alpha CSV must have 'symbol' column")
    if "alpha" not in df.columns:
        raise ValueError("Alpha CSV must have 'alpha' column")
    return pd.Series(df["alpha"].values, index=df["symbol"].values)


def load_constraints(filepath: str) -> list:
    """Load constraints from YAML file."""
    from src.core.domain.constraint import Constraint, ConstraintType, Bounds

    with open(filepath, "r") as f:
        data = yaml.safe_load(f)

    constraints = []
    for item in data.get("constraints", []):
        constraint_type = ConstraintType[item["type"].upper()]
        bounds = Bounds(
            lower=item.get("lower"),
            upper=item.get("upper"),
        )
        constraints.append(
            Constraint(
                type=constraint_type,
                bounds=bounds,
                securities=item.get("securities", []),
                name=item.get("name", ""),
            )
        )

    return constraints


def load_current_portfolio(filepath: str, nav: float):
    """Load current portfolio from CSV."""
    from src.core.domain.portfolio import Portfolio

    df = pd.read_csv(filepath)
    if "symbol" not in df.columns:
        raise ValueError("Portfolio CSV must have 'symbol' column")

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

    if not weights:
        total = sum(abs(p) for p in positions.values())
        weights = {s: abs(p) / total for s, p in positions.items()}

    return Portfolio(
        positions=positions,
        weights=weights,
        nav=nav,
        as_of_date=date.today(),
    )


def generate_risk_model(symbols: list[str]) -> pd.DataFrame:
    """Generate simple risk model (identity covariance)."""
    n = len(symbols)
    # Use identity matrix scaled by typical volatility
    cov = np.eye(n) * 0.04  # 20% annual volatility
    return pd.DataFrame(cov, index=symbols, columns=symbols)


def main(args: list[str] | None = None) -> int:
    """Main entry point."""
    parser = create_parser()
    parsed = parser.parse_args(args)

    # Load alpha signals
    if parsed.alpha:
        alpha_path = Path(parsed.alpha)
        if not alpha_path.exists():
            print(f"Error: Alpha file not found: {parsed.alpha}", file=sys.stderr)
            return 1
        print(f"Loading alpha signals from {parsed.alpha}...")
        alpha = load_alpha(parsed.alpha)
    elif parsed.universe:
        # Generate equal alpha for all symbols
        symbols = parsed.universe.split(",")
        alpha = pd.Series(1.0, index=symbols)
        print(f"Using equal alpha for universe: {', '.join(symbols)}")
    else:
        parser.error("Either --alpha or --universe is required")
        return 1

    symbols = list(alpha.index)
    print(f"Optimizing {len(symbols)} symbols")

    # Load or generate risk model
    if parsed.risk_model:
        risk_model = pd.read_csv(parsed.risk_model, index_col=0)
    else:
        print("Generating default risk model (identity covariance)...")
        risk_model = generate_risk_model(symbols)

    # Load constraints
    constraints = []
    if parsed.constraints:
        constraints_path = Path(parsed.constraints)
        if not constraints_path.exists():
            print(f"Error: Constraints file not found: {parsed.constraints}", file=sys.stderr)
            return 1
        print(f"Loading constraints from {parsed.constraints}...")
        constraints = load_constraints(parsed.constraints)
        print(f"Loaded {len(constraints)} constraints")

    # Add default max position constraint
    from src.core.domain.constraint import Constraint, ConstraintType, Bounds

    if parsed.max_position < 1.0:
        for symbol in symbols:
            constraints.append(
                Constraint(
                    type=ConstraintType.POSITION_LIMIT,
                    bounds=Bounds(lower=0.0, upper=parsed.max_position),
                    securities=[symbol],
                    name=f"{symbol} max {parsed.max_position:.0%}",
                )
            )

    # Run optimization
    print(f"\nRunning {parsed.objective} optimization...")

    try:
        from src.adapters.optimizer_adapter import OptimizerAdapter

        optimizer = OptimizerAdapter(timeout_seconds=parsed.timeout)

        target_portfolio = optimizer.optimize(
            alpha=alpha,
            risk_model=risk_model,
            constraints=constraints,
            objective=parsed.objective,
        )
    except ImportError:
        print("Error: cvxpy not installed. Install with: pip install cvxpy", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Optimization failed: {e}", file=sys.stderr)
        return 1

    # Print results
    print("\n" + "=" * 50)
    print("OPTIMAL PORTFOLIO WEIGHTS")
    print("=" * 50)
    print(f"{'Symbol':<10} {'Weight':>12}")
    print("-" * 22)

    sorted_weights = sorted(
        target_portfolio.weights.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    for symbol, weight in sorted_weights:
        if abs(weight) > 0.001:
            print(f"{symbol:<10} {weight:>11.2%}")

    print("-" * 22)
    print(f"{'Total':<10} {sum(target_portfolio.weights.values()):>11.2%}")

    # Generate trades if current portfolio provided
    trades = []
    if parsed.current_portfolio:
        current_path = Path(parsed.current_portfolio)
        if not current_path.exists():
            print(f"Warning: Current portfolio not found: {parsed.current_portfolio}", file=sys.stderr)
        else:
            print(f"\nLoading current portfolio from {parsed.current_portfolio}...")
            current = load_current_portfolio(parsed.current_portfolio, parsed.nav)

            from src.core.services.optimization_service import OptimizationService

            # Calculate trades
            all_symbols = set(current.symbols) | set(target_portfolio.symbols)

            print("\n" + "=" * 50)
            print("TRADE LIST")
            print("=" * 50)
            print(f"{'Symbol':<10} {'Side':<6} {'Notional':>15}")
            print("-" * 31)

            for symbol in sorted(all_symbols):
                current_weight = current.get_weight(symbol)
                target_weight = target_portfolio.weights.get(symbol, 0.0)
                weight_change = target_weight - current_weight

                if abs(weight_change) > 0.001:
                    side = "BUY" if weight_change > 0 else "SELL"
                    notional = abs(weight_change) * parsed.nav
                    print(f"{symbol:<10} {side:<6} ${notional:>14,.0f}")
                    trades.append({
                        "symbol": symbol,
                        "side": side.lower(),
                        "notional": notional,
                        "weight_change": weight_change,
                    })

            print("-" * 31)
            total_turnover = sum(t["notional"] for t in trades) / 2
            print(f"{'Turnover':<10} {'':6} ${total_turnover:>14,.0f}")

    # Save results
    output_dir = Path(parsed.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = output_dir / f"optimization_{timestamp}.json"

    results = {
        "objective": parsed.objective,
        "symbols": symbols,
        "optimal_weights": target_portfolio.weights,
        "trades": trades,
        "constraints_count": len(constraints),
        "timestamp": timestamp,
    }

    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {results_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
