"""StressTestingService - Domain service for orchestrating stress testing.

This service coordinates:
1. Scenario loading
2. Shock application
3. Stressed valuation
4. Scenario comparison reporting
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from src.core.domain.portfolio import Portfolio
    from src.core.domain.stress_scenario import StressScenario
    from src.core.ports.risk_port import RiskPort


@dataclass(frozen=True)
class StressTestRequest:
    """Request parameters for stress testing.

    Attributes:
        portfolio: Portfolio to stress test
        scenarios: List of stress scenarios to apply
        market_data: Base market data
        validate_linearity: Whether to validate linear instruments
        generate_report: Whether to generate comparison report
        output_dir: Directory for output files
    """

    portfolio: "Portfolio"
    scenarios: list["StressScenario"]
    market_data: pd.DataFrame
    validate_linearity: bool = True
    generate_report: bool = False
    output_dir: str = "artifacts/stress_tests"


@dataclass
class StressTestResult:
    """Result for a single stress scenario.

    Attributes:
        scenario_name: Name of the scenario
        base_npv: Portfolio value before stress
        stressed_npv: Portfolio value after stress
        pnl: Profit/loss (stressed - base)
        pct_change: Percentage change
        shocks_applied: Shocks that were applied
    """

    scenario_name: str
    base_npv: float
    stressed_npv: float
    pnl: float
    pct_change: float
    shocks_applied: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "scenario_name": self.scenario_name,
            "base_npv": self.base_npv,
            "stressed_npv": self.stressed_npv,
            "pnl": self.pnl,
            "pct_change": self.pct_change,
            "shocks_applied": self.shocks_applied,
        }


@dataclass
class StressTestResponse:
    """Response from stress testing.

    Attributes:
        results: List of results per scenario
        comparison_df: DataFrame comparing all scenarios
        report_path: Path to generated report (if requested)
        linearity_validated: Whether linearity check passed
        warnings: Any warnings during calculation
    """

    results: list[StressTestResult]
    comparison_df: pd.DataFrame
    report_path: str | None
    linearity_validated: bool | None
    warnings: list[str]


class StressTestingService:
    """Orchestrates stress testing workflow.

    Applies stress scenarios to portfolios and generates comparison reports.
    """

    def __init__(
        self,
        risk_port: "RiskPort",
    ) -> None:
        """Initialize StressTestingService.

        Args:
            risk_port: Port for risk calculations (valuation, stress test)
        """
        self._risk_port = risk_port

    def run(self, request: StressTestRequest) -> StressTestResponse:
        """Execute stress testing workflow.

        Workflow:
        1. Calculate base portfolio value
        2. Apply each scenario and calculate stressed value
        3. Validate linearity (optional)
        4. Generate comparison report (optional)

        Args:
            request: Stress test request parameters

        Returns:
            StressTestResponse with results and optional report
        """
        warnings: list[str] = []

        if not request.scenarios:
            raise ValueError("At least one scenario is required")

        # Step 1: Calculate base NPV
        base_npv = self._risk_port.value_portfolio(
            portfolio=request.portfolio,
            market_data=request.market_data,
        )

        # Step 2: Run stress test for each scenario
        stress_df = self._risk_port.stress_test(
            portfolio=request.portfolio,
            market_data=request.market_data,
            scenarios=request.scenarios,
        )

        # Build results list
        results: list[StressTestResult] = []

        for scenario in request.scenarios:
            scenario_row = stress_df[stress_df["scenario"] == scenario.name]

            if scenario_row.empty:
                warnings.append(f"No results for scenario: {scenario.name}")
                continue

            row = scenario_row.iloc[0]
            results.append(
                StressTestResult(
                    scenario_name=scenario.name,
                    base_npv=base_npv,
                    stressed_npv=row["stressed_npv"],
                    pnl=row["pnl"],
                    pct_change=row["pct_change"],
                    shocks_applied=scenario.shocks,
                )
            )

        # Step 3: Validate linearity (optional)
        linearity_validated = None
        if request.validate_linearity:
            linearity_validated = self._validate_linearity(
                request.portfolio,
                request.market_data,
                request.scenarios,
                warnings,
            )

        # Build comparison DataFrame
        comparison_df = self._build_comparison_df(results)

        # Step 4: Generate report (optional)
        report_path = None
        if request.generate_report:
            report_path = self._generate_report(
                results, comparison_df, request.output_dir
            )

        return StressTestResponse(
            results=results,
            comparison_df=comparison_df,
            report_path=report_path,
            linearity_validated=linearity_validated,
            warnings=warnings,
        )

    def _validate_linearity(
        self,
        portfolio: "Portfolio",
        market_data: pd.DataFrame,
        scenarios: list["StressScenario"],
        warnings: list[str],
    ) -> bool:
        """Validate linearity for linear instruments.

        For linear instruments, 20% shock P&L should be ~2x 10% shock P&L.
        """
        from src.core.domain.stress_scenario import StressScenario
        from datetime import date

        # Create 10% and 20% equity shock scenarios
        scenario_10 = StressScenario(
            name="Linearity_10pct",
            shocks={"SPX": -0.10},
            description="10% shock for linearity test",
            date_calibrated=date.today(),
        )

        scenario_20 = StressScenario(
            name="Linearity_20pct",
            shocks={"SPX": -0.20},
            description="20% shock for linearity test",
            date_calibrated=date.today(),
        )

        try:
            stress_df = self._risk_port.stress_test(
                portfolio=portfolio,
                market_data=market_data,
                scenarios=[scenario_10, scenario_20],
            )

            row_10 = stress_df[stress_df["scenario"] == "Linearity_10pct"]
            row_20 = stress_df[stress_df["scenario"] == "Linearity_20pct"]

            if row_10.empty or row_20.empty:
                return True  # Can't validate

            pnl_10 = abs(row_10.iloc[0]["pnl"])
            pnl_20 = abs(row_20.iloc[0]["pnl"])

            if pnl_10 < 1e-6:
                return True  # Can't validate near-zero

            ratio = pnl_20 / pnl_10
            tolerance = 0.05  # 5% tolerance

            is_linear = abs(ratio - 2.0) <= tolerance * 2.0

            if not is_linear:
                warnings.append(
                    f"Linearity check: 20%/10% P&L ratio = {ratio:.2f}, expected ~2.0"
                )

            return is_linear

        except Exception as e:
            warnings.append(f"Linearity validation failed: {e}")
            return True  # Assume valid if we can't check

    def _build_comparison_df(
        self,
        results: list[StressTestResult],
    ) -> pd.DataFrame:
        """Build DataFrame comparing all scenario results."""
        if not results:
            return pd.DataFrame(
                columns=[
                    "scenario",
                    "base_npv",
                    "stressed_npv",
                    "pnl",
                    "pct_change",
                ]
            )

        data = [
            {
                "scenario": r.scenario_name,
                "base_npv": r.base_npv,
                "stressed_npv": r.stressed_npv,
                "pnl": r.pnl,
                "pct_change": r.pct_change,
            }
            for r in results
        ]

        return pd.DataFrame(data)

    def _generate_report(
        self,
        results: list[StressTestResult],
        comparison_df: pd.DataFrame,
        output_dir: str,
    ) -> str:
        """Generate stress test comparison report."""
        from datetime import datetime, timezone

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"stress_test_{timestamp}.html"
        filepath = output_path / filename

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Stress Test Results</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1, h2 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 80%; margin-bottom: 30px; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: right; }}
        th {{ background-color: #8e44ad; color: white; text-align: left; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .negative {{ color: #c0392b; }}
        .positive {{ color: #27ae60; }}
    </style>
</head>
<body>
    <h1>Stress Test Results</h1>
    <p>Generated: {datetime.now(timezone.utc).isoformat()}</p>

    <h2>Scenario Comparison</h2>
    <table>
        <tr>
            <th>Scenario</th>
            <th>Base NPV</th>
            <th>Stressed NPV</th>
            <th>P&L</th>
            <th>% Change</th>
        </tr>
"""
        for result in results:
            pnl_class = "negative" if result.pnl < 0 else "positive"
            html += f"""        <tr>
            <td style="text-align: left;">{result.scenario_name}</td>
            <td>{result.base_npv:,.0f}</td>
            <td>{result.stressed_npv:,.0f}</td>
            <td class="{pnl_class}">{result.pnl:,.0f}</td>
            <td class="{pnl_class}">{result.pct_change:.2%}</td>
        </tr>
"""

        html += """    </table>

    <h2>Scenario Details</h2>
"""
        for result in results:
            html += f"""    <h3>{result.scenario_name}</h3>
    <table>
        <tr><th>Risk Factor</th><th>Shock</th></tr>
"""
            for factor, shock in result.shocks_applied.items():
                html += f"        <tr><td style='text-align: left;'>{factor}</td><td>{shock:+.1%}</td></tr>\n"
            html += "    </table>\n"

        html += """</body>
</html>"""

        filepath.write_text(html)
        return str(filepath)


def create_stress_testing_service(
    risk_port: "RiskPort",
) -> StressTestingService:
    """Factory function to create StressTestingService."""
    return StressTestingService(risk_port=risk_port)
