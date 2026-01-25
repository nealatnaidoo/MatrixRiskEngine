# Matrix Investment Management Platform - Persona Evaluation

**Document Version**: 1.0
**Date**: 2026-01-25
**Evaluator**: PersonaEval Agent
**Product**: Matrix Investment Management Platform MVP

---

## Executive Summary

This document evaluates the Matrix Investment Management Platform through three domain-specific personas representing key users in quantitative finance. The platform integrates Open Risk Engine (ORE), ArcticDB, VectorBT, and QuantStats to deliver a lightweight risk and backtesting solution for systematic investment management.

**Technology Stack Overview**:
- **ORE (Open Risk Engine)**: Pricing, XVA, VaR, exposure simulation, 130+ instruments
- **ArcticDB**: High-performance time series storage, versioning, billions of rows
- **VectorBT**: Fast vectorized backtesting, portfolio simulation, parameter optimization
- **QuantStats**: Portfolio analytics, performance metrics, tearsheet generation

---

## Persona 1: Quant Analyst

### 1.1 Persona Card

| Attribute | Details |
|-----------|---------|
| **Name** | Dr. Elena Markov |
| **Role** | Senior Quantitative Analyst |
| **Organization** | Multi-strategy hedge fund (AUM $2B) |
| **Experience** | 8 years in quantitative research |
| **Education** | PhD in Financial Mathematics, MSc Statistics |
| **Technical Proficiency** | Expert Python/R, intermediate C++, SQL |
| **Daily Tools** | Jupyter notebooks, pandas, numpy, scipy, sklearn, QuantLib |
| **Reporting To** | Head of Quant Research |

**Background**: Elena builds and validates factor models for equity and fixed income strategies. She spends 60% of her time on data exploration and feature engineering, 30% on model development, and 10% on documentation and peer review.

**Primary Goals**:
1. Develop robust alpha signals with statistical significance
2. Ensure reproducibility of research across team members
3. Validate models through rigorous out-of-sample testing
4. Maintain clean data lineage for audit trails

**Frustrations with Current Tools**:
- Data versioning is manual and error-prone
- Reproducing colleague's research requires extensive environment setup
- Large dataset operations crash memory limits
- Model versioning scattered across git repos and notebooks

### 1.2 User Journey

**Scenario**: Elena is developing a new momentum factor for the equity portfolio.

| Step | Action | System Interaction | Expected Output |
|------|--------|-------------------|-----------------|
| 1 | **Data Discovery** | Query ArcticDB for available symbols and date ranges | Symbol universe, data availability matrix |
| 2 | **Data Retrieval** | Load 10 years of daily price data for 2000 stocks | DataFrame with OHLCV, corporate actions |
| 3 | **Data Quality Check** | Run automated quality gates | Missing data report, outlier flags |
| 4 | **Feature Engineering** | Calculate momentum signals (12-1 month) | New columns with factor exposures |
| 5 | **Universe Definition** | Apply liquidity and market cap filters | Filtered investable universe |
| 6 | **Factor Analysis** | Compute factor returns, IC, turnover | Time series of factor metrics |
| 7 | **Statistical Validation** | Run t-tests, Sharpe ratio, decay analysis | Statistical significance report |
| 8 | **Backtest Setup** | Configure backtest parameters in VectorBT | Backtest configuration object |
| 9 | **Backtest Execution** | Run historical simulation | Portfolio returns, trades, positions |
| 10 | **Performance Analysis** | Generate QuantStats tearsheet | HTML report with 50+ metrics |
| 11 | **Robustness Testing** | Parameter sensitivity analysis | Heatmap of Sharpe vs parameters |
| 12 | **Model Versioning** | Save model artifacts with metadata | Versioned model in registry |
| 13 | **Peer Review** | Share reproducible notebook | Notebook URL with pinned dependencies |
| 14 | **Documentation** | Auto-generate model documentation | Markdown specification |
| 15 | **Handoff** | Package for production deployment | Deployment manifest |

### 1.3 Data Requirements

| Data Type | Format | Frequency | Quality Requirements |
|-----------|--------|-----------|---------------------|
| **Price Data** | OHLCV DataFrame | Daily | <0.1% missing, adjusted for splits/dividends |
| **Fundamental Data** | Factor exposures | Quarterly (point-in-time) | Survivorship bias-free |
| **Reference Data** | Security master | As-of-date | ISIN, SEDOL, ticker mapping |
| **Corporate Actions** | Events | Event-driven | Complete history for adjustments |
| **Factor Returns** | Time series | Daily | Published factors (Fama-French, Barra) |
| **Index Data** | Benchmark returns | Daily | Total return indices |
| **Calendar Data** | Trading calendars | Static | Exchange-specific holidays |

**Data Volume Estimates**:
- Universe: 5,000-10,000 securities
- History: 20+ years
- Frequency: Daily (250 obs/year/security)
- Total rows: ~50 million time series observations

### 1.4 Functionality Requirements

| Category | Feature | Priority | Notes |
|----------|---------|----------|-------|
| **Data Access** | Versioned time series retrieval | Must Have | ArcticDB snapshots |
| **Data Access** | Point-in-time queries | Must Have | Avoid look-ahead bias |
| **Data Access** | Bulk data loading with filtering | Must Have | Column/date range selection |
| **Analysis** | Factor analysis toolkit | Must Have | IC, turnover, decay |
| **Analysis** | Statistical testing suite | Must Have | t-test, bootstrap, cross-validation |
| **Analysis** | Correlation/covariance estimation | Must Have | Shrinkage, rolling windows |
| **Backtest** | Event-driven simulation | Should Have | Order-level simulation |
| **Backtest** | Transaction cost modeling | Must Have | Spread, impact, commissions |
| **Backtest** | Slippage simulation | Should Have | Market impact models |
| **Reporting** | Performance attribution | Must Have | Sector, factor, security-level |
| **Reporting** | Risk decomposition | Must Have | Factor vs idiosyncratic |
| **Workflow** | Notebook integration | Must Have | Jupyter, VS Code |
| **Workflow** | Model registry | Should Have | MLflow or similar |
| **Workflow** | Reproducibility framework | Must Have | Environment + data versioning |

### 1.5 Pain Points

1. **Memory Constraints**: Loading full universe history exhausts RAM; need streaming/chunked operations
2. **Reproducibility Hell**: "Works on my machine" syndrome across team
3. **Data Drift**: Models degrade silently when underlying data changes
4. **Version Chaos**: No single source of truth for model versions
5. **Slow Iteration**: Backtest takes hours, discouraging experimentation
6. **Documentation Burden**: Manual documentation lags behind code changes

### 1.6 Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Data load time (1M rows) | <5 seconds | Wall clock time |
| Backtest speed (10 years, 500 securities) | <60 seconds | VectorBT benchmark |
| Research reproducibility rate | 100% | Notebook reruns produce identical results |
| Time to first insight | <30 minutes | From data query to initial analysis |
| Model documentation coverage | >90% | Auto-generated vs manual |

---

## Persona 2: Systematic Investment Designer

### 2.1 Persona Card

| Attribute | Details |
|-----------|---------|
| **Name** | Marcus Chen, CFA |
| **Role** | Portfolio Manager - Systematic Strategies |
| **Organization** | Quantitative asset manager |
| **Experience** | 12 years in systematic investing |
| **Education** | MS Financial Engineering, CFA Charterholder |
| **Technical Proficiency** | Advanced Python, intermediate R, Excel/VBA |
| **Daily Tools** | Bloomberg Terminal, proprietary OMS, risk systems |
| **Reporting To** | CIO |

**Background**: Marcus designs and manages systematic equity and multi-asset strategies. He focuses on portfolio construction, optimization, and risk budgeting. His strategies range from factor tilts to tactical allocation overlays.

**Primary Goals**:
1. Design robust strategies that perform across market regimes
2. Manage portfolio risk within defined limits
3. Minimize implementation slippage and transaction costs
4. Achieve consistent risk-adjusted returns

**Frustrations with Current Tools**:
- Optimization tools don't integrate with backtesting seamlessly
- Transaction cost modeling is oversimplified
- Capacity analysis requires separate systems
- Rebalancing simulation lacks realistic market impact

### 2.2 User Journey

**Scenario**: Marcus is designing a multi-factor equity strategy with risk constraints.

| Step | Action | System Interaction | Expected Output |
|------|--------|-------------------|-----------------|
| 1 | **Strategy Specification** | Define factor weights, constraints, universe | Strategy configuration YAML |
| 2 | **Alpha Signal Ingestion** | Load factor scores from quant team | Normalized alpha signals |
| 3 | **Risk Model Loading** | Retrieve factor covariance, specific risk | Risk model object |
| 4 | **Universe Construction** | Apply investability constraints | Eligible security list |
| 5 | **Constraint Definition** | Specify sector, country, position limits | Constraint matrix |
| 6 | **Optimization Setup** | Configure objective (max alpha, min variance) | Optimization problem |
| 7 | **Portfolio Optimization** | Solve for optimal weights | Target portfolio weights |
| 8 | **Trade Generation** | Calculate trades from current to target | Trade list with costs |
| 9 | **Cost/Benefit Analysis** | Evaluate alpha capture vs transaction costs | Trade efficiency report |
| 10 | **Backtest Simulation** | Run walk-forward optimization | Historical portfolio returns |
| 11 | **Turnover Analysis** | Measure realized turnover vs expected | Turnover metrics |
| 12 | **Capacity Estimation** | Estimate strategy capacity | Max AUM without degradation |
| 13 | **Regime Analysis** | Test performance across market regimes | Regime-conditional returns |
| 14 | **Sensitivity Analysis** | Vary parameters, measure stability | Parameter sensitivity grid |
| 15 | **Strategy Documentation** | Generate strategy specification | Investment policy document |

### 2.3 Data Requirements

| Data Type | Format | Frequency | Quality Requirements |
|-----------|--------|-----------|---------------------|
| **Alpha Signals** | Security-level scores | Daily | Standardized, cross-sectionally neutral |
| **Risk Model** | Factor loadings + covariance | Daily/Monthly | Commercial-grade (Barra, Axioma) |
| **Transaction Costs** | Spread + impact estimates | Daily | Realistic market impact models |
| **Position Data** | Current holdings | Real-time | Accurate NAV, shares |
| **Benchmark Data** | Index weights | Monthly | Constituent-level weights |
| **Capacity Data** | ADV, market cap | Daily | For sizing constraints |
| **Regime Indicators** | Macro state | Daily | VIX, yield curve, etc. |

### 2.4 Functionality Requirements

| Category | Feature | Priority | Notes |
|----------|---------|----------|-------|
| **Optimization** | Mean-variance optimization | Must Have | Quadratic programming |
| **Optimization** | Risk parity/budgeting | Must Have | Equal risk contribution |
| **Optimization** | Robust optimization | Should Have | Worst-case, resampled |
| **Optimization** | Multi-period optimization | Could Have | Dynamic programming |
| **Constraints** | Linear constraints | Must Have | Sector, country, position |
| **Constraints** | Turnover constraints | Must Have | Dollar or share limits |
| **Constraints** | Factor exposure limits | Must Have | Beta, size, style neutral |
| **Transaction Costs** | Linear cost model | Must Have | Commission + spread |
| **Transaction Costs** | Market impact model | Should Have | Square-root, Almgren-Chriss |
| **Backtest** | Walk-forward optimization | Must Have | Out-of-sample testing |
| **Backtest** | Rebalancing simulation | Must Have | Calendar, threshold triggers |
| **Analysis** | Performance attribution | Must Have | Brinson, factor-based |
| **Analysis** | Capacity analysis | Should Have | Strategy AUM limits |
| **Reporting** | Strategy tearsheet | Must Have | Comprehensive metrics |

### 2.5 Pain Points

1. **Optimization-Backtest Gap**: Optimized portfolios don't match backtest assumptions
2. **Transaction Cost Blindness**: Strategies look great ignoring costs, fail in reality
3. **Constraint Explosion**: Complex constraints slow optimization to crawl
4. **Regime Blindness**: Strategies optimized for one regime fail in another
5. **Rebalancing Frequency Dilemma**: Too frequent = high costs, too rare = tracking error
6. **Capacity Uncertainty**: No systematic way to estimate when strategy "fills up"

### 2.6 Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Optimization solve time | <10 seconds | 500-security portfolio |
| Backtest-to-live slippage | <50 bps/year | Tracking difference |
| Strategy Sharpe ratio | >0.8 net of costs | Risk-adjusted return |
| Maximum drawdown | <15% | Peak-to-trough |
| Information ratio vs benchmark | >0.5 | Active return / tracking error |

---

## Persona 3: Risk & Simulation Specialist

### 3.1 Persona Card

| Attribute | Details |
|-----------|---------|
| **Name** | Sarah Okonkwo, FRM |
| **Role** | Head of Portfolio Risk |
| **Organization** | Investment management firm |
| **Experience** | 15 years in risk management |
| **Education** | MS Applied Mathematics, FRM certified |
| **Technical Proficiency** | Expert Python, R, SAS; familiar with C++ |
| **Daily Tools** | ORE, RiskMetrics, proprietary risk systems |
| **Reporting To** | Chief Risk Officer |

**Background**: Sarah oversees portfolio risk measurement, stress testing, and limit monitoring. She ensures the firm operates within risk tolerances and regulatory requirements. She manages a team of 4 risk analysts.

**Primary Goals**:
1. Accurate daily risk measurement across all portfolios
2. Proactive stress testing for emerging risks
3. Clear risk reporting to investment committee
4. Regulatory compliance (UCITS, AIFMD risk limits)

**Frustrations with Current Tools**:
- Risk systems are slow and inflexible
- Stress testing requires extensive manual setup
- Historical simulation lacks sufficient scenarios
- Greeks computation doesn't match trading desk values

### 3.2 User Journey

**Scenario**: Sarah is conducting daily risk monitoring and running a custom stress test.

| Step | Action | System Interaction | Expected Output |
|------|--------|-------------------|-----------------|
| 1 | **Position Load** | Ingest end-of-day positions | Portfolio holdings snapshot |
| 2 | **Market Data Update** | Refresh prices, curves, volatilities | Updated market data store |
| 3 | **Portfolio Valuation** | Price all instruments using ORE | NAV, P&L, mark-to-market |
| 4 | **VaR Calculation** | Run historical/parametric VaR | 95%, 99% VaR numbers |
| 5 | **CVaR/ES Calculation** | Compute expected shortfall | Tail risk metrics |
| 6 | **Greeks Computation** | Calculate delta, gamma, vega, duration | Sensitivity report |
| 7 | **Limit Monitoring** | Check positions against limits | Breach alerts |
| 8 | **Stress Scenario Definition** | Define custom shock scenarios | Scenario configuration |
| 9 | **Stress Test Execution** | Apply shocks, revalue portfolio | Stressed P&L |
| 10 | **Scenario Analysis** | Compare multiple scenarios | Scenario comparison matrix |
| 11 | **Monte Carlo Simulation** | Run 10,000 path simulation | Distribution of outcomes |
| 12 | **Risk Attribution** | Decompose risk by factor/position | Risk contribution report |
| 13 | **Report Generation** | Create daily risk report | PDF/HTML report |
| 14 | **Limit Breach Escalation** | Document and escalate breaches | Escalation workflow |
| 15 | **Regulatory Reporting** | Generate regulatory risk reports | UCITS/AIFMD reports |

### 3.3 Data Requirements

| Data Type | Format | Frequency | Quality Requirements |
|-----------|--------|-----------|---------------------|
| **Position Data** | Holdings + trades | Real-time/EOD | Complete, reconciled |
| **Price Data** | Clean prices | Real-time/EOD | Validated, no stale prices |
| **Yield Curves** | Term structure | Daily | Bootstrap quality |
| **Volatility Surfaces** | Implied vol | Daily | Calibrated surfaces |
| **Credit Spreads** | CDS curves | Daily | Issuer-level |
| **Correlation Matrix** | Factor correlations | Monthly | Stable, positive semi-definite |
| **Stress Scenarios** | Shock definitions | As needed | Historically calibrated |
| **Limit Structure** | Risk limits | Static | Approved by board |

### 3.4 Functionality Requirements

| Category | Feature | Priority | Notes |
|----------|---------|----------|-------|
| **VaR** | Historical VaR | Must Have | 250-day window minimum |
| **VaR** | Parametric VaR | Must Have | Variance-covariance |
| **VaR** | Monte Carlo VaR | Should Have | Full revaluation |
| **Risk Metrics** | Expected Shortfall (CVaR) | Must Have | Tail risk measure |
| **Risk Metrics** | Component VaR | Must Have | Position-level contributions |
| **Risk Metrics** | Marginal VaR | Should Have | Incremental risk |
| **Sensitivities** | Delta, Gamma, Vega | Must Have | First/second order Greeks |
| **Sensitivities** | Duration, Convexity | Must Have | Fixed income |
| **Sensitivities** | Credit DV01 | Must Have | Credit spread sensitivity |
| **Stress Testing** | Predefined scenarios | Must Have | 2008, COVID, etc. |
| **Stress Testing** | Custom scenario builder | Must Have | Ad-hoc shocks |
| **Stress Testing** | Reverse stress testing | Should Have | Find breaking scenarios |
| **Simulation** | Monte Carlo engine | Must Have | Correlated paths |
| **Simulation** | Scenario generation | Must Have | Interest rate, equity, FX |
| **Reporting** | Daily risk dashboard | Must Have | Key metrics summary |
| **Reporting** | Regulatory reports | Must Have | UCITS VaR, leverage |
| **Limits** | Limit monitoring | Must Have | Real-time alerts |
| **Limits** | Breach documentation | Must Have | Audit trail |

### 3.5 Pain Points

1. **Slow VaR Computation**: Full Monte Carlo takes hours, limits scenario exploration
2. **Greeks Mismatch**: Risk system Greeks differ from front office
3. **Scenario Rigidity**: Predefined scenarios don't capture emerging risks
4. **Correlation Instability**: Correlations break down in stress periods
5. **Limit Framework Gaps**: Limits don't cover all risk types
6. **Reporting Lag**: Daily reports ready after trading starts

### 3.6 Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| VaR computation time | <15 minutes | Full portfolio |
| VaR backtesting breaches | <5% at 95% confidence | P&L exceptions |
| Stress test throughput | 100 scenarios/hour | Custom shocks |
| Report delivery time | Before 7:00 AM | Market open readiness |
| Greeks accuracy vs front office | <1% deviation | Cross-validation |

---

## Synthesized User Stories

### Priority Legend (MoSCoW)
- **M** = Must Have (MVP requirement)
- **S** = Should Have (High priority post-MVP)
- **C** = Could Have (Nice to have)
- **W** = Won't Have (Out of scope for now)

### User Stories with Acceptance Criteria

| ID | Story | Persona | Priority | Acceptance Criteria |
|----|-------|---------|----------|---------------------|
| US-01 | As a Quant Analyst, I want to load versioned time series data so that I can reproduce historical research | Quant | M | Given a symbol and version, when I query data, then I receive the exact dataset from that version |
| US-02 | As a Quant Analyst, I want to run point-in-time queries so that I avoid look-ahead bias | Quant | M | Given a historical date, when I query factors, then only data available as of that date is returned |
| US-03 | As a Quant Analyst, I want to calculate factor returns and IC so that I can evaluate signal quality | Quant | M | Given factor scores, when I run factor analysis, then I get IC, t-stat, turnover metrics |
| US-04 | As a Quant Analyst, I want to run backtests with transaction costs so that I get realistic performance | Quant | M | Given signals and cost model, when I backtest, then costs are deducted from returns |
| US-05 | As a Quant Analyst, I want to generate performance tearsheets so that I can summarize strategy quality | Quant | M | Given returns series, when I generate tearsheet, then I get 50+ metrics in HTML format |
| US-06 | As a Quant Analyst, I want to version my models so that I can track model evolution | Quant | S | Given a trained model, when I save it, then it's stored with version, timestamp, and metadata |
| US-07 | As a Quant Analyst, I want parameter sensitivity analysis so that I validate model robustness | Quant | S | Given parameter ranges, when I run sensitivity, then I get performance heatmap |
| US-08 | As a Sys. Designer, I want to run portfolio optimization so that I construct efficient portfolios | Designer | M | Given alpha, risk model, constraints, when I optimize, then I get optimal weights |
| US-09 | As a Sys. Designer, I want to specify constraints (sector, position limits) so that I meet investment policy | Designer | M | Given constraint definitions, when I optimize, then solution respects all constraints |
| US-10 | As a Sys. Designer, I want walk-forward backtesting so that I test realistic strategy performance | Designer | M | Given rebalancing schedule, when I backtest, then optimization runs at each rebalance |
| US-11 | As a Sys. Designer, I want market impact modeling so that I estimate realistic transaction costs | Designer | M | Given trade sizes and ADV, when I estimate costs, then impact is calculated |
| US-12 | As a Sys. Designer, I want risk budgeting so that I allocate risk equally across factors | Designer | S | Given target risk contributions, when I optimize, then each factor contributes equally to risk |
| US-13 | As a Sys. Designer, I want capacity estimation so that I know strategy AUM limits | Designer | S | Given strategy turnover and universe, when I analyze capacity, then I get max AUM estimate |
| US-14 | As a Risk Specialist, I want to calculate VaR so that I measure portfolio risk | Risk | M | Given positions and history, when I calculate VaR, then I get 95% and 99% values |
| US-15 | As a Risk Specialist, I want to calculate CVaR/ES so that I measure tail risk | Risk | M | Given VaR parameters, when I calculate ES, then I get expected shortfall value |
| US-16 | As a Risk Specialist, I want to compute Greeks so that I measure portfolio sensitivities | Risk | M | Given positions, when I compute Greeks, then I get delta, gamma, vega, duration |
| US-17 | As a Risk Specialist, I want to run stress tests so that I assess portfolio resilience | Risk | M | Given scenarios, when I run stress test, then I get stressed P&L for each scenario |
| US-18 | As a Risk Specialist, I want Monte Carlo simulation so that I generate risk distributions | Risk | S | Given simulation parameters, when I run MC, then I get return distribution |
| US-19 | As a Risk Specialist, I want risk attribution so that I understand risk sources | Risk | S | Given risk metrics, when I decompose, then I get factor vs idiosyncratic split |
| US-20 | As a Risk Specialist, I want automated risk reports so that stakeholders stay informed | Risk | M | Given risk metrics, when I generate report, then I get formatted PDF/HTML |

---

## QA Test Scenarios

### Quant Analyst Scenarios

| ID | Scenario | Steps | Expected Result |
|----|----------|-------|-----------------|
| QA-Q1 | Version retrieval consistency | 1. Save dataset v1, 2. Modify data, 3. Save as v2, 4. Retrieve v1 | v1 data unchanged |
| QA-Q2 | Point-in-time accuracy | 1. Query factor as of 2020-01-15, 2. Verify no post-date data | Only pre-date data returned |
| QA-Q3 | Backtest reproducibility | 1. Run backtest, 2. Record results, 3. Rerun same parameters | Identical results |
| QA-Q4 | Large dataset handling | 1. Load 50M rows, 2. Run analysis | Completes without memory error |
| QA-Q5 | Transaction cost deduction | 1. Run backtest with 10 bps cost, 2. Compare to zero cost | Returns reduced by cost amount |
| QA-Q6 | Factor IC calculation | 1. Provide known signal, 2. Calculate IC | IC matches manual calculation |
| QA-Q7 | Tearsheet completeness | 1. Generate tearsheet, 2. Check metrics | All 50+ metrics present |
| QA-Q8 | Model versioning integrity | 1. Save model v1, 2. Load v1 | Model state fully restored |

### Systematic Designer Scenarios

| ID | Scenario | Steps | Expected Result |
|----|----------|-------|-----------------|
| QA-D1 | Constraint satisfaction | 1. Add 10% sector limit, 2. Optimize | No sector exceeds 10% |
| QA-D2 | Optimization convergence | 1. Submit complex optimization, 2. Wait | Solution found within timeout |
| QA-D3 | Market impact scaling | 1. Double trade size, 2. Compute impact | Impact increases >2x (convex) |
| QA-D4 | Walk-forward consistency | 1. Run walk-forward, 2. Check each period | No look-ahead in optimization |
| QA-D5 | Turnover limit enforcement | 1. Set 20% turnover limit, 2. Optimize | Realized turnover <= 20% |
| QA-D6 | Risk parity verification | 1. Run risk parity, 2. Compute contributions | All risk contributions equal |
| QA-D7 | Capacity regression | 1. Increase AUM, 2. Measure performance | Performance degrades at capacity |
| QA-D8 | Multi-period optimization | 1. Run multi-period, 2. Verify path | Trades smooth across periods |

### Risk Specialist Scenarios

| ID | Scenario | Steps | Expected Result |
|----|----------|-------|-----------------|
| QA-R1 | VaR backtest | 1. Calculate 95% VaR daily for 1 year, 2. Count breaches | ~12-13 breaches (5% of 250) |
| QA-R2 | Greeks accuracy | 1. Compute delta, 2. Shift underlying 1%, 3. Compare P&L | P&L matches delta prediction |
| QA-R3 | Stress test linearity | 1. Apply 10% shock, 2. Apply 20% shock | 20% shock P&L ~ 2x 10% P&L |
| QA-R4 | Monte Carlo convergence | 1. Run 1000 paths, 2. Run 10000 paths | VaR estimates converge |
| QA-R5 | CVaR > VaR | 1. Calculate VaR and CVaR | CVaR >= VaR always |
| QA-R6 | Limit breach detection | 1. Breach limit, 2. Check alerts | Alert generated immediately |
| QA-R7 | Report completeness | 1. Generate daily report | All required sections present |
| QA-R8 | Duration accuracy | 1. Compute duration, 2. Shift rates 1bp, 3. Compare P&L | P&L matches duration prediction |

---

## MVP Feature Backlog

### WSJF Scoring

**WSJF = (Business Value + Time Criticality + Risk Reduction) / Job Size**

Scores: 1 (Low) to 5 (High)

| ID | Feature | BV | TC | RR | Size | WSJF | Priority |
|----|---------|----|----|----|----|------|----------|
| F-01 | ArcticDB time series storage | 5 | 5 | 4 | 3 | 4.7 | 1 |
| F-02 | Version control for datasets | 5 | 4 | 5 | 2 | 7.0 | 2 |
| F-03 | VectorBT backtest integration | 5 | 5 | 4 | 3 | 4.7 | 3 |
| F-04 | QuantStats tearsheet generation | 4 | 4 | 3 | 1 | 11.0 | 4 |
| F-05 | Transaction cost modeling | 5 | 4 | 5 | 2 | 7.0 | 5 |
| F-06 | Historical VaR calculation | 5 | 5 | 5 | 2 | 7.5 | 6 |
| F-07 | Portfolio optimization (MVO) | 5 | 4 | 4 | 3 | 4.3 | 7 |
| F-08 | Constraint specification | 4 | 4 | 4 | 2 | 6.0 | 8 |
| F-09 | Greeks computation (ORE) | 5 | 4 | 5 | 3 | 4.7 | 9 |
| F-10 | Stress testing framework | 5 | 4 | 5 | 3 | 4.7 | 10 |
| F-11 | Point-in-time data queries | 5 | 3 | 5 | 2 | 6.5 | 11 |
| F-12 | Expected Shortfall (CVaR) | 4 | 4 | 5 | 2 | 6.5 | 12 |
| F-13 | Factor analysis toolkit | 4 | 3 | 3 | 2 | 5.0 | 13 |
| F-14 | Walk-forward optimization | 4 | 3 | 4 | 3 | 3.7 | 14 |
| F-15 | Monte Carlo simulation | 4 | 3 | 4 | 4 | 2.8 | 15 |
| F-16 | Risk attribution | 4 | 3 | 4 | 3 | 3.7 | 16 |
| F-17 | Market impact modeling | 4 | 3 | 4 | 3 | 3.7 | 17 |
| F-18 | Model versioning/registry | 3 | 2 | 4 | 3 | 3.0 | 18 |
| F-19 | Risk parity optimization | 3 | 2 | 3 | 2 | 4.0 | 19 |
| F-20 | Automated risk reports | 4 | 3 | 3 | 3 | 3.3 | 20 |
| F-21 | Capacity estimation | 3 | 2 | 3 | 3 | 2.7 | 21 |
| F-22 | Regulatory reporting | 3 | 2 | 4 | 4 | 2.3 | 22 |
| F-23 | Limit monitoring/alerts | 3 | 3 | 4 | 3 | 3.3 | 23 |
| F-24 | Reverse stress testing | 2 | 1 | 3 | 4 | 1.5 | 24 |

### MVP Scope (Top 12 Features)

**Phase 1 - Foundation (Weeks 1-4)**:
- F-01: ArcticDB time series storage
- F-02: Version control for datasets
- F-11: Point-in-time data queries

**Phase 2 - Backtesting (Weeks 5-8)**:
- F-03: VectorBT backtest integration
- F-05: Transaction cost modeling
- F-04: QuantStats tearsheet generation

**Phase 3 - Risk Analytics (Weeks 9-12)**:
- F-06: Historical VaR calculation
- F-12: Expected Shortfall (CVaR)
- F-09: Greeks computation (ORE)
- F-10: Stress testing framework

**Phase 4 - Optimization (Weeks 13-16)**:
- F-07: Portfolio optimization (MVO)
- F-08: Constraint specification

---

## Handoff Envelope for Solution Designer

```yaml
# Matrix Risk Engine - Handoff Envelope
# Generated: 2026-01-25
# Source: PersonaEval Agent

project_slug: matrix_risk_engine

problem_statement: |
  Investment professionals lack an integrated, open-source platform for
  quantitative research, systematic strategy design, and risk measurement.
  Current solutions are either expensive commercial products or fragmented
  open-source tools that don't integrate well. The Matrix platform aims to
  provide a cohesive solution using ORE, ArcticDB, VectorBT, and QuantStats.

stakeholders:
  - persona: Quant Analyst
    goals:
      - Reproducible research with versioned data
      - Fast backtest iteration
      - Robust statistical validation
    success_metrics:
      - Research reproducibility rate: 100%
      - Backtest speed: <60 seconds for 10 years

  - persona: Systematic Investment Designer
    goals:
      - Portfolio optimization with realistic constraints
      - Walk-forward backtesting
      - Transaction cost awareness
    success_metrics:
      - Backtest-to-live slippage: <50 bps/year
      - Optimization solve time: <10 seconds

  - persona: Risk & Simulation Specialist
    goals:
      - Accurate daily risk measurement
      - Flexible stress testing
      - Timely risk reporting
    success_metrics:
      - VaR computation: <15 minutes
      - Report delivery: before market open

in_scope:
  - Versioned time series storage (ArcticDB)
  - Point-in-time data queries
  - Vectorized backtesting (VectorBT)
  - Transaction cost modeling
  - Performance analytics (QuantStats)
  - Historical and parametric VaR
  - Expected Shortfall (CVaR)
  - Greeks computation (delta, gamma, vega, duration)
  - Stress testing with custom scenarios
  - Mean-variance portfolio optimization
  - Linear constraint specification
  - Daily frequency data (slow-moving)

out_of_scope:
  - Real-time/intraday data
  - Live trading execution
  - Order management system (OMS)
  - Commercial data feeds
  - Multi-user collaboration features
  - Web-based UI (CLI/notebook only for MVP)
  - Regulatory reporting (UCITS, AIFMD)
  - Monte Carlo simulation engine (post-MVP)
  - Exotic derivatives pricing
  - Credit risk capital calculations

key_flows:
  F1_data_pipeline:
    description: Load, version, and query time series data
    steps:
      - Ingest raw data to ArcticDB
      - Create versioned snapshot
      - Query with point-in-time filters
    actors: [Quant Analyst]

  F2_backtest_flow:
    description: Run vectorized backtests with costs
    steps:
      - Load historical data
      - Generate signals
      - Execute VectorBT simulation
      - Apply transaction costs
      - Generate QuantStats tearsheet
    actors: [Quant Analyst, Sys. Designer]

  F3_optimization_flow:
    description: Construct optimal portfolios
    steps:
      - Load alpha signals and risk model
      - Define constraints
      - Solve optimization problem
      - Generate target portfolio
    actors: [Sys. Designer]

  F4_risk_measurement:
    description: Calculate daily risk metrics
    steps:
      - Load positions and market data
      - Value portfolio using ORE
      - Calculate VaR, CVaR
      - Compute Greeks
    actors: [Risk Specialist]

  F5_stress_testing:
    description: Apply stress scenarios
    steps:
      - Define shock scenarios
      - Apply shocks to market data
      - Revalue portfolio
      - Report stressed P&L
    actors: [Risk Specialist]

domain_objects:
  TimeSeries:
    attributes: [symbol, date_index, values, version]
    invariants:
      - date_index must be monotonically increasing
      - version is immutable once created

  Portfolio:
    attributes: [positions, weights, NAV, as_of_date]
    invariants:
      - weights sum to 1.0 (or 0.0 for cash)
      - NAV = sum(position_value)

  BacktestResult:
    attributes: [returns, trades, positions, metrics]
    invariants:
      - returns aligned with trading calendar
      - trades have timestamps

  RiskMetrics:
    attributes: [VaR, CVaR, Greeks, as_of_date]
    invariants:
      - CVaR >= VaR
      - Greeks computed at same valuation point

  StressScenario:
    attributes: [name, shocks, description]
    invariants:
      - shocks specify all required risk factors

  Constraint:
    attributes: [type, bounds, securities]
    invariants:
      - bounds are feasible (lower <= upper)

risks:
  security:
    - Data leakage if version control misconfigured
    - API keys for data sources exposed

  operational:
    - ArcticDB storage growth unbounded
    - Long-running backtests block notebook

  data:
    - Stale prices causing incorrect valuations
    - Survivorship bias in historical data
    - Look-ahead bias in point-in-time queries

assumptions:
  - Users have Python 3.10+ environment
  - Data is daily frequency only
  - Portfolio size < 2000 securities
  - Single-user deployment (no multi-tenancy)
  - Local or S3 storage for ArcticDB
  - ORE binaries available via pip

open_questions:
  - Which risk model to use (Barra, Axioma, or custom)?
  - How to handle corporate actions in backtest?
  - What transaction cost model (fixed, linear, Almgren-Chriss)?
  - Should we support intraday data in future?
  - How to integrate with existing data vendors?
  - What authentication for future API layer?

recommended_next_agent: solution-designer
handoff_notes: |
  The persona evaluation is complete with 3 personas, 20 user stories,
  24 QA scenarios, and a prioritized backlog of 24 features. The MVP
  scope covers 12 features across 4 phases (16 weeks). Key integration
  points are ORE for risk/pricing, ArcticDB for storage, VectorBT for
  backtesting, and QuantStats for analytics. Solution designer should
  focus on data layer architecture, backtest engine integration, and
  risk calculation pipeline.
```

---

## Appendix A: Technology Reference

### Open Risk Engine (ORE)
- **License**: Modified BSD
- **Capabilities**: XVA, VaR, exposure simulation, 130+ instruments
- **Integration**: Python bindings via ORE-SWIG
- **Documentation**: [opensourcerisk.org/documentation](https://www.opensourcerisk.org/documentation/)

### ArcticDB
- **License**: BSL 1.1 (free for non-production)
- **Capabilities**: High-performance time series, versioning, billions of rows
- **Integration**: Native Python API with pandas
- **Documentation**: [arcticdb.io](https://arcticdb.io/)

### VectorBT
- **License**: Open source (Pro version available)
- **Capabilities**: Vectorized backtesting, 1M orders in 100ms
- **Integration**: pandas/numpy with Numba acceleration
- **Documentation**: [vectorbt.dev](https://vectorbt.dev/)

### QuantStats
- **License**: Apache 2.0
- **Capabilities**: 50+ metrics, tearsheets, Monte Carlo
- **Integration**: Pure Python with pandas
- **Documentation**: [github.com/ranaroussi/quantstats](https://github.com/ranaroussi/quantstats)

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **Alpha** | Excess return over benchmark |
| **CVaR** | Conditional Value at Risk (Expected Shortfall) |
| **Greeks** | Sensitivity measures (delta, gamma, vega, etc.) |
| **IC** | Information Coefficient (signal-return correlation) |
| **MVO** | Mean-Variance Optimization |
| **NAV** | Net Asset Value |
| **P&L** | Profit and Loss |
| **VaR** | Value at Risk |
| **Walk-forward** | Out-of-sample testing methodology |
| **XVA** | X-Value Adjustment (CVA, DVA, FVA, etc.) |

---

*Document generated by PersonaEval Agent for Matrix Investment Management Platform MVP*
