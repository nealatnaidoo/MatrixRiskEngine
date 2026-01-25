"""Port interfaces for the Matrix Risk Engine.

Ports define abstract interfaces that adapters must implement.
Following hexagonal architecture, core depends only on ports.
"""

from src.core.ports.backtest_port import (
    BacktestError,
    BacktestPort,
    InfeasibleError,
    OptimizationTimeoutError,
)
from src.core.ports.data_port import (
    DataNotFoundError,
    DataPort,
    DataQualityError,
    VersionExistsError,
)
from src.core.ports.report_port import ReportGenerationError, ReportPort
from src.core.ports.risk_port import (
    InsufficientDataError,
    PricingError,
    RiskPort,
)

__all__ = [
    # DataPort
    "DataPort",
    "DataNotFoundError",
    "VersionExistsError",
    "DataQualityError",
    # BacktestPort
    "BacktestPort",
    "BacktestError",
    "InfeasibleError",
    "OptimizationTimeoutError",
    # ReportPort
    "ReportPort",
    "ReportGenerationError",
    # RiskPort
    "RiskPort",
    "InsufficientDataError",
    "PricingError",
]
