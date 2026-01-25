#!/usr/bin/env python3
"""Comprehensive Risk Validation Report.

Generates a full risk validation report including:
- VaR analysis (multiple confidence levels and methods)
- CVaR (Expected Shortfall)
- Stress testing
- Greeks (if applicable)
- Risk attribution

Usage:
    python -m scripts.risk_validation_report --portfolio portfolio.json
    python -m scripts.risk_validation_report --nav 10000000 --symbols AAPL,GOOGL,MSFT
"""

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from src.adapters.ore_adapter import OREAdapter
from src.core.domain.portfolio import Portfolio
from src.core.domain.stress_scenario import StressScenario


def load_portfolio(portfolio_path: Path) -> Portfolio:
    """Load portfolio from JSON file."""
    with open(portfolio_path) as f:
        data = json.load(f)

    return Portfolio(
        positions=data["positions"],
        weights=data["weights"],
        nav=data["nav"],
        as_of_date=date.fromisoformat(data["as_of_date"]),
    )


def create_portfolio(symbols: list[str], nav: float) -> Portfolio:
    """Create equal-weight portfolio."""
    weights = {s: 1 / len(symbols) for s in symbols}
    positions = {s: nav * w for s, w in weights.items()}

    return Portfolio(
        positions=positions,
        weights=weights,
        nav=nav,
        as_of_date=date.today(),
    )


def generate_market_data(
    symbols: list[str],
    days: int = 504,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic market data."""
    np.random.seed(seed)
    dates = pd.date_range(end=date.today(), periods=days, freq="B")

    data = {}
    for symbol in symbols:
        # Add some correlation structure
        market_return = np.random.randn(len(dates)) * 0.015
        idio_return = np.random.randn(len(dates)) * 0.01
        returns = 0.7 * market_return + 0.3 * idio_return + 0.0002

        data[symbol] = 100 * np.cumprod(1 + returns)

    return pd.DataFrame(data, index=dates)


def compute_var_analysis(
    risk_adapter: OREAdapter,
    portfolio: Portfolio,
    market_data: pd.DataFrame,
) -> dict:
    """Compute comprehensive VaR analysis."""
    confidence_levels = [0.90, 0.95, 0.99]

    # Historical VaR
    hist_var = risk_adapter.calculate_var(
        portfolio=portfolio,
        market_data=market_data,
        method="historical",
        confidence_levels=confidence_levels,
    )

    # Parametric VaR
    param_var = risk_adapter.calculate_var(
        portfolio=portfolio,
        market_data=market_data,
        method="parametric",
        confidence_levels=confidence_levels,
    )

    return {
        "historical": {
            f"{int(cl*100)}%": hist_var[f"{int(cl*100)}%"]
            for cl in confidence_levels
        },
        "parametric": {
            f"{int(cl*100)}%": param_var[f"{int(cl*100)}%"]
            for cl in confidence_levels
        },
        "comparison": {
            f"{int(cl*100)}%": {
                "historical": hist_var[f"{int(cl*100)}%"],
                "parametric": param_var[f"{int(cl*100)}%"],
                "difference_pct": (hist_var[f"{int(cl*100)}%"] - param_var[f"{int(cl*100)}%"]) / abs(param_var[f"{int(cl*100)}%"]) * 100
                if param_var[f"{int(cl*100)}%"] != 0 else 0,
            }
            for cl in confidence_levels
        },
    }


def compute_cvar_analysis(
    risk_adapter: OREAdapter,
    portfolio: Portfolio,
    market_data: pd.DataFrame,
    var_results: dict,
) -> dict:
    """Compute CVaR (Expected Shortfall) analysis."""
    cvar = risk_adapter.calculate_cvar(
        portfolio=portfolio,
        market_data=market_data,
    )

    return {
        "95%": cvar["95%"],
        "99%": cvar["99%"],
        "cvar_var_ratio": {
            "95%": cvar["95%"] / var_results["historical"]["95%"]
            if var_results["historical"]["95%"] != 0 else 0,
            "99%": cvar["99%"] / var_results["historical"]["99%"]
            if var_results["historical"]["99%"] != 0 else 0,
        },
    }


def compute_stress_analysis(
    risk_adapter: OREAdapter,
    portfolio: Portfolio,
    market_data: pd.DataFrame,
) -> dict:
    """Compute stress test analysis."""
    # Standard scenarios
    scenarios = [
        StressScenario("Mild Correction (-10%)", {"equity_all": -0.10},
                      "10% market decline", date.today()),
        StressScenario("Moderate Crash (-20%)", {"equity_all": -0.20},
                      "20% market decline", date.today()),
        StressScenario("Severe Crisis (-40%)", {"equity_all": -0.40},
                      "40% market decline", date.today()),
        StressScenario("Black Swan (-60%)", {"equity_all": -0.60},
                      "60% market decline", date.today()),
        StressScenario("Rally (+20%)", {"equity_all": 0.20},
                      "20% market rally", date.today()),
    ]

    results = risk_adapter.stress_test(
        portfolio=portfolio,
        market_data=market_data,
        scenarios=scenarios,
    )

    return {
        "scenarios": results.to_dict(orient="records"),
        "worst_case": {
            "scenario": results.loc[results["pnl"].idxmin(), "scenario"],
            "pnl": float(results["pnl"].min()),
            "pct_change": float(results["pct_change"].min()),
        },
        "best_case": {
            "scenario": results.loc[results["pnl"].idxmax(), "scenario"],
            "pnl": float(results["pnl"].max()),
            "pct_change": float(results["pct_change"].max()),
        },
    }


def compute_greeks(
    risk_adapter: OREAdapter,
    portfolio: Portfolio,
    market_data: pd.DataFrame,
) -> dict:
    """Compute portfolio Greeks."""
    greeks = risk_adapter.compute_greeks(
        portfolio=portfolio,
        market_data=market_data,
    )

    return {
        "delta": greeks.get("delta"),
        "beta": greeks.get("beta"),
        "gamma": greeks.get("gamma"),
        "vega": greeks.get("vega"),
    }


def compute_risk_attribution(
    portfolio: Portfolio,
    market_data: pd.DataFrame,
) -> dict:
    """Compute risk attribution by position."""
    returns = market_data.pct_change().dropna()

    # Individual volatilities
    vols = returns.std() * np.sqrt(252)

    # Correlation matrix
    corr = returns.corr()

    # Marginal contribution to risk
    portfolio_vol = (returns @ pd.Series(portfolio.weights)).std() * np.sqrt(252)

    attribution = []
    for symbol in portfolio.weights:
        if symbol in returns.columns:
            weight = portfolio.weights[symbol]
            vol = vols[symbol]
            position_risk = weight * vol

            attribution.append({
                "symbol": symbol,
                "weight": weight,
                "volatility": vol,
                "weighted_vol": position_risk,
                "contribution_pct": position_risk / portfolio_vol * 100 if portfolio_vol > 0 else 0,
            })

    return {
        "portfolio_volatility": portfolio_vol,
        "position_attribution": attribution,
        "correlation_matrix": corr.to_dict(),
        "diversification_ratio": sum(a["weighted_vol"] for a in attribution) / portfolio_vol
        if portfolio_vol > 0 else 1,
    }


def generate_report(
    portfolio: Portfolio,
    market_data: pd.DataFrame,
    output_dir: Path,
) -> dict:
    """Generate comprehensive risk validation report."""
    risk_adapter = OREAdapter()

    print("Generating Risk Validation Report...")
    print(f"  Portfolio NAV: ${portfolio.nav:,.0f}")
    print(f"  Positions: {portfolio.num_positions}")
    print()

    report = {
        "metadata": {
            "report_date": datetime.now(timezone.utc).isoformat(),
            "portfolio_nav": portfolio.nav,
            "num_positions": portfolio.num_positions,
            "positions": dict(portfolio.weights),
            "market_data_days": len(market_data),
        },
    }

    # VaR Analysis
    print("  Computing VaR...")
    report["var_analysis"] = compute_var_analysis(
        risk_adapter, portfolio, market_data
    )

    # CVaR Analysis
    print("  Computing CVaR...")
    report["cvar_analysis"] = compute_cvar_analysis(
        risk_adapter, portfolio, market_data, report["var_analysis"]
    )

    # Stress Testing
    print("  Running stress tests...")
    report["stress_analysis"] = compute_stress_analysis(
        risk_adapter, portfolio, market_data
    )

    # Greeks
    print("  Computing Greeks...")
    report["greeks"] = compute_greeks(
        risk_adapter, portfolio, market_data
    )

    # Risk Attribution
    print("  Computing risk attribution...")
    report["risk_attribution"] = compute_risk_attribution(
        portfolio, market_data
    )

    # Summary metrics
    report["summary"] = {
        "var_95_pct": abs(report["var_analysis"]["historical"]["95%"]) / portfolio.nav,
        "var_99_pct": abs(report["var_analysis"]["historical"]["99%"]) / portfolio.nav,
        "cvar_95_pct": abs(report["cvar_analysis"]["95%"]) / portfolio.nav,
        "max_stress_loss_pct": abs(report["stress_analysis"]["worst_case"]["pct_change"]),
        "portfolio_volatility": report["risk_attribution"]["portfolio_volatility"],
        "diversification_ratio": report["risk_attribution"]["diversification_ratio"],
    }

    # Save report
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"risk_validation_report_{date.today()}.json"

    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n  Report saved to: {report_path}")

    return report


def print_summary(report: dict) -> None:
    """Print formatted summary report."""
    nav = report["metadata"]["portfolio_nav"]
    var = report["var_analysis"]
    cvar = report["cvar_analysis"]
    stress = report["stress_analysis"]
    summary = report["summary"]
    attr = report["risk_attribution"]

    print("\n" + "=" * 70)
    print("RISK VALIDATION REPORT")
    print("=" * 70)

    print(f"\nPORTFOLIO OVERVIEW")
    print(f"  NAV:        ${nav:,.0f}")
    print(f"  Positions:  {report['metadata']['num_positions']}")
    print(f"  Data Days:  {report['metadata']['market_data_days']}")

    print(f"\nVALUE AT RISK (1-Day)")
    print(f"  {'Level':<10} {'Historical':<18} {'Parametric':<18} {'% of NAV':<12}")
    print(f"  {'-'*58}")
    for level in ["90%", "95%", "99%"]:
        hist = var["historical"][level]
        param = var["parametric"][level]
        pct = abs(hist) / nav * 100
        print(f"  {level:<10} ${abs(hist):>14,.0f}   ${abs(param):>14,.0f}   {pct:>8.2f}%")

    print(f"\nCONDITIONAL VAR (Expected Shortfall)")
    print(f"  95% CVaR:   ${abs(cvar['95%']):>14,.0f} ({abs(cvar['95%'])/nav*100:.2f}% of NAV)")
    print(f"  99% CVaR:   ${abs(cvar['99%']):>14,.0f} ({abs(cvar['99%'])/nav*100:.2f}% of NAV)")
    print(f"  CVaR/VaR:   {cvar['cvar_var_ratio']['95%']:.2f}x (95%), {cvar['cvar_var_ratio']['99%']:.2f}x (99%)")

    print(f"\nSTRESS TEST RESULTS")
    print(f"  {'Scenario':<30} {'P&L':<18} {'% Change':<12}")
    print(f"  {'-'*60}")
    for s in stress["scenarios"]:
        print(f"  {s['scenario']:<30} ${s['pnl']:>14,.0f}   {s['pct_change']:>8.1%}")
    print(f"  {'-'*60}")
    print(f"  Worst Case: {stress['worst_case']['scenario']}")
    print(f"              ${stress['worst_case']['pnl']:,.0f} ({stress['worst_case']['pct_change']:.1%})")

    print(f"\nRISK ATTRIBUTION")
    print(f"  Portfolio Vol (Ann.): {attr['portfolio_volatility']*100:.1f}%")
    print(f"  Diversification:      {attr['diversification_ratio']:.2f}x")
    print()
    print(f"  {'Symbol':<10} {'Weight':<10} {'Vol':<10} {'Contribution':<12}")
    print(f"  {'-'*42}")
    for p in attr["position_attribution"]:
        print(f"  {p['symbol']:<10} {p['weight']:>8.1%}   {p['volatility']*100:>6.1f}%   {p['contribution_pct']:>8.1f}%")

    print(f"\nRISK LIMITS CHECK")
    limits = {
        "VaR 95% < 5%": summary["var_95_pct"] < 0.05,
        "VaR 99% < 10%": summary["var_99_pct"] < 0.10,
        "Max Stress Loss < 50%": summary["max_stress_loss_pct"] < 0.50,
        "Portfolio Vol < 30%": summary["portfolio_volatility"] < 0.30,
    }
    for limit, passed in limits.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {limit:<30} {status}")

    print("=" * 70)


def main(args: list[str] | None = None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate comprehensive risk validation report"
    )
    parser.add_argument(
        "--portfolio",
        type=Path,
        help="Path to portfolio JSON file",
    )
    parser.add_argument(
        "--nav",
        type=float,
        default=10_000_000,
        help="Portfolio NAV if not using file (default: 10,000,000)",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default="AAPL,GOOGL,MSFT,AMZN,META",
        help="Comma-separated symbols if not using file",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./risk_reports"),
        help="Output directory for reports",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=504,
        help="Days of market data to use (default: 504 = 2 years)",
    )

    parsed = parser.parse_args(args)

    # Load or create portfolio
    if parsed.portfolio:
        portfolio = load_portfolio(parsed.portfolio)
        symbols = list(portfolio.weights.keys())
    else:
        symbols = parsed.symbols.split(",")
        portfolio = create_portfolio(symbols, parsed.nav)

    # Generate market data
    print("Loading market data...")
    market_data = generate_market_data(symbols, parsed.days)

    # Generate report
    report = generate_report(portfolio, market_data, parsed.output_dir)

    # Print summary
    print_summary(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
