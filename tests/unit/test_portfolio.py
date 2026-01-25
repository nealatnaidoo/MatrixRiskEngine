"""Unit tests for Portfolio domain object."""

import pytest
from datetime import date

from src.core.domain.portfolio import Portfolio, PortfolioMetadata, WEIGHT_SUM_TOLERANCE


class TestPortfolioInvariants:
    """Test Portfolio invariant enforcement."""

    def test_valid_portfolio_creation(self) -> None:
        """Valid Portfolio should be created without errors."""
        portfolio = Portfolio(
            positions={"AAPL": 100, "MSFT": 50},
            weights={"AAPL": 0.6, "MSFT": 0.4},
            nav=100000.0,
            as_of_date=date(2020, 1, 15),
        )

        assert portfolio.num_positions == 2
        assert portfolio.nav == 100000.0

    def test_mismatched_symbols_raises(self) -> None:
        """Mismatched position and weight symbols should raise ValueError."""
        with pytest.raises(ValueError, match="same symbols"):
            Portfolio(
                positions={"AAPL": 100, "MSFT": 50},
                weights={"AAPL": 0.6, "GOOGL": 0.4},  # GOOGL not in positions
                nav=100000.0,
                as_of_date=date(2020, 1, 15),
            )

    def test_weights_not_summing_to_one_raises(self) -> None:
        """Weights not summing to 1.0 (or 0.0) should raise ValueError."""
        with pytest.raises(ValueError, match="sum to 1.0"):
            Portfolio(
                positions={"AAPL": 100, "MSFT": 50},
                weights={"AAPL": 0.5, "MSFT": 0.3},  # Sums to 0.8
                nav=100000.0,
                as_of_date=date(2020, 1, 15),
            )

    def test_negative_nav_raises(self) -> None:
        """Negative NAV should raise ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            Portfolio(
                positions={"AAPL": 100},
                weights={"AAPL": 1.0},
                nav=-100.0,
                as_of_date=date(2020, 1, 15),
            )

    def test_cash_only_portfolio_allowed(self) -> None:
        """Cash-only portfolio (weights sum to 0) should be allowed."""
        portfolio = Portfolio(
            positions={},
            weights={},
            nav=100000.0,
            as_of_date=date(2020, 1, 15),
        )

        assert portfolio.is_empty
        assert portfolio.num_positions == 0

    def test_weights_within_tolerance(self) -> None:
        """Weights within tolerance of 1.0 should be accepted."""
        small_deviation = WEIGHT_SUM_TOLERANCE / 2
        portfolio = Portfolio(
            positions={"AAPL": 100, "MSFT": 50},
            weights={"AAPL": 0.6 + small_deviation, "MSFT": 0.4},
            nav=100000.0,
            as_of_date=date(2020, 1, 15),
        )

        assert portfolio.num_positions == 2


class TestPortfolioMethods:
    """Test Portfolio methods."""

    @pytest.fixture
    def sample_portfolio(self) -> Portfolio:
        """Create a sample Portfolio for testing."""
        return Portfolio(
            positions={"AAPL": 100, "MSFT": 200, "GOOGL": 50},
            weights={"AAPL": 0.5, "MSFT": 0.3, "GOOGL": 0.2},
            nav=100000.0,
            as_of_date=date(2020, 1, 15),
            metadata=PortfolioMetadata(strategy_name="Test Strategy"),
        )

    def test_symbols(self, sample_portfolio: Portfolio) -> None:
        """symbols should return list of held symbols."""
        symbols = sample_portfolio.symbols
        assert set(symbols) == {"AAPL", "MSFT", "GOOGL"}

    def test_get_position(self, sample_portfolio: Portfolio) -> None:
        """get_position should return position quantity."""
        assert sample_portfolio.get_position("AAPL") == 100
        assert sample_portfolio.get_position("UNKNOWN") == 0.0

    def test_get_weight(self, sample_portfolio: Portfolio) -> None:
        """get_weight should return portfolio weight."""
        assert sample_portfolio.get_weight("AAPL") == 0.5
        assert sample_portfolio.get_weight("UNKNOWN") == 0.0

    def test_get_position_value(self, sample_portfolio: Portfolio) -> None:
        """get_position_value should return NAV * weight."""
        assert sample_portfolio.get_position_value("AAPL") == 50000.0  # 100k * 0.5
        assert sample_portfolio.get_position_value("MSFT") == 30000.0  # 100k * 0.3

    def test_to_dict(self, sample_portfolio: Portfolio) -> None:
        """to_dict should return serializable dictionary."""
        result = sample_portfolio.to_dict()

        assert result["nav"] == 100000.0
        assert result["positions"]["AAPL"] == 100
        assert result["weights"]["AAPL"] == 0.5

    def test_from_weights(self) -> None:
        """from_weights should create portfolio with calculated positions."""
        weights = {"AAPL": 0.6, "MSFT": 0.4}
        prices = {"AAPL": 150.0, "MSFT": 300.0}
        nav = 100000.0

        portfolio = Portfolio.from_weights(
            weights=weights,
            nav=nav,
            prices=prices,
            as_of_date=date(2020, 1, 15),
        )

        # AAPL: 60000 / 150 = 400 shares
        assert portfolio.positions["AAPL"] == 400.0
        # MSFT: 40000 / 300 = 133.33 shares
        assert abs(portfolio.positions["MSFT"] - 133.333) < 0.01

    def test_from_weights_missing_price_raises(self) -> None:
        """from_weights should raise if price missing for a symbol."""
        with pytest.raises(ValueError, match="Price not found"):
            Portfolio.from_weights(
                weights={"AAPL": 0.6, "MSFT": 0.4},
                nav=100000.0,
                prices={"AAPL": 150.0},  # Missing MSFT
                as_of_date=date(2020, 1, 15),
            )
