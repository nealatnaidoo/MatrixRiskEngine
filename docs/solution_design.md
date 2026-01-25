# matrix_risk_engine — Solution Designer Handoff Pack

**Version**: 1.0
**Date**: 2026-01-25
**Designer**: Solution Designer Agent
**Project Slug**: matrix_risk_engine

---

## 1. Problem Statement

Investment professionals (quant analysts, portfolio managers, risk specialists) lack an integrated, open-source platform for quantitative research, systematic strategy design, and risk measurement. Current solutions are either expensive commercial products ($50K+ annual licenses) or fragmented open-source tools requiring extensive custom integration work. Users need a cohesive solution that combines versioned time series storage, vectorized backtesting, portfolio optimization, and institutional-grade risk analytics while maintaining full reproducibility and auditability.

---

## 2. Constraints & Inputs

### Explicit Constraints

**Technology Stack (MUST USE)**:
- **ORE (Open Risk Engine)**: Risk analytics, VaR, CVaR, Greeks, stress testing, XVA (Modified BSD license)
- **ArcticDB**: Versioned time series storage (BSL 1.1, free for non-production, Apache 2.0 for production use with restrictions)
- **VectorBT**: Vectorized backtesting engine (Apache 2.0 open source, Pro version optional)
- **QuantStats**: Performance analytics and tearsheet generation (Apache 2.0)
- **Pandas**: Primary data structure for time series
- **Python 3.10+**: Runtime environment

**Deployment**:
- Single-user local deployment (MVP)
- Local storage or S3-compatible storage for ArcticDB
- CLI and Jupyter notebook interfaces only (no web UI for MVP)

**Timeline**:
- MVP: 16 weeks across 4 phases (persona evaluation suggests)

**Data Constraints**:
- Daily frequency only (no intraday for MVP)
- Portfolio size: max 2000 securities
- Historical data: 20+ years, ~50M time series rows

### Implied Constraints

**Performance Requirements**:
- VaR computation: <15 minutes for full portfolio
- Backtest execution: <60 seconds for 10 years, 500 securities
- Data load: <5 seconds for 1M rows
- Optimization solve: <10 seconds for 500-security portfolio

**Data Integrity**:
- Point-in-time correctness to avoid look-ahead bias
- Corporate action adjustments must be applied correctly
- Immutable version history for reproducibility
- Audit trail for all risk calculations

**Operational**:
- Memory efficient (laptop-deployable, not just server-grade hardware)
- Graceful degradation when data missing
- Clear error messages for validation failures
- No hardcoded data paths (configuration-driven)

**Regulatory/Professional**:
- Risk metrics must match industry standards (ISDA, Basel)
- Greeks must reconcile with front-office systems
- VaR backtesting must support validation (95% confidence = ~5% breaches)

---

## 3. Personas & Roles

### P1: Quant Analyst (Dr. Elena Markov)
**Goal**: Build reproducible alpha signals with statistical validation
**Daily Task**: Factor research, backtest iteration, model validation
**Success**: 100% reproducible research, <30 min time-to-insight

### P2: Systematic Investment Designer (Marcus Chen, CFA)
**Goal**: Construct risk-aware portfolios with realistic transaction costs
**Daily Task**: Portfolio optimization, walk-forward testing, capacity analysis
**Success**: <50 bps backtest-to-live slippage, Sharpe >0.8 net of costs

### P3: Risk & Simulation Specialist (Sarah Okonkwo, FRM)
**Goal**: Accurate daily risk measurement and stress testing
**Daily Task**: VaR/CVaR calculation, Greeks computation, stress scenarios
**Success**: Daily risk report before market open, <1% Greeks deviation vs front office

---

## 4. In Scope / Out of Scope

### IN SCOPE (MVP)

**Data Management**:
- Versioned time series storage using ArcticDB
- Point-in-time data queries (as-of-date filtering)
- Data quality validation gates
- Corporate action adjustments
- Data versioning and snapshot management

**Backtesting**:
- Vectorized backtesting via VectorBT
- Transaction cost modeling (linear: spread + commission)
- Performance tearsheet generation via QuantStats
- Factor analysis toolkit (IC, t-stats, turnover)
- Walk-forward optimization testing

**Portfolio Construction**:
- Mean-variance optimization (quadratic programming)
- Linear constraint specification (sector, position, factor exposure limits)
- Risk budgeting frameworks
- Rebalancing simulation

**Risk Analytics**:
- Historical VaR (95%, 99%)
- Parametric VaR (variance-covariance)
- Expected Shortfall (CVaR)
- Greeks computation (delta, gamma, vega, duration, convexity)
- Stress testing framework with custom scenarios
- Risk attribution (factor vs idiosyncratic)
- Component VaR

**Reporting**:
- Performance tearsheets (50+ metrics)
- Daily risk dashboards
- Backtest summary reports

### OUT OF SCOPE (MVP)

**Not in MVP** (defer to post-MVP):
- Real-time/intraday data feeds
- Live trading execution
- Order management system (OMS)
- Multi-user collaboration features
- Web-based UI
- Regulatory reporting (UCITS, AIFMD)
- Monte Carlo simulation engine (full revaluation)
- Reverse stress testing
- Model registry/versioning (MLflow-style)
- Capacity estimation analytics
- Attribution beyond simple factor decomposition

**Never** (anti-goals):
- Commercial data feed integrations (users supply own data)
- Exotic derivatives pricing (use ORE directly for that)
- Credit risk capital calculations (FRTB, SA-CCR beyond ORE's built-in)
- Multi-tenancy
- Real-time collaboration

---

## 5. Core User Flows

### F1: Data Pipeline Flow
**Actors**: Quant Analyst, Risk Specialist
**Trigger**: New market data arrives or user queries historical data

**Happy Path**:
1. User ingests raw CSV/Parquet data (OHLCV, fundamentals, reference data)
2. System validates data quality (missing values <0.1%, outlier detection)
3. System applies corporate actions (splits, dividends) if configured
4. System writes to ArcticDB with version tag (e.g., "v20260125_eod")
5. User queries data with as-of-date filter (e.g., "give me all factor data as of 2020-06-15")
6. System returns only data available as of that timestamp (point-in-time correct)

**Edge Cases**:
- Missing data for requested symbols → return partial result + warning log
- Stale version requested → retrieve from versioned snapshot
- Concurrent writes → ArcticDB handles with optimistic locking

**State Transitions**:
- Raw Data → Validated → Versioned → Query-Ready

**Acceptance**:
- Version v1 data retrievable even after v2 written (immutable)
- Point-in-time query excludes data published after as-of-date
- Data quality report generated with pass/fail metrics

### F2: Backtest Flow
**Actors**: Quant Analyst, Systematic Designer
**Trigger**: User wants to test alpha signal or strategy performance

**Happy Path**:
1. User loads historical data (prices, factors) from ArcticDB
2. User defines signal generation logic (e.g., momentum = 12-month return - 1-month return)
3. User configures backtest parameters (universe filters, rebalancing frequency, transaction costs)
4. System executes VectorBT simulation (entry/exit signals → trades → positions → returns)
5. System applies transaction costs (e.g., 10 bps per trade)
6. System generates QuantStats tearsheet with metrics (Sharpe, max drawdown, Calmar ratio, etc.)
7. User reviews tearsheet and trades log

**Edge Cases**:
- Signal produces no trades → backtest completes with zero returns
- Portfolio exceeds constraint (e.g., sector limit) → constraint enforcement logs violation
- Data missing mid-backtest → forward-fill last valid value OR halt with error (configurable)

**State Transitions**:
- Raw Signal → Backtest Config → Simulated Trades → Performance Metrics → Tearsheet

**Acceptance**:
- Backtest with zero transaction costs → returns higher than with costs
- Rerun identical backtest → identical results (reproducibility)
- Tearsheet contains 50+ metrics (Sharpe, Sortino, Omega, tail ratio, etc.)

### F3: Optimization Flow
**Actors**: Systematic Designer
**Trigger**: User wants to construct optimal portfolio given alpha signals and risk model

**Happy Path**:
1. User loads alpha signals (expected returns) from research
2. User loads risk model (factor covariance matrix, specific risk)
3. User defines constraints (sector limits: 10%, position limits: 5%, turnover: 20%)
4. System formulates quadratic programming problem (max alpha - λ × risk)
5. System solves optimization (cvxpy or scipy.optimize)
6. System returns target portfolio weights
7. User generates trade list (current → target)
8. System estimates transaction costs for trade list

**Edge Cases**:
- Infeasible constraints → solver returns status, user relaxes constraints
- Risk model not positive semi-definite → apply shrinkage or reject
- Optimization timeout (>10 sec) → return partial solution or fail

**State Transitions**:
- Alpha Signals + Risk Model + Constraints → Optimization Problem → Target Weights → Trade List

**Acceptance**:
- All constraints satisfied in solution (sector ≤10%, position ≤5%, turnover ≤20%)
- Solution found within 10 seconds for 500 securities
- Trade list sums to zero (cash neutral or fully invested as configured)

### F4: Risk Measurement Flow
**Actors**: Risk Specialist
**Trigger**: Daily end-of-day risk calculation or ad-hoc risk check

**Happy Path**:
1. User loads portfolio positions (holdings snapshot)
2. User loads market data (prices, curves, vols) from ArcticDB
3. System values portfolio using ORE pricing engines (NPV calculation)
4. System calculates VaR (historical: 250-day window, 95% and 99% quantiles)
5. System calculates CVaR (mean of losses beyond VaR threshold)
6. System computes Greeks via ORE (delta, gamma, vega for options; duration, convexity for bonds)
7. System generates risk report (VaR, CVaR, Greeks by position, aggregate metrics)

**Edge Cases**:
- Missing market data for instrument → use last valid price OR fail (configurable)
- VaR breach (actual loss exceeds VaR) → flag for investigation
- Greeks computation fails for instrument → log error, continue with rest

**State Transitions**:
- Positions + Market Data → Valuation → Risk Metrics → Risk Report

**Acceptance**:
- VaR 95% breached ~5% of time over backtesting period (validation)
- CVaR ≥ VaR always (mathematical property)
- Greeks match manual calculation within 1% (spot check)

### F5: Stress Testing Flow
**Actors**: Risk Specialist
**Trigger**: User wants to assess portfolio resilience to market shocks

**Happy Path**:
1. User defines stress scenario (e.g., "2008 Crisis": equity -40%, credit spreads +300 bps, VIX +200%)
2. System applies shocks to market data (shift prices, curves, vols)
3. System revalues portfolio using ORE with shocked market data
4. System calculates stressed P&L (shocked NPV - base NPV)
5. System generates scenario comparison report (multiple scenarios side-by-side)

**Edge Cases**:
- Scenario specifies incomplete shocks (e.g., missing FX rates) → assume unchanged OR fail
- Extreme shock causes pricing failure → log error, report as "N/A"
- Multiple scenarios → parallelize computation if possible

**State Transitions**:
- Base Portfolio + Scenarios → Shocked Market Data → Stressed Valuation → Stressed P&L → Scenario Report

**Acceptance**:
- Stressed P&L calculated for all scenarios
- Linearity check: 20% shock P&L ≈ 2× 10% shock P&L (for linear instruments)
- Scenario definitions stored in YAML (human-readable, version-controlled)

---

## 6. Key Domain Objects

### DO1: TimeSeries
**Attributes**:
- `symbol: str` (identifier, e.g., "AAPL", "SPY")
- `date_index: DatetimeIndex` (sorted, unique dates)
- `values: DataFrame` (OHLCV, factors, etc.)
- `version: str` (immutable tag, e.g., "v20260125_eod")
- `metadata: dict` (source, quality flags)

**Invariants**:
- `date_index` must be monotonically increasing (no duplicates)
- `version` is immutable once written (append-only history)
- `values` must align with `date_index` (no missing index entries)

**Source-of-Truth**: ArcticDB library + symbol

### DO2: Portfolio
**Attributes**:
- `positions: dict[str, float]` (symbol → shares/notional)
- `weights: dict[str, float]` (symbol → portfolio weight)
- `NAV: float` (net asset value)
- `as_of_date: date` (valuation date)
- `metadata: dict` (strategy name, rebalance ID)

**Invariants**:
- `sum(weights.values()) ≈ 1.0` (or 0.0 for cash, within tolerance 1e-6)
- `NAV = sum(position_value for all positions)`
- `positions` and `weights` must reference same symbol set

**Source-of-Truth**: Portfolio state file or database record

### DO3: BacktestResult
**Attributes**:
- `returns: Series` (date → portfolio return)
- `trades: DataFrame` (timestamp, symbol, quantity, price, cost)
- `positions: DataFrame` (date, symbol → position size)
- `metrics: dict` (Sharpe, max_dd, Calmar, etc.)
- `config: dict` (backtest parameters for reproducibility)

**Invariants**:
- `returns.index` aligns with trading calendar (no weekends/holidays unless configured)
- `trades` have valid timestamps within backtest period
- `metrics` calculated from `returns` (derived, not independent)

**Source-of-Truth**: Backtest run output (persisted to disk/DB)

### DO4: RiskMetrics
**Attributes**:
- `VaR: dict[str, float]` (confidence level → VaR value, e.g., "95%": -1.5M)
- `CVaR: dict[str, float]` (confidence level → CVaR value)
- `Greeks: dict[str, float]` (delta, gamma, vega, theta, rho, duration, convexity)
- `as_of_date: date` (valuation date)
- `portfolio_id: str` (links to Portfolio)

**Invariants**:
- `CVaR[c] >= VaR[c]` for all confidence levels c (tail risk property)
- All `Greeks` computed at same valuation point (consistent market data)
- `as_of_date` matches market data snapshot date

**Source-of-Truth**: Risk calculation output (may be cached)

### DO5: StressScenario
**Attributes**:
- `name: str` (e.g., "COVID Crash", "2008 Crisis")
- `shocks: dict[str, float]` (risk factor → shock, e.g., "SPX": -0.40, "VIX": +2.0)
- `description: str` (narrative, source)
- `date_calibrated: date` (when scenario was defined)

**Invariants**:
- `shocks` must specify all required risk factors (completeness check)
- Shock magnitudes must be reasonable (validation: abs(shock) < 5.0 for most factors)

**Source-of-Truth**: YAML configuration file (`scenarios.yaml`)

### DO6: Constraint
**Attributes**:
- `type: str` (e.g., "sector_limit", "position_limit", "turnover_limit")
- `bounds: dict` (lower, upper limits, e.g., {"lower": 0.0, "upper": 0.10})
- `securities: list[str]` (applies to which symbols/sectors)
- `name: str` (human-readable label)

**Invariants**:
- `bounds["lower"] <= bounds["upper"]` (feasibility)
- If `type == "sector_limit"`, `securities` must be valid sector identifiers
- All referenced securities must exist in universe

**Source-of-Truth**: Constraint configuration (YAML or portfolio policy doc)

---

## 7. Policy & Rules Candidates

**PR1: Data Versioning Policy**
- All writes to ArcticDB MUST include version tag (format: `vYYYYMMDD_label`)
- Version tags are immutable (no overwrites allowed)
- Queries without version → default to latest version
- Retention policy: keep all versions for 90 days, archive older snapshots to S3

**PR2: Point-in-Time Correctness**
- Data queries with `as_of_date` MUST filter out records with `published_date > as_of_date`
- Corporate actions applied only if effective_date ≤ as_of_date
- NO forward-looking data allowed in backtests (validation gate)

**PR3: Transaction Cost Modeling**
- Default: linear model (spread + commission)
- Spread: user-configurable (default 10 bps)
- Commission: flat per trade OR percentage (default 5 bps)
- Market impact: OUT OF SCOPE for MVP (defer to post-MVP)

**PR4: Risk Calculation Consistency**
- All risk metrics (VaR, CVaR, Greeks) calculated using same market data snapshot
- Valuation date must match market data as_of_date
- Mismatch → reject calculation with error

**PR5: Optimization Constraint Enforcement**
- Solver MUST return feasible solution (all constraints satisfied) OR status "infeasible"
- No "best effort" solutions (partial constraint satisfaction not allowed)
- Timeout: 30 seconds, then fail (user can relax constraints)

**PR6: Data Quality Gates**
- Missing data threshold: <0.1% of expected records
- Outlier detection: values beyond 5 sigma flagged for review
- Negative prices rejected (except spreads/yields)
- Volume = 0 flagged as suspicious

**PR7: Backtest Reproducibility**
- Backtest config (universe, parameters, costs) persisted with results
- Same config + same data version → identical results (deterministic)
- Random seed specified for any stochastic elements (e.g., Monte Carlo, if added)

---

## 8. Architecture Proposal (Hexagonal/Atomic)

### Component Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                    CORE DOMAIN                                 │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐      │
│  │ Portfolio   │  │ TimeSeries   │  │ BacktestResult  │      │
│  │ RiskMetrics │  │ Constraint   │  │ StressScenario  │      │
│  └─────────────┘  └──────────────┘  └─────────────────┘      │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │            DOMAIN SERVICES                              │  │
│  │  - PortfolioValuationService                           │  │
│  │  - BacktestEngine                                      │  │
│  │  - OptimizationService                                 │  │
│  │  - RiskCalculationService                              │  │
│  │  - StressTestingService                                │  │
│  │  - FactorAnalysisService                               │  │
│  └─────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
                              ▲
                              │ depends on (ports)
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                        PORTS (Interfaces)                      │
│  ┌──────────────┐  ┌─────────────┐  ┌────────────────────┐   │
│  │ DataPort     │  │ BacktestPort│  │ RiskPort           │   │
│  │ - load()     │  │ - simulate()│  │ - calculate_var()  │   │
│  │ - save()     │  │ - optimize()│  │ - compute_greeks() │   │
│  │ - query()    │  │             │  │ - stress_test()    │   │
│  └──────────────┘  └─────────────┘  └────────────────────┘   │
│  ┌────────────────────┐                                       │
│  │ ReportPort         │                                       │
│  │ - generate_report()│                                       │
│  └────────────────────┘                                       │
└────────────────────────────────────────────────────────────────┘
                              ▲
                              │ implements
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                    ADAPTERS (Infrastructure)                   │
│  ┌────────────────────┐  ┌─────────────────────────────┐     │
│  │ ArcticDBAdapter    │  │ OREAdapter                  │     │
│  │ - implements       │  │ - implements RiskPort       │     │
│  │   DataPort         │  │ - wraps ORE Python bindings │     │
│  │ - manages versions │  │ - pricing engines           │     │
│  │ - point-in-time    │  │ - Greeks calculation        │     │
│  │   queries          │  │ - stress scenario execution │     │
│  └────────────────────┘  └─────────────────────────────┘     │
│  ┌────────────────────┐  ┌─────────────────────────────┐     │
│  │ VectorBTAdapter    │  │ QuantStatsAdapter           │     │
│  │ - implements       │  │ - implements ReportPort     │     │
│  │   BacktestPort     │  │ - tearsheet generation      │     │
│  │ - signal execution │  │ - metrics calculation       │     │
│  │ - position mgmt    │  │                             │     │
│  └────────────────────┘  └─────────────────────────────┘     │
│  ┌────────────────────┐  ┌─────────────────────────────┐     │
│  │ OptimizerAdapter   │  │ FileSystemAdapter           │     │
│  │ - implements       │  │ - config loading (YAML)     │     │
│  │   BacktestPort     │  │ - result persistence        │     │
│  │ - cvxpy wrapper    │  │                             │     │
│  └────────────────────┘  └─────────────────────────────┘     │
└────────────────────────────────────────────────────────────────┘
                              ▲
                              │ uses
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                   APPLICATION LAYER                            │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ CLI Commands                                            │  │
│  │  - backtest_runner.py                                   │  │
│  │  - risk_calculator.py                                   │  │
│  │  - optimizer_runner.py                                  │  │
│  │  - data_loader.py                                       │  │
│  └─────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ Jupyter Notebooks                                       │  │
│  │  - Research.ipynb                                       │  │
│  │  - RiskDashboard.ipynb                                  │  │
│  │  - StrategyBacktest.ipynb                               │  │
│  └─────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

**C1: ArcticDBAdapter**
- Implements `DataPort` interface
- Manages versioned time series storage
- Handles point-in-time queries (as-of-date filtering)
- Data quality validation on write
- Snapshot/version management

**C2: VectorBTAdapter**
- Implements `BacktestPort` interface
- Wraps VectorBT Portfolio simulation
- Signal-to-trade execution logic
- Transaction cost application
- Performance metrics extraction

**C3: OREAdapter**
- Implements `RiskPort` interface
- Wraps ORE Python bindings (ORE-SWIG)
- Portfolio valuation (NPV)
- VaR/CVaR calculation (historical, parametric)
- Greeks computation (delta, gamma, vega, duration, convexity)
- Stress scenario execution
- Market data loading for ORE pricing engines

**C4: QuantStatsAdapter**
- Implements `ReportPort` interface
- Generates tearsheets (HTML/PDF)
- Calculates 50+ performance metrics
- Return series visualization

**C5: OptimizerAdapter**
- Implements `BacktestPort.optimize()` method
- Wraps cvxpy or scipy.optimize
- Formulates QP problem (mean-variance)
- Constraint enforcement
- Solution extraction

**C6: BacktestEngine (Domain Service)**
- Orchestrates backtest workflow
- Loads data via DataPort
- Executes simulation via BacktestPort
- Applies transaction costs
- Generates result via ReportPort

**C7: RiskCalculationService (Domain Service)**
- Orchestrates risk workflow
- Loads positions and market data via DataPort
- Calculates risk metrics via RiskPort
- Generates risk report via ReportPort

**C8: OptimizationService (Domain Service)**
- Orchestrates optimization workflow
- Loads alpha signals and risk model via DataPort
- Solves optimization via BacktestPort.optimize()
- Generates trade list

**C9: StressTestingService (Domain Service)**
- Orchestrates stress testing workflow
- Loads scenarios via FileSystemAdapter
- Applies shocks and revalues via RiskPort
- Generates scenario comparison report via ReportPort

**C10: FactorAnalysisService (Domain Service)**
- Calculates factor returns
- Information Coefficient (IC)
- Turnover analysis
- Statistical significance tests (t-stats, p-values)

### Data Stores & Source-of-Truth

**DS1: ArcticDB Time Series Library**
- Purpose: Versioned storage for all time series data (prices, factors, fundamentals)
- Technology: ArcticDB with local storage or S3 backend
- Schema: symbol → DataFrame with versioned snapshots
- Access: Via ArcticDBAdapter

**DS2: Configuration Files (YAML)**
- Purpose: Scenarios, constraints, backtest configs, risk model parameters
- Technology: YAML files in `config/` directory
- Schema: Structured YAML per domain (scenarios.yaml, constraints.yaml, etc.)
- Access: Via FileSystemAdapter

**DS3: Result Store (Parquet/CSV)**
- Purpose: Backtest results, risk reports, tearsheets
- Technology: Parquet files for structured data, CSV for tabular exports, HTML for tearsheets
- Schema: Per-result-type (backtest_results/, risk_reports/, tearsheets/)
- Access: Via FileSystemAdapter

**DS4: ORE Market Data (In-Memory)**
- Purpose: Yield curves, vol surfaces, pricing engine calibration
- Technology: ORE internal data structures (not persisted by Matrix, loaded per-session)
- Access: Via OREAdapter (constructed from ArcticDB data)

### Integration Points

**I1: ArcticDB Integration**
- Python API: `arcticdb` package
- Versioning: `library.write(symbol, data, metadata={'version': 'v20260125'})`
- Point-in-time: `library.read(symbol, as_of=timestamp)`
- Data format: pandas DataFrame

**I2: ORE Integration**
- Python API: `ORE` package (ORE-SWIG bindings)
- Pricing: `ore.OREApp(inputParams, logFile)` → `ore_app.run(market_data, fixings_data)`
- Greeks: Computed via ORE pricing engines, extracted from reports
- Stress: Apply shocks to market data, revalue portfolio
- Configuration: XML files for market config, pricing engines, portfolios (generated programmatically)

**I3: VectorBT Integration**
- Python API: `vectorbt` package
- Simulation: `vbt.Portfolio.from_signals(close, entries, exits)` → `portfolio.returns()`
- Transaction costs: `slippage` and `fees` parameters
- Metrics: `portfolio.stats()` dictionary

**I4: QuantStats Integration**
- Python API: `quantstats` package
- Tearsheet: `quantstats.reports.html(returns, benchmark)` → HTML file
- Metrics: `quantstats.stats.sharpe(returns)`, `quantstats.stats.max_drawdown(returns)`, etc.

---

## 9. Security & Privacy Threat Pass

### T1: Data Leakage via Misconfigured Versioning
**Threat**: User accidentally exposes future data in point-in-time queries
**Impact**: Look-ahead bias → overestimated backtest performance → production losses
**Control**: CTRL1 - Automated validation gate checks all queries for `as_of_date` compliance

### T2: API Key Exposure in Configuration Files
**Threat**: Data source API keys (e.g., S3 credentials) hardcoded in YAML or notebooks
**Impact**: Unauthorized data access, financial loss
**Control**: CTRL2 - Environment variable injection, never commit credentials to git, use `.gitignore` for `.env` files

### T3: Stale Price Causing Incorrect Valuations
**Threat**: Missing market data update → risk calculations use outdated prices
**Impact**: Incorrect VaR → undetected risk breaches → regulatory violations
**Control**: CTRL3 - Data freshness validation (max age: 24 hours for daily data), alert if stale

### T4: Survivorship Bias in Historical Data
**Threat**: Backtest universe excludes delisted/bankrupt companies
**Impact**: Overestimated strategy performance (survivor bias)
**Control**: CTRL4 - Require "point-in-time universe" (companies listed as of each rebalance date), validation gate

### T5: Unauthorized Access to Proprietary Models
**Threat**: Single-user deployment on shared machine → other users access model code/data
**Impact**: IP theft, competitive disadvantage
**Control**: CTRL5 - File system permissions (chmod 600 for config/model files), user-specific home directories

### T6: Malicious Scenario Injection
**Threat**: Attacker modifies `scenarios.yaml` to produce misleading stress test results
**Impact**: False sense of security → unhedged risk exposure
**Control**: CTRL6 - File integrity checks (hash scenarios.yaml at load time, compare to known-good hash)

### T7: Unbounded ArcticDB Storage Growth
**Threat**: Versioning without cleanup → disk fills up → system failure
**Impact**: Service outage, data loss if writes fail
**Control**: CTRL7 - Retention policy (90-day rolling window), automated archive to S3, disk usage monitoring

### T8: Optimization Solver Manipulation
**Threat**: Malicious constraint file causes solver to produce extreme portfolios (e.g., 100% in one stock)
**Impact**: Concentration risk, portfolio blowup
**Control**: CTRL8 - Post-optimization validation (check position limits, sector limits), reject if invalid

### T9: Greeks Mismatch Leading to Hedge Errors
**Threat**: ORE Greeks differ from trading desk Greeks → incorrect hedge ratios
**Impact**: Hedge fails, unexpected P&L
**Control**: CTRL9 - Cross-validation against known benchmarks (e.g., Black-Scholes for vanilla options), <1% tolerance

### T10: Jupyter Notebook Code Injection
**Threat**: Malicious notebook cell executes arbitrary code
**Impact**: System compromise, data exfiltration
**Control**: CTRL10 - Notebook security: disable auto-execute, code review for shared notebooks, sandboxed execution environment

---

## 10. Operational Reality

### Deployment Model
- **MVP**: Single-user local installation (laptop or desktop)
- **Environment**: Python 3.10+ virtualenv or conda environment
- **Storage**: Local filesystem for ArcticDB (expandable to S3)
- **Compute**: Local CPU (no GPU required for MVP)
- **Interface**: CLI scripts + Jupyter notebooks

### Resource Requirements
- **RAM**: 16 GB minimum (32 GB recommended for large backtests)
- **Disk**: 100 GB for ArcticDB storage (scales with data volume)
- **CPU**: 4+ cores (parallelization for backtests, optimization)

### Scaling Considerations
- **Data Volume**: ArcticDB handles billions of rows; MVP targets ~50M rows
- **Backtest Speed**: VectorBT vectorization → 10 years in <60 sec (meets target)
- **Risk Calculation**: ORE historical VaR → 250-day window, 2000 securities → <15 min (meets target)
- **Optimization**: cvxpy with OSQP solver → 500 securities in <10 sec (meets target)

### Failure Modes & Recovery
1. **Data load failure (missing file)**: Graceful degradation → skip missing symbols, log warning
2. **Backtest timeout**: Configurable timeout (default 5 min), partial results returned
3. **Optimization infeasible**: Return status "infeasible", log constraint conflicts, suggest relaxation
4. **ORE pricing failure**: Skip failing instrument, log error, continue with rest
5. **Disk full (ArcticDB)**: Pre-emptive check (if <10% free, alert), write fails gracefully

### Monitoring & Observability
- **Logging**: Python `logging` module, structured logs (JSON format)
- **Metrics**: Execution time, data quality scores, backtest count, VaR breach count
- **Alerts**: Disk usage >90%, data staleness >24h, VaR breaches >10% of expected

### Maintenance Windows
- **Data refresh**: Daily (after market close, before next open)
- **Version cleanup**: Weekly (archive old snapshots to S3)
- **Dependency updates**: Monthly (security patches), quarterly (feature updates)

---

## 11. Gotchas & Ambiguities

### G1: Corporate Action Handling
**Ambiguity**: Should splits/dividends be applied before or after point-in-time query?
**Recommendation**: Apply corporate actions AFTER point-in-time filtering (only actions known as of that date)
**Rationale**: Avoids look-ahead bias (future split shouldn't affect past prices in backtest)

### G2: Transaction Cost Model Choice
**Ambiguity**: Linear vs market impact (square-root law, Almgren-Chriss)?
**Recommendation**: MVP uses linear (spread + commission), defer market impact to post-MVP
**Rationale**: Linear is deterministic and fast; market impact requires calibration data (ADV, spread estimates)

### G3: Risk Model Source
**Ambiguity**: Use commercial risk model (Barra, Axioma) or custom factor model?
**Recommendation**: MVP allows user-supplied covariance matrix (CSV/Parquet), no built-in risk model
**Rationale**: Commercial models require licenses ($); custom models are user's responsibility

### G4: Constraint Relaxation Strategy
**Ambiguity**: When optimization infeasible, which constraints to relax automatically?
**Recommendation**: No automatic relaxation; user must manually adjust constraints
**Rationale**: Constraint relaxation is investment policy decision (can't be automated safely)

### G5: VaR Method Selection
**Ambiguity**: Historical vs parametric vs Monte Carlo VaR?
**Recommendation**: MVP supports historical and parametric; Monte Carlo deferred to post-MVP
**Rationale**: Monte Carlo requires full revaluation (slow), historical/parametric sufficient for MVP

### G6: Benchmark Selection for Tearsheets
**Ambiguity**: What benchmark to use for Sharpe ratio, alpha calculation?
**Recommendation**: User-specified benchmark (e.g., SPY for equity long-only), default to risk-free rate if not provided
**Rationale**: Benchmark is strategy-specific (can't auto-detect)

### G7: Rebalancing Trigger Logic
**Ambiguity**: Rebalance on calendar schedule OR when portfolio drifts beyond threshold?
**Recommendation**: MVP supports calendar rebalancing only (monthly, quarterly); drift-based deferred
**Rationale**: Drift-based requires continuous monitoring (more complex)

### G8: Greeks Computation Instrument Coverage
**Ambiguity**: Compute Greeks for all instruments or only derivatives?
**Recommendation**: Compute Greeks for all instruments supported by ORE; stocks get delta=shares, duration=0
**Rationale**: Consistency (all positions have Greeks), simplifies aggregation

### G9: Data Quality Validation Scope
**Ambiguity**: Validate on write only OR also on read?
**Recommendation**: Validate on write (reject bad data), skip validation on read (trust stored data)
**Rationale**: Write-time validation prevents garbage in; read-time validation is redundant overhead

### G10: ORE Configuration Generation
**Ambiguity**: User writes XML manually OR system generates XML from high-level config?
**Recommendation**: System generates ORE XML from YAML/Python config (user never sees XML)
**Rationale**: XML is verbose and error-prone; abstraction improves usability

---

## 12. Illustrative Examples

### Example 1: Momentum Backtest
```python
# Load data
data = arcticdb_adapter.load("prices", symbols=["SPY", "QQQ", "IWM"],
                              start_date="2010-01-01", end_date="2023-12-31")

# Calculate momentum signal (12-month return)
signals = data.pct_change(252)  # 12-month return

# Run backtest
backtest = backtest_engine.run(
    signals=signals,
    universe=["SPY", "QQQ", "IWM"],
    rebalance_freq="monthly",
    transaction_costs={"spread_bps": 10, "commission_bps": 5}
)

# Generate tearsheet
tearsheet = quantstats_adapter.generate_report(backtest.returns, benchmark="SPY")
# Output: momentum_tearsheet_20260125.html
```

### Example 2: Mean-Variance Optimization
```python
# Load alpha signals (expected returns)
alpha = data_port.load("alpha_signals", as_of_date="2026-01-24")

# Load risk model (factor covariance)
risk_model = data_port.load("risk_model", as_of_date="2026-01-24")

# Define constraints
constraints = [
    Constraint(type="sector_limit", bounds={"lower": 0.0, "upper": 0.10}, securities=["Technology"]),
    Constraint(type="position_limit", bounds={"lower": -0.05, "upper": 0.05}, securities=["all"]),
    Constraint(type="turnover_limit", bounds={"lower": 0.0, "upper": 0.20}, securities=["all"])
]

# Solve optimization
target_portfolio = optimization_service.optimize(
    alpha=alpha,
    risk_model=risk_model,
    constraints=constraints,
    objective="max_sharpe"
)

# Generate trade list
trades = portfolio_service.generate_trades(current_portfolio, target_portfolio)
# Output: trades.csv (symbol, quantity, estimated_cost)
```

### Example 3: Daily VaR Calculation
```python
# Load portfolio positions
portfolio = data_port.load("portfolio", portfolio_id="main_fund", as_of_date="2026-01-24")

# Load market data
market_data = arcticdb_adapter.load("market_data", as_of_date="2026-01-24")

# Calculate VaR
risk_metrics = risk_calculation_service.calculate(
    portfolio=portfolio,
    market_data=market_data,
    methods=["historical_var", "parametric_var"],
    confidence_levels=[0.95, 0.99],
    window_days=250
)

# Generate risk report
report = quantstats_adapter.generate_report(risk_metrics, template="daily_risk")
# Output: risk_report_20260124.pdf (VaR, CVaR, Greeks, component VaR)
```

### Example 4: Stress Testing
```python
# Load stress scenarios
scenarios = filesystem_adapter.load("config/scenarios.yaml")

# Apply stress test
stressed_portfolios = stress_testing_service.run(
    portfolio=portfolio,
    market_data=market_data,
    scenarios=scenarios["crisis_scenarios"]  # 2008, COVID, etc.
)

# Generate scenario comparison
comparison = report_port.generate_report(
    stressed_portfolios,
    template="scenario_comparison"
)
# Output: stress_test_20260124.html (table with base vs stressed P&L for each scenario)
```

---

## 13. Open Questions (Blocking Only)

### Q1: ORE Python Bindings Completeness
**Question**: Do ORE-SWIG bindings support all required analytics (VaR, CVaR, Greeks)?
**Impact**: If missing, need to call ORE via subprocess (slower, less integrated)
**Research Needed**: Review ORE-SWIG test suite and examples
**Recommendation**: Prototype ORE integration in Phase 1 (risk analytics phase)

### Q2: ArcticDB License for Production Use
**Question**: BSL 1.1 restricts production use without license; does this affect MVP?
**Impact**: If MVP is used for "production research" (live trading decisions), may need Apache 2.0 license
**Research Needed**: Clarify with user whether MVP will inform live trading OR pure research
**Recommendation**: Assume research-only for MVP; revisit licensing for production deployment

### Q3: VectorBT Pro vs Open Source
**Question**: Does MVP require VectorBT Pro features (advanced portfolio construction)?
**Impact**: Pro version is paid ($); open source may suffice for basic backtesting
**Research Needed**: Compare feature sets, identify must-haves
**Recommendation**: Start with open source; upgrade to Pro if needed (Phase 2 backtest work)

### Q4: Risk Model Calibration Responsibility
**Question**: Who provides risk model (factor covariance)? User or system?
**Impact**: If system, need calibration logic (expensive); if user, need clear API
**Research Needed**: Clarify user expectations
**Recommendation**: User-supplied for MVP (CSV/Parquet upload), system calibration post-MVP

---

## 14. BA Handoff Instructions

### Artifacts to Create
1. **matrix_risk_engine_spec.md**: Detailed requirements for each component (C1-C10), ports (P1-P4), domain objects (DO1-DO6)
2. **matrix_risk_engine_tasklist.md**: Dependency-ordered tasks (30-120 min each) for 16-week MVP
3. **matrix_risk_engine_rules.yaml**: Domain rules (data versioning, point-in-time, transaction costs, VaR calculation)
4. **matrix_risk_engine_quality_gates.md**: Quality gates for each phase (test coverage, performance benchmarks, data integrity checks)
5. **matrix_risk_engine_evolution.md**: Evolution log (append-only drift tracking)
6. **matrix_risk_engine_decisions.md**: Architectural decisions (append-only ADR log)

### Key Decisions for BA to Expand
1. **ORE Integration Pattern**: Python bindings vs subprocess (depends on Q1 answer)
2. **Constraint Specification DSL**: YAML structure for constraints (sector_limit, position_limit, turnover_limit)
3. **Result Persistence Format**: Parquet vs SQLite for backtest results
4. **Configuration Management**: How YAML configs map to runtime objects
5. **Error Handling Strategy**: Fail-fast vs graceful degradation per component

### Acceptance Criteria Templates
Each user story (US-01 to US-20 from persona evaluation) should have:
- **Given**: Preconditions (data loaded, config specified)
- **When**: Action (query executed, backtest run, optimization solved)
- **Then**: Outcome (data returned, metrics calculated, constraints satisfied)
- **Evidence**: Artifact to prove success (test output, report, log entry)

### Testing Strategy
1. **Unit Tests**: Each adapter (C1-C5) has test suite (pytest)
2. **Integration Tests**: End-to-end flows (F1-F5) validated with sample data
3. **Performance Tests**: Benchmark against targets (VaR <15 min, backtest <60 sec, etc.)
4. **Validation Tests**: Point-in-time correctness, VaR backtesting, Greeks cross-validation

### Phase Sequencing Recommendation
- **Phase 1 (Weeks 1-4)**: Foundation - ArcticDB integration, data versioning, point-in-time queries
- **Phase 2 (Weeks 5-8)**: Backtesting - VectorBT integration, transaction costs, QuantStats tearsheets
- **Phase 3 (Weeks 9-12)**: Risk Analytics - ORE integration, VaR/CVaR, Greeks, stress testing
- **Phase 4 (Weeks 13-16)**: Optimization - Portfolio optimization, constraint enforcement, walk-forward testing

---

## 15. Handoff Envelope for BA

```yaml
# Matrix Risk Engine - Solution Design → BA Handoff Envelope
# Generated: 2026-01-25
# Source: Solution Designer Agent

version: "1.0"
project_slug: matrix_risk_engine

problem_statement: |
  Investment professionals (quant analysts, portfolio managers, risk specialists)
  lack an integrated, open-source platform for quantitative research, systematic
  strategy design, and risk measurement. The Matrix platform integrates ORE,
  ArcticDB, VectorBT, and QuantStats to deliver reproducible research, realistic
  backtesting, and institutional-grade risk analytics.

stakeholders:
  - role: Quant Analyst
    goals:
      - Reproducible research with versioned data (100% reproducibility)
      - Fast backtest iteration (<60 sec for 10 years)
      - Statistical validation of alpha signals
    constraints:
      - Laptop-deployable (16 GB RAM)
      - Python 3.10+ environment
      - No commercial data feeds (user-supplied data)

  - role: Systematic Investment Designer
    goals:
      - Risk-aware portfolio construction (Sharpe >0.8 net of costs)
      - Realistic transaction cost modeling
      - Walk-forward optimization testing
    constraints:
      - Optimization solve time <10 sec (500 securities)
      - Backtest-to-live slippage <50 bps/year

  - role: Risk & Simulation Specialist
    goals:
      - Accurate daily risk measurement (VaR, CVaR, Greeks)
      - Flexible stress testing with custom scenarios
      - Timely risk reporting (before market open)
    constraints:
      - VaR computation <15 min (full portfolio)
      - Greeks accuracy <1% deviation vs front office

in_scope:
  data_management:
    - Versioned time series storage (ArcticDB)
    - Point-in-time queries (as-of-date filtering)
    - Data quality validation gates
    - Corporate action adjustments
  backtesting:
    - Vectorized backtesting (VectorBT)
    - Transaction cost modeling (linear: spread + commission)
    - Performance tearsheet generation (QuantStats)
    - Factor analysis toolkit (IC, t-stats, turnover)
    - Walk-forward optimization
  portfolio_construction:
    - Mean-variance optimization (quadratic programming)
    - Linear constraints (sector, position, factor exposure limits)
    - Risk budgeting
    - Rebalancing simulation (calendar-based)
  risk_analytics:
    - Historical and parametric VaR (95%, 99%)
    - Expected Shortfall (CVaR)
    - Greeks (delta, gamma, vega, duration, convexity)
    - Stress testing with custom scenarios
    - Risk attribution (factor vs idiosyncratic)
    - Component VaR
  reporting:
    - Performance tearsheets (50+ metrics)
    - Daily risk dashboards
    - Backtest summary reports

out_of_scope:
  mvp_deferred:
    - Real-time/intraday data feeds
    - Live trading execution
    - Order management system (OMS)
    - Multi-user collaboration
    - Web-based UI
    - Regulatory reporting (UCITS, AIFMD)
    - Monte Carlo simulation (full revaluation)
    - Reverse stress testing
    - Model registry (MLflow-style)
    - Capacity estimation
    - Market impact modeling (Almgren-Chriss)
  anti_goals:
    - Commercial data feed integrations
    - Exotic derivatives pricing
    - Credit risk capital (FRTB, SA-CCR beyond ORE)
    - Multi-tenancy
    - Real-time collaboration

key_flows:
  F1_data_pipeline:
    description: Load, version, and query time series data with point-in-time correctness
    actors: [Quant Analyst, Risk Specialist]
    steps:
      - Ingest raw data (CSV/Parquet) → validate quality → apply corporate actions
      - Write to ArcticDB with version tag (e.g., v20260125_eod)
      - Query with as-of-date filter → return only data available at that time
    acceptance:
      - Version immutability (v1 retrievable after v2 written)
      - Point-in-time correctness (no future data in past queries)
      - Data quality report (pass/fail metrics)

  F2_backtest_flow:
    description: Run vectorized backtests with transaction costs and generate tearsheets
    actors: [Quant Analyst, Systematic Designer]
    steps:
      - Load historical data → generate signals → configure backtest params
      - Execute VectorBT simulation → apply transaction costs
      - Generate QuantStats tearsheet (50+ metrics)
    acceptance:
      - Reproducibility (identical results on rerun)
      - Transaction costs deducted (zero-cost > cost-aware returns)
      - Tearsheet completeness (all 50+ metrics present)

  F3_optimization_flow:
    description: Construct optimal portfolios with constraints
    actors: [Systematic Designer]
    steps:
      - Load alpha signals + risk model → define constraints
      - Solve quadratic programming problem → return target weights
      - Generate trade list with cost estimates
    acceptance:
      - All constraints satisfied (sector ≤10%, position ≤5%, turnover ≤20%)
      - Solve time <10 sec (500 securities)
      - Trade list sums to zero (cash neutral or fully invested)

  F4_risk_measurement:
    description: Calculate daily risk metrics (VaR, CVaR, Greeks)
    actors: [Risk Specialist]
    steps:
      - Load portfolio positions + market data → value portfolio (ORE)
      - Calculate VaR (historical 250-day window) + CVaR
      - Compute Greeks via ORE → generate risk report
    acceptance:
      - VaR backtesting (95% confidence → ~5% breaches over time)
      - CVaR ≥ VaR (mathematical property)
      - Greeks accuracy <1% vs manual calculation

  F5_stress_testing:
    description: Apply stress scenarios and report stressed P&L
    actors: [Risk Specialist]
    steps:
      - Define stress scenarios (YAML) → apply shocks to market data
      - Revalue portfolio with shocked data (ORE) → calculate stressed P&L
      - Generate scenario comparison report
    acceptance:
      - Stressed P&L calculated for all scenarios
      - Linearity check for linear instruments (20% shock ≈ 2× 10% shock)
      - Scenario definitions version-controlled (YAML in git)

domain_objects:
  TimeSeries:
    attributes: [symbol, date_index, values, version, metadata]
    invariants:
      - date_index monotonically increasing
      - version immutable once written
  Portfolio:
    attributes: [positions, weights, NAV, as_of_date, metadata]
    invariants:
      - sum(weights) ≈ 1.0 (tolerance 1e-6)
      - NAV = sum(position_value)
  BacktestResult:
    attributes: [returns, trades, positions, metrics, config]
    invariants:
      - returns aligned with trading calendar
      - trades have valid timestamps
      - metrics derived from returns (deterministic)
  RiskMetrics:
    attributes: [VaR, CVaR, Greeks, as_of_date, portfolio_id]
    invariants:
      - CVaR ≥ VaR for all confidence levels
      - Greeks computed at same valuation point
  StressScenario:
    attributes: [name, shocks, description, date_calibrated]
    invariants:
      - shocks specify all required risk factors
      - shock magnitudes reasonable (abs(shock) < 5.0 for most)
  Constraint:
    attributes: [type, bounds, securities, name]
    invariants:
      - bounds["lower"] ≤ bounds["upper"]
      - all referenced securities exist in universe

component_architecture:
  core_domain:
    - Portfolio, TimeSeries, BacktestResult, RiskMetrics, StressScenario, Constraint
  domain_services:
    - BacktestEngine (orchestrates backtest workflow)
    - RiskCalculationService (orchestrates risk calculation)
    - OptimizationService (orchestrates portfolio optimization)
    - StressTestingService (orchestrates stress testing)
    - FactorAnalysisService (IC, t-stats, turnover)
  ports:
    - DataPort (load, save, query time series)
    - BacktestPort (simulate, optimize)
    - RiskPort (calculate_var, compute_greeks, stress_test)
    - ReportPort (generate_report)
  adapters:
    - ArcticDBAdapter (implements DataPort)
    - VectorBTAdapter (implements BacktestPort.simulate)
    - OREAdapter (implements RiskPort)
    - QuantStatsAdapter (implements ReportPort)
    - OptimizerAdapter (implements BacktestPort.optimize, wraps cvxpy)
    - FileSystemAdapter (config loading, result persistence)

risks:
  security:
    - T1: Data leakage via misconfigured versioning (CTRL1: automated validation gates)
    - T2: API key exposure in config files (CTRL2: environment variables, .gitignore .env)
    - T5: Unauthorized access to models (CTRL5: file permissions chmod 600)
    - T6: Malicious scenario injection (CTRL6: file integrity checks, hash validation)
    - T10: Jupyter notebook code injection (CTRL10: disable auto-execute, code review)
  operational:
    - T3: Stale prices causing incorrect valuations (CTRL3: data freshness validation, max age 24h)
    - T7: Unbounded ArcticDB storage growth (CTRL7: 90-day retention, automated S3 archive)
    - T8: Optimization solver manipulation (CTRL8: post-optimization validation, position/sector checks)
  data_integrity:
    - T4: Survivorship bias (CTRL4: point-in-time universe, validation gate)
    - T9: Greeks mismatch (CTRL9: cross-validation vs Black-Scholes, <1% tolerance)

assumptions:
  - Users have Python 3.10+ environment (virtualenv or conda)
  - Data is daily frequency only (no intraday for MVP)
  - Portfolio size <2000 securities
  - Single-user deployment (no multi-tenancy)
  - Local or S3 storage for ArcticDB
  - ORE binaries available via pip (ORE-SWIG package)
  - User supplies own market data (no commercial feeds)
  - Risk model (factor covariance) user-supplied (CSV/Parquet)

open_questions:
  Q1_ore_bindings:
    question: Do ORE-SWIG bindings support all required analytics (VaR, CVaR, Greeks)?
    impact: If missing, need subprocess call to ORE (slower, less integrated)
    action: Prototype ORE integration in Phase 3 (Weeks 9-12)

  Q2_arcticdb_license:
    question: BSL 1.1 restricts production use; does MVP qualify as production?
    impact: May need Apache 2.0 license for live trading decisions
    action: Clarify with user (research-only vs production research)

  Q3_vectorbt_pro:
    question: Does MVP need VectorBT Pro features (paid)?
    impact: Budget implications if Pro required
    action: Start with open source, upgrade if needed in Phase 2

  Q4_risk_model_source:
    question: Who provides risk model (user or system calibration)?
    impact: If system, need calibration logic (complex)
    action: Assume user-supplied for MVP, document CSV schema

recommended_next_agent: business-analyst

handoff_notes: |
  Solution design complete. 10 components (C1-C10), 4 ports (P1-P4), 6 domain
  objects (DO1-DO6), 5 key flows (F1-F5), 10 threats with controls (T1-T10),
  and 4 open questions (Q1-Q4) identified.

  BA should focus on:
  1. ORE integration pattern (Python bindings vs subprocess) - depends on Q1
  2. Constraint specification DSL (YAML schema for sector_limit, position_limit, etc.)
  3. Result persistence format (Parquet vs SQLite)
  4. Configuration management (YAML → runtime objects)
  5. Error handling strategy (fail-fast vs graceful degradation)

  Phase sequencing:
  - Phase 1 (Weeks 1-4): ArcticDB integration, data versioning, point-in-time queries
  - Phase 2 (Weeks 5-8): VectorBT backtest, transaction costs, QuantStats tearsheets
  - Phase 3 (Weeks 9-12): ORE risk analytics, VaR/CVaR, Greeks, stress testing
  - Phase 4 (Weeks 13-16): Optimization, constraints, walk-forward testing

  Critical integration points:
  - ORE-SWIG: Wrap Python bindings for VaR, Greeks, stress testing
  - ArcticDB: Version management, point-in-time queries
  - VectorBT: Signal-to-backtest execution, transaction cost application
  - QuantStats: Tearsheet generation from returns series

  All 20 user stories from persona evaluation should map to tasks in tasklist.
  Quality gates required after each phase (test coverage, performance benchmarks).
```

---

**End of Solution Designer Handoff Pack**

**Next Step**: Business Analyst agent receives this handoff envelope and produces:
- `matrix_risk_engine_spec.md` (detailed requirements)
- `matrix_risk_engine_tasklist.md` (dependency-ordered tasks)
- `matrix_risk_engine_rules.yaml` (domain rules)
- `matrix_risk_engine_quality_gates.md` (test/performance gates)
- `matrix_risk_engine_evolution.md` (drift log)
- `matrix_risk_engine_decisions.md` (architectural decisions)
