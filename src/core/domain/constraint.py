"""Constraint Domain Object - Portfolio optimization constraints.

Represents constraints for portfolio optimization problems.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ConstraintType(Enum):
    """Types of portfolio constraints."""

    SECTOR_LIMIT = "sector_limit"
    POSITION_LIMIT = "position_limit"
    TURNOVER_LIMIT = "turnover_limit"
    FACTOR_EXPOSURE = "factor_exposure"
    BETA_LIMIT = "beta_limit"
    TRACKING_ERROR = "tracking_error"


@dataclass(frozen=True)
class Bounds:
    """Lower and upper bounds for a constraint.

    Attributes:
        lower: Lower bound (None means unbounded below)
        upper: Upper bound (None means unbounded above)
    """

    lower: float | None = None
    upper: float | None = None

    def __post_init__(self) -> None:
        """Validate bounds."""
        if self.lower is not None and self.upper is not None:
            if self.lower > self.upper:
                raise ValueError(
                    f"Bounds lower ({self.lower}) must be <= upper ({self.upper})"
                )

    def contains(self, value: float) -> bool:
        """Check if value is within bounds.

        Args:
            value: Value to check

        Returns:
            True if value is within bounds
        """
        if self.lower is not None and value < self.lower:
            return False
        if self.upper is not None and value > self.upper:
            return False
        return True

    def to_dict(self) -> dict[str, float | None]:
        """Convert to dictionary."""
        return {"lower": self.lower, "upper": self.upper}


@dataclass
class Constraint:
    """Portfolio optimization constraint.

    Represents a constraint that must be satisfied by the optimizer.

    Attributes:
        type: Constraint type (sector_limit, position_limit, etc.)
        bounds: Lower and upper limits
        securities: Symbols/sectors this constraint applies to
        name: Human-readable label

    Invariants:
        - bounds.lower <= bounds.upper (feasibility)
        - If type == SECTOR_LIMIT, securities must be valid sector identifiers
        - All referenced securities must exist in universe (validated at optimization time)

    Source of Truth: Constraint configuration (YAML or portfolio policy doc)
    """

    type: ConstraintType
    bounds: Bounds
    securities: list[str] = field(default_factory=list)
    name: str = ""

    def __post_init__(self) -> None:
        """Validate invariants after initialization."""
        self._validate_invariants()

    def _validate_invariants(self) -> None:
        """Validate all domain invariants.

        Raises:
            ValueError: If any invariant is violated
        """
        # Invariant 1: bounds must be feasible (handled by Bounds.__post_init__)
        # Already validated in Bounds dataclass

        # Invariant 2: securities must not be empty for certain constraint types
        requires_securities = {
            ConstraintType.SECTOR_LIMIT,
            ConstraintType.POSITION_LIMIT,
            ConstraintType.FACTOR_EXPOSURE,
        }

        if self.type in requires_securities and not self.securities:
            raise ValueError(
                f"Constraint type {self.type.value} requires at least one security/sector"
            )

    @property
    def is_bounded_above(self) -> bool:
        """Return True if constraint has an upper bound."""
        return self.bounds.upper is not None

    @property
    def is_bounded_below(self) -> bool:
        """Return True if constraint has a lower bound."""
        return self.bounds.lower is not None

    @property
    def is_equality(self) -> bool:
        """Return True if constraint is an equality (lower == upper)."""
        return (
            self.bounds.lower is not None
            and self.bounds.upper is not None
            and abs(self.bounds.lower - self.bounds.upper) < 1e-10
        )

    def applies_to(self, symbol: str) -> bool:
        """Check if constraint applies to a specific symbol.

        Args:
            symbol: Symbol to check

        Returns:
            True if constraint applies to this symbol
        """
        if not self.securities:
            return True  # Applies to all
        return symbol in self.securities

    def is_satisfied(self, value: float) -> bool:
        """Check if a value satisfies this constraint.

        Args:
            value: Value to check (e.g., weight, exposure)

        Returns:
            True if value satisfies the constraint
        """
        return self.bounds.contains(value)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type.value,
            "bounds": self.bounds.to_dict(),
            "securities": list(self.securities),
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Constraint":
        """Create Constraint from dictionary.

        Args:
            data: Dictionary with constraint data

        Returns:
            Constraint instance
        """
        return cls(
            type=ConstraintType(data["type"]),
            bounds=Bounds(
                lower=data.get("bounds", {}).get("lower"),
                upper=data.get("bounds", {}).get("upper"),
            ),
            securities=data.get("securities", []),
            name=data.get("name", ""),
        )


# Factory functions for common constraints
def sector_limit(
    sector: str,
    lower: float = 0.0,
    upper: float = 1.0,
    name: str = "",
) -> Constraint:
    """Create a sector limit constraint.

    Args:
        sector: Sector identifier
        lower: Minimum weight (default 0.0)
        upper: Maximum weight (default 1.0 = 100%)
        name: Optional name

    Returns:
        Sector limit constraint
    """
    return Constraint(
        type=ConstraintType.SECTOR_LIMIT,
        bounds=Bounds(lower=lower, upper=upper),
        securities=[sector],
        name=name or f"Sector limit: {sector} [{lower:.1%}, {upper:.1%}]",
    )


def position_limit(
    symbol: str,
    lower: float = 0.0,
    upper: float = 0.10,
    name: str = "",
) -> Constraint:
    """Create a position limit constraint.

    Args:
        symbol: Security identifier
        lower: Minimum weight (default 0.0)
        upper: Maximum weight (default 0.10 = 10%)
        name: Optional name

    Returns:
        Position limit constraint
    """
    return Constraint(
        type=ConstraintType.POSITION_LIMIT,
        bounds=Bounds(lower=lower, upper=upper),
        securities=[symbol],
        name=name or f"Position limit: {symbol} [{lower:.1%}, {upper:.1%}]",
    )


def turnover_limit(upper: float, name: str = "") -> Constraint:
    """Create a turnover limit constraint.

    Args:
        upper: Maximum turnover (e.g., 0.20 = 20% of NAV)
        name: Optional name

    Returns:
        Turnover limit constraint
    """
    return Constraint(
        type=ConstraintType.TURNOVER_LIMIT,
        bounds=Bounds(lower=0.0, upper=upper),
        securities=[],
        name=name or f"Turnover limit: {upper:.1%}",
    )
