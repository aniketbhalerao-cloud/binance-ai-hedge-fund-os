# ADR-013: Position Management Framework

## Status

Accepted

## Date

2026-08-02

## Context

The AI Trading Operating System now includes dedicated frameworks for market data, trading, strategies, risk management, order management, execution, exchange adapters, broker integration, and portfolio management.

While the Portfolio Management Framework maintains the aggregate state of the portfolio—including holdings, cash, valuation, allocation, and performance—it does not maintain the lifecycle of individual trading positions.

A separate framework is required to manage the complete lifecycle of each trading position from opening through partial reductions and final closure.

The Position Management Framework provides a standardized, exchange-independent representation of individual positions while integrating seamlessly with the Portfolio Management Framework.

---

## Decision

Introduce a standalone Position Management Framework responsible for managing individual trading positions after portfolio updates.

The framework consists of:

- Position Engine
- Position Manager
- Position Tracker
- Position Lifecycle
- Position Calculator
- Position History
- Position Metrics
- Position Registry
- Position Models
- Position Events

The framework consumes standardized PortfolioResult objects and produces immutable position models.

No existing framework is modified.

---

## Rationale

### Separation of Responsibilities

Each framework within the AI Trading Operating System owns a single responsibility.

Portfolio Management answers:

**"What assets does the portfolio currently contain?"**

Position Management answers:

**"How has each individual position evolved throughout its lifecycle?"**

Keeping these responsibilities separate prevents portfolio accounting from becoming tightly coupled with individual position management.

---

### Exchange Independence

The Position Management Framework never communicates directly with:

- Binance
- REST APIs
- WebSockets
- Broker SDKs

Instead, it consumes standardized domain models such as:

- PortfolioResult
- PositionContext
- Portfolio Ledger Entries

This ensures identical position behavior regardless of which exchange executes trades.

---

### Position Tracking

Position tracking is responsible for maintaining ownership of individual trades.

Responsibilities include:

- Position creation
- Position updates
- Position closure
- Partial reductions
- Quantity tracking
- Average entry price
- Average exit price

Tracking intentionally excludes valuation and portfolio calculations.

---

### Position Lifecycle

Lifecycle management is isolated from position tracking.

Responsibilities include:

- State transitions
- State validation
- Lifecycle events

Supported lifecycle states include:

- Pending
- Open
- Partially Closed
- Closed
- Cancelled

Separating lifecycle management allows future workflows to evolve independently from quantity calculations.

---

### Position Calculator

The calculator performs all financial calculations related to individual positions.

Responsibilities include:

- Average entry price
- Average exit price
- Realized P&L
- Unrealized P&L
- Position duration
- Total traded quantity

The calculator consumes standardized position models and contains no exchange-specific logic.

---

### Position History

Position History maintains an immutable audit trail.

Responsibilities include:

- Trade history
- Position timeline
- Historical state
- Position snapshots

History is append-only.

Historical records are never modified after creation.

---

### Position Metrics

Metrics are derived from completed position history.

Responsibilities include:

- Holding time
- Win rate
- Average profit
- Average loss
- Position statistics
- Performance metrics

Metrics are never stored independently.

They are always derived from historical records.

---

### Atomic Position Updates

Position updates occur atomically.

The Position Manager coordinates:

Portfolio Update

↓

History

↓

Calculator

↓

Lifecycle

↓

Tracker

↓

Metrics

↓

Updated Position

If any stage fails, the previous position state remains unchanged.

Partial updates are never persisted.

---

### Dependency Injection

All framework components are resolved through the existing Dependency Injection container.

Dependencies include:

- Position Engine
- Position Manager
- Position Tracker
- Position Lifecycle
- Position Calculator
- Position History
- Position Metrics
- Event Bus
- LoggerFactory

No infrastructure is manually instantiated.

---

### Event-Driven Architecture

The framework publishes position lifecycle events through the existing Event Bus.

Examples include:

- PositionOpened
- PositionUpdated
- PositionPartiallyClosed
- PositionClosed
- PositionHistoryUpdated
- PositionMetricsUpdated
- PositionSnapshotCreated
- PositionStateChanged
- PositionErrorOccurred

Consumers subscribe to these events without requiring direct framework coupling.

---

### Thread Safety

The framework supports concurrent position updates.

Thread safety is achieved through:

- Stateless calculator
- Stateless history service
- Stateless metrics service
- Thread-safe registry
- Atomic position updates
- Protected mutable state

Shared mutable state is minimized.

---

### Testability

The framework is fully testable without external services.

Tests use:

- Fake portfolio updates
- Fake position components
- Standardized position models

No exchange connectivity is required.

All tests remain deterministic.

---

## Alternatives Considered

### Position Logic Inside Portfolio Framework

Rejected.

Portfolio Management and Position Management solve different problems.

Combining them would violate the Single Responsibility Principle and tightly couple aggregate portfolio accounting with individual position tracking.

---

### Position Logic Inside Execution Framework

Rejected.

Execution is responsible for coordinating order submission.

Position management begins only after portfolio updates have been completed.

---

### Mutable Position History

Rejected.

Historical records form the audit trail for analytics, reporting, and replay.

Allowing modification would compromise data integrity and reproducibility.

---

## Consequences

### Positive

- Clear separation of responsibilities
- Exchange-independent position management
- Immutable position history
- Thread-safe updates
- Event-driven architecture
- Highly testable design
- Easy extension for advanced position features

### Negative

- Additional architectural layer
- Increased coordination between framework components

These trade-offs are acceptable because they preserve scalability, maintainability, and modularity.

---

## Related Components

- positions/
- portfolio/
- execution/
- exchange_adapters/
- adapters/binance/
- trading/
- events/
- core/

---

## Implementation

Implemented during:

**Sprint 3 – Task 20**

Key components include:

- DefaultPositionEngine
- DefaultPositionManager
- DefaultPositionTracker
- DefaultPositionLifecycle
- DefaultPositionCalculator
- DefaultPositionHistory
- DefaultPositionMetrics
- InMemoryPositionRegistry

Supporting capabilities include:

- Position tracking
- Lifecycle management
- Average entry and exit calculation
- Realized and unrealized P&L
- Position duration
- Position history
- Position metrics
- Position snapshots
- Structured logging
- Event publication

The framework integrates with:

- Portfolio Management Framework
- Execution Framework
- Exchange Adapter Framework
- Binance Spot Adapter
- Dependency Injection Container
- Event Bus
- LoggerFactory

No modifications to existing frameworks were required.

---

## Future Considerations

Future position capabilities may include:

- Multi-leg Positions
- Options Positions
- Futures Positions
- Hedged Positions
- Tax Lot Accounting
- Position Attribution
- Position Replay
- Advanced Position Analytics
- Portfolio–Position Synchronization
- Cross-Account Position Tracking

These features should extend the existing framework without requiring architectural changes.

---

## Decision Summary

The Position Management Framework introduces a dedicated, exchange-independent layer responsible for managing the complete lifecycle of individual trading positions.

By separating position tracking, lifecycle management, calculations, history, and metrics into independent components while integrating through dependency injection and event-driven communication, the AI Trading Operating System remains modular, scalable, thread-safe, and ready for advanced trading capabilities without modifying existing frameworks.