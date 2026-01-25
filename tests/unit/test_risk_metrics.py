"""Unit tests for RiskMetrics domain object."""

import pytest
from datetime import date

from src.core.domain.risk_metrics import RiskMetrics, Greeks


class TestRiskMetricsInvariants:
    """Test RiskMetrics invariant enforcement."""

    def test_valid_risk_metrics_creation(self) -> None:
        """Valid RiskMetrics should be created without errors."""
        metrics = RiskMetrics(
            var={"95%": -1500000, "99%": -2200000},
            cvar={"95%": -1800000, "99%": -2600000},
            greeks=Greeks(delta=0.65, gamma=0.02, vega=15000),
            as_of_date=date(2020, 1, 15),
            portfolio_id="portfolio_001",
        )

        assert metrics.get_var("95%") == -1500000
        assert metrics.get_cvar("99%") == -2600000

    def test_mismatched_confidence_levels_raises(self) -> None:
        """Mismatched VaR and CVaR confidence levels should raise ValueError."""
        with pytest.raises(ValueError, match="same confidence levels"):
            RiskMetrics(
                var={"95%": -1500000, "99%": -2200000},
                cvar={"95%": -1800000},  # Missing 99%
                greeks=Greeks(),
                as_of_date=date(2020, 1, 15),
                portfolio_id="portfolio_001",
            )

    def test_cvar_less_extreme_than_var_raises(self) -> None:
        """CVaR less extreme (less negative) than VaR should raise ValueError."""
        with pytest.raises(ValueError, match="CVaR must be <= VaR"):
            RiskMetrics(
                var={"95%": -1500000},
                cvar={"95%": -1000000},  # Less negative than VaR - invalid
                greeks=Greeks(),
                as_of_date=date(2020, 1, 15),
                portfolio_id="portfolio_001",
            )

    def test_cvar_equals_var_allowed(self) -> None:
        """CVaR equal to VaR should be allowed (edge case)."""
        metrics = RiskMetrics(
            var={"95%": -1500000},
            cvar={"95%": -1500000},  # Equal to VaR - allowed
            greeks=Greeks(),
            as_of_date=date(2020, 1, 15),
            portfolio_id="portfolio_001",
        )

        assert metrics.get_var("95%") == metrics.get_cvar("95%")


class TestRiskMetricsMethods:
    """Test RiskMetrics methods."""

    @pytest.fixture
    def sample_risk_metrics(self) -> RiskMetrics:
        """Create sample RiskMetrics for testing."""
        return RiskMetrics(
            var={"95%": -1500000, "99%": -2200000},
            cvar={"95%": -1800000, "99%": -2600000},
            greeks=Greeks(delta=0.65, gamma=0.02, vega=15000, duration=5.5),
            as_of_date=date(2020, 1, 15),
            portfolio_id="portfolio_001",
        )

    def test_get_var(self, sample_risk_metrics: RiskMetrics) -> None:
        """get_var should return VaR for confidence level."""
        assert sample_risk_metrics.get_var("95%") == -1500000
        assert sample_risk_metrics.get_var("90%") is None

    def test_get_cvar(self, sample_risk_metrics: RiskMetrics) -> None:
        """get_cvar should return CVaR for confidence level."""
        assert sample_risk_metrics.get_cvar("95%") == -1800000

    def test_confidence_levels(self, sample_risk_metrics: RiskMetrics) -> None:
        """confidence_levels should return list of levels."""
        levels = sample_risk_metrics.confidence_levels
        assert set(levels) == {"95%", "99%"}

    def test_has_greeks(self, sample_risk_metrics: RiskMetrics) -> None:
        """has_greeks should return True when Greeks are populated."""
        assert sample_risk_metrics.has_greeks is True

    def test_has_greeks_empty(self) -> None:
        """has_greeks should return False for empty Greeks."""
        metrics = RiskMetrics.create_with_var_only(
            var={"95%": -1500000},
            cvar={"95%": -1800000},
            as_of_date=date(2020, 1, 15),
            portfolio_id="portfolio_001",
        )
        assert metrics.has_greeks is False

    def test_to_dict(self, sample_risk_metrics: RiskMetrics) -> None:
        """to_dict should return serializable dictionary."""
        result = sample_risk_metrics.to_dict()

        assert result["var"]["95%"] == -1500000
        assert result["cvar"]["99%"] == -2600000
        assert result["greeks"]["delta"] == 0.65
        assert result["portfolio_id"] == "portfolio_001"


class TestGreeks:
    """Test Greeks dataclass."""

    def test_greeks_creation(self) -> None:
        """Greeks should be created with optional values."""
        greeks = Greeks(delta=0.5, gamma=0.1)

        assert greeks.delta == 0.5
        assert greeks.gamma == 0.1
        assert greeks.vega is None

    def test_greeks_to_dict(self) -> None:
        """to_dict should include all fields."""
        greeks = Greeks(delta=0.5, duration=5.5)
        result = greeks.to_dict()

        assert result["delta"] == 0.5
        assert result["duration"] == 5.5
        assert result["gamma"] is None
