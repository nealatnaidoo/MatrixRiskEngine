# Matrix Risk Engine - Architectural Decisions Log

**Version**: 1.0
**Date**: 2026-01-25
**Status**: Active
**Format**: Append-only (ADR pattern)

---

## Purpose

This log records significant architectural decisions made during Matrix Risk Engine development. Each decision includes context, options considered, decision rationale, and consequences.

---

## ADR-001: Technology Stack Selection

**Date**: 2026-01-25
**Status**: Accepted
**Deciders**: Solution Designer, Business Analyst

### Context
Need to select open-source tools for time series storage, backtesting, risk analytics, and reporting that meet enterprise-grade requirements while remaining cost-effective.

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| ORE + ArcticDB + VectorBT + QuantStats | Open source, mature, performant, integrates well | Multiple tools to integrate |
| QuantLib alone | Single library | Limited backtesting, no time series storage |
| Commercial (Bloomberg PORT, MSCI) | Full-featured | Expensive licensing ($100k+/year) |
| Build custom | Full control | Significant development effort |

### Decision
Selected: **ORE + ArcticDB + VectorBT + QuantStats**

### Rationale
- ORE: Industry-standard risk analytics (130+ instruments), QuantLib-based, open source
- ArcticDB: Bloomberg-backed, handles billions of rows, native Pandas integration
- VectorBT: Fastest Python backtester, vectorized operations
- QuantStats: Comprehensive tearsheets (50+ metrics), Apache 2.0 license

### Consequences
- **Positive**: Low/no licensing cost, mature tools, active communities
- **Negative**: Integration work required, multiple upgrade cycles to manage
- **Risks**: Tool deprecation, API breaking changes

---

## ADR-002: Hexagonal Architecture Adoption

**Date**: 2026-01-25
**Status**: Accepted
**Deciders**: Solution Designer

### Context
Need architecture pattern that enables testability, maintainability, and flexible technology swaps (e.g., replace VectorBT with another backtester).

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| Hexagonal (Ports & Adapters) | Testable, swappable adapters, clear boundaries | Initial complexity |
| Layered (traditional MVC) | Simple, familiar | Tight coupling, hard to test |
| Microservices | Independent scaling | Over-engineered for MVP |
| Monolith (no pattern) | Fast to build | Unmaintainable at scale |

### Decision
Selected: **Hexagonal Architecture**

### Rationale
- Core domain (Portfolio, RiskMetrics, etc.) isolated from infrastructure
- Adapters (ArcticDB, VectorBT, ORE) easily swappable
- Ports define contracts enabling test doubles
- Supports TDD workflow

### Consequences
- **Positive**: High testability, clear component boundaries, future-proof
- **Negative**: More initial setup, learning curve for hexagonal pattern
- **Structure**:
  - Core: Domain objects, domain services
  - Ports: DataPort, BacktestPort, RiskPort, ReportPort
  - Adapters: ArcticDBAdapter, VectorBTAdapter, OREAdapter, QuantStatsAdapter

---

## ADR-003: Phase Sequencing Strategy

**Date**: 2026-01-25
**Status**: Accepted
**Deciders**: Business Analyst

### Context
16-week MVP with 4 major capability areas (data, backtest, risk, optimization). Need to determine build order.

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| Data → Backtest → Risk → Optimization | Natural dependency order | Risk/optimization late |
| All parallel | Fastest if resources available | Integration nightmare |
| Risk first | Early risk capabilities | No data to analyze |
| Optimization first | Portfolio construction early | No backtest validation |

### Decision
Selected: **Data → Backtest → Risk → Optimization** (Sequential)

### Rationale
- Data layer is foundational (all other components depend on it)
- Backtest validates signals before risk/optimization layers use them
- Risk analytics builds on backtest results
- Optimization is final layer (requires alpha, risk model, constraints)

### Consequences
- **Positive**: Clear dependencies, incremental value delivery, testable milestones
- **Negative**: Risk/optimization capabilities available only in later phases
- **Phases**:
  - Phase 1 (Weeks 1-4): ArcticDB, versioning, point-in-time queries
  - Phase 2 (Weeks 5-8): VectorBT, transaction costs, QuantStats
  - Phase 3 (Weeks 9-12): ORE VaR/CVaR/Greeks, stress testing
  - Phase 4 (Weeks 13-16): Optimization, constraints, walk-forward

---

## ADR-004: ORE Integration Pattern

**Date**: 2026-01-25
**Status**: Proposed (pending Q1 resolution)
**Deciders**: TBD (depends on ORE-SWIG bindings availability)

### Context
ORE provides risk analytics (VaR, Greeks, stress testing). Need to determine integration method.

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| Python bindings (ORE-SWIG) | Native integration, fast, type-safe | May not cover all features |
| Subprocess (CLI) | Access all ORE features | Slower, serialization overhead |
| REST API wrapper | Network access, language agnostic | Deployment complexity |

### Decision
**Pending** - Prototype both options in Phase 3

### Rationale
- ORE-SWIG bindings may not expose all required analytics
- Prototype will determine coverage and performance
- Decision will be recorded when prototype completes

### Consequences
- **If Python bindings**: Faster execution, simpler code
- **If Subprocess**: More configuration, slower but complete coverage
- **Hybrid**: Use bindings where available, subprocess for gaps

---

## ADR-005: Transaction Cost Model

**Date**: 2026-01-25
**Status**: Accepted
**Deciders**: Solution Designer

### Context
Backtest requires transaction cost modeling for realistic performance estimation.

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| Linear (spread + commission) | Simple, deterministic, fast | Ignores market impact |
| Square-root (Almgren-Chriss) | Realistic for large trades | Requires ADV data, complex |
| Market microstructure | Most realistic | Very complex, data-intensive |
| No costs | Simplest | Unrealistic, overfits |

### Decision
Selected: **Linear model for MVP**

### Rationale
- Linear is sufficient for daily rebalancing with moderate AUM
- Market impact models require ADV data (not in scope)
- Can be extended post-MVP if needed

### Consequences
- **Positive**: Simple to implement, fast to compute
- **Negative**: May underestimate costs for large trades
- **Formula**: `cost = shares * price * (spread_bps + commission_bps) / 10000`

---

## ADR-006: Risk Model Sourcing

**Date**: 2026-01-25
**Status**: Accepted
**Deciders**: Solution Designer, Business Analyst

### Context
Portfolio optimization requires covariance matrix (risk model). Options: user-supplied vs system-calibrated.

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| User-supplied (CSV/Parquet) | Simple, user control | User must provide |
| System-calibrated | Automatic | Complex, compute-intensive |
| Commercial (Barra, Axioma) | High quality | Expensive licensing |

### Decision
Selected: **User-supplied for MVP**

### Rationale
- Commercial risk models require expensive licenses
- System calibration is complex (factor selection, estimation window, etc.)
- User-supplied allows flexibility (own factor model, third-party data)

### Consequences
- **Positive**: No licensing cost, user flexibility
- **Negative**: User responsible for risk model quality
- **Format**: CSV or Parquet with (N x N) covariance matrix

---

## ADR-007: Point-in-Time Implementation

**Date**: 2026-01-25
**Status**: Accepted
**Deciders**: Solution Designer

### Context
Backtests must avoid look-ahead bias. Data queries must return only data available as of a specified date.

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| ArcticDB versioning + as_of query | Native support, efficient | Requires careful versioning |
| Database snapshots | Simple concept | Storage-intensive |
| Event sourcing | Complete audit trail | Complex reconstruction |

### Decision
Selected: **ArcticDB versioning with as_of_date filtering**

### Rationale
- ArcticDB natively supports versioned snapshots
- as_of_date parameter filters to data available at query time
- Efficient storage (only changes stored, not full copies)

### Consequences
- **Positive**: Built-in versioning, efficient storage, fast queries
- **Negative**: Requires discipline in version tagging
- **Rule**: R2 enforces point-in-time correctness at query time

---

## Template for Future ADRs

```markdown
## ADR-XXX: [Decision Title]

**Date**: YYYY-MM-DD
**Status**: [Proposed | Accepted | Deprecated | Superseded]
**Deciders**: [Team members involved]

### Context
[What is the issue that we're seeing that is motivating this decision?]

### Options Considered
| Option | Pros | Cons |
|--------|------|------|
| Option 1 | ... | ... |
| Option 2 | ... | ... |

### Decision
Selected: **[Option chosen]**

### Rationale
[Why was this option chosen over others?]

### Consequences
- **Positive**: [Good outcomes]
- **Negative**: [Trade-offs, risks]
- **Notes**: [Additional context]
```

---

**End of Decisions Log**

**Note**: This log is append-only. Do not delete or modify existing entries. Only add new ADRs or update status fields.
