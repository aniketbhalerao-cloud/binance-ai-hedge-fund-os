# ADR-017: Paper Trading Framework

## Status

Accepted

## Date

2026-08-04

## Context

The AI Trading Operating System now includes dedicated frameworks for market data, trading, strategies, risk management, order management, execution, exchange adapters, broker integration, portfolio management, position management, trade lifecycle management, performance analytics, and historical backtesting.

While the Backtesting Framework replays historical data, none of the frameworks can exercise a strategy against *live* market data before real capital is committed.

Running a strategy live to observe how it would behave in current market conditions — without ever placing a real order — is a distinct concern that must not be mixed into any live trading framework, and must never touch a real exchange.

The system therefore requires a dedicated Paper Trading Framework responsible for simulating live trading across the existing architecture, one market update at a time, deterministically and completely independent of any exchange.

---

## Decision

Introduce a standalone Paper Trading Framework that consumes live market data and drives it through the existing frameworks (Strategy → Risk → Order → Execution → Portfolio → Position → Trade → Performance) and produces immutable session metrics and snapshots.

The framework consists of:

- Paper Trading Engine
- Paper Trading Manager
- Feed
- Paper Broker
- Metrics
- History
- Registry
- Paper Trading Models
- Paper Trading Events

The framework consumes live `OHLCV` market updates and the standardized results produced by the existing frameworks, and drives those frameworks only through their public engines. No real order is ever placed.

No existing framework requires modification.

---

## Rationale

### Separation of Responsibilities

Each framework within the AI Trading Operating System owns a single responsibility.

The live frameworks answer:

**"What should happen, and what is happening, as trades occur?"**

Paper Trading answers:

**"How would this strategy behave against live data if it traded — without placing a real order?"**

Separating live simulation from the frameworks being simulated prevents paper trading from becoming tightly coupled with strategy, risk, execution, portfolio, position, trade, or performance logic.

---

### Exchange Independence

The Paper Trading Framework never communicates directly with:

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

This ensures identical simulation behaviour regardless of which broker would have executed the trades, and guarantees that a paper-trading session can never submit a real order.

---

### Feed Design

The Feed normalizes one live market update.

Responsibilities include:

- Live market data consumption
- Market update normalization
- Timestamp synchronization
- Session progression

The Feed is completely stateless and holds no business logic. It normalizes the current live update into the strategy context the pipeline consumes; the rolling market and session state live in the Registry-owned session, never in the Feed, so the live-update policy can evolve without touching simulation or metrics.

---

### Paper Broker Design

The Paper Broker simulates live fills strictly after the Execution Framework.

Responsibilities include:

- Live fill simulation
- Simulated slippage
- Simulated commission
- Simulated latency

The Paper Broker is invoked only after Execution has coordinated an order into a ready result. It never validates, sizes, or routes orders, and it never submits an order to an exchange or exchange adapter — those remain the responsibilities of the Execution Framework and the Exchange Adapter Framework. The broker computes only the fill economics, deterministically, from the session parameters and the live candle, and no real order is ever placed.

---

### Session Design

The durable state of a live session is an immutable Paper Session owned by the Registry.

Responsibilities include:

- Rolling market window
- Latest portfolio, position, and trade results
- Equity curve and returns
- Collected trades and fill history
- Session lifecycle state

Because paper trading is event-driven and long-lived, session state must persist across live updates. The Registry owns the running session, and the manager loads it, processes one update, and writes back a new immutable session — so the Feed and the calculators remain stateless while the session provides continuity.

---

### Metrics Design

Paper Trading Metrics derives live figures per update.

Responsibilities include:

- Total return
- Realized and unrealized PnL
- Sharpe ratio and maximum drawdown
- Win rate and profit factor
- Average trade, average holding time, and expectancy

Metrics are derived from the in-pipeline Performance Analytics result and the collected trades rather than recomputed independently, reusing existing analytics and avoiding duplication.

---

### Atomic Session Processing

Each live update is processed atomically.

The Paper Trading Manager coordinates:

Live Market Update

↓

Load Session

↓

Feed

↓

Strategy → Risk → Order → Execution

↓

Paper Broker

↓

Portfolio → Position → Trade

↓

Performance Analytics

↓

Paper Trading Metrics

↓

New Immutable Session

If the update fails, the session is not overwritten.

Partial session state is never persisted.

---

### Immutability

All paper-trading models are immutable frozen dataclasses.

Immutability applies to:

- Paper Trading Context
- Session parameters and simulated fills
- Paper Session
- Session metrics and summaries
- Session snapshots and results

Every monetary value uses Decimal, and metadata is exposed as a read-only mapping. Each update produces a new immutable session; existing sessions and snapshots are never mutated, which guarantees that reported state is safe to share, log, and reproduce.

---

### Error Handling

Session failures are isolated inside the framework.

Stage failures are translated into framework exceptions:

- FeedError
- BrokerError
- MetricsError
- HistoryError
- RegistryError

Any failure is published as a PaperTradingErrorOccurred event and returned as a failed PaperTradingResult. Internal implementation details never escape the framework, and no partial session is written on failure.

---

### Dependency Injection

All framework components are resolved through the existing Dependency Injection container.

Dependencies include:

- Paper Trading Engine
- Paper Trading Manager
- Feed
- Paper Broker
- Metrics
- History
- Registry
- Event Bus
- LoggerFactory

Every upstream engine — Strategy, Risk, Order, Execution, Portfolio, Position, Trade, and Performance — is an optional injected dependency, resolved only when already registered. No infrastructure is instantiated manually.

---

### Event-Driven Architecture

The framework publishes paper-trading events through the existing Event Bus.

Examples include:

- PaperTradingStarted
- PaperTradingStopped
- MarketDataProcessed
- PaperOrderFilled
- PaperTradeExecuted
- PaperSnapshotCreated
- PaperMetricsUpdated
- PaperSessionCompleted
- PaperSessionCancelled
- PaperTradingErrorOccurred

Events are published only after a consistent state, and consumers subscribe without requiring direct coupling to the framework.

---

### Thread Safety

The framework supports concurrent sessions.

Thread safety is achieved through:

- Stateless feed
- Stateless broker
- Stateless metrics calculator
- Thread-safe registry
- Atomic per-update processing
- Immutable context, session, models, and events

Shared mutable state is minimized, and one update is processed atomically before the next begins.

---

### Testability

The framework is fully testable without external services.

Tests use:

- Deterministic live candles
- A controllable fake strategy
- Fake upstream engines and standardized results

No exchange connectivity is required.

All tests remain deterministic, with no sleeps and no randomness, and no real orders are placed.

---

## Alternatives Considered

### Paper Trading Logic Inside the Trading Framework

Rejected.

The Trading Framework owns live application lifecycle.

Embedding live simulation and fill generation would violate the Single Responsibility Principle and couple orchestration with simulation.

---

### A Parallel Simulated Spine

Rejected.

Reimplementing strategy, risk, order, execution, portfolio, position, trade, and performance logic for live simulation would duplicate the entire system, drift from live behaviour, and break the reuse principle.

Paper trading instead drives the real frameworks through dependency injection.

---

### Paper Broker Duplicating Execution or the Exchange Adapter

Rejected.

Validating, sizing, or routing orders is the Execution Framework's responsibility, and submitting to a venue is the Exchange Adapter's responsibility.

The Paper Broker therefore acts strictly after Execution and computes only fill economics, so it never duplicates those responsibilities, never contacts an exchange, and never places a real order.

---

### Caller-Managed or Persisted Session State

Rejected.

The running session is the reproducible continuity of a live simulation across updates.

Requiring the caller to carry it, or introducing a persistence or caching layer inside the framework, would compromise atomicity and reproducibility and violate the framework's registry-owned, immutable design.

---

## Consequences

### Positive

- Clear separation of live simulation from live trading
- Exchange-independent, deterministic paper trading
- No real orders placed
- Full reuse of the existing frameworks
- Registry-owned, immutable session state
- Thread-safe, atomic per-update processing
- Event-driven architecture
- High testability
- Easy extension for advanced live-simulation capabilities

### Negative

- Additional architectural layer
- Additional coordination across the frameworks the manager drives per update

These trade-offs are acceptable because they preserve scalability, maintainability, and modularity.

---

## Related Components

- paper_trading/
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

**Sprint 4 – Task 24**

Key components include:

- DefaultPaperTradingEngine
- DefaultPaperTradingManager
- DefaultFeed
- DefaultPaperBroker
- DefaultPaperTradingMetrics
- DefaultPaperTradingHistory
- InMemoryPaperTradingRegistry

Supporting capabilities include:

- Live market data consumption
- Post-Execution fill simulation
- Registry-owned session state
- Atomic per-update orchestration
- Session metrics
- Append-only history
- Session registration
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

Future paper-trading capabilities may include:

- Live event-bus market feeds
- Multi-symbol and portfolio sessions
- Alternative fill and slippage models
- Live monitoring and dashboards
- Session persistence and resumption
- Advanced reporting
- Alerting and notifications
- Integration with the AI Decision Engine

These features should extend the existing framework without requiring architectural changes.

---

## Decision Summary

The Paper Trading Framework introduces a dedicated, exchange-independent layer that consumes live market data and drives it through the existing processing spine to simulate live trading without ever placing a real order.

By separating feed normalization, post-Execution fill simulation, registry-owned session state, atomic per-update orchestration, metrics, history, and registration into independent components while reusing the real frameworks through dependency injection and event-driven communication, the AI Trading Operating System remains modular, scalable, thread-safe, and ready for advanced live-simulation capabilities without modifying existing frameworks.
