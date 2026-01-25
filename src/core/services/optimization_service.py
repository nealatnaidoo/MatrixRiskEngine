"""OptimizationService - Domain service for portfolio optimization workflow.

This service coordinates:
1. Alpha and risk model loading
2. Constraint configuration
3. Portfolio optimization
4. Trade generation
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from src.core.domain.constraint import Constraint
    from src.core.domain.portfolio import Portfolio
    from src.core.ports.data_port import DataPort


@dataclass(frozen=True)
class OptimizationRequest:
    """Request parameters for optimization.

    Attributes:
        universe: List of symbols to consider
        alpha_source: Source identifier for alpha signals
        risk_model_version: Version of risk model to use
        constraints: List of optimization constraints
        objective: Optimization objective
        current_portfolio: Current portfolio for trade generation
        transaction_costs: Cost estimates for trade generation
        data_version: ArcticDB version for data
    """

    universe: list[str]
    alpha_source: str
    risk_model_version: str
    constraints: list["Constraint"]
    objective: str = "max_sharpe"
    current_portfolio: "Portfolio | None" = None
    transaction_costs: dict[str, float] | None = None
    data_version: str = "latest"


@dataclass
class TradeOrder:
    """A single trade order.

    Attributes:
        symbol: Security symbol
        side: "buy" or "sell"
        quantity: Trade quantity (shares or notional)
        estimated_cost: Estimated transaction cost
    """

    symbol: str
    side: str
    quantity: float
    estimated_cost: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "estimated_cost": self.estimated_cost,
        }


@dataclass
class OptimizationResponse:
    """Response from optimization.

    Attributes:
        target_portfolio: Optimized target portfolio
        trades: List of trades to reach target
        total_trade_value: Total value of trades
        estimated_cost: Total estimated transaction cost
        optimization_metadata: Details about the optimization
    """

    target_portfolio: "Portfolio"
    trades: list[TradeOrder]
    total_trade_value: float
    estimated_cost: float
    optimization_metadata: dict[str, Any]


class OptimizationService:
    """Orchestrates portfolio optimization workflow.

    Coordinates data loading, optimization, and trade generation.
    """

    def __init__(
        self,
        data_port: "DataPort",
        optimizer: Any,  # OptimizerAdapter
    ) -> None:
        """Initialize OptimizationService.

        Args:
            data_port: Port for loading alpha and risk model data
            optimizer: Optimizer adapter for running optimization
        """
        self._data_port = data_port
        self._optimizer = optimizer

    def optimize(self, request: OptimizationRequest) -> OptimizationResponse:
        """Execute optimization workflow.

        Workflow:
        1. Load alpha signals
        2. Load risk model
        3. Run optimization
        4. Generate trades (if current portfolio provided)

        Args:
            request: Optimization request parameters

        Returns:
            OptimizationResponse with target portfolio and trades
        """
        # Step 1: Load alpha signals
        alpha = self._load_alpha(request)

        # Step 2: Load risk model
        risk_model = self._load_risk_model(request)

        # Step 3: Run optimization
        target_portfolio = self._optimizer.optimize(
            alpha=alpha,
            risk_model=risk_model,
            constraints=request.constraints,
            objective=request.objective,
        )

        # Step 4: Generate trades
        trades: list[TradeOrder] = []
        total_trade_value = 0.0
        estimated_cost = 0.0

        if request.current_portfolio is not None:
            trades = self.generate_trades(
                current_portfolio=request.current_portfolio,
                target_portfolio=target_portfolio,
                transaction_costs=request.transaction_costs or {},
            )
            total_trade_value = sum(abs(t.quantity) for t in trades)
            estimated_cost = sum(t.estimated_cost for t in trades)

        return OptimizationResponse(
            target_portfolio=target_portfolio,
            trades=trades,
            total_trade_value=total_trade_value,
            estimated_cost=estimated_cost,
            optimization_metadata={
                "objective": request.objective,
                "universe_size": len(request.universe),
                "constraints_count": len(request.constraints),
                "alpha_source": request.alpha_source,
                "risk_model_version": request.risk_model_version,
            },
        )

    def generate_trades(
        self,
        current_portfolio: "Portfolio",
        target_portfolio: "Portfolio",
        transaction_costs: dict[str, float] | None = None,
    ) -> list[TradeOrder]:
        """Generate trade list from current to target portfolio.

        Args:
            current_portfolio: Current portfolio holdings
            target_portfolio: Target portfolio after optimization
            transaction_costs: Cost parameters for estimation

        Returns:
            List of trade orders
        """
        costs = transaction_costs or {"spread_bps": 5, "commission_bps": 2}
        cost_pct = (costs.get("spread_bps", 0) + costs.get("commission_bps", 0)) / 10000

        trades: list[TradeOrder] = []

        # Get all symbols
        all_symbols = set(current_portfolio.symbols) | set(target_portfolio.symbols)

        for symbol in all_symbols:
            current_weight = current_portfolio.get_weight(symbol)
            target_weight = target_portfolio.get_weight(symbol)

            weight_change = target_weight - current_weight

            if abs(weight_change) < 1e-6:
                continue

            # Calculate trade quantity (using current NAV)
            trade_value = abs(weight_change) * current_portfolio.nav
            estimated_cost = trade_value * cost_pct

            trades.append(
                TradeOrder(
                    symbol=symbol,
                    side="buy" if weight_change > 0 else "sell",
                    quantity=trade_value,  # In notional terms
                    estimated_cost=estimated_cost,
                )
            )

        return trades

    def _load_alpha(self, request: OptimizationRequest) -> pd.Series:
        """Load alpha signals for universe."""
        # Try to load from data port
        try:
            df = self._data_port.load(
                symbol=request.alpha_source,
                version=request.data_version,
            )

            # Get latest alpha values
            if not df.empty:
                latest = df.iloc[-1]
                # Filter to universe
                return latest[
                    [s for s in request.universe if s in latest.index]
                ]
        except Exception:
            pass

        # Fallback: return equal alpha for all symbols
        return pd.Series(1.0, index=request.universe)

    def _load_risk_model(self, request: OptimizationRequest) -> pd.DataFrame:
        """Load risk model (covariance matrix)."""
        # Try to load from data port
        try:
            df = self._data_port.load(
                symbol=f"risk_model_{request.risk_model_version}",
                version=request.data_version,
            )

            if not df.empty:
                # Ensure it's square and symmetric
                common = list(set(df.index) & set(df.columns) & set(request.universe))
                return df.loc[common, common]
        except Exception:
            pass

        # Fallback: identity matrix (equal and uncorrelated risk)
        n = len(request.universe)
        return pd.DataFrame(
            data=0.04 * np.eye(n),  # 20% vol each
            index=request.universe,
            columns=request.universe,
        )


def create_optimization_service(
    data_port: "DataPort",
    optimizer: Any,
) -> OptimizationService:
    """Factory function to create OptimizationService."""
    return OptimizationService(
        data_port=data_port,
        optimizer=optimizer,
    )


# Need numpy for fallback
import numpy as np
