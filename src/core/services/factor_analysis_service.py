"""FactorAnalysisService - Domain service for factor/alpha analysis.

This service provides:
- Information Coefficient (IC) calculation
- Factor turnover analysis
- Statistical significance tests
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class FactorAnalysisResult:
    """Results from factor analysis.

    Attributes:
        ic_series: Time series of IC values
        ic_mean: Mean IC
        ic_std: IC standard deviation
        ic_ir: Information Ratio (IC mean / IC std)
        turnover_series: Time series of turnover
        turnover_mean: Mean turnover
        t_statistic: T-statistic for IC significance
        p_value: P-value for IC significance
        sharpe_ratio: Sharpe ratio of factor returns
        hit_rate: Percentage of positive IC periods
    """

    ic_series: pd.Series
    ic_mean: float
    ic_std: float
    ic_ir: float
    turnover_series: pd.Series
    turnover_mean: float
    t_statistic: float
    p_value: float
    sharpe_ratio: float
    hit_rate: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "ic_mean": self.ic_mean,
            "ic_std": self.ic_std,
            "ic_ir": self.ic_ir,
            "turnover_mean": self.turnover_mean,
            "t_statistic": self.t_statistic,
            "p_value": self.p_value,
            "sharpe_ratio": self.sharpe_ratio,
            "hit_rate": self.hit_rate,
            "ic_series_length": len(self.ic_series),
            "turnover_series_length": len(self.turnover_series),
        }


class FactorAnalysisService:
    """Service for analyzing factor/alpha signals.

    Provides statistical analysis of factor effectiveness including
    IC calculation, turnover analysis, and significance testing.
    """

    def __init__(self, annualization_factor: int = 252) -> None:
        """Initialize FactorAnalysisService.

        Args:
            annualization_factor: Trading days per year for annualization
        """
        self._annualization_factor = annualization_factor

    def analyze(
        self,
        factor_scores: pd.DataFrame,
        forward_returns: pd.DataFrame,
        positions: pd.DataFrame | None = None,
    ) -> FactorAnalysisResult:
        """Perform complete factor analysis.

        Args:
            factor_scores: Factor scores (date x symbol)
            forward_returns: Forward returns aligned with factor scores
            positions: Optional position weights for turnover calculation

        Returns:
            Complete FactorAnalysisResult
        """
        # Calculate IC
        ic_series = self.calculate_ic(factor_scores, forward_returns)

        # Calculate turnover (from positions or infer from scores)
        if positions is not None:
            turnover_series = self.calculate_turnover(positions)
        else:
            # Use normalized factor scores as proxy positions
            normalized_scores = factor_scores.div(
                factor_scores.abs().sum(axis=1), axis=0
            ).fillna(0)
            turnover_series = self.calculate_turnover(normalized_scores)

        # Calculate factor returns for Sharpe
        factor_returns = self._calculate_factor_returns(
            factor_scores, forward_returns
        )

        # Run statistical tests
        stats_result = self.statistical_tests(ic_series)

        return FactorAnalysisResult(
            ic_series=ic_series,
            ic_mean=float(ic_series.mean()),
            ic_std=float(ic_series.std()),
            ic_ir=stats_result["ic_ir"],
            turnover_series=turnover_series,
            turnover_mean=float(turnover_series.mean()),
            t_statistic=stats_result["t_statistic"],
            p_value=stats_result["p_value"],
            sharpe_ratio=stats_result["sharpe_ratio"],
            hit_rate=stats_result["hit_rate"],
        )

    def calculate_ic(
        self,
        factor_scores: pd.DataFrame,
        forward_returns: pd.DataFrame,
    ) -> pd.Series:
        """Calculate Information Coefficient (Spearman rank correlation).

        The IC measures the correlation between factor scores and
        subsequent returns. Higher IC indicates better predictive power.

        Args:
            factor_scores: Factor scores (date x symbol)
            forward_returns: Forward returns (date x symbol)

        Returns:
            Time series of IC values (one per date)
        """
        # Ensure alignment
        common_dates = factor_scores.index.intersection(forward_returns.index)
        common_symbols = list(
            set(factor_scores.columns) & set(forward_returns.columns)
        )

        if len(common_dates) == 0 or len(common_symbols) == 0:
            return pd.Series(dtype=float)

        scores = factor_scores.loc[common_dates, common_symbols]
        returns = forward_returns.loc[common_dates, common_symbols]

        # Calculate IC for each date
        ic_values = []

        for date_idx in common_dates:
            score_row = scores.loc[date_idx].dropna()
            return_row = returns.loc[date_idx].dropna()

            # Need at least 3 observations for correlation
            common_syms = list(set(score_row.index) & set(return_row.index))
            if len(common_syms) < 3:
                ic_values.append(np.nan)
                continue

            # Spearman rank correlation
            correlation, _ = stats.spearmanr(
                score_row[common_syms], return_row[common_syms]
            )
            ic_values.append(correlation)

        return pd.Series(ic_values, index=common_dates, name="IC")

    def calculate_turnover(self, positions: pd.DataFrame) -> pd.Series:
        """Calculate portfolio turnover over time.

        Turnover is defined as sum(|position_change|) / 2.

        Args:
            positions: Position weights (date x symbol)

        Returns:
            Time series of turnover values
        """
        if positions.empty:
            return pd.Series(dtype=float)

        # Calculate absolute changes
        position_changes = positions.diff().abs()

        # Sum across symbols and divide by 2 (buys + sells)
        turnover = position_changes.sum(axis=1) / 2

        # First row is NaN from diff
        turnover = turnover.iloc[1:]

        turnover.name = "turnover"
        return turnover

    def statistical_tests(
        self,
        ic_series: pd.Series,
    ) -> dict[str, float]:
        """Run statistical significance tests on IC series.

        Args:
            ic_series: Time series of IC values

        Returns:
            Dictionary with:
            - t_statistic: T-test statistic
            - p_value: Two-tailed p-value
            - sharpe_ratio: Annualized Sharpe of IC
            - hit_rate: Percentage of positive IC
            - ic_ir: Information Ratio (IC mean / IC std)
        """
        # Remove NaN values
        ic_clean = ic_series.dropna()

        if len(ic_clean) < 2:
            return {
                "t_statistic": 0.0,
                "p_value": 1.0,
                "sharpe_ratio": 0.0,
                "hit_rate": 0.0,
                "ic_ir": 0.0,
            }

        # T-test: is mean IC significantly different from zero?
        t_stat, p_value = stats.ttest_1samp(ic_clean, 0)

        # IC Information Ratio
        ic_mean = ic_clean.mean()
        ic_std = ic_clean.std()
        ic_ir = ic_mean / ic_std if ic_std > 0 else 0.0

        # Annualized Sharpe (treating IC as returns)
        # Assumes IC is calculated at same frequency as annualization factor
        sharpe_ratio = ic_ir * np.sqrt(self._annualization_factor)

        # Hit rate (percentage of positive IC)
        hit_rate = (ic_clean > 0).mean()

        return {
            "t_statistic": float(t_stat),
            "p_value": float(p_value),
            "sharpe_ratio": float(sharpe_ratio),
            "hit_rate": float(hit_rate),
            "ic_ir": float(ic_ir),
        }

    def calculate_decay(
        self,
        factor_scores: pd.DataFrame,
        returns: pd.DataFrame,
        max_lag: int = 20,
    ) -> pd.Series:
        """Calculate IC decay over multiple forward periods.

        Useful for understanding how quickly alpha decays.

        Args:
            factor_scores: Factor scores
            returns: Daily returns
            max_lag: Maximum forward period to test

        Returns:
            Series of mean IC by lag period
        """
        decay_values = []

        for lag in range(1, max_lag + 1):
            # Create forward returns for this lag
            forward_returns = returns.shift(-lag)

            # Calculate IC
            ic_series = self.calculate_ic(factor_scores, forward_returns)
            decay_values.append(ic_series.mean())

        return pd.Series(
            decay_values,
            index=range(1, max_lag + 1),
            name="IC_decay",
        )

    def _calculate_factor_returns(
        self,
        factor_scores: pd.DataFrame,
        forward_returns: pd.DataFrame,
    ) -> pd.Series:
        """Calculate factor portfolio returns (long-short)."""
        # Normalize scores to weights
        weights = factor_scores.div(
            factor_scores.abs().sum(axis=1), axis=0
        ).fillna(0)

        # Align with returns
        common_dates = weights.index.intersection(forward_returns.index)
        common_symbols = list(
            set(weights.columns) & set(forward_returns.columns)
        )

        weights = weights.loc[common_dates, common_symbols]
        returns = forward_returns.loc[common_dates, common_symbols]

        # Calculate weighted returns
        factor_returns = (weights * returns).sum(axis=1)

        return factor_returns
