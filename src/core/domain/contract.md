# Domain Object Contracts

## TimeSeries

**Purpose**: Versioned time series data with invariants

### Attributes
- `symbol: str` - Asset identifier
- `date_index: DatetimeIndex` - Sorted, unique dates
- `values: DataFrame` - OHLCV, factors, etc.
- `version: str` - Immutable tag (format: vYYYYMMDD_label)
- `metadata: TimeSeriesMetadata` - Source, quality flags

### Invariants
- `date_index` must be monotonically increasing (no duplicates)
- `version` is immutable once written
- `values` must align with `date_index`

---

## Portfolio

**Purpose**: Holdings snapshot with valuation

### Attributes
- `positions: dict[str, float]` - Symbol to shares/notional
- `weights: dict[str, float]` - Symbol to portfolio weight
- `nav: float` - Net Asset Value
- `as_of_date: date` - Valuation date
- `metadata: PortfolioMetadata` - Strategy info

### Invariants
- `sum(weights) ≈ 1.0` (or 0.0 for cash-only)
- `positions` and `weights` reference same symbols
- `nav >= 0`

---

## BacktestResult

**Purpose**: Complete backtest output with metrics

### Attributes
- `returns: Series` - Date to portfolio return
- `trades: DataFrame` - Trade history
- `positions: DataFrame` - Position history
- `metrics: dict` - Performance metrics
- `config: BacktestConfig` - Reproducibility info

### Invariants
- `returns.index` is DatetimeIndex, sorted
- `trades` have valid timestamps within backtest period

---

## RiskMetrics

**Purpose**: VaR, CVaR, Greeks at a point in time

### Attributes
- `var: dict[str, float]` - VaR by confidence level
- `cvar: dict[str, float]` - CVaR by confidence level
- `greeks: Greeks` - Sensitivities
- `as_of_date: date` - Valuation date
- `portfolio_id: str` - Links to Portfolio

### Invariants
- `CVaR[c] >= VaR[c]` for all confidence levels
- VaR and CVaR have same confidence levels

---

## StressScenario

**Purpose**: Market shock scenario definition

### Attributes
- `name: str` - Scenario name
- `shocks: dict[str, float]` - Risk factor to shock
- `description: str` - Narrative
- `date_calibrated: date` - When defined

### Invariants
- `name` must not be empty
- `shocks` must have at least one entry
- `|shock| < 5.0` (reasonable magnitude)

---

## Constraint

**Purpose**: Portfolio optimization constraint

### Attributes
- `type: ConstraintType` - sector_limit, position_limit, etc.
- `bounds: Bounds` - Lower and upper limits
- `securities: list[str]` - Symbols/sectors
- `name: str` - Human-readable label

### Invariants
- `bounds.lower <= bounds.upper` (feasibility)
- Certain types require non-empty securities
