"""Unit tests for OptimizationService."""

import pytest
import pandas as pd
import numpy as np
from datetime import date
from unittest.mock import Mock

from src.core.services.optimization_service import (
    OptimizationService,
    OptimizationRequest,
    OptimizationResponse,
    TradeOrder,
)
from src.core.domain.constraint import Constraint, ConstraintType, Bounds
from src.core.domain.portfolio import Portfolio, PortfolioMetadata


class TestOptimizationServiceBasic:
    """Test basic optimization workflow."""

    @pytest.fixture
    def mock_ports(self) -> tuple[Mock, Mock]:
        """Create mock ports for testing."""
        data_port = Mock()
        optimizer = Mock()

        # Configure optimizer to return a portfolio
        target = Portfolio(
            positions={"AAPL": 0.4, "MSFT": 0.3, "GOOGL": 0.3},
            weights={"AAPL": 0.4, "MSFT": 0.3, "GOOGL": 0.3},
            nav=1.0,
            as_of_date=date.today(),
        )
        optimizer.optimize.return_value = target

        return data_port, optimizer

    def test_optimize_returns_response(
        self, mock_ports: tuple[Mock, Mock]
    ) -> None:
        """optimize should return OptimizationResponse."""
        data_port, optimizer = mock_ports
        service = OptimizationService(data_port, optimizer)

        request = OptimizationRequest(
            universe=["AAPL", "MSFT", "GOOGL"],
            alpha_source="alpha_signals",
            risk_model_version="v1",
            constraints=[],
            objective="max_sharpe",
        )

        response = service.optimize(request)

        assert isinstance(response, OptimizationResponse)
        assert response.target_portfolio is not None

    def test_optimize_calls_optimizer(
        self, mock_ports: tuple[Mock, Mock]
    ) -> None:
        """optimize should call optimizer with correct params."""
        data_port, optimizer = mock_ports
        service = OptimizationService(data_port, optimizer)

        constraints = [
            Constraint(
                type=ConstraintType.POSITION_LIMIT,
                bounds=Bounds(upper=0.3),
                securities=["AAPL"],
            ),
        ]

        request = OptimizationRequest(
            universe=["AAPL", "MSFT"],
            alpha_source="alpha",
            risk_model_version="v1",
            constraints=constraints,
            objective="min_variance",
        )

        service.optimize(request)

        optimizer.optimize.assert_called_once()
        call_kwargs = optimizer.optimize.call_args.kwargs
        assert call_kwargs["objective"] == "min_variance"
        assert len(call_kwargs["constraints"]) == 1


class TestOptimizationServiceTradeGeneration:
    """Test trade generation."""

    def test_generate_trades_calculates_difference(self) -> None:
        """generate_trades should calculate weight differences."""
        data_port = Mock()
        optimizer = Mock()
        service = OptimizationService(data_port, optimizer)

        current = Portfolio(
            positions={"AAPL": 0.5, "MSFT": 0.5},
            weights={"AAPL": 0.5, "MSFT": 0.5},
            nav=100000.0,
            as_of_date=date.today(),
        )

        target = Portfolio(
            positions={"AAPL": 0.7, "MSFT": 0.3},
            weights={"AAPL": 0.7, "MSFT": 0.3},
            nav=1.0,
            as_of_date=date.today(),
        )

        trades = service.generate_trades(current, target)

        assert len(trades) == 2

        # Find trades by symbol
        aapl_trade = next(t for t in trades if t.symbol == "AAPL")
        msft_trade = next(t for t in trades if t.symbol == "MSFT")

        assert aapl_trade.side == "buy"
        assert msft_trade.side == "sell"

    def test_generate_trades_no_change(self) -> None:
        """No weight change should produce no trades."""
        data_port = Mock()
        optimizer = Mock()
        service = OptimizationService(data_port, optimizer)

        portfolio = Portfolio(
            positions={"AAPL": 0.5, "MSFT": 0.5},
            weights={"AAPL": 0.5, "MSFT": 0.5},
            nav=100000.0,
            as_of_date=date.today(),
        )

        trades = service.generate_trades(portfolio, portfolio)

        assert len(trades) == 0

    def test_generate_trades_new_position(self) -> None:
        """Adding new position should create buy trade."""
        data_port = Mock()
        optimizer = Mock()
        service = OptimizationService(data_port, optimizer)

        current = Portfolio(
            positions={"AAPL": 1.0},
            weights={"AAPL": 1.0},
            nav=100000.0,
            as_of_date=date.today(),
        )

        target = Portfolio(
            positions={"AAPL": 0.5, "MSFT": 0.5},
            weights={"AAPL": 0.5, "MSFT": 0.5},
            nav=1.0,
            as_of_date=date.today(),
        )

        trades = service.generate_trades(current, target)

        msft_trade = next(t for t in trades if t.symbol == "MSFT")
        assert msft_trade.side == "buy"

    def test_generate_trades_exit_position(self) -> None:
        """Exiting position should create sell trade."""
        data_port = Mock()
        optimizer = Mock()
        service = OptimizationService(data_port, optimizer)

        current = Portfolio(
            positions={"AAPL": 0.5, "MSFT": 0.5},
            weights={"AAPL": 0.5, "MSFT": 0.5},
            nav=100000.0,
            as_of_date=date.today(),
        )

        target = Portfolio(
            positions={"AAPL": 1.0},
            weights={"AAPL": 1.0},
            nav=1.0,
            as_of_date=date.today(),
        )

        trades = service.generate_trades(current, target)

        msft_trade = next(t for t in trades if t.symbol == "MSFT")
        assert msft_trade.side == "sell"


class TestTradeOrder:
    """Test TradeOrder dataclass."""

    def test_trade_order_to_dict(self) -> None:
        """to_dict should return serializable dictionary."""
        order = TradeOrder(
            symbol="AAPL",
            side="buy",
            quantity=10000.0,
            estimated_cost=7.0,
        )

        result = order.to_dict()

        assert result["symbol"] == "AAPL"
        assert result["side"] == "buy"
        assert result["quantity"] == 10000.0
        assert result["estimated_cost"] == 7.0
