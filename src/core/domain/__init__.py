"""Domain objects for the Matrix Risk Engine.

This module exports all domain objects representing core business entities.
These are pure domain objects with invariant validation - no I/O dependencies.
"""

from src.core.domain.backtest_result import BacktestConfig, BacktestResult
from src.core.domain.constraint import (
    Bounds,
    Constraint,
    ConstraintType,
    position_limit,
    sector_limit,
    turnover_limit,
)
from src.core.domain.portfolio import Portfolio, PortfolioMetadata
from src.core.domain.risk_metrics import Greeks, RiskMetrics
from src.core.domain.stress_scenario import (
    SCENARIO_2008_CRISIS,
    SCENARIO_COVID_CRASH,
    StressScenario,
)
from src.core.domain.time_series import TimeSeries, TimeSeriesMetadata

__all__ = [
    # TimeSeries
    "TimeSeries",
    "TimeSeriesMetadata",
    # Portfolio
    "Portfolio",
    "PortfolioMetadata",
    # BacktestResult
    "BacktestResult",
    "BacktestConfig",
    # RiskMetrics
    "RiskMetrics",
    "Greeks",
    # StressScenario
    "StressScenario",
    "SCENARIO_2008_CRISIS",
    "SCENARIO_COVID_CRASH",
    # Constraint
    "Constraint",
    "ConstraintType",
    "Bounds",
    "sector_limit",
    "position_limit",
    "turnover_limit",
]
