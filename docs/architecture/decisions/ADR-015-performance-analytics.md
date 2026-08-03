# ADR-015: Performance Analytics Framework

## Status

Accepted

## Date

2026-08-03

## Context

The AI Trading Operating System now includes dedicated frameworks for market data, trading, strategies, risk management, order management, execution, exchange adapters, broker integration, portfolio management, position management, and trade lifecycle management.

While these frameworks produce standardized results describing what happened, none of them interprets those results into performance metrics.

Measuring how the system performed — returns, risk-adjusted performance, trading statistics, and benchmark comparison — is a distinct concern that must not be mixed into portfolio valuation, position tracking, or trade lifecycle management.

The system therefore requires a dedicated Performance Analytics Framework responsible for analyzing completed trading activity and producing standardized, immutable performance metrics while remaining completely exchange-independent and strictly read-only.

---

## Decision

Introduce a standalone Performance Analytics Framework positioned at the end of the processing spine, responsible for analyzing completed trading activity after portfolio, position, and trade updates.

The framework consists of:

- Performance Engine
- Performance Manager
- Returns Calculator
- Risk Calculator
- Statistics Calculator
- Benchmarking Service
- Performance Registry
- Performance Models
- Performance Events

The framework consumes standardized `PortfolioResult`, `PositionResult`, `TradeResult`, and `ExecutionResult` objects and produces immutable performance models.

No existing framework requires modification.

---

## Rationale

### Separation of Responsibilities

Each framework within the AI Trading Operating System owns a single responsibility.

Portfolio, Position, and Trade Management answer:

**"What happened to capital, positions, and trades?"**

Performance Analytics answers:

**"How well did the system perform?"**

Separating measurement from the frameworks being measured prevents analytics from becoming tightly coupled with valuation, tracking, and lifecycle logic.

---

### Exchange Independence and Read-Only Boundary

The Performance Analytics Framework never communicates directly with:

- Binance
- REST APIs
- WebSockets
- Broker SDKs

Instead, it consumes standardized domain models such as:

- PortfolioResult
- PositionResult
- TradeResult
- ExecutionResult
- PerformanceContext

The framework is strictly read-only. It never executes trades, manages positions, modifies portfolio state, or feeds decisions back into execution. This ensures identical analytical behaviour regardless of which broker executed the underlying trades.

---

### Returns Analytics

The Returns Calculator derives return metrics from the analytical context.

Responsibilities include:

- Daily, weekly, monthly, quarterly, and yearly returns
- Total return
- Compound return
- CAGR
- Absolute and percentage return
- Realized and unrealized return
- Return on investment

Returns computation intentionally excludes risk and statistics.

---

### Risk Analytics

The Risk Calculator derives risk analytics from the returns series and equity curve.

Responsibilities include:

- Volatility
- Sharpe ratio
- Sortino ratio
- Calmar ratio
- Maximum and average drawdown
- Downside deviation
- Upside capture
- Risk/reward ratio
- Recovery factor

Risk computation is isolated from returns and statistics so that risk methodology can evolve independently.

---

### Trading Statistics

The Statistics Calculator derives trading statistics from completed trades.

Responsibilities include:

- Trade counts by status
- Win rate and loss rate
- Average and extreme profit and loss
- Profit factor and expectancy
- Average position size
- Holding time and trade duration
- Best and worst period

Statistics are derived only from the completed trade set carried by the context.

---

### Benchmark Comparison

The Benchmarking Service compares performance against an abstract benchmark.

Responsibilities include:

- Benchmark return
- Relative and excess return
- Alpha and beta
- Tracking error
- Information ratio
- Benchmark drawdown

The benchmark remains abstract and is supplied to the context as a standardized series, so future benchmarks integrate without modifying existing code.

---

### Performance Snapshots

Every completed analysis produces a single immutable snapshot.

Responsibilities include:

- Performance identifier
- Returns, risk, statistics, and benchmark metrics
- Portfolio, position, and trade summary
- Correlation identifier
- Metadata

Snapshots are read-only and provide the reproducible record for reporting and dashboards.

---

### Atomic Analysis Execution

Performance analysis executes atomically.

The Performance Manager coordinates:

Performance Context

↓

Returns Calculator

↓

Risk Calculator

↓

Statistics Calculator

↓

Benchmarking Service

↓

Performance Snapshot

↓

Registry

If any stage fails, no snapshot is registered.

Partial analyses are never persisted.

---

### Immutability

All performance models are immutable frozen dataclasses.

Immutability applies to:

- Performance Context
- Returns, risk, statistics, and benchmark metrics
- Performance snapshots
- Performance results

Every monetary value uses Decimal, and mappings are exposed as read-only views. Completed snapshots are never mutated, which guarantees that reported analytics are safe to share, log, and reproduce.

---

### Error Handling

Analysis failures are isolated inside the framework.

Stage failures are translated into framework exceptions:

- ReturnsCalculationError
- RiskCalculationError
- StatisticsCalculationError
- BenchmarkCalculationError
- PerformanceRegistryError

Any failure is published as a PerformanceErrorOccurred event and returned as a failed PerformanceResult. Internal implementation details never escape the framework, and no partial snapshot is ever registered.

---

### Dependency Injection

All framework components are resolved through the existing Dependency Injection container.

Dependencies include:

- Performance Engine
- Performance Manager
- Returns Calculator
- Risk Calculator
- Statistics Calculator
- Benchmarking Service
- Performance Registry
- Event Bus
- LoggerFactory

No infrastructure is instantiated manually.

---

### Event-Driven Architecture

The framework publishes performance events through the existing Event Bus.

Examples include:

- PerformanceAnalysisStarted
- ReturnsCalculated
- RiskCalculated
- StatisticsCalculated
- BenchmarkCalculated
- PerformanceSnapshotCreated
- PerformanceAnalysisCompleted
- PerformanceEngineStarted
- PerformanceEngineStopped
- PerformanceErrorOccurred

Events are published only after a successful analysis, and consumers subscribe without requiring direct coupling to the framework.

---

### Thread Safety

The framework supports concurrent analyses.

Thread safety is achieved through:

- Stateless returns calculator
- Stateless risk calculator
- Stateless statistics calculator
- Stateless benchmarking service
- Thread-safe registry
- Atomic analysis execution
- Immutable context and models

Shared mutable state is minimized.

---

### Testability

The framework is fully testable without external services.

Tests use:

- Fake standardized results
- Fake performance contexts
- Deterministic analytical series

No exchange connectivity is required.

All tests remain deterministic.

---

## Alternatives Considered

### Performance Logic Inside Portfolio Framework

Rejected.

Portfolio Management is responsible for valuation and accounting.

Embedding analytics would violate the Single Responsibility Principle and couple valuation with measurement.

---

### Performance Logic Inside Trade Framework

Rejected.

Trade Lifecycle is responsible for individual trade progression.

Performance analytics span portfolio, position, and trade data, and must remain independent of any single upstream framework.

---

### Feedback Into Execution

Rejected.

Allowing performance analytics to influence execution would break the read-only boundary and introduce hidden coupling between measurement and trading decisions.

Analytics must remain strictly read-only.

---

### Mutable or Persisted Performance State

Rejected.

Performance snapshots provide the reproducible record for reporting, dashboards, and attribution.

Allowing modification, or introducing a persistence or caching layer inside the framework, would compromise reproducibility and violate the framework's stateless, immutable design.

---

## Consequences

### Positive

- Clear separation of measurement from execution
- Exchange-independent, read-only analytics
- Immutable performance snapshots
- Thread-safe analysis
- Event-driven architecture
- High testability
- Easy extension for advanced analytics and reporting

### Negative

- Additional architectural layer
- Additional standardized analytical inputs required for series-based metrics

These trade-offs are acceptable because they preserve scalability, maintainability, and modularity.

---

## Related Components

- performance/
- trades/
- positions/
- portfolio/
- execution/
- trading/
- events/
- core/

---

## Implementation

Implemented during:

**Sprint 3 – Task 22**

Key components include:

- DefaultPerformanceEngine
- DefaultPerformanceManager
- DefaultReturnsCalculator
- DefaultRiskCalculator
- DefaultStatisticsCalculator
- DefaultBenchmarkingService
- InMemoryPerformanceRegistry

Supporting capabilities include:

- Returns analytics
- Risk analytics
- Trading statistics
- Benchmark comparison
- Performance snapshots
- Snapshot registration
- Structured logging
- Event publication

The framework integrates with:

- Portfolio Management Framework
- Position Management Framework
- Trade Lifecycle Framework
- Execution Framework
- Dependency Injection Container
- Event Bus
- LoggerFactory

No modifications to existing frameworks were required.

---

## Future Considerations

Future performance capabilities may include:

- Portfolio Analytics Dashboard
- Historical Performance Tracking
- Benchmark Expansion (BTC, ETH, NIFTY, S&P 500, NASDAQ, Custom Index)
- Performance Reporting
- Trade Attribution
- Rolling and Windowed Analytics
- Risk-Adjusted Performance Reporting
- Compliance and Regulatory Reporting
- Integration with the AI Decision Engine

These features should extend the existing framework without requiring architectural changes.

---

## Decision Summary

The Performance Analytics Framework introduces a dedicated, exchange-independent, read-only layer responsible for analyzing completed trading activity.

By separating returns, risk, statistics, and benchmark analysis into independent stateless components while integrating through dependency injection and event-driven communication, the AI Trading Operating System remains modular, scalable, thread-safe, and ready for advanced analytics and reporting capabilities without modifying existing frameworks.
