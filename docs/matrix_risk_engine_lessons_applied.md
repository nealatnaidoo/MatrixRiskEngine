# Matrix Risk Engine - Lessons Applied

**Version**: 1.0
**Date**: 2026-01-25
**Source**: `/Users/naidooone/Developer/claude/prompts/devlessons.md`

---

## Critical Lessons for This Project

### Lesson #2: Version Pinning & Dependencies

**Problem**: Stack fragility with C++/Python bindings
- ORE-SWIG breaks with specific Python/NumPy versions
- ArcticDB has strict Pandas version requirements
- VectorBT conflicts with newer scipy

**Applied**:
```toml
# pyproject.toml - exact pins with documented reasons
numpy>=1.21.0,<1.25.0       # ORE-SWIG sensitive to array interface
arcticdb>=4.0.0,<5.0.0      # API breaking changes between majors
vectorbt>=0.25.3,<0.26.0    # Package structure changes
cvxpy>=1.3.0,<1.5.0         # Convex solver - API sensitive
pandas>=2.0.0,<2.1.0        # ArcticDB compatibility
quantstats>=0.0.62          # Stable release
```

---

### Lesson #4: Hexagonal Architecture for C++ Integration

**Problem**: C++ binding complexity leaking into core logic

**Applied**: Complete isolation via Port interface
```python
# src/core/ports/risk_port.py
class RiskPort(Protocol):
    def calculate_var(self, portfolio: Portfolio, ...) -> dict: ...
    def compute_greeks(self, portfolio: Portfolio, ...) -> dict: ...

# src/adapters/ore_adapter.py - production (C++ bindings)
# tests/stubs/stub_ore_adapter.py - testing (zero C++ runtime)
```

**Rule**: Core components NEVER import ORE directly.

---

### Lesson #13: Deterministic Core & Dependency Injection

**Problem**: Non-reproducible backtests

**Applied**:
- **NO** `datetime.now()` - inject `as_of_date` parameter
- **NO** `np.random.seed()` - inject seed as explicit parameter
- **NO** global state - inject all adapters
- Same input + same time + same seed = identical results

```python
def run_backtest(
    signals: pd.DataFrame,
    *,
    data_port: DataPort,
    as_of_date: date,
    random_seed: int | None = None
) -> BacktestResult:
```

---

### Lesson #8: Atomic Component Pattern

**Applied Structure**:
```
src/
├── core/
│   ├── domain/         # Pure domain objects
│   ├── ports/          # Protocol interfaces
│   └── services/       # Domain services
├── adapters/           # I/O implementations
└── cli/                # CLI entry points
```

Each component has:
- `models.py` - frozen Input/Output dataclasses
- `ports.py` - Protocol interfaces
- `contract.md` - specification

---

### Lesson #5: Quality Gates After Every Task

**Applied Gates**:
- `artifacts/quality_gates_run.json` status = "PASS"
- `artifacts/test_report.json` exists (100% tests passing)
- No `artifacts/test_failures.json` file present
- `mypy --strict src/` returns zero errors
- Test coverage >= 80%

**DO NOT mark task complete unless gates pass.**

---

### Lesson #30, #47: Test Double Synchronization

**Problem**: Stub adapters drift from production adapters

**Applied**:
- StubOREAdapter signature must match OREAdapter
- StubDataAdapter parameters must match ArcticDBAdapter
- Automated gate: verify signature parity after every adapter change

---

### Lesson #48, #54: Data Schema Versioning

**Applied for ArcticDB**:
- Store schema version as metadata
- Integration tests use same migration path as production
- Verify data consistency: no gaps >1 day for daily data
- Make ingestion idempotent (allow re-runs safely)

---

## Pre-Flight Checklist

- [ ] Create component stubs with Port interfaces
- [ ] Create dependency pinning in pyproject.toml with version comments
- [ ] Create stub adapters for testing (StubDataAdapter, StubRiskAdapter)
- [ ] Quality gates script: `python -m pytest` with coverage
- [ ] Verify ORE-SWIG installation on target Python version
- [ ] Test ArcticDB instance running locally

---

## Lesson Citation Index

| Topic | Lesson # | Applied To |
|-------|----------|------------|
| Dependency pinning | #2 | pyproject.toml |
| Hexagonal architecture | #4 | src/ structure |
| Quality gates | #5 | artifacts/ |
| Atomic components | #8 | Component pattern |
| Deterministic core | #13 | Backtest reproducibility |
| datetime handling | #27 | as_of_date injection |
| Test doubles | #30, #47 | Stub adapters |
| Schema versioning | #48, #54 | ArcticDB |

---

**End of Lessons Applied Document**
