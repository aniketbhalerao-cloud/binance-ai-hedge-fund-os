# ADR-016: Backtesting Framework

## Status

Accepted

## Date

2026-08-03

## Context

The AI Trading Operating System now includes dedicated frameworks for market data, trading, strategies, risk management, order management, execution, exchange adapters, broker integration, portfolio management, position management, trade lifecycle management, and performance analytics.

While these frameworks describe live trading, none of them can evaluate a strategy over historical data before capital is committed.

Replaying historical market data through the full processing spine — to measure how a strategy would have performed — is a distinct concern that must not be mixed into any live framework, and must never touch a real exchange.

The system therefore requires a dedicated Backtesting Framework responsible for simulating historical trading across the existing architecture, deterministically and completely independent of any exchange.

---

## Decision

Introduce a standalone Backtesting Framework that replays historical market data through the existing frameworks (Strategy → Risk → Order → Execution → Portfolio → Position → Trade → Performance) and produces immutable backtest metrics and snapshots.

The framework consists of:

- Backtesting Engine
- Backtesting Manager
- Scheduler
- Simulator
- Metrics
- History
- Registry
- Backtesting Models
- Backtesting Events

The framework consumes historical `OHLCV` candles and the standardized results produced by the existing frameworks, and drives those frameworks only through their public engines.

No existing framework requires modification.

---

## Rationale

### Separation of Responsibilities

Each framework within the AI Trading Operating System owns a single responsibility.

The live frameworks answer:

**"What should happen, and what is happening, as trades occur?"**

Backtesting answers:

**"How would this strategy have performed over historical data?"**

Separating simulation from the frameworks being simulated prevents backtesting from becoming tightly coupled with strategy, risk, execution, portfolio, position, trade, or performance logic.

---

### Exchange Independence

The Backtesting Framework never communicates directly with:

- Binance
- REST APIs
- WebSockets
- Broker SDKs
- Exchange adapters

Instead, it consumes standardized domain models such as:

- OHLCV candles
- ExecutionResult
- PortfolioResult
- PositionResult
- TradeResult
- PerformanceResult

This ensures identical simulation behaviour regardless of which broker would have executed the trades, and guarantees that a backtest can never place a real order.

---

### Scheduler Design

The Scheduler progresses the historical timeline.

Responsibilities include:

- Candle iteration
- Timeline progression
- Timestamp synchronization
- Replay speed control

The scheduler is stateless and holds no business logic. It decides only which candle comes next — never what to do with it — so replay policy can evolve without touching simulation or metrics.

---

### Simulator Design

The Simulator simulates historical fills strictly after the Execution Framework.

Responsibilities include:

- Historical fill simulation
- Simulated slippage
- Simulated commission
- Simulated latency

The Simulator is invoked only after Execution has coordinated an order into a ready result. It never validates, sizes, or routes orders, and it never contacts an exchange or exchange adapter — those remain the responsibilities of the Execution Framework and the Exchange Adapter Framework. The Simulator computes only the fill economics, deterministically, from the simulation parameters and the historical candle.

---

### History Design

Backtesting History maintains an immutable simulation record.

Responsibilities include:

- Simulation timeline
- Simulation steps
- Simulation snapshots
- Replay history

History is append-only.

Historical records are never modified after creation, preserving a reproducible audit trail of the run.

---

### Metrics Design

Backtesting Metrics derives performance figures from the completed run.

Responsibilities include:

- CAGR and annual return
- Total return
- Sharpe and Sortino ratios
- Maximum drawdown
- Win rate and profit factor
- Recovery factor
- Average trade and average holding time
- Expectancy

Metrics are derived from the in-pipeline Performance Analytics result and the collected trades rather than recomputed independently, reusing existing analytics and avoiding duplication.

---

### Atomic Backtesting Execution

Backtest execution finalizes atomically.

The Backtesting Manager coordinates:

Historical Data

↓

Scheduler

↓

Strategy → Risk → Order → Execution

↓

Simulator

↓

Portfolio → Position → Trade

↓

Performance Analytics

↓

Backtesting Metrics

↓

Snapshot

If the run fails, no snapshot is registered.

Partial results are never persisted.

---

### Immutability

All backtesting models are immutable frozen dataclasses.

Immutability applies to:

- Backtesting Context
- Simulation parameters and simulated fills
- Backtest metrics and summaries
- Backtest snapshots
- Backtest results

Every monetary value uses Decimal, and metadata is exposed as a read-only mapping. Completed snapshots are never mutated, which guarantees that a reported backtest is safe to share, log, and reproduce.

---

### Error Handling

Backtest failures are isolated inside the framework.

Stage failures are translated into framework exceptions:

- SchedulerError
- SimulationError
- MetricsError
- HistoryError
- RegistryError

Any failure is published as a BacktestErrorOccurred event and returned as a failed BacktestResult. Internal implementation details never escape the framework, and no partial snapshot is registered.

---

### Dependency Injection

All framework components are resolved through the existing Dependency Injection container.

Dependencies include:

- Backtesting Engine
- Backtesting Manager
- Scheduler
- Simulator
- Metrics
- History
- Registry
- Event Bus
- LoggerFactory

Every upstream engine — Strategy, Risk, Order, Execution, Portfolio, Position, Trade, and Performance — is an optional injected dependency, resolved only when already registered. No infrastructure is instantiated manually.

---

### Event-Driven Architecture

The framework publishes backtest events through the existing Event Bus.

Examples include:

- BacktestStarted
- BacktestProgress
- BacktestPaused
- BacktestResumed
- BacktestCompleted
- BacktestCancelled
- SimulationStepCompleted
- BacktestSnapshotCreated
- BacktestMetricsUpdated
- BacktestErrorOccurred

Events are published only after a consistent state, and consumers subscribe without requiring direct coupling to the framework.

---

### Thread Safety

The framework supports concurrent runs.

Thread safety is achieved through:

- Stateless scheduler
- Stateless simulator
- Stateless metrics calculator
- Thread-safe registry
- Atomic snapshot registration
- Immutable context, models, and events

Shared mutable state is minimized.

---

### Testability

The framework is fully testable without external services.

Tests use:

- Deterministic historical candles
- A controllable fake strategy
- Fake upstream engines and standardized results

No exchange connectivity is required.

All tests remain deterministic, with no sleeps and no randomness.

---

## Alternatives Considered

### Backtesting Logic Inside the Strategy Framework

Rejected.

The Strategy Framework is responsible for generating signals.

Embedding historical replay and simulation would violate the Single Responsibility Principle and couple signal generation with orchestration.

---

### A Parallel Simulated Spine

Rejected.

Reimplementing strategy, risk, order, execution, portfolio, position, trade, and performance logic for simulation would duplicate the entire system, drift from live behaviour, and break the reuse principle.

Backtesting instead drives the real frameworks through dependency injection.

---

### Simulator Duplicating Execution or the Exchange Adapter

Rejected.

Validating, sizing, or routing orders is the Execution Framework's responsibility, and submitting to a venue is the Exchange Adapter's responsibility.

The Simulator therefore acts strictly after Execution and computes only fill economics, so it never duplicates those responsibilities or contacts an exchange.

---

### Mutable or Persisted Backtest State

Rejected.

Backtest snapshots and history provide the reproducible record for reporting, analysis, and comparison.

Allowing modification, or introducing a persistence or caching layer inside the framework, would compromise reproducibility and violate the framework's stateless, immutable design.

---

## Consequences

### Positive

- Clear separation of simulation from live trading
- Exchange-independent, deterministic backtesting
- Full reuse of the existing frameworks
- Immutable, append-only history
- Thread-safe runs
- Event-driven architecture
- High testability
- Easy extension for advanced backtesting capabilities

### Negative

- Additional architectural layer
- Additional coordination across the frameworks the manager drives

These trade-offs are acceptable because they preserve scalability, maintainability, and modularity.

---

## Related Components

- backtesting/
- market_data/
- strategies/
- risk/
- order_management/
- execution/
- portfolio/
- positions/
- trades/
- performance/
- events/
- core/

---

## Implementation

Implemented during:

**Sprint 4 – Task 23**

Key components include:

- DefaultBacktestEngine
- DefaultBacktestManager
- DefaultScheduler
- DefaultSimulator
- DefaultBacktestMetrics
- DefaultBacktestHistory
- InMemoryBacktestRegistry

Supporting capabilities include:

- Historical timeline scheduling
- Post-Execution fill simulation
- Pipeline orchestration
- Backtest metrics
- Append-only history
- Snapshot registration
- Structured logging
- Event publication

The framework integrates with:

- Market Data Framework
- Strategy Framework
- Risk Framework
- Order Management Framework
- Execution Framework
- Portfolio Management Framework
- Position Management Framework
- Trade Lifecycle Framework
- Performance Analytics Framework
- Dependency Injection Container
- Event Bus
- LoggerFactory

No modifications to existing frameworks were required.

---

## Future Considerations

Future backtesting capabilities may include:

- Walk-forward analysis
- Multi-symbol and portfolio backtests
- Parameter sweeps and optimization
- Alternative fill and slippage models
- Monte Carlo simulation
- Benchmark and buy-and-hold comparison
- Advanced reporting and visualization
- Integration with the AI Decision Engine

These features should extend the existing framework without requiring architectural changes.

---

## Decision Summary

The Backtesting Framework introduces a dedicated, exchange-independent layer that replays historical market data through the existing processing spine to evaluate strategies.

By separating scheduling, post-Execution fill simulation, orchestration, metrics, history, and registration into independent components while reusing the real frameworks through dependency injection and event-driven communication, the AI Trading Operating System remains modular, scalable, thread-safe, and ready for advanced backtesting capabilities without modifying existing frameworks.
