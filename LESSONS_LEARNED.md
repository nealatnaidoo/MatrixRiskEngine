# Matrix Risk Engine - Lessons Learned

## Critical Lessons from Development

### Lesson 1: Stress Test P&L Calculation - Weight Normalization Required

**Problem**: The `stress_test()` method used `positions * price * shock` which double-counted position size, showing a -$112M loss on a $10M portfolio.

**Root Cause**: Mixing dollar amounts (positions: `{"AAPL": $2M}`) with percentage shocks, then applying shocks to position values that were already in dollars.

**Solution**: Use weight-normalized formula:
```python
# WRONG: positions are already in dollars
pnl = position_value * price * shock  # Double-counts!

# CORRECT: use weights as percentages of NAV
pnl = NAV * weight * shock
# Example: $10M * 0.20 * -0.10 = -$200K loss for 20% position with 10% drop
```

**Evidence**: `src/adapters/ore_adapter.py` lines 264-329

**Prevention Checklist**:
- [ ] Always verify units in financial calculations (dollars vs shares vs percentages)
- [ ] Sanity check: stress test loss should be proportional to shock magnitude
- [ ] Add assertion: `abs(pct_change) <= abs(max_shock) * 1.1` (allow 10% margin)

---

### Lesson 2: Functional Validation > Unit Test Coverage Percentage

**Problem**: Attempted to increase coverage from 54% to 80% by adding 5 test files. All failed due to API mismatches between test assumptions and actual implementations.

**Key Finding**: Functional validation scripts caught the stress test bug that unit tests missed.

**Solution**: For complex financial calculations, prioritize:
1. Functional tests that exercise real workflows end-to-end
2. Historical scenario replay (known market events with documented outcomes)
3. Model backtesting (VaR predictions vs actual losses)

**Scripts Created**:
- `scripts/var_backtest.py` - Kupiec POF test for VaR model validation
- `scripts/historical_scenarios.py` - Replay 2008 Crisis, COVID crash, etc.
- `scripts/risk_validation_report.py` - Comprehensive risk report

**Prevention Checklist**:
- [ ] Before adding unit tests, read actual implementation code
- [ ] Create functional validation scripts for financial calculations
- [ ] Run historical scenario replay after any risk calculation changes

---

### Lesson 3: Module Import Issues - Script Path Setup

**Problem**: Scripts in `scripts/` directory couldn't import from `src/` package:
```
ModuleNotFoundError: No module named 'src'
```

**Solution**: Add at top of each script:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
```

**Better Long-term Solution**: Use `pip install -e .` for development mode installation.

**Prevention Checklist**:
- [ ] Add path setup boilerplate to all scripts in `scripts/` directory
- [ ] Consider using `pip install -e .` for proper package installation
- [ ] Document import requirements in script headers

---

### Lesson 4: VaR Model Validation - Kupiec POF Test

**Learning**: After implementing VaR, validate it using Kupiec Proportion of Failures test:
- For 95% VaR: expect ~5% of days to breach (actual loss > VaR estimate)
- For 99% VaR: expect ~1% of days to breach

**Implementation**:
```python
# Kupiec POF test
expected_breach_rate = 1 - confidence_level  # e.g., 0.05 for 95% VaR
actual_breach_rate = breaches / total_days

# LR statistic (should be < 3.84 for 95% confidence)
lr_pof = -2 * (x * log(p / (x/n)) + (n-x) * log((1-p) / (1-x/n)))
```

**Prevention Checklist**:
- [ ] Run VaR backtest after any risk model changes
- [ ] Breach rate should be within 20% of expected rate
- [ ] Check for breach clustering (independence test)

---

### Lesson 5: Hexagonal Architecture - Clean Ports Enable Testing

**Benefit**: `RiskPort` protocol interface isolated risk logic from `OREAdapter`:
- `StubOREAdapter` enables unit testing without C++ ORE libraries
- Tests run in milliseconds vs seconds
- CI/CD doesn't need heavy dependencies

**Pattern**:
```python
# Port (interface)
class RiskPort(Protocol):
    def calculate_var(self, portfolio, market_data, ...) -> dict: ...

# Adapter (implementation)
class OREAdapter:  # implements RiskPort
    def calculate_var(self, portfolio, market_data, ...) -> dict:
        # Real ORE implementation

# Stub (testing)
class StubOREAdapter:  # also implements RiskPort
    def calculate_var(self, portfolio, market_data, ...) -> dict:
        return {"95%": -50000, "99%": -75000}  # Fixed test values
```

**Prevention Checklist**:
- [ ] Define ports as Protocol classes in `src/core/ports/`
- [ ] Adapters in `src/adapters/` implement ports
- [ ] Create stubs in `tests/stubs/` for unit testing
- [ ] Never import adapters directly in core domain code

---

## Quick Reference

| Issue | Solution | File |
|-------|----------|------|
| Stress test P&L wrong | Use `NAV * weight * shock` | `ore_adapter.py:264-329` |
| Can't import src | Add `sys.path.insert` | All `scripts/*.py` |
| VaR validation | Kupiec POF test | `scripts/var_backtest.py` |
| Test without ORE | Use stub adapters | `tests/stubs/` |

## Evidence Files

- Stress test fix: `src/adapters/ore_adapter.py`
- VaR backtest: `scripts/var_backtest.py`
- Historical replay: `scripts/historical_scenarios.py`
- Risk report: `scripts/risk_validation_report.py`
- Validation report output: `risk_reports/risk_validation_report_*.json`
