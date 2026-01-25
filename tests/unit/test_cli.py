"""Unit tests for CLI scripts."""

import pytest
import tempfile
import os
from pathlib import Path
from datetime import date

import pandas as pd
import numpy as np


class TestDataLoaderCLI:
    """Test data loader CLI functionality."""

    @pytest.fixture
    def sample_csv(self, tmp_path: Path) -> Path:
        """Create sample CSV file."""
        dates = pd.date_range("2020-01-01", periods=100, freq="B")
        data = pd.DataFrame({
            "date": dates,
            "close": 100 + np.cumsum(np.random.randn(100) * 2),
            "volume": np.random.randint(1000000, 10000000, size=100),
        })
        csv_path = tmp_path / "sample_data.csv"
        data.to_csv(csv_path, index=False)
        return csv_path

    def test_create_parser(self) -> None:
        """Parser should be created correctly."""
        from src.cli.data_loader import create_parser

        parser = create_parser()
        assert parser is not None

    def test_parse_required_args(self) -> None:
        """Required arguments should be parsed."""
        from src.cli.data_loader import create_parser

        parser = create_parser()
        args = parser.parse_args([
            "--symbol", "AAPL",
            "--list-versions",
        ])

        assert args.symbol == "AAPL"
        assert args.list_versions is True

    def test_parse_full_args(self, sample_csv: Path) -> None:
        """All arguments should be parsed correctly."""
        from src.cli.data_loader import create_parser

        parser = create_parser()
        args = parser.parse_args([
            "--input", str(sample_csv),
            "--symbol", "AAPL",
            "--version", "v1",
            "--connection", "lmdb://./test_data",
            "--source", "test",
        ])

        assert args.input == str(sample_csv)
        assert args.symbol == "AAPL"
        assert args.version == "v1"
        assert args.connection == "lmdb://./test_data"
        assert args.source == "test"

    def test_load_csv(self, sample_csv: Path) -> None:
        """CSV loading should work correctly."""
        from src.cli.data_loader import load_csv

        df = load_csv(str(sample_csv), "date")

        assert isinstance(df.index, pd.DatetimeIndex)
        assert len(df) == 100
        assert "close" in df.columns


class TestBacktestRunnerCLI:
    """Test backtest runner CLI functionality."""

    def test_create_parser(self) -> None:
        """Parser should be created correctly."""
        from src.cli.backtest_runner import create_parser

        parser = create_parser()
        assert parser is not None

    def test_parse_inline_args(self) -> None:
        """Inline arguments should be parsed."""
        from src.cli.backtest_runner import create_parser

        parser = create_parser()
        args = parser.parse_args([
            "--universe", "AAPL,MSFT,GOOGL",
            "--start", "2020-01-01",
            "--end", "2020-12-31",
            "--strategy", "momentum",
            "--rebalance", "monthly",
        ])

        assert args.universe == "AAPL,MSFT,GOOGL"
        assert args.start == "2020-01-01"
        assert args.end == "2020-12-31"
        assert args.strategy == "momentum"
        assert args.rebalance == "monthly"

    def test_create_signal_generator(self) -> None:
        """Signal generators should be created correctly."""
        from src.cli.backtest_runner import create_signal_generator

        # Equal weight
        gen = create_signal_generator("equal_weight")
        prices = pd.DataFrame({
            "AAPL": [100, 101, 102],
            "MSFT": [200, 201, 202],
        }, index=pd.date_range("2020-01-01", periods=3))

        signals = gen(prices)
        assert signals.iloc[0, 0] == pytest.approx(0.5)

    def test_momentum_signal_generator(self) -> None:
        """Momentum signal generator should rank by returns."""
        from src.cli.backtest_runner import create_signal_generator

        gen = create_signal_generator("momentum")

        # Create prices where AAPL has better momentum
        dates = pd.date_range("2019-01-01", periods=300, freq="B")
        prices = pd.DataFrame({
            "AAPL": 100 * np.cumprod(1 + 0.001 * np.ones(300)),  # Positive momentum
            "MSFT": 100 * np.cumprod(1 - 0.0005 * np.ones(300)),  # Negative momentum
        }, index=dates)

        signals = gen(prices)

        # AAPL should have higher signal (better momentum)
        assert signals["AAPL"].iloc[-1] > signals["MSFT"].iloc[-1]


class TestRiskCalculatorCLI:
    """Test risk calculator CLI functionality."""

    @pytest.fixture
    def sample_portfolio_csv(self, tmp_path: Path) -> Path:
        """Create sample portfolio CSV."""
        data = pd.DataFrame({
            "symbol": ["AAPL", "MSFT", "GOOGL"],
            "position": [1000, 500, 200],
            "weight": [0.5, 0.3, 0.2],
        })
        csv_path = tmp_path / "portfolio.csv"
        data.to_csv(csv_path, index=False)
        return csv_path

    def test_create_parser(self) -> None:
        """Parser should be created correctly."""
        from src.cli.risk_calculator import create_parser

        parser = create_parser()
        assert parser is not None

    def test_parse_basic_args(self, sample_portfolio_csv: Path) -> None:
        """Basic arguments should be parsed."""
        from src.cli.risk_calculator import create_parser

        parser = create_parser()
        args = parser.parse_args([
            "--portfolio", str(sample_portfolio_csv),
            "--date", "2026-01-25",
        ])

        assert args.portfolio == str(sample_portfolio_csv)
        assert args.date == "2026-01-25"

    def test_parse_var_args(self, sample_portfolio_csv: Path) -> None:
        """VaR arguments should be parsed."""
        from src.cli.risk_calculator import create_parser

        parser = create_parser()
        args = parser.parse_args([
            "--portfolio", str(sample_portfolio_csv),
            "--var-method", "parametric",
            "--confidence", "90,95,99",
            "--window", "500",
        ])

        assert args.var_method == "parametric"
        assert args.confidence == "90,95,99"
        assert args.window == 500

    def test_load_portfolio(self, sample_portfolio_csv: Path) -> None:
        """Portfolio loading should work correctly."""
        from src.cli.risk_calculator import load_portfolio

        portfolio = load_portfolio(str(sample_portfolio_csv), nav=1000000.0)

        assert len(portfolio.positions) == 3
        assert "AAPL" in portfolio.positions
        assert portfolio.nav == 1000000.0
