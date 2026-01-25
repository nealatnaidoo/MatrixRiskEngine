"""Unit tests for Constraint domain object."""

import pytest

from src.core.domain.constraint import (
    Constraint,
    ConstraintType,
    Bounds,
    sector_limit,
    position_limit,
    turnover_limit,
)


class TestBounds:
    """Test Bounds dataclass."""

    def test_valid_bounds_creation(self) -> None:
        """Valid bounds should be created without errors."""
        bounds = Bounds(lower=0.0, upper=0.10)

        assert bounds.lower == 0.0
        assert bounds.upper == 0.10

    def test_unbounded_allowed(self) -> None:
        """Unbounded (None) values should be allowed."""
        bounds_above = Bounds(upper=0.10)
        bounds_below = Bounds(lower=0.0)

        assert bounds_above.lower is None
        assert bounds_below.upper is None

    def test_invalid_bounds_raises(self) -> None:
        """Lower > upper should raise ValueError."""
        with pytest.raises(ValueError, match="lower.*upper"):
            Bounds(lower=0.20, upper=0.10)

    def test_contains(self) -> None:
        """contains should check if value is within bounds."""
        bounds = Bounds(lower=0.0, upper=0.10)

        assert bounds.contains(0.05) is True
        assert bounds.contains(0.0) is True
        assert bounds.contains(0.10) is True
        assert bounds.contains(-0.01) is False
        assert bounds.contains(0.11) is False

    def test_contains_unbounded(self) -> None:
        """contains should work with unbounded values."""
        bounds_above = Bounds(upper=0.10)
        bounds_below = Bounds(lower=0.0)

        assert bounds_above.contains(-1000) is True
        assert bounds_above.contains(0.11) is False
        assert bounds_below.contains(1000) is True
        assert bounds_below.contains(-0.01) is False


class TestConstraintInvariants:
    """Test Constraint invariant enforcement."""

    def test_valid_constraint_creation(self) -> None:
        """Valid Constraint should be created without errors."""
        constraint = Constraint(
            type=ConstraintType.POSITION_LIMIT,
            bounds=Bounds(lower=0.0, upper=0.10),
            securities=["AAPL"],
            name="AAPL position limit",
        )

        assert constraint.is_bounded_above is True
        assert constraint.is_bounded_below is True

    def test_sector_limit_requires_securities(self) -> None:
        """Sector limit without securities should raise ValueError."""
        with pytest.raises(ValueError, match="requires at least one"):
            Constraint(
                type=ConstraintType.SECTOR_LIMIT,
                bounds=Bounds(upper=0.10),
                securities=[],  # Empty
            )

    def test_turnover_limit_allows_empty_securities(self) -> None:
        """Turnover limit should allow empty securities (applies to all)."""
        constraint = Constraint(
            type=ConstraintType.TURNOVER_LIMIT,
            bounds=Bounds(lower=0.0, upper=0.20),
            securities=[],  # OK for turnover
        )

        assert constraint.applies_to("ANY_SYMBOL") is True


class TestConstraintMethods:
    """Test Constraint methods."""

    @pytest.fixture
    def sample_constraint(self) -> Constraint:
        """Create sample Constraint for testing."""
        return Constraint(
            type=ConstraintType.POSITION_LIMIT,
            bounds=Bounds(lower=0.0, upper=0.05),
            securities=["AAPL", "MSFT"],
            name="Max 5% position",
        )

    def test_is_bounded_above(self, sample_constraint: Constraint) -> None:
        """is_bounded_above should check upper bound."""
        assert sample_constraint.is_bounded_above is True

    def test_is_bounded_below(self, sample_constraint: Constraint) -> None:
        """is_bounded_below should check lower bound."""
        assert sample_constraint.is_bounded_below is True

    def test_is_equality(self) -> None:
        """is_equality should detect equal bounds."""
        equality = Constraint(
            type=ConstraintType.POSITION_LIMIT,
            bounds=Bounds(lower=0.05, upper=0.05),
            securities=["AAPL"],
        )
        range_constraint = Constraint(
            type=ConstraintType.POSITION_LIMIT,
            bounds=Bounds(lower=0.0, upper=0.05),
            securities=["AAPL"],
        )

        assert equality.is_equality is True
        assert range_constraint.is_equality is False

    def test_applies_to(self, sample_constraint: Constraint) -> None:
        """applies_to should check if constraint applies to symbol."""
        assert sample_constraint.applies_to("AAPL") is True
        assert sample_constraint.applies_to("GOOGL") is False

    def test_is_satisfied(self, sample_constraint: Constraint) -> None:
        """is_satisfied should check if value satisfies constraint."""
        assert sample_constraint.is_satisfied(0.03) is True
        assert sample_constraint.is_satisfied(0.06) is False

    def test_to_dict(self, sample_constraint: Constraint) -> None:
        """to_dict should return serializable dictionary."""
        result = sample_constraint.to_dict()

        assert result["type"] == "position_limit"
        assert result["bounds"]["upper"] == 0.05
        assert "AAPL" in result["securities"]

    def test_from_dict(self) -> None:
        """from_dict should create constraint from dictionary."""
        data = {
            "type": "sector_limit",
            "bounds": {"lower": 0.0, "upper": 0.15},
            "securities": ["Technology"],
            "name": "Tech sector limit",
        }

        constraint = Constraint.from_dict(data)

        assert constraint.type == ConstraintType.SECTOR_LIMIT
        assert constraint.bounds.upper == 0.15


class TestFactoryFunctions:
    """Test constraint factory functions."""

    def test_sector_limit(self) -> None:
        """sector_limit should create valid sector constraint."""
        constraint = sector_limit("Technology", lower=0.05, upper=0.15)

        assert constraint.type == ConstraintType.SECTOR_LIMIT
        assert constraint.bounds.lower == 0.05
        assert constraint.bounds.upper == 0.15
        assert "Technology" in constraint.securities

    def test_position_limit(self) -> None:
        """position_limit should create valid position constraint."""
        constraint = position_limit("AAPL", upper=0.05)

        assert constraint.type == ConstraintType.POSITION_LIMIT
        assert constraint.bounds.upper == 0.05
        assert "AAPL" in constraint.securities

    def test_turnover_limit(self) -> None:
        """turnover_limit should create valid turnover constraint."""
        constraint = turnover_limit(0.20)

        assert constraint.type == ConstraintType.TURNOVER_LIMIT
        assert constraint.bounds.upper == 0.20
        assert len(constraint.securities) == 0
