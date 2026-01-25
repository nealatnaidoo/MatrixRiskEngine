"""RiskCalculationService - Domain service for orchestrating risk calculations.

This service coordinates:
1. Position and market data loading
2. VaR and CVaR calculation
3. Greeks computation
4. Risk report generation
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from src.core.domain.portfolio import Portfolio
    from src.core.domain.risk_metrics import RiskMetrics
    from src.core.ports.data_port import DataPort
    from src.core.ports.report_port import ReportPort
    from src.core.ports.risk_port import RiskPort


@dataclass(frozen=True)
class RiskCalculationRequest:
    """Request parameters for risk calculation.

    Attributes:
        portfolio: Portfolio to analyze
        market_data_version: ArcticDB version for market data
        methods: VaR methods to use ("historical", "parametric")
        confidence_levels: Confidence levels for VaR/CVaR
        window_days: Historical window for VaR calculation
        compute_greeks: Whether to compute Greeks
        generate_report: Whether to generate HTML report
        output_dir: Directory for output files
    """

    portfolio: "Portfolio"
    market_data_version: str
    methods: list[str] | None = None
    confidence_levels: list[float] | None = None
    window_days: int = 250
    compute_greeks: bool = True
    generate_report: bool = False
    output_dir: str = "artifacts/risk_reports"


@dataclass
class RiskCalculationResponse:
    """Response from risk calculation.

    Attributes:
        metrics: Complete risk metrics
        report_path: Path to generated report (if requested)
        warnings: Any warnings during calculation
    """

    metrics: "RiskMetrics"
    report_path: str | None
    warnings: list[str]


class RiskCalculationService:
    """Orchestrates risk calculation workflow.

    Coordinates data loading, risk metrics computation, and reporting.
    """

    def __init__(
        self,
        data_port: "DataPort",
        risk_port: "RiskPort",
        report_port: "ReportPort | None" = None,
    ) -> None:
        """Initialize RiskCalculationService with required ports.

        Args:
            data_port: Port for loading market data
            risk_port: Port for risk calculations
            report_port: Optional port for generating reports
        """
        self._data_port = data_port
        self._risk_port = risk_port
        self._report_port = report_port

    def calculate(
        self,
        request: RiskCalculationRequest,
    ) -> RiskCalculationResponse:
        """Execute complete risk calculation workflow.

        Workflow:
        1. Load market data for portfolio symbols
        2. Calculate VaR using specified methods
        3. Calculate CVaR
        4. Compute Greeks (if requested)
        5. Generate report (if requested)

        Args:
            request: Risk calculation request parameters

        Returns:
            RiskCalculationResponse with metrics and optional report
        """
        warnings: list[str] = []

        # Set defaults
        methods = request.methods or ["historical"]
        confidence_levels = request.confidence_levels or [0.95, 0.99]

        # Step 1: Load market data
        market_data = self._load_market_data(request)

        # Step 2: Calculate VaR
        var_results: dict[str, float] = {}

        for method in methods:
            method_var = self._risk_port.calculate_var(
                portfolio=request.portfolio,
                market_data=market_data,
                method=method,
                confidence_levels=confidence_levels,
                window_days=request.window_days,
            )
            # Merge results (use method prefix if multiple methods)
            if len(methods) > 1:
                for level, value in method_var.items():
                    var_results[f"{method}_{level}"] = value
            else:
                var_results = method_var

        # Step 3: Calculate CVaR
        cvar_results = self._risk_port.calculate_cvar(
            portfolio=request.portfolio,
            market_data=market_data,
            var_params={
                "method": methods[0],  # Use first method
                "confidence_levels": confidence_levels,
                "window_days": request.window_days,
            },
        )

        # Step 4: Compute Greeks (if requested)
        greeks_dict: dict[str, float | None] = {}
        if request.compute_greeks:
            try:
                greeks_dict = self._risk_port.compute_greeks(
                    portfolio=request.portfolio,
                    market_data=market_data,
                )
            except Exception as e:
                warnings.append(f"Greeks computation failed: {e}")

        # Build RiskMetrics object
        from src.core.domain.risk_metrics import Greeks, RiskMetrics

        metrics = RiskMetrics(
            var=var_results,
            cvar=cvar_results,
            greeks=Greeks(**{k: v for k, v in greeks_dict.items() if v is not None}),
            as_of_date=request.portfolio.as_of_date,
            portfolio_id=request.portfolio.metadata.strategy_name or "unknown",
            calculation_metadata={
                "methods": methods,
                "confidence_levels": confidence_levels,
                "window_days": request.window_days,
                "market_data_version": request.market_data_version,
            },
        )

        # Step 5: Generate report (optional)
        report_path = None
        if request.generate_report and self._report_port is not None:
            report_path = self._generate_risk_report(
                metrics, request.output_dir
            )

        return RiskCalculationResponse(
            metrics=metrics,
            report_path=report_path,
            warnings=warnings,
        )

    def _load_market_data(
        self,
        request: RiskCalculationRequest,
    ) -> pd.DataFrame:
        """Load market data for portfolio symbols."""
        portfolio = request.portfolio
        price_data: dict[str, pd.Series] = {}

        for symbol in portfolio.symbols:
            try:
                df = self._data_port.load(
                    symbol=symbol,
                    version=request.market_data_version,
                )
                if "close" in df.columns:
                    price_data[symbol] = df["close"]
                elif len(df.columns) > 0:
                    price_data[symbol] = df.iloc[:, 0]
            except Exception:
                # Skip symbols that fail to load
                continue

        if not price_data:
            raise ValueError("No market data loaded for any portfolio symbol")

        return pd.DataFrame(price_data).ffill()

    def _generate_risk_report(
        self,
        metrics: "RiskMetrics",
        output_dir: str,
    ) -> str:
        """Generate risk report."""
        if self._report_port is None:
            raise ValueError("Report port not configured")

        from datetime import datetime, timezone

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"risk_report_{timestamp}.html"
        filepath = output_path / filename

        # Generate simple risk report HTML
        html_content = self._build_risk_report_html(metrics)
        filepath.write_text(html_content)

        return str(filepath)

    def _build_risk_report_html(self, metrics: "RiskMetrics") -> str:
        """Build HTML content for risk report."""
        from datetime import datetime, timezone

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Risk Report - {metrics.as_of_date}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1, h2 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 60%; margin-bottom: 30px; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #c0392b; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1>Risk Report</h1>
    <p>Portfolio: {metrics.portfolio_id}</p>
    <p>As of Date: {metrics.as_of_date}</p>
    <p>Generated: {datetime.now(timezone.utc).isoformat()}</p>

    <h2>Value at Risk</h2>
    <table>
        <tr><th>Confidence Level</th><th>VaR</th><th>CVaR</th></tr>
"""
        for level in metrics.confidence_levels:
            var_val = metrics.var.get(level, 0)
            cvar_val = metrics.cvar.get(level, 0)
            html += f"        <tr><td>{level}</td><td>{var_val:,.0f}</td><td>{cvar_val:,.0f}</td></tr>\n"

        html += """    </table>

    <h2>Greeks</h2>
    <table>
        <tr><th>Greek</th><th>Value</th></tr>
"""
        greeks_dict = metrics.greeks.to_dict()
        for name, value in greeks_dict.items():
            if value is not None:
                html += f"        <tr><td>{name}</td><td>{value:,.4f}</td></tr>\n"

        html += """    </table>
</body>
</html>"""

        return html


def create_risk_calculation_service(
    data_port: "DataPort",
    risk_port: "RiskPort",
    report_port: "ReportPort | None" = None,
) -> RiskCalculationService:
    """Factory function to create RiskCalculationService."""
    return RiskCalculationService(
        data_port=data_port,
        risk_port=risk_port,
        report_port=report_port,
    )
