"""Unit tests for Corporate Action functionality."""

import pytest
import pandas as pd
import numpy as np
from datetime import date

from tests.stubs.stub_data_adapter import StubDataAdapter


class TestCorporateActionSave:
    """Test saving corporate actions."""

    @pytest.fixture
    def adapter(self) -> StubDataAdapter:
        """Create fresh adapter."""
        return StubDataAdapter()

    def test_save_split_action(self, adapter: StubDataAdapter) -> None:
        """Saving a split action should work."""
        adapter.save_corporate_action(
            symbol="AAPL",
            action_type="split",
            effective_date=date(2020, 8, 31),
            adjustment_factor=4.0,
        )

        actions = adapter.load_corporate_actions("AAPL")
        assert len(actions) == 1
        assert actions["action_type"].iloc[0] == "split"
        assert actions["adjustment_factor"].iloc[0] == 4.0

    def test_save_dividend_action(self, adapter: StubDataAdapter) -> None:
        """Saving a dividend action should work."""
        adapter.save_corporate_action(
            symbol="AAPL",
            action_type="dividend",
            effective_date=date(2020, 5, 8),
            adjustment_factor=0.82,  # Dividend amount per share
        )

        actions = adapter.load_corporate_actions("AAPL")
        assert len(actions) == 1
        assert actions["action_type"].iloc[0] == "dividend"

    def test_save_invalid_action_type_raises(self, adapter: StubDataAdapter) -> None:
        """Invalid action type should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid action type"):
            adapter.save_corporate_action(
                symbol="AAPL",
                action_type="merger",  # Invalid
                effective_date=date(2020, 1, 1),
                adjustment_factor=1.0,
            )

    def test_save_multiple_actions(self, adapter: StubDataAdapter) -> None:
        """Multiple actions for same symbol should be saved."""
        adapter.save_corporate_action(
            symbol="AAPL",
            action_type="split",
            effective_date=date(2020, 8, 31),
            adjustment_factor=4.0,
        )
        adapter.save_corporate_action(
            symbol="AAPL",
            action_type="dividend",
            effective_date=date(2020, 5, 8),
            adjustment_factor=0.82,
        )

        actions = adapter.load_corporate_actions("AAPL")
        assert len(actions) == 2


class TestCorporateActionLoad:
    """Test loading corporate actions."""

    @pytest.fixture
    def adapter_with_actions(self) -> StubDataAdapter:
        """Create adapter with seeded actions."""
        adapter = StubDataAdapter()

        adapter.save_corporate_action(
            symbol="AAPL",
            action_type="split",
            effective_date=date(2020, 8, 31),
            adjustment_factor=4.0,
        )
        adapter.save_corporate_action(
            symbol="AAPL",
            action_type="dividend",
            effective_date=date(2020, 5, 8),
            adjustment_factor=0.82,
        )
        adapter.save_corporate_action(
            symbol="AAPL",
            action_type="dividend",
            effective_date=date(2020, 11, 6),
            adjustment_factor=0.205,
        )

        return adapter

    def test_load_all_actions(self, adapter_with_actions: StubDataAdapter) -> None:
        """Loading without filters returns all actions."""
        actions = adapter_with_actions.load_corporate_actions("AAPL")
        assert len(actions) == 3

    def test_load_with_date_range(self, adapter_with_actions: StubDataAdapter) -> None:
        """Date range filter returns correct actions."""
        actions = adapter_with_actions.load_corporate_actions(
            symbol="AAPL",
            start_date=date(2020, 6, 1),
            end_date=date(2020, 9, 30),
        )

        # Should only include August split
        assert len(actions) == 1
        assert actions["action_type"].iloc[0] == "split"

    def test_load_nonexistent_symbol(self, adapter_with_actions: StubDataAdapter) -> None:
        """Loading for unknown symbol returns empty DataFrame."""
        actions = adapter_with_actions.load_corporate_actions("UNKNOWN")
        assert len(actions) == 0


class TestApplyCorporateActions:
    """Test applying corporate actions to price data."""

    @pytest.fixture
    def price_data(self) -> pd.DataFrame:
        """Create sample price data spanning a split."""
        dates = pd.date_range("2020-01-01", "2020-12-31", freq="B")
        prices = pd.DataFrame({
            "close": [100.0] * len(dates),  # Constant price for easy verification
            "volume": [1000000] * len(dates),
        }, index=dates)
        return prices

    @pytest.fixture
    def adapter_with_split(self) -> StubDataAdapter:
        """Create adapter with a 4:1 split on Aug 31, 2020."""
        adapter = StubDataAdapter()
        adapter.save_corporate_action(
            symbol="AAPL",
            action_type="split",
            effective_date=date(2020, 8, 31),
            adjustment_factor=4.0,
        )
        return adapter

    def test_split_adjusts_pre_split_prices(
        self,
        adapter_with_split: StubDataAdapter,
        price_data: pd.DataFrame,
    ) -> None:
        """Split should divide pre-split prices by factor."""
        adjusted = adapter_with_split.apply_corporate_actions(
            data=price_data,
            symbol="AAPL",
        )

        # Pre-split price should be divided by 4
        pre_split = adjusted.loc[adjusted.index < pd.Timestamp("2020-08-31"), "close"]
        assert (pre_split == 25.0).all()

        # Post-split price unchanged
        post_split = adjusted.loc[adjusted.index >= pd.Timestamp("2020-08-31"), "close"]
        assert (post_split == 100.0).all()

    def test_split_adjusts_volume(
        self,
        adapter_with_split: StubDataAdapter,
        price_data: pd.DataFrame,
    ) -> None:
        """Split should multiply pre-split volume by factor."""
        adjusted = adapter_with_split.apply_corporate_actions(
            data=price_data,
            symbol="AAPL",
        )

        # Pre-split volume should be multiplied by 4
        pre_split = adjusted.loc[adjusted.index < pd.Timestamp("2020-08-31"), "volume"]
        assert (pre_split == 4000000).all()

    def test_as_of_date_filters_actions(
        self,
        adapter_with_split: StubDataAdapter,
        price_data: pd.DataFrame,
    ) -> None:
        """Actions after as_of_date should not be applied."""
        # Query as of before the split
        adjusted = adapter_with_split.apply_corporate_actions(
            data=price_data,
            symbol="AAPL",
            as_of_date=date(2020, 7, 1),
        )

        # No adjustment should be applied - split wasn't known yet
        assert (adjusted["close"] == 100.0).all()

    def test_as_of_date_includes_past_actions(
        self,
        adapter_with_split: StubDataAdapter,
        price_data: pd.DataFrame,
    ) -> None:
        """Actions before as_of_date should be applied."""
        # Query as of after the split
        adjusted = adapter_with_split.apply_corporate_actions(
            data=price_data,
            symbol="AAPL",
            as_of_date=date(2020, 10, 1),
        )

        # Pre-split prices should be adjusted
        pre_split = adjusted.loc[adjusted.index < pd.Timestamp("2020-08-31"), "close"]
        assert (pre_split == 25.0).all()

    def test_dividend_adjustment(self) -> None:
        """Dividend should subtract from pre-ex-date prices."""
        adapter = StubDataAdapter()
        adapter.save_corporate_action(
            symbol="AAPL",
            action_type="dividend",
            effective_date=date(2020, 5, 8),
            adjustment_factor=1.0,  # $1 dividend
        )

        dates = pd.date_range("2020-01-01", "2020-12-31", freq="B")
        prices = pd.DataFrame({
            "close": [100.0] * len(dates),
        }, index=dates)

        adjusted = adapter.apply_corporate_actions(prices, "AAPL")

        # Pre-dividend prices should be reduced by dividend amount
        pre_div = adjusted.loc[adjusted.index < pd.Timestamp("2020-05-08"), "close"]
        assert (pre_div == 99.0).all()

    def test_no_actions_returns_unchanged(self) -> None:
        """No corporate actions returns original data."""
        adapter = StubDataAdapter()

        dates = pd.date_range("2020-01-01", periods=10, freq="B")
        prices = pd.DataFrame({"close": [100.0] * 10}, index=dates)

        adjusted = adapter.apply_corporate_actions(prices, "AAPL")

        pd.testing.assert_frame_equal(adjusted, prices)
