"""Portfolio Domain Object - Holdings snapshot with invariants.

Represents a portfolio at a specific point in time with:
- Position quantities
- Portfolio weights
- Net asset value
- Valuation date
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

# Tolerance for weight sum validation (floating point)
WEIGHT_SUM_TOLERANCE = 1e-6


@dataclass(frozen=True)
class PortfolioMetadata:
    """Metadata associated with a portfolio snapshot.

    Attributes:
        strategy_name: Name of the strategy/fund
        rebalance_id: Identifier for the rebalance event
        benchmark: Optional benchmark identifier
        created_at: When this snapshot was created
    """

    strategy_name: str = ""
    rebalance_id: str = ""
    benchmark: str | None = None
    created_at: date | None = None


@dataclass
class Portfolio:
    """Portfolio holdings snapshot with invariants.

    Represents the state of a portfolio at a specific valuation date,
    including all positions and their weights.

    Attributes:
        positions: Symbol to shares/notional mapping
        weights: Symbol to portfolio weight mapping
        nav: Net Asset Value (total portfolio value)
        as_of_date: Valuation date
        metadata: Strategy info, rebalance ID, benchmark

    Invariants:
        - sum(weights.values()) approximately equals 1.0 (within tolerance)
          OR equals 0.0 for cash-only portfolios
        - nav = sum(position_value for all positions) - implied, not validated here
        - positions and weights must reference the same symbol set

    Source of Truth: Portfolio state file or database record
    """

    positions: dict[str, float]
    weights: dict[str, float]
    nav: float
    as_of_date: date
    metadata: PortfolioMetadata = field(default_factory=PortfolioMetadata)

    def __post_init__(self) -> None:
        """Validate invariants after initialization."""
        self._validate_invariants()

    def _validate_invariants(self) -> None:
        """Validate all domain invariants.

        Raises:
            ValueError: If any invariant is violated
        """
        # Invariant 1: positions and weights must have same symbols
        position_symbols = set(self.positions.keys())
        weight_symbols = set(self.weights.keys())

        if position_symbols != weight_symbols:
            missing_in_weights = position_symbols - weight_symbols
            missing_in_positions = weight_symbols - position_symbols
            raise ValueError(
                f"Portfolio positions and weights must reference same symbols. "
                f"Missing in weights: {missing_in_weights}. "
                f"Missing in positions: {missing_in_positions}."
            )

        # Invariant 2: weights must sum to ~1.0 or 0.0 (cash-only)
        weight_sum = sum(self.weights.values())
        is_valid_sum = (
            abs(weight_sum - 1.0) < WEIGHT_SUM_TOLERANCE
            or abs(weight_sum) < WEIGHT_SUM_TOLERANCE  # Cash-only portfolio
        )

        if not is_valid_sum:
            raise ValueError(
                f"Portfolio weights must sum to 1.0 (or 0.0 for cash-only). "
                f"Got sum = {weight_sum:.6f}"
            )

        # Invariant 3: NAV must be non-negative
        if self.nav < 0:
            raise ValueError(f"Portfolio NAV must be non-negative. Got: {self.nav}")

    @property
    def symbols(self) -> list[str]:
        """Return list of symbols in the portfolio."""
        return list(self.positions.keys())

    @property
    def num_positions(self) -> int:
        """Return the number of positions."""
        return len(self.positions)

    @property
    def is_empty(self) -> bool:
        """Return True if portfolio has no positions."""
        return len(self.positions) == 0

    def get_position(self, symbol: str) -> float:
        """Get position quantity for a symbol.

        Args:
            symbol: Asset identifier

        Returns:
            Position quantity (0.0 if not held)
        """
        return self.positions.get(symbol, 0.0)

    def get_weight(self, symbol: str) -> float:
        """Get portfolio weight for a symbol.

        Args:
            symbol: Asset identifier

        Returns:
            Portfolio weight (0.0 if not held)
        """
        return self.weights.get(symbol, 0.0)

    def get_position_value(self, symbol: str) -> float:
        """Get position value (NAV * weight) for a symbol.

        Args:
            symbol: Asset identifier

        Returns:
            Position value in NAV currency
        """
        return self.nav * self.get_weight(symbol)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "positions": dict(self.positions),
            "weights": dict(self.weights),
            "nav": self.nav,
            "as_of_date": self.as_of_date.isoformat(),
            "metadata": {
                "strategy_name": self.metadata.strategy_name,
                "rebalance_id": self.metadata.rebalance_id,
                "benchmark": self.metadata.benchmark,
            },
        }

    @classmethod
    def from_weights(
        cls,
        weights: dict[str, float],
        nav: float,
        prices: dict[str, float],
        as_of_date: date,
        metadata: PortfolioMetadata | None = None,
    ) -> "Portfolio":
        """Create portfolio from weights and prices.

        Args:
            weights: Symbol to weight mapping
            nav: Total portfolio NAV
            prices: Symbol to price mapping
            as_of_date: Valuation date
            metadata: Optional metadata

        Returns:
            Portfolio with calculated positions

        Raises:
            ValueError: If prices missing for any symbol in weights
        """
        positions: dict[str, float] = {}

        for symbol, weight in weights.items():
            if symbol not in prices:
                raise ValueError(f"Price not found for symbol '{symbol}'")
            position_value = nav * weight
            positions[symbol] = position_value / prices[symbol]

        return cls(
            positions=positions,
            weights=weights,
            nav=nav,
            as_of_date=as_of_date,
            metadata=metadata or PortfolioMetadata(),
        )
