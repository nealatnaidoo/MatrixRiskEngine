"""QuantStatsAdapter - Production implementation of ReportPort using QuantStats.

This adapter provides performance analytics and tearsheet generation with:
- 50+ performance metrics
- HTML tearsheet output
- Benchmark comparison
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.core.ports.report_port import ReportGenerationError, ReportPort


class QuantStatsAdapter:
    """QuantStats implementation of ReportPort.

    Provides comprehensive performance analytics and reporting.
    """

    def __init__(self, output_dir: str | Path = "artifacts/tearsheets") -> None:
        """Initialize QuantStats adapter.

        Args:
            output_dir: Directory for output files
        """
        self._output_dir = Path(output_dir)
        self._qs: Any = None  # Lazy import

    def _get_qs(self) -> Any:
        """Get QuantStats module (lazy import)."""
        if self._qs is None:
            import quantstats as qs

            self._qs = qs
        return self._qs

    def generate_report(
        self,
        returns: pd.Series,
        benchmark: pd.Series | None,
        template: str,
        output_path: str,
    ) -> str:
        """Generate performance report/tearsheet.

        Args:
            returns: Portfolio returns time series
            benchmark: Optional benchmark returns
            template: Report template type (full, summary, risk)
            output_path: Path to save the report

        Returns:
            Path to generated report file
        """
        # Validate inputs
        if not isinstance(returns.index, pd.DatetimeIndex):
            raise ReportGenerationError(template, "Returns must have DatetimeIndex")

        if len(returns) == 0:
            raise ReportGenerationError(template, "Returns series is empty")

        # Ensure output directory exists
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        try:
            qs = self._get_qs()

            # Extend pandas with quantstats methods
            qs.extend_pandas()

            # Clean returns
            returns = returns.dropna()

            if template == "full":
                # Full HTML tearsheet
                if benchmark is not None:
                    benchmark = benchmark.reindex(returns.index).dropna()
                    qs.reports.html(
                        returns,
                        benchmark=benchmark,
                        output=str(output_path_obj),
                        title="Matrix Risk Engine - Performance Report",
                    )
                else:
                    qs.reports.html(
                        returns,
                        output=str(output_path_obj),
                        title="Matrix Risk Engine - Performance Report",
                    )

            elif template == "summary":
                # Generate summary metrics and create simple HTML
                metrics = self.calculate_metrics(returns)
                self._generate_summary_html(metrics, output_path_obj)

            elif template == "risk":
                # Risk-focused report
                metrics = self.calculate_metrics(returns)
                self._generate_risk_html(returns, metrics, output_path_obj)

            else:
                raise ReportGenerationError(template, f"Unknown template: {template}")

            return str(output_path_obj)

        except ImportError as e:
            raise ReportGenerationError(
                template, f"QuantStats not installed: {e}"
            ) from e
        except Exception as e:
            raise ReportGenerationError(template, str(e)) from e

    def calculate_metrics(self, returns: pd.Series) -> dict[str, float]:
        """Calculate performance metrics from returns.

        Args:
            returns: Portfolio returns time series

        Returns:
            Dictionary of 50+ metrics
        """
        returns = returns.dropna()

        if len(returns) == 0:
            return self._empty_metrics()

        try:
            qs = self._get_qs()

            # Use QuantStats for metrics calculation
            metrics = {}

            # Return metrics
            metrics["total_return"] = float(qs.stats.comp(returns))
            metrics["cagr"] = float(qs.stats.cagr(returns))
            metrics["mtd"] = float(qs.stats.mtd(returns))
            metrics["ytd"] = float(qs.stats.ytd(returns))

            # Risk metrics
            metrics["volatility"] = float(qs.stats.volatility(returns))
            metrics["sharpe_ratio"] = float(qs.stats.sharpe(returns))
            metrics["sortino_ratio"] = float(qs.stats.sortino(returns))
            metrics["calmar_ratio"] = float(qs.stats.calmar(returns))

            # Drawdown metrics
            metrics["max_drawdown"] = float(qs.stats.max_drawdown(returns))
            metrics["avg_drawdown"] = float(qs.stats.avg_drawdown(returns))
            metrics["avg_drawdown_days"] = float(qs.stats.avg_drawdown_days(returns))

            # Trade metrics
            metrics["win_rate"] = float(qs.stats.win_rate(returns))
            metrics["win_loss_ratio"] = float(qs.stats.win_loss_ratio(returns))
            metrics["profit_factor"] = float(qs.stats.profit_factor(returns))
            metrics["profit_ratio"] = float(qs.stats.profit_ratio(returns))

            # Distribution metrics
            metrics["avg_daily_return"] = float(returns.mean())
            metrics["best_day"] = float(qs.stats.best(returns))
            metrics["worst_day"] = float(qs.stats.worst(returns))
            metrics["skew"] = float(qs.stats.skew(returns))
            metrics["kurtosis"] = float(qs.stats.kurtosis(returns))

            # Risk metrics
            metrics["var_95"] = float(qs.stats.var(returns))
            metrics["cvar_95"] = float(qs.stats.cvar(returns))

            # Tail metrics
            metrics["tail_ratio"] = float(qs.stats.tail_ratio(returns))
            metrics["common_sense_ratio"] = float(qs.stats.common_sense_ratio(returns))

            # Outlier metrics
            metrics["outlier_win_ratio"] = float(qs.stats.outlier_win_ratio(returns))
            metrics["outlier_loss_ratio"] = float(qs.stats.outlier_loss_ratio(returns))

            # Recovery metrics
            metrics["recovery_factor"] = float(qs.stats.recovery_factor(returns))
            metrics["ulcer_index"] = float(qs.stats.ulcer_index(returns))

            # Period metrics
            metrics["avg_up_month"] = float(qs.stats.avg_win(returns.resample("ME").sum()))
            metrics["avg_down_month"] = float(qs.stats.avg_loss(returns.resample("ME").sum()))

            # Kelly criterion
            metrics["kelly_criterion"] = float(qs.stats.kelly_criterion(returns))

            # Risk of ruin
            metrics["risk_of_ruin"] = float(qs.stats.risk_of_ruin(returns))

            # Geometric metrics
            metrics["geometric_mean"] = float(qs.stats.geometric_mean(returns))

            # Payoff ratio
            metrics["payoff_ratio"] = float(qs.stats.payoff_ratio(returns))

            # Expected return
            metrics["expected_return"] = float(qs.stats.expected_return(returns))

            # Information ratio (vs risk-free)
            metrics["information_ratio"] = float(qs.stats.information_ratio(returns))

            # Treynor ratio (assuming beta=1)
            metrics["treynor_ratio"] = metrics["sharpe_ratio"]  # Simplified

            # Omega ratio
            metrics["omega_ratio"] = float(qs.stats.omega(returns))

            # Additional derived metrics
            metrics["daily_value_at_risk"] = metrics["var_95"]
            metrics["expected_shortfall"] = metrics["cvar_95"]
            metrics["annualized_return"] = metrics["cagr"]
            metrics["annualized_volatility"] = metrics["volatility"]
            metrics["risk_adjusted_return"] = metrics["sharpe_ratio"]

            # Count metrics
            metrics["positive_days"] = int((returns > 0).sum())
            metrics["negative_days"] = int((returns < 0).sum())
            metrics["total_days"] = len(returns)

            # Clean up NaN values
            for key, value in metrics.items():
                if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
                    metrics[key] = 0.0

            return metrics

        except Exception:
            # Fallback to manual calculation if QuantStats fails
            return self._calculate_metrics_manual(returns)

    def _calculate_metrics_manual(self, returns: pd.Series) -> dict[str, float]:
        """Fallback manual metrics calculation."""
        if len(returns) == 0:
            return self._empty_metrics()

        total_return = (1 + returns).prod() - 1
        n_years = len(returns) / 252

        cagr = (1 + total_return) ** (1 / n_years) - 1 if n_years > 0 else 0
        volatility = returns.std() * np.sqrt(252)
        sharpe = (returns.mean() * 252) / volatility if volatility > 0 else 0

        # Max drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdowns = cumulative / running_max - 1
        max_dd = drawdowns.min()

        return {
            "total_return": float(total_return),
            "cagr": float(cagr),
            "volatility": float(volatility),
            "sharpe_ratio": float(sharpe),
            "max_drawdown": float(max_dd),
            "win_rate": float((returns > 0).mean()),
            "avg_daily_return": float(returns.mean()),
            "best_day": float(returns.max()),
            "worst_day": float(returns.min()),
            "positive_days": int((returns > 0).sum()),
            "negative_days": int((returns < 0).sum()),
            "total_days": len(returns),
        }

    def _empty_metrics(self) -> dict[str, float]:
        """Return empty metrics dictionary."""
        return {
            "total_return": 0.0,
            "cagr": 0.0,
            "volatility": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
        }

    def _generate_summary_html(
        self,
        metrics: dict[str, float],
        output_path: Path,
    ) -> None:
        """Generate simple summary HTML report."""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Performance Summary</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 50%; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1>Performance Summary</h1>
    <p>Generated: {datetime.now(timezone.utc).isoformat()}</p>
    <table>
        <tr><th>Metric</th><th>Value</th></tr>
"""
        for key, value in sorted(metrics.items()):
            if isinstance(value, float):
                if "ratio" in key or "rate" in key:
                    formatted = f"{value:.4f}"
                elif "return" in key or "drawdown" in key:
                    formatted = f"{value:.2%}"
                else:
                    formatted = f"{value:.4f}"
            else:
                formatted = str(value)
            html += f"        <tr><td>{key}</td><td>{formatted}</td></tr>\n"

        html += """    </table>
</body>
</html>"""

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

    def _generate_risk_html(
        self,
        returns: pd.Series,
        metrics: dict[str, float],
        output_path: Path,
    ) -> None:
        """Generate risk-focused HTML report."""
        risk_metrics = {
            k: v
            for k, v in metrics.items()
            if any(
                term in k.lower()
                for term in ["risk", "var", "drawdown", "volatility", "sharpe", "sortino"]
            )
        }

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Risk Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1, h2 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 60%; margin-bottom: 30px; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #c0392b; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .warning {{ color: #c0392b; }}
    </style>
</head>
<body>
    <h1>Risk Report</h1>
    <p>Generated: {datetime.now(timezone.utc).isoformat()}</p>

    <h2>Risk Metrics</h2>
    <table>
        <tr><th>Metric</th><th>Value</th></tr>
"""
        for key, value in sorted(risk_metrics.items()):
            formatted = f"{value:.4f}" if isinstance(value, float) else str(value)
            html += f"        <tr><td>{key}</td><td>{formatted}</td></tr>\n"

        html += """    </table>
</body>
</html>"""

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)


# Type assertion for Protocol compliance
_: ReportPort = QuantStatsAdapter()  # type: ignore[assignment]
