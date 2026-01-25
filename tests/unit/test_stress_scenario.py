"""Unit tests for StressScenario domain object."""

import pytest
from datetime import date

from src.core.domain.stress_scenario import (
    StressScenario,
    SCENARIO_2008_CRISIS,
    SCENARIO_COVID_CRASH,
)


class TestStressScenarioInvariants:
    """Test StressScenario invariant enforcement."""

    def test_valid_scenario_creation(self) -> None:
        """Valid StressScenario should be created without errors."""
        scenario = StressScenario(
            name="Test Scenario",
            shocks={"SPX": -0.20, "VIX": 0.50},
            description="A test stress scenario",
            date_calibrated=date(2020, 1, 15),
        )

        assert scenario.name == "Test Scenario"
        assert scenario.num_shocks == 2

    def test_empty_name_raises(self) -> None:
        """Empty name should raise ValueError."""
        with pytest.raises(ValueError, match="name must not be empty"):
            StressScenario(
                name="",
                shocks={"SPX": -0.20},
                description="Test",
                date_calibrated=date(2020, 1, 15),
            )

    def test_whitespace_only_name_raises(self) -> None:
        """Whitespace-only name should raise ValueError."""
        with pytest.raises(ValueError, match="name must not be empty"):
            StressScenario(
                name="   ",
                shocks={"SPX": -0.20},
                description="Test",
                date_calibrated=date(2020, 1, 15),
            )

    def test_empty_shocks_raises(self) -> None:
        """Empty shocks dict should raise ValueError."""
        with pytest.raises(ValueError, match="at least one shock"):
            StressScenario(
                name="Test",
                shocks={},
                description="Test",
                date_calibrated=date(2020, 1, 15),
            )

    def test_extreme_shock_raises(self) -> None:
        """Shock magnitude > 5.0 should raise ValueError."""
        with pytest.raises(ValueError, match="extreme shocks"):
            StressScenario(
                name="Extreme Test",
                shocks={"SPX": -6.0},  # 600% - too extreme
                description="Test",
                date_calibrated=date(2020, 1, 15),
            )

    def test_boundary_shock_allowed(self) -> None:
        """Shock magnitude exactly at 5.0 should be allowed."""
        scenario = StressScenario(
            name="Boundary Test",
            shocks={"SPX": -5.0},  # Exactly at limit
            description="Test",
            date_calibrated=date(2020, 1, 15),
        )

        assert scenario.get_shock("SPX") == -5.0


class TestStressScenarioMethods:
    """Test StressScenario methods."""

    @pytest.fixture
    def sample_scenario(self) -> StressScenario:
        """Create sample StressScenario for testing."""
        return StressScenario(
            name="Test Crisis",
            shocks={"SPX": -0.35, "VIX": 1.5, "US10Y": -0.01},
            description="A test crisis scenario",
            date_calibrated=date(2020, 3, 16),
        )

    def test_get_shock(self, sample_scenario: StressScenario) -> None:
        """get_shock should return shock value for risk factor."""
        assert sample_scenario.get_shock("SPX") == -0.35
        assert sample_scenario.get_shock("UNKNOWN") is None

    def test_risk_factors(self, sample_scenario: StressScenario) -> None:
        """risk_factors should return list of factors."""
        factors = sample_scenario.risk_factors
        assert set(factors) == {"SPX", "VIX", "US10Y"}

    def test_num_shocks(self, sample_scenario: StressScenario) -> None:
        """num_shocks should return count of shocks."""
        assert sample_scenario.num_shocks == 3

    def test_has_shock(self, sample_scenario: StressScenario) -> None:
        """has_shock should check if factor has a shock."""
        assert sample_scenario.has_shock("SPX") is True
        assert sample_scenario.has_shock("UNKNOWN") is False

    def test_to_dict(self, sample_scenario: StressScenario) -> None:
        """to_dict should return serializable dictionary."""
        result = sample_scenario.to_dict()

        assert result["name"] == "Test Crisis"
        assert result["shocks"]["SPX"] == -0.35
        assert result["date_calibrated"] == "2020-03-16"

    def test_from_dict(self) -> None:
        """from_dict should create scenario from dictionary."""
        data = {
            "name": "From Dict Test",
            "shocks": {"SPX": -0.25},
            "description": "Created from dict",
            "date_calibrated": "2020-01-15",
        }

        scenario = StressScenario.from_dict(data)

        assert scenario.name == "From Dict Test"
        assert scenario.get_shock("SPX") == -0.25


class TestPredefinedScenarios:
    """Test pre-defined stress scenarios."""

    def test_2008_crisis_scenario(self) -> None:
        """2008 Crisis scenario should be valid."""
        assert SCENARIO_2008_CRISIS.name == "2008 Financial Crisis"
        assert SCENARIO_2008_CRISIS.get_shock("SPX") == -0.40
        assert SCENARIO_2008_CRISIS.get_shock("VIX") == 2.0

    def test_covid_crash_scenario(self) -> None:
        """COVID Crash scenario should be valid."""
        assert SCENARIO_COVID_CRASH.name == "COVID Crash"
        assert SCENARIO_COVID_CRASH.get_shock("SPX") == -0.35
