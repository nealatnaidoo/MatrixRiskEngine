# Matrix Risk Engine

An integrated platform for quantitative research, backtesting, and risk analytics combining ArcticDB, VectorBT, ORE (Open Risk Engine), cvxpy, and QuantStats.

## Features

- **Data Management**: Versioned, immutable time series storage with point-in-time queries
- **Factor Analysis**: IC calculation, turnover analysis, statistical significance tests
- **Backtesting**: Fast vectorized backtests with transaction costs and rebalancing
- **Risk Analytics**: VaR, CVaR, Greeks, stress testing
- **Portfolio Optimization**: Mean-variance optimization with constraints
- **Reporting**: QuantStats-powered tearsheets and reports

## Architecture

The project follows **hexagonal architecture** (ports and adapters) with domain-driven design:

```
src/
├── core/
│   ├── domain/         # Domain objects with invariant validation
│   │   ├── portfolio.py
│   │   ├── time_series.py
│   │   ├── constraint.py
│   │   ├── risk_metrics.py
│   │   └── stress_scenario.py
│   ├── ports/          # Interface definitions
│   │   ├── data_port.py
│   │   ├── backtest_port.py
│   │   ├── risk_port.py
│   │   └── optimizer_port.py
│   └── services/       # Business logic
│       ├── backtest_engine.py
│       ├── factor_analysis_service.py
│       └── risk_calculation_service.py
├── adapters/           # External system integrations
│   ├── arcticdb_adapter.py
│   ├── vectorbt_adapter.py
│   ├── ore_adapter.py
│   ├── optimizer_adapter.py
│   └── quantstats_adapter.py
└── cli/                # Command-line tools
    ├── data_loader.py
    ├── backtest_runner.py
    ├── risk_calculator.py
    └── optimizer_runner.py
```

## Installation

```bash
# Clone the repository
git clone https://github.com/your-org/matrix-risk-engine.git
cd matrix-risk-engine

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows

# Install dependencies
pip install -e ".[dev]"

# Optional: Install optimization support
pip install cvxpy

# Optional: Install QuantStats for reports
pip install quantstats
```

## Quick Start

### 1. Load Market Data

```python
from src.adapters.arcticdb_adapter import ArcticDBAdapter
import pandas as pd

# Initialize adapter
adapter = ArcticDBAdapter(uri="lmdb://./data/arctic")

# Load data from CSV
data = pd.read_csv("prices.csv", index_col=0, parse_dates=True)

# Save with version
adapter.save(
    symbol="AAPL",
    data=data,
    version="v1",
    quality_score=1.0,
)

# Load data (latest version)
prices = adapter.load(symbol="AAPL")

# Load specific version with date range
prices = adapter.load(
    symbol="AAPL",
    version="v1",
    start_date=date(2023, 1, 1),
    end_date=date(2023, 12, 31),
)
```

### 2. Run Factor Analysis

```python
from src.core.services.factor_analysis_service import FactorAnalysisService
import pandas as pd

# Create factor signals (e.g., momentum)
prices = pd.DataFrame(...)  # Your price data
momentum = prices.pct_change(20)
signals = momentum.rank(axis=1, pct=True)

# Compute forward returns
returns = prices.pct_change().shift(-1)

# Analyze factor
service = FactorAnalysisService()
result = service.analyze(
    factor_values=signals,
    returns=returns,
    holding_period=5,
)

print(f"Mean IC: {result.mean_ic:.4f}")
print(f"t-stat: {result.t_stat:.2f}")
print(f"Hit Rate: {result.hit_rate:.2%}")
```

### 3. Run a Backtest

```python
from src.core.services.backtest_engine import BacktestEngine, BacktestRequest
from src.adapters.vectorbt_adapter import VectorBTAdapter
from datetime import date

# Setup
data_adapter = ...  # Your data adapter
backtest_adapter = VectorBTAdapter()

engine = BacktestEngine(
    data_port=data_adapter,
    backtest_port=backtest_adapter,
)

# Define signal generator
def momentum_signal(prices):
    momentum = prices.pct_change(20)
    ranks = momentum.rank(axis=1, pct=True)
    weights = (ranks > 0.5).astype(float)
    return weights.div(weights.sum(axis=1), axis=0).fillna(0)

# Run backtest
request = BacktestRequest(
    universe=["AAPL", "GOOGL", "MSFT"],
    start_date=date(2022, 1, 1),
    end_date=date(2023, 12, 31),
    data_version="v1",
    signal_generator=momentum_signal,
    rebalance_freq="monthly",
    transaction_costs={"spread_bps": 5, "commission_bps": 2},
)

response = engine.run(request)
print(f"Sharpe: {response.result.sharpe_ratio:.2f}")
print(f"Return: {response.result.total_return:.2%}")
```

### 4. Calculate Risk Metrics

```python
from src.adapters.ore_adapter import OREAdapter
from src.core.domain.portfolio import Portfolio
from datetime import date

# Create portfolio
portfolio = Portfolio(
    positions={"AAPL": 500000, "GOOGL": 300000, "MSFT": 200000},
    weights={"AAPL": 0.5, "GOOGL": 0.3, "MSFT": 0.2},
    nav=1000000,
    as_of_date=date.today(),
)

# Calculate VaR
risk_adapter = OREAdapter()
var = risk_adapter.calculate_var(
    portfolio=portfolio,
    market_data=prices_df,
    method="historical",
    confidence_levels=[0.95, 0.99],
)

print(f"95% VaR: ${abs(var['95%']):,.0f}")
print(f"99% VaR: ${abs(var['99%']):,.0f}")
```

### 5. Run Stress Tests

```python
from src.core.domain.stress_scenario import StressScenario

scenarios = [
    StressScenario(
        name="Market Crash",
        shocks={"equity_all": -0.20},
        description="20% equity decline",
        date_calibrated=date.today(),
    ),
    StressScenario(
        name="Tech Selloff",
        shocks={"AAPL": -0.30, "GOOGL": -0.25},
        description="Tech sector selloff",
        date_calibrated=date.today(),
    ),
]

results = risk_adapter.stress_test(
    portfolio=portfolio,
    market_data=prices_df,
    scenarios=scenarios,
)

for _, row in results.iterrows():
    print(f"{row['scenario']}: P&L ${row['pnl']:,.0f}")
```

### 6. Optimize Portfolio

```python
from src.adapters.optimizer_adapter import OptimizerAdapter
from src.core.domain.constraint import sector_limit, position_limit

# Alpha signals (expected returns)
alpha = pd.Series({
    "AAPL": 0.15,
    "GOOGL": 0.12,
    "MSFT": 0.10,
})

# Risk model (covariance matrix)
risk_model = returns.cov() * 252

# Constraints
constraints = [
    position_limit(0.0, 0.30),  # Max 30% per position
    sector_limit("tech", 0.6, ["AAPL", "GOOGL", "MSFT"]),
]

# Optimize
optimizer = OptimizerAdapter()
portfolio = optimizer.optimize(
    alpha=alpha,
    risk_model=risk_model,
    constraints=constraints,
    objective="max_sharpe",
)

print("Optimal Weights:")
for symbol, weight in portfolio.weights.items():
    print(f"  {symbol}: {weight:.2%}")
```

## CLI Tools

### Data Loader

```bash
python -m src.cli.data_loader \
    --source prices.csv \
    --symbol AAPL \
    --version v1 \
    --uri lmdb://./data/arctic
```

### Backtest Runner

```bash
python -m src.cli.backtest_runner \
    --universe AAPL,GOOGL,MSFT \
    --start 2022-01-01 \
    --end 2023-12-31 \
    --strategy momentum \
    --rebalance monthly
```

### Risk Calculator

```bash
python -m src.cli.risk_calculator \
    --portfolio portfolio.json \
    --confidence 0.95,0.99 \
    --method historical \
    --output risk_report.json
```

### Optimizer

```bash
python -m src.cli.optimizer_runner \
    --alpha alpha_signals.csv \
    --universe AAPL,GOOGL,MSFT \
    --objective max_sharpe \
    --max-position 0.3
```

## Notebooks

Example Jupyter notebooks are provided in `notebooks/`:

- `Research.ipynb` - Factor analysis and alpha research
- `StrategyBacktest.ipynb` - Strategy backtesting workflow
- `RiskDashboard.ipynb` - Risk analytics dashboard

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test category
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/e2e/ -v
pytest tests/performance/ -v

# Run quality gates
python scripts/quality_gates.py --phase all
```

## Quality Gates

Each phase has defined acceptance criteria:

| Phase | Feature | Criteria |
|-------|---------|----------|
| 1 | Data Ingestion | Version immutability, point-in-time queries |
| 2 | Backtesting | Transaction costs, rebalancing, tearsheets |
| 3 | Risk Analytics | VaR/CVaR, Greeks, stress testing |
| 4 | Optimization | Valid weights, constraint satisfaction |

Run quality gates:

```bash
python scripts/quality_gates.py --phase all --output-dir artifacts/
```

## Performance Benchmarks

| Operation | Benchmark | Target |
|-----------|-----------|--------|
| Data Load | 1M rows | < 5 seconds |
| Backtest | 500 securities, 10 years | < 60 seconds |
| VaR Calculation | 2000 securities | < 15 minutes |
| Optimization | 500 securities | < 10 seconds |

## Project Structure

```
matrix-risk-engine/
├── src/
│   ├── core/           # Domain logic (no external dependencies)
│   ├── adapters/       # External integrations
│   └── cli/            # Command-line tools
├── tests/
│   ├── unit/           # Unit tests
│   ├── integration/    # Integration tests
│   ├── e2e/            # End-to-end tests
│   ├── performance/    # Performance benchmarks
│   └── stubs/          # Test stubs
├── notebooks/          # Jupyter notebooks
├── scripts/            # Utility scripts
└── artifacts/          # Generated artifacts
```

## Dependencies

**Core:**
- pandas >= 2.0
- numpy >= 1.24
- arcticdb >= 1.0

**Backtesting:**
- vectorbt >= 0.26

**Risk:**
- scipy >= 1.10

**Optimization (optional):**
- cvxpy >= 1.4

**Reporting (optional):**
- quantstats >= 0.0.62

## License

MIT License - see LICENSE file for details.
