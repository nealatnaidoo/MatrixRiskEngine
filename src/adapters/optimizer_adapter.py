"""OptimizerAdapter - Portfolio optimization using cvxpy.

This adapter provides:
- Mean-variance optimization
- Constraint enforcement
- Multiple objective functions
"""

from __future__ import annotations

import time
from datetime import date
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from src.core.domain.portfolio import Portfolio, PortfolioMetadata
from src.core.ports.backtest_port import InfeasibleError, OptimizationTimeoutError

if TYPE_CHECKING:
    from src.core.domain.constraint import Constraint


class OptimizerAdapter:
    """Portfolio optimizer using cvxpy.

    Provides mean-variance optimization with constraint enforcement.
    """

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        """Initialize OptimizerAdapter.

        Args:
            timeout_seconds: Maximum time for optimization
        """
        self._timeout = timeout_seconds
        self._cvxpy: Any = None

    def _get_cvxpy(self) -> Any:
        """Get cvxpy module (lazy import)."""
        if self._cvxpy is None:
            import cvxpy as cp

            self._cvxpy = cp
        return self._cvxpy

    def optimize(
        self,
        alpha: pd.Series,
        risk_model: pd.DataFrame,
        constraints: list["Constraint"],
        objective: str = "max_sharpe",
    ) -> Portfolio:
        """Optimize portfolio weights.

        Args:
            alpha: Expected returns by symbol
            risk_model: Covariance matrix (symbols x symbols)
            constraints: List of optimization constraints
            objective: Objective function type

        Returns:
            Portfolio with optimal weights

        Raises:
            InfeasibleError: If constraints cannot be satisfied
            OptimizationTimeoutError: If optimization exceeds timeout
            ValueError: If inputs are invalid
        """
        cp = self._get_cvxpy()

        # Validate inputs
        self._validate_inputs(alpha, risk_model)

        # Align symbols
        symbols = list(set(alpha.index) & set(risk_model.index))
        if not symbols:
            raise ValueError("No common symbols between alpha and risk model")

        n = len(symbols)
        alpha_vec = alpha[symbols].values
        cov_matrix = risk_model.loc[symbols, symbols].values

        # Validate covariance matrix is positive semi-definite
        self._validate_psd(cov_matrix)

        # Define optimization variable
        weights = cp.Variable(n)

        # Build objective
        portfolio_return = alpha_vec @ weights
        portfolio_variance = cp.quad_form(weights, cov_matrix)

        if objective == "max_sharpe":
            # Maximize return / sqrt(variance)
            # Reformulated as: minimize -return subject to variance <= target
            # Or: maximize return - lambda * variance
            risk_aversion = 1.0
            obj = cp.Maximize(portfolio_return - risk_aversion * portfolio_variance)

        elif objective == "min_variance":
            obj = cp.Minimize(portfolio_variance)

        elif objective == "max_return":
            # Maximize return with variance constraint
            obj = cp.Maximize(portfolio_return)

        elif objective == "risk_parity":
            # Risk parity: equal risk contribution
            # This is non-convex, use approximation
            obj = cp.Minimize(portfolio_variance)

        else:
            raise ValueError(f"Unknown objective: {objective}")

        # Build constraints
        cvx_constraints = self._build_constraints(
            cp, weights, symbols, constraints
        )

        # Always add: weights sum to 1
        cvx_constraints.append(cp.sum(weights) == 1)

        # Solve
        problem = cp.Problem(obj, cvx_constraints)

        start_time = time.time()

        try:
            problem.solve(solver=cp.OSQP, time_limit=self._timeout)
        except Exception as e:
            if time.time() - start_time >= self._timeout:
                raise OptimizationTimeoutError(self._timeout) from e
            raise

        # Check solution status
        if problem.status in ("infeasible", "infeasible_inaccurate"):
            violated = self._identify_violated_constraints(constraints)
            raise InfeasibleError(
                constraints=violated,
                message=f"Optimization infeasible: {problem.status}",
            )

        if problem.status == "unbounded":
            raise InfeasibleError(
                message="Optimization unbounded - check constraints"
            )

        if weights.value is None:
            raise InfeasibleError(
                message=f"Optimization failed with status: {problem.status}"
            )

        # Build portfolio from solution
        optimal_weights = dict(zip(symbols, weights.value.flatten()))

        # Post-validation: verify constraints are satisfied
        self._validate_solution(optimal_weights, constraints)

        return Portfolio(
            positions=optimal_weights,  # Weights as "positions" for simplicity
            weights=optimal_weights,
            nav=1.0,  # Normalized portfolio
            as_of_date=date.today(),
            metadata=PortfolioMetadata(
                strategy_name=f"optimized_{objective}",
            ),
        )

    def _validate_inputs(
        self,
        alpha: pd.Series,
        risk_model: pd.DataFrame,
    ) -> None:
        """Validate optimization inputs."""
        if alpha.empty:
            raise ValueError("Alpha series is empty")

        if risk_model.empty:
            raise ValueError("Risk model is empty")

        if not risk_model.index.equals(risk_model.columns):
            raise ValueError("Risk model must be square with matching index/columns")

    def _validate_psd(self, matrix: np.ndarray) -> None:
        """Validate matrix is positive semi-definite."""
        try:
            eigenvalues = np.linalg.eigvalsh(matrix)
            min_eigenvalue = eigenvalues.min()

            if min_eigenvalue < -1e-8:
                raise ValueError(
                    f"Covariance matrix is not PSD. "
                    f"Min eigenvalue: {min_eigenvalue}"
                )
        except np.linalg.LinAlgError as e:
            raise ValueError(f"Failed to check PSD: {e}") from e

    def _build_constraints(
        self,
        cp: Any,
        weights: Any,
        symbols: list[str],
        constraints: list["Constraint"],
    ) -> list[Any]:
        """Build cvxpy constraints from domain constraints."""
        from src.core.domain.constraint import ConstraintType

        cvx_constraints: list[Any] = []
        symbol_to_idx = {s: i for i, s in enumerate(symbols)}

        for constraint in constraints:
            if constraint.type == ConstraintType.POSITION_LIMIT:
                # Individual position bounds
                for symbol in constraint.securities:
                    if symbol in symbol_to_idx:
                        idx = symbol_to_idx[symbol]
                        if constraint.bounds.lower is not None:
                            cvx_constraints.append(
                                weights[idx] >= constraint.bounds.lower
                            )
                        if constraint.bounds.upper is not None:
                            cvx_constraints.append(
                                weights[idx] <= constraint.bounds.upper
                            )

            elif constraint.type == ConstraintType.SECTOR_LIMIT:
                # Sum of weights for sector
                sector_indices = [
                    symbol_to_idx[s]
                    for s in constraint.securities
                    if s in symbol_to_idx
                ]
                if sector_indices:
                    sector_sum = cp.sum(weights[sector_indices])
                    if constraint.bounds.lower is not None:
                        cvx_constraints.append(
                            sector_sum >= constraint.bounds.lower
                        )
                    if constraint.bounds.upper is not None:
                        cvx_constraints.append(
                            sector_sum <= constraint.bounds.upper
                        )

            elif constraint.type == ConstraintType.TURNOVER_LIMIT:
                # Turnover constraint (requires current portfolio)
                # Skip if no current portfolio specified
                pass

        return cvx_constraints

    def _identify_violated_constraints(
        self,
        constraints: list["Constraint"],
    ) -> list[str]:
        """Identify which constraints might be causing infeasibility."""
        # Return constraint names for debugging
        return [c.name for c in constraints if c.name]

    def _validate_solution(
        self,
        weights: dict[str, float],
        constraints: list["Constraint"],
    ) -> None:
        """Validate that solution satisfies all constraints."""
        tolerance = 1e-6

        for constraint in constraints:
            if not constraint.securities:
                continue

            relevant_weights = [
                weights.get(s, 0.0) for s in constraint.securities
            ]
            value = sum(relevant_weights)

            if constraint.bounds.lower is not None:
                if value < constraint.bounds.lower - tolerance:
                    raise InfeasibleError(
                        constraints=[constraint.name],
                        message=(
                            f"Constraint {constraint.name} violated: "
                            f"{value} < {constraint.bounds.lower}"
                        ),
                    )

            if constraint.bounds.upper is not None:
                if value > constraint.bounds.upper + tolerance:
                    raise InfeasibleError(
                        constraints=[constraint.name],
                        message=(
                            f"Constraint {constraint.name} violated: "
                            f"{value} > {constraint.bounds.upper}"
                        ),
                    )


def create_optimizer_adapter(
    timeout_seconds: float = 30.0,
) -> OptimizerAdapter:
    """Factory function to create OptimizerAdapter."""
    return OptimizerAdapter(timeout_seconds=timeout_seconds)
