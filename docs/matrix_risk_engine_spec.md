# Matrix Risk Engine - Technical Specification

**Version**: 1.0
**Date**: 2026-01-25
**Status**: Active
**Authors**: Business Analyst Agent

---

## 1. Executive Summary

The Matrix Risk Engine is an integrated, open-source platform for quantitative research, systematic strategy design, and institutional-grade risk measurement. It combines versioned time series storage (ArcticDB), vectorized backtesting (VectorBT), portfolio optimization, and risk analytics (ORE) to deliver reproducible research and accurate risk measurement for investment management.

**Key Objectives**:
- 100% reproducible research through versioned data and point-in-time queries
- Fast backtest iteration (<60 sec for 10 years, 500 securities)
- Accurate risk measurement (VaR <15 min, Greeks <1% deviation)
- Realistic transaction cost modeling
- Institutional-grade risk reporting

**Technology Stack**:
- ORE (Open Risk Engine): Risk analytics, VaR, CVaR, Greeks, stress testing
- ArcticDB: Versioned time series storage
- VectorBT: Vectorized backtesting
- QuantStats: Performance analytics
- Python 3.10+: Runtime environment

**Deployment**: Single-user local deployment (MVP), CLI and Jupyter notebook interfaces

---

## 2. Stakeholders and Personas

### 2.1 Primary Stakeholders

**P1: Quant Analyst (Dr. Elena Markov)**
- **Goal**: Reproducible alpha signal development with statistical validation
- **Success**: 100% reproducible research, <30 min time-to-insight
- **Pain Points**: Manual data versioning, slow backtests, memory constraints

**P2: Systematic Investment Designer (Marcus Chen, CFA)**
- **Goal**: Risk-aware portfolio construction with realistic transaction costs
- **Success**: <50 bps backtest-to-live slippage, Sharpe >0.8 net of costs
- **Pain Points**: Optimization-backtest gap, oversimplified transaction costs

**P3: Risk & Simulation Specialist (Sarah Okonkwo, FRM)**
- **Goal**: Accurate daily risk measurement and stress testing
- **Success**: Daily risk report before market open, <1% Greeks deviation
- **Pain Points**: Slow risk systems, inflexible stress testing

### 2.2 Secondary Stakeholders

- Head of Quant Research: Strategy approval, research governance
- Chief Investment Officer: Portfolio oversight, risk limits
- Chief Risk Officer: Risk governance, regulatory compliance

---

## 3. Functional Requirements by Flow

### 3.1 Flow F1: Data Pipeline Flow

**Actors**: Quant Analyst, Risk Specialist
**Trigger**: New market data arrives or historical data query needed

#### Requirements

**FR-F1-001: Data Ingestion**
- System SHALL accept CSV and Parquet formats for time series data
- System SHALL validate data quality on ingestion (missing values <0.1%, outlier detection)
- System SHALL support OHLCV, fundamental, and reference data types
- System SHALL apply corporate action adjustments (splits, dividends) when configured

**FR-F1-002: Data Versioning**
- System SHALL write all data to ArcticDB with immutable version tags (format: `vYYYYMMDD_label`)
- System SHALL prevent overwriting existing versions (append-only history)
- System SHALL default to latest version when version not specified in query
- System SHALL maintain version metadata (timestamp, source, quality flags)

**FR-F1-003: Point-in-Time Queries**
- System SHALL support `as_of_date` parameter in all data queries
- System SHALL return only data with `published_date <= as_of_date`
- System SHALL apply corporate actions only if `effective_date <= as_of_date`
- System SHALL reject queries with future `as_of_date` relative to data availability

**FR-F1-004: Data Quality Validation**
- System SHALL generate data quality report with pass/fail metrics
- System SHALL flag missing data >0.1% threshold
- System SHALL flag outliers beyond 5 sigma
- System SHALL reject negative prices (except spreads/yields)
- System SHALL flag zero volume as suspicious

#### Acceptance Criteria

**AC-F1-001**: Given data version v1 is written, when version v2 is written later, then v1 data is retrievable unchanged
**AC-F1-002**: Given a query with `as_of_date=2020-06-15`, when data is retrieved, then no records with `published_date > 2020-06-15` are included
**AC-F1-003**: Given data ingestion completes, when quality report is generated, then pass/fail status for all validation gates is present

---

### 3.2 Flow F2: Backtest Flow

**Actors**: Quant Analyst, Systematic Designer
**Trigger**: User wants to test alpha signal or strategy performance

#### Requirements

**FR-F2-001: Data Loading**
- System SHALL load historical data from ArcticDB with date range filtering
- System SHALL align multiple time series on common trading calendar
- System SHALL handle missing data via forward-fill or error (configurable)

**FR-F2-002: Signal Generation**
- System SHALL accept user-defined signal logic as Python functions
- System SHALL support vectorized operations on DataFrame inputs
- System SHALL validate signal outputs (numeric, finite values)

**FR-F2-003: Backtest Configuration**
- System SHALL accept backtest parameters: universe filters, rebalancing frequency, transaction costs
- System SHALL persist backtest configuration with results for reproducibility
- System SHALL support calendar-based rebalancing (daily, weekly, monthly, quarterly)

**FR-F2-004: VectorBT Simulation**
- System SHALL execute VectorBT portfolio simulation from entry/exit signals
- System SHALL track trades, positions, and returns over backtest period
- System SHALL complete 10-year backtest for 500 securities in <60 seconds

**FR-F2-005: Transaction Cost Application**
- System SHALL apply linear transaction cost model (spread + commission)
- System SHALL deduct transaction costs from gross returns
- System SHALL track cumulative transaction costs separately

**FR-F2-006: Performance Metrics**
- System SHALL generate QuantStats tearsheet with 50+ metrics
- System SHALL include: Sharpe, Sortino, Calmar, max drawdown, win rate, profit factor
- System SHALL output tearsheet in HTML format

**FR-F2-007: Reproducibility**
- System SHALL produce identical results for identical backtest configuration and data version
- System SHALL log random seed for any stochastic elements

#### Acceptance Criteria

**AC-F2-001**: Given identical backtest configuration, when backtest is rerun, then all metrics are identical
**AC-F2-002**: Given backtest with 10 bps transaction costs, when compared to zero-cost backtest, then returns are lower by cost amount
**AC-F2-003**: Given backtest completion, when tearsheet is generated, then all 50+ metrics are present in HTML output

---

### 3.3 Flow F3: Optimization Flow

**Actors**: Systematic Designer
**Trigger**: User wants to construct optimal portfolio given alpha signals and risk model

#### Requirements

**FR-F3-001: Input Loading**
- System SHALL load alpha signals (expected returns) from data store
- System SHALL load risk model (factor covariance matrix, specific risk) from data store
- System SHALL validate risk model is positive semi-definite

**FR-F3-002: Constraint Definition**
- System SHALL support sector limit constraints (lower, upper bounds)
- System SHALL support position limit constraints (per-security bounds)
- System SHALL support turnover limit constraints (dollar or share)
- System SHALL validate constraint feasibility (lower <= upper)

**FR-F3-003: Optimization Problem Formulation**
- System SHALL formulate quadratic programming problem (max alpha - λ × risk)
- System SHALL support custom objective functions (max Sharpe, min variance, risk parity)
- System SHALL use cvxpy or scipy.optimize solvers

**FR-F3-004: Optimization Execution**
- System SHALL solve optimization within 10 seconds for 500 securities
- System SHALL return target portfolio weights OR status "infeasible"
- System SHALL NOT return "best effort" solutions if constraints violated
- System SHALL timeout after 30 seconds and fail with error

**FR-F3-005: Trade Generation**
- System SHALL generate trade list (current → target portfolio)
- System SHALL estimate transaction costs for trade list
- System SHALL validate trade list sums to zero (cash neutral) or configured net exposure

#### Acceptance Criteria

**AC-F3-001**: Given constraints (sector ≤10%, position ≤5%, turnover ≤20%), when optimization completes, then all constraints are satisfied
**AC-F3-002**: Given 500-security portfolio, when optimization executes, then solution is found within 10 seconds
**AC-F3-003**: Given trade list generation, when trades are summed, then net trade value equals zero (cash neutral) OR configured net exposure

---

### 3.4 Flow F4: Risk Measurement Flow

**Actors**: Risk Specialist
**Trigger**: Daily end-of-day risk calculation or ad-hoc risk check

#### Requirements

**FR-F4-001: Position and Market Data Loading**
- System SHALL load portfolio positions (holdings snapshot) with as_of_date
- System SHALL load market data (prices, curves, vols) from ArcticDB
- System SHALL validate market data matches position as_of_date

**FR-F4-002: Portfolio Valuation**
- System SHALL value portfolio using ORE pricing engines (NPV calculation)
- System SHALL support equities, bonds, options, and other ORE-supported instruments
- System SHALL handle missing market data via last valid price OR error (configurable)

**FR-F4-003: VaR Calculation**
- System SHALL calculate historical VaR (250-day window, 95% and 99% quantiles)
- System SHALL calculate parametric VaR (variance-covariance method)
- System SHALL complete VaR computation in <15 minutes for full portfolio

**FR-F4-004: CVaR Calculation**
- System SHALL calculate Expected Shortfall (mean of losses beyond VaR threshold)
- System SHALL enforce CVaR ≥ VaR mathematical property

**FR-F4-005: Greeks Computation**
- System SHALL compute Greeks via ORE (delta, gamma, vega for options; duration, convexity for bonds)
- System SHALL match manual calculations within 1% (spot check validation)
- System SHALL handle Greeks computation failures gracefully (log error, continue with rest)

**FR-F4-006: Risk Report Generation**
- System SHALL generate risk report with VaR, CVaR, Greeks by position
- System SHALL include aggregate metrics (portfolio-level Greeks)
- System SHALL output report in HTML or PDF format

#### Acceptance Criteria

**AC-F4-001**: Given 95% VaR calculated over backtesting period, when breaches are counted, then ~5% of observations exceed VaR
**AC-F4-002**: Given CVaR and VaR calculated, then CVaR ≥ VaR for all confidence levels
**AC-F4-003**: Given Greeks computed for known instrument, when compared to manual calculation, then deviation is <1%

---

### 3.5 Flow F5: Stress Testing Flow

**Actors**: Risk Specialist
**Trigger**: User wants to assess portfolio resilience to market shocks

#### Requirements

**FR-F5-001: Scenario Definition**
- System SHALL load stress scenarios from YAML configuration files
- System SHALL support scenario shocks (equity %, credit spread bps, vol %, FX %)
- System SHALL validate scenario completeness (all required risk factors specified)

**FR-F5-002: Shock Application**
- System SHALL apply shocks to market data (shift prices, curves, vols)
- System SHALL handle incomplete shocks via assume-unchanged OR error (configurable)

**FR-F5-003: Stressed Valuation**
- System SHALL revalue portfolio using ORE with shocked market data
- System SHALL calculate stressed P&L (shocked NPV - base NPV)
- System SHALL handle extreme shocks causing pricing failures (log error, report "N/A")

**FR-F5-004: Scenario Comparison**
- System SHALL support multiple scenarios in parallel (2008 Crisis, COVID, custom)
- System SHALL generate scenario comparison report (side-by-side P&L)
- System SHALL store scenario definitions in version-controlled YAML

**FR-F5-005: Linearity Validation**
- System SHALL validate linearity for linear instruments (20% shock P&L ≈ 2× 10% shock P&L)

#### Acceptance Criteria

**AC-F5-001**: Given multiple stress scenarios, when stress test executes, then stressed P&L is calculated for all scenarios
**AC-F5-002**: Given linear instrument with 10% and 20% shocks, when P&L is compared, then 20% shock P&L ≈ 2× 10% shock P&L (within 5% tolerance)
**AC-F5-003**: Given scenario definition in YAML, when scenario is loaded, then all risk factor shocks are parsed correctly

---

## 4. Non-Functional Requirements

### 4.1 Performance Requirements

**NFR-P-001**: VaR computation SHALL complete in <15 minutes for full portfolio (2000 securities)
**NFR-P-002**: Backtest execution SHALL complete in <60 seconds for 10 years, 500 securities
**NFR-P-003**: Data load SHALL complete in <5 seconds for 1M rows
**NFR-P-004**: Optimization solve SHALL complete in <10 seconds for 500-security portfolio
**NFR-P-005**: System SHALL operate on laptop hardware (16 GB RAM minimum, 32 GB recommended)

### 4.2 Data Integrity Requirements

**NFR-DI-001**: Point-in-time correctness SHALL be enforced (no future data in past queries)
**NFR-DI-002**: Corporate action adjustments SHALL be applied correctly (only if effective_date ≤ as_of_date)
**NFR-DI-003**: Version history SHALL be immutable (no overwrites allowed)
**NFR-DI-004**: Audit trail SHALL exist for all risk calculations (logged parameters, timestamps)

### 4.3 Security Requirements

**NFR-S-001**: API keys and credentials SHALL NOT be hardcoded in configuration files
**NFR-S-002**: Environment variables SHALL be used for sensitive configuration
**NFR-S-003**: `.env` files SHALL be excluded from git via `.gitignore`
**NFR-S-004**: Configuration and model files SHALL use file permissions (chmod 600)
**NFR-S-005**: Scenario files SHALL use integrity checks (hash validation on load)

### 4.4 Operational Requirements

**NFR-O-001**: System SHALL handle missing data gracefully (configurable: forward-fill OR error)
**NFR-O-002**: Error messages SHALL be clear and actionable
**NFR-O-003**: Configuration SHALL be file-driven (no hardcoded paths)
**NFR-O-004**: Logging SHALL use structured JSON format
**NFR-O-005**: Data retention SHALL be 90 days (archive to S3 after)

### 4.5 Regulatory/Professional Requirements

**NFR-R-001**: Risk metrics SHALL match industry standards (ISDA, Basel)
**NFR-R-002**: Greeks SHALL reconcile with front-office systems (<1% deviation)
**NFR-R-003**: VaR backtesting SHALL support validation (95% confidence = ~5% breaches)

---

## 5. Component Specifications

### 5.1 Component C1: ArcticDBAdapter

**Responsibility**: Implements `DataPort` interface for versioned time series storage

**Interface**:
```python
class DataPort(Protocol):
    def load(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        as_of_date: Optional[date] = None,
        version: Optional[str] = None
    ) -> pd.DataFrame:
        """Load time series data with optional point-in-time filtering"""

    def save(
        self,
        symbol: str,
        data: pd.DataFrame,
        version: str,
        metadata: dict
    ) -> None:
        """Save versioned time series data"""

    def query_versions(self, symbol: str) -> List[str]:
        """List available versions for symbol"""

    def validate_data_quality(self, data: pd.DataFrame) -> dict:
        """Validate data quality, return report"""
```

**Invariants**:
- Version tags are immutable once written
- Data must have monotonically increasing date index
- Quality validation runs on every write

**Dependencies**:
- `arcticdb` Python package
- Local storage or S3 backend configuration

---

### 5.2 Component C2: VectorBTAdapter

**Responsibility**: Implements `BacktestPort` interface for vectorized backtesting

**Interface**:
```python
class BacktestPort(Protocol):
    def simulate(
        self,
        signals: pd.DataFrame,
        prices: pd.DataFrame,
        transaction_costs: dict,
        rebalance_freq: str
    ) -> BacktestResult:
        """Execute backtest simulation"""

    def optimize(
        self,
        alpha: pd.Series,
        risk_model: pd.DataFrame,
        constraints: List[Constraint],
        objective: str
    ) -> Portfolio:
        """Optimize portfolio (implemented by OptimizerAdapter)"""
```

**Invariants**:
- Signals and prices must be aligned on common date index
- Transaction costs must be non-negative
- Backtest results must be deterministic for same inputs

**Dependencies**:
- `vectorbt` Python package
- pandas, numpy

---

### 5.3 Component C3: OREAdapter

**Responsibility**: Implements `RiskPort` interface for risk analytics using ORE

**Interface**:
```python
class RiskPort(Protocol):
    def calculate_var(
        self,
        portfolio: Portfolio,
        market_data: pd.DataFrame,
        method: str,  # "historical" or "parametric"
        confidence_levels: List[float],
        window_days: int
    ) -> dict:
        """Calculate VaR at specified confidence levels"""

    def calculate_cvar(
        self,
        portfolio: Portfolio,
        market_data: pd.DataFrame,
        var_params: dict
    ) -> dict:
        """Calculate Expected Shortfall"""

    def compute_greeks(
        self,
        portfolio: Portfolio,
        market_data: pd.DataFrame
    ) -> dict:
        """Compute Greeks (delta, gamma, vega, duration, convexity)"""

    def stress_test(
        self,
        portfolio: Portfolio,
        market_data: pd.DataFrame,
        scenarios: List[StressScenario]
    ) -> pd.DataFrame:
        """Apply stress scenarios and return stressed P&L"""
```

**Invariants**:
- All risk metrics must use same market data snapshot (as_of_date consistency)
- CVaR must be >= VaR for all confidence levels
- Greeks must match manual calculations within 1%

**Dependencies**:
- ORE Python bindings (ORE-SWIG)
- Market data curves and surfaces constructed from ArcticDB data

---

### 5.4 Component C4: QuantStatsAdapter

**Responsibility**: Implements `ReportPort` interface for performance analytics

**Interface**:
```python
class ReportPort(Protocol):
    def generate_report(
        self,
        returns: pd.Series,
        benchmark: Optional[pd.Series],
        template: str,
        output_path: str
    ) -> str:
        """Generate tearsheet/report in specified format"""

    def calculate_metrics(
        self,
        returns: pd.Series
    ) -> dict:
        """Calculate performance metrics"""
```

**Invariants**:
- Returns must be aligned with trading calendar
- Metrics must be derived deterministically from returns
- Output format must match template specification

**Dependencies**:
- `quantstats` Python package
- pandas

---

### 5.5 Component C5: OptimizerAdapter

**Responsibility**: Implements optimization method in `BacktestPort` interface

**Interface**:
```python
class OptimizerAdapter:
    def optimize(
        self,
        alpha: pd.Series,
        risk_model: pd.DataFrame,
        constraints: List[Constraint],
        objective: str,
        timeout: int = 30
    ) -> Portfolio:
        """Solve portfolio optimization problem"""
```

**Invariants**:
- Solution must satisfy all constraints OR return status "infeasible"
- Optimization must complete within timeout
- Risk model must be positive semi-definite

**Dependencies**:
- `cvxpy` or `scipy.optimize`
- numpy

---

### 5.6 Component C6: BacktestEngine (Domain Service)

**Responsibility**: Orchestrates backtest workflow

**Interface**:
```python
class BacktestEngine:
    def run(
        self,
        signals: pd.DataFrame,
        universe: List[str],
        rebalance_freq: str,
        transaction_costs: dict,
        data_version: str
    ) -> BacktestResult:
        """Execute complete backtest workflow"""
```

**Workflow**:
1. Load data via DataPort
2. Execute simulation via BacktestPort
3. Apply transaction costs
4. Generate result via ReportPort

**Dependencies**:
- DataPort, BacktestPort, ReportPort

---

### 5.7 Component C7: RiskCalculationService (Domain Service)

**Responsibility**: Orchestrates risk calculation workflow

**Interface**:
```python
class RiskCalculationService:
    def calculate(
        self,
        portfolio: Portfolio,
        market_data_version: str,
        methods: List[str],
        confidence_levels: List[float]
    ) -> RiskMetrics:
        """Execute complete risk calculation workflow"""
```

**Workflow**:
1. Load positions and market data via DataPort
2. Calculate risk metrics via RiskPort
3. Generate risk report via ReportPort

**Dependencies**:
- DataPort, RiskPort, ReportPort

---

### 5.8 Component C8: OptimizationService (Domain Service)

**Responsibility**: Orchestrates optimization workflow

**Interface**:
```python
class OptimizationService:
    def optimize(
        self,
        alpha: pd.Series,
        risk_model: pd.DataFrame,
        constraints: List[Constraint]
    ) -> Portfolio:
        """Execute portfolio optimization workflow"""

    def generate_trades(
        self,
        current_portfolio: Portfolio,
        target_portfolio: Portfolio
    ) -> pd.DataFrame:
        """Generate trade list from current to target"""
```

**Workflow**:
1. Load alpha signals and risk model via DataPort
2. Solve optimization via BacktestPort.optimize()
3. Generate trade list
4. Estimate transaction costs

**Dependencies**:
- DataPort, BacktestPort (OptimizerAdapter)

---

### 5.9 Component C9: StressTestingService (Domain Service)

**Responsibility**: Orchestrates stress testing workflow

**Interface**:
```python
class StressTestingService:
    def run(
        self,
        portfolio: Portfolio,
        market_data: pd.DataFrame,
        scenarios: List[StressScenario]
    ) -> pd.DataFrame:
        """Execute stress testing workflow"""
```

**Workflow**:
1. Load scenarios via FileSystemAdapter
2. Apply shocks and revalue via RiskPort
3. Generate scenario comparison report via ReportPort

**Dependencies**:
- RiskPort, ReportPort, FileSystemAdapter

---

### 5.10 Component C10: FactorAnalysisService (Domain Service)

**Responsibility**: Calculate factor returns, IC, turnover, statistical tests

**Interface**:
```python
class FactorAnalysisService:
    def calculate_ic(
        self,
        factor_scores: pd.DataFrame,
        forward_returns: pd.DataFrame
    ) -> pd.Series:
        """Calculate Information Coefficient"""

    def calculate_turnover(
        self,
        positions: pd.DataFrame
    ) -> pd.Series:
        """Calculate turnover over time"""

    def statistical_tests(
        self,
        factor_returns: pd.Series
    ) -> dict:
        """Run t-tests, p-values, Sharpe ratio"""
```

**Dependencies**:
- pandas, scipy.stats

---

## 6. Domain Object Specifications

### 6.1 DO1: TimeSeries

**Attributes**:
- `symbol: str` - Identifier (e.g., "AAPL", "SPY")
- `date_index: pd.DatetimeIndex` - Sorted, unique dates
- `values: pd.DataFrame` - OHLCV, factors, etc.
- `version: str` - Immutable tag (e.g., "v20260125_eod")
- `metadata: dict` - Source, quality flags

**Invariants**:
- `date_index` must be monotonically increasing (no duplicates)
- `version` is immutable once written (append-only history)
- `values` must align with `date_index` (no missing index entries)

**Source-of-Truth**: ArcticDB library + symbol

---

### 6.2 DO2: Portfolio

**Attributes**:
- `positions: dict[str, float]` - Symbol → shares/notional
- `weights: dict[str, float]` - Symbol → portfolio weight
- `NAV: float` - Net asset value
- `as_of_date: date` - Valuation date
- `metadata: dict` - Strategy name, rebalance ID

**Invariants**:
- `sum(weights.values()) ≈ 1.0` (or 0.0 for cash, within tolerance 1e-6)
- `NAV = sum(position_value for all positions)`
- `positions` and `weights` must reference same symbol set

**Source-of-Truth**: Portfolio state file or database record

---

### 6.3 DO3: BacktestResult

**Attributes**:
- `returns: pd.Series` - Date → portfolio return
- `trades: pd.DataFrame` - Timestamp, symbol, quantity, price, cost
- `positions: pd.DataFrame` - Date, symbol → position size
- `metrics: dict` - Sharpe, max_dd, Calmar, etc.
- `config: dict` - Backtest parameters for reproducibility

**Invariants**:
- `returns.index` aligns with trading calendar
- `trades` have valid timestamps within backtest period
- `metrics` calculated from `returns` (derived, not independent)

**Source-of-Truth**: Backtest run output (persisted to disk/DB)

---

### 6.4 DO4: RiskMetrics

**Attributes**:
- `VaR: dict[str, float]` - Confidence level → VaR value (e.g., "95%": -1.5M)
- `CVaR: dict[str, float]` - Confidence level → CVaR value
- `Greeks: dict[str, float]` - delta, gamma, vega, theta, rho, duration, convexity
- `as_of_date: date` - Valuation date
- `portfolio_id: str` - Links to Portfolio

**Invariants**:
- `CVaR[c] >= VaR[c]` for all confidence levels c
- All `Greeks` computed at same valuation point
- `as_of_date` matches market data snapshot date

**Source-of-Truth**: Risk calculation output (may be cached)

---

### 6.5 DO5: StressScenario

**Attributes**:
- `name: str` - E.g., "COVID Crash", "2008 Crisis"
- `shocks: dict[str, float]` - Risk factor → shock (e.g., "SPX": -0.40, "VIX": +2.0)
- `description: str` - Narrative, source
- `date_calibrated: date` - When scenario was defined

**Invariants**:
- `shocks` must specify all required risk factors (completeness check)
- Shock magnitudes must be reasonable (validation: abs(shock) < 5.0 for most factors)

**Source-of-Truth**: YAML configuration file (`scenarios.yaml`)

---

### 6.6 DO6: Constraint

**Attributes**:
- `type: str` - E.g., "sector_limit", "position_limit", "turnover_limit"
- `bounds: dict` - Lower, upper limits (e.g., {"lower": 0.0, "upper": 0.10})
- `securities: list[str]` - Applies to which symbols/sectors
- `name: str` - Human-readable label

**Invariants**:
- `bounds["lower"] <= bounds["upper"]` (feasibility)
- If `type == "sector_limit"`, `securities` must be valid sector identifiers
- All referenced securities must exist in universe

**Source-of-Truth**: Constraint configuration (YAML or portfolio policy doc)

---

## 7. API Contracts for Ports

### 7.1 Port P1: DataPort

**Purpose**: Abstract interface for time series data storage and retrieval

**Methods**:

```python
load(
    symbol: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    as_of_date: Optional[date] = None,
    version: Optional[str] = None
) -> pd.DataFrame
```
- **Pre-conditions**: `symbol` must exist in data store
- **Post-conditions**: Returns DataFrame with date index, optionally filtered by `as_of_date`
- **Errors**: Raises `DataNotFoundError` if symbol not found

```python
save(
    symbol: str,
    data: pd.DataFrame,
    version: str,
    metadata: dict
) -> None
```
- **Pre-conditions**: `data` must have date index, `version` must not exist for symbol
- **Post-conditions**: Data persisted with version tag, metadata stored
- **Errors**: Raises `VersionExistsError` if version already exists

---

### 7.2 Port P2: BacktestPort

**Purpose**: Abstract interface for backtesting and optimization

**Methods**:

```python
simulate(
    signals: pd.DataFrame,
    prices: pd.DataFrame,
    transaction_costs: dict,
    rebalance_freq: str
) -> BacktestResult
```
- **Pre-conditions**: `signals` and `prices` must have aligned date index
- **Post-conditions**: Returns `BacktestResult` with returns, trades, positions
- **Errors**: Raises `BacktestError` if simulation fails

```python
optimize(
    alpha: pd.Series,
    risk_model: pd.DataFrame,
    constraints: List[Constraint],
    objective: str
) -> Portfolio
```
- **Pre-conditions**: `risk_model` must be positive semi-definite
- **Post-conditions**: Returns `Portfolio` with optimal weights OR raises `InfeasibleError`
- **Errors**: Raises `OptimizationTimeoutError` if timeout exceeded

---

### 7.3 Port P3: RiskPort

**Purpose**: Abstract interface for risk analytics

**Methods**:

```python
calculate_var(
    portfolio: Portfolio,
    market_data: pd.DataFrame,
    method: str,
    confidence_levels: List[float],
    window_days: int
) -> dict
```
- **Pre-conditions**: `market_data.as_of_date == portfolio.as_of_date`
- **Post-conditions**: Returns dict with VaR values for each confidence level
- **Errors**: Raises `InsufficientDataError` if window_days > available data

```python
compute_greeks(
    portfolio: Portfolio,
    market_data: pd.DataFrame
) -> dict
```
- **Pre-conditions**: Market data contains required curves/surfaces for pricing
- **Post-conditions**: Returns dict with Greeks (delta, gamma, vega, duration, convexity)
- **Errors**: Raises `PricingError` for instruments that fail valuation

---

### 7.4 Port P4: ReportPort

**Purpose**: Abstract interface for report generation

**Methods**:

```python
generate_report(
    returns: pd.Series,
    benchmark: Optional[pd.Series],
    template: str,
    output_path: str
) -> str
```
- **Pre-conditions**: `returns` must have date index
- **Post-conditions**: Report file written to `output_path`, returns file path
- **Errors**: Raises `ReportGenerationError` if template invalid

---

## 8. Error Handling Specifications

### 8.1 Error Categories

**Data Errors**:
- `DataNotFoundError`: Requested symbol/version not found
- `VersionExistsError`: Attempted overwrite of existing version
- `DataQualityError`: Data fails quality validation gates
- `InsufficientDataError`: Not enough historical data for calculation

**Calculation Errors**:
- `BacktestError`: Backtest simulation fails
- `OptimizationTimeoutError`: Optimization exceeds timeout
- `InfeasibleError`: Optimization constraints are infeasible
- `PricingError`: Instrument valuation fails

**Configuration Errors**:
- `InvalidConfigError`: Configuration file malformed
- `MissingParameterError`: Required parameter not provided

### 8.2 Error Handling Strategy

**Fail-Fast (Reject and Error)**:
- Data quality failures (missing data >0.1%)
- Optimization infeasibility
- Market data staleness (>24 hours)
- Configuration errors

**Graceful Degradation (Log and Continue)**:
- Missing data for single instrument in portfolio (skip instrument, log warning)
- Greeks computation failure for single position (log error, continue with rest)
- Pricing failure for non-critical instrument in stress test (report "N/A")

---

## 9. Testing Requirements

### 9.1 Unit Testing

**Coverage**: Minimum 80% code coverage for all components

**Components to Test**:
- Each adapter (C1-C5): Port interface implementation
- Each domain service (C6-C10): Workflow orchestration logic
- Domain objects (DO1-DO6): Invariant enforcement

**Test Categories**:
- Happy path: Valid inputs produce expected outputs
- Error cases: Invalid inputs raise appropriate errors
- Boundary conditions: Edge cases (empty data, single observation, etc.)
- Invariant validation: Domain object invariants enforced

---

### 9.2 Integration Testing

**End-to-End Flow Tests**:
- F1: Data ingestion → versioning → point-in-time query
- F2: Data load → backtest → tearsheet generation
- F3: Alpha/risk load → optimization → trade generation
- F4: Position load → risk calculation → report generation
- F5: Scenario load → stress test → scenario comparison

**Integration Points to Test**:
- ArcticDB read/write operations
- VectorBT simulation execution
- ORE risk calculation invocation
- QuantStats report generation

---

### 9.3 Performance Testing

**Benchmarks**:
- VaR computation: <15 min for 2000 securities
- Backtest: <60 sec for 10 years, 500 securities
- Data load: <5 sec for 1M rows
- Optimization: <10 sec for 500 securities

**Test Data**:
- Synthetic portfolios: 500, 1000, 2000 securities
- Historical periods: 5 years, 10 years, 20 years
- Data frequencies: Daily (MVP), potentially monthly for long histories

---

### 9.4 Validation Testing

**Point-in-Time Correctness**:
- Test: Query data as of historical date, verify no future data included
- Method: Automated check comparing query results with manually filtered dataset

**VaR Backtesting**:
- Test: Calculate 95% VaR daily for 1 year, count breaches
- Method: Expect ~12-13 breaches (5% of 250 trading days)

**Greeks Cross-Validation**:
- Test: Compute delta for vanilla option, compare to Black-Scholes
- Method: Expect <1% deviation

---

## 10. Appendix: Data Schemas

### 10.1 ArcticDB Time Series Schema

**Symbol Naming Convention**: `{asset_class}_{identifier}` (e.g., `equity_AAPL`, `bond_US10Y`)

**DataFrame Structure**:
```
Index: DatetimeIndex (date)
Columns:
  - open: float
  - high: float
  - low: float
  - close: float
  - volume: int
  - {custom_factors}: float
```

**Metadata**:
```yaml
version: "v20260125_eod"
source: "vendor_name"
quality_flags:
  missing_pct: 0.001
  outliers_count: 3
published_date: "2026-01-25T16:00:00Z"
```

---

### 10.2 Risk Model Schema (CSV/Parquet)

**Factor Covariance Matrix**:
```
CSV Format:
factor_name, factor_1, factor_2, ..., factor_N
factor_1, cov_11, cov_12, ..., cov_1N
factor_2, cov_21, cov_22, ..., cov_2N
...
```

**Specific Risk**:
```
CSV Format:
symbol, specific_risk
AAPL, 0.015
MSFT, 0.012
...
```

---

### 10.3 Scenario Definition Schema (YAML)

```yaml
scenarios:
  - name: "2008 Financial Crisis"
    description: "Lehman Brothers collapse scenario"
    date_calibrated: "2008-09-15"
    shocks:
      SPX: -0.40       # Equity down 40%
      VIX: 2.0         # Vol up 200%
      US10Y: -0.015    # Rates down 150 bps
      USDEUR: 0.10     # USD up 10%

  - name: "COVID Crash"
    description: "March 2020 pandemic shock"
    date_calibrated: "2020-03-16"
    shocks:
      SPX: -0.35
      VIX: 1.5
      US10Y: -0.010
      CreditIG: 0.015  # IG spreads up 150 bps
```

---

**End of Specification Document**
