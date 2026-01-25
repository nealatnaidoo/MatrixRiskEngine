"""ReportPort Protocol - Abstract interface for report generation.

This port defines the contract for generating performance reports and tearsheets.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import pandas as pd


@runtime_checkable
class ReportPort(Protocol):
    """Abstract interface for report generation.

    Implementations:
    - QuantStatsAdapter: Production implementation using QuantStats
    - StubReportAdapter: Test stub for unit testing
    """

    def generate_report(
        self,
        returns: "pd.Series",
        benchmark: "pd.Series | None",
        template: str,
        output_path: str,
    ) -> str:
        """Generate performance report/tearsheet.

        Args:
            returns: Portfolio returns time series (daily)
            benchmark: Optional benchmark returns for comparison
            template: Report template type
                - "full": Complete tearsheet with all metrics
                - "summary": Summary metrics only
                - "risk": Risk-focused report
            output_path: Path to save the report

        Returns:
            Path to generated report file

        Raises:
            ReportGenerationError: If report generation fails

        Pre-conditions:
            - returns must have DatetimeIndex
            - returns must be aligned with benchmark if provided

        Post-conditions:
            - Report file written to output_path
            - Returns the output file path
        """
        ...

    def calculate_metrics(
        self,
        returns: "pd.Series",
    ) -> dict[str, float]:
        """Calculate performance metrics from returns.

        Args:
            returns: Portfolio returns time series

        Returns:
            Dictionary of metrics:
            - sharpe_ratio: Annualized Sharpe ratio
            - sortino_ratio: Sortino ratio
            - calmar_ratio: Calmar ratio
            - max_drawdown: Maximum drawdown (negative value)
            - cagr: Compound annual growth rate
            - volatility: Annualized volatility
            - win_rate: Percentage of positive return days
            - profit_factor: Gross profits / gross losses
            - total_return: Cumulative return
            - best_day: Best single day return
            - worst_day: Worst single day return
            - avg_daily_return: Average daily return
            - skew: Return distribution skewness
            - kurtosis: Return distribution kurtosis
            ... (50+ metrics in full implementation)

        Post-conditions:
            - All metrics calculated from same return series
            - Metrics are deterministic
        """
        ...


class ReportGenerationError(Exception):
    """Raised when report generation fails."""

    def __init__(self, template: str, message: str) -> None:
        self.template = template
        super().__init__(f"Failed to generate '{template}' report: {message}")
