# ADR-014: Trade Lifecycle Framework

## Status

Accepted

## Date

2026-08-02

## Context

The AI Trading Operating System now includes dedicated frameworks for market data, trading, strategies, risk management, order management, execution, exchange adapters, broker integration, portfolio management, and position management.

While the Position Management Framework maintains the lifecycle of positions, it does not manage the lifecycle of individual trades.

A position may consist of multiple entries, exits, and partial fills, while each trade represents a distinct transaction that must be tracked independently.

The system therefore requires a dedicated Trade Lifecycle Framework responsible for managing individual trades from creation until completion while remaining completely exchange-independent.

---

## Decision

Introduce a standalone Trade Lifecycle Framework responsible for managing individual trades after Position Management updates.

The framework consists of:

- Trade Engine
- Trade Manager
- Trade Tracker
- Trade Matcher
- Trade Lifecycle
- Trade History
- Trade Analytics
- Trade Registry
- Trade Models
- Trade Events

The framework consumes standardized `PositionResult` objects and produces immutable trade models.

No existing framework requires modification.

---

## Rationale

### Separation of Responsibilities

Each framework within the AI Trading Operating System owns a single responsibility.

Position Management answers:

**"What is the lifecycle of this trading position?"**

Trade Lifecycle answers:

**"How did each individual trade progress from entry to exit?"**

Separating these concerns prevents position management from becoming tightly coupled with trade tracking and analytics.

---

### Exchange Independence

The Trade Lifecycle Framework never communicates directly with:

- Binance
- REST APIs
- WebSockets
- Broker SDKs

Instead, it consumes standardized domain models such as:

- PositionResult
- TradeContext
- Position Updates

This ensures identical trade behaviour regardless of which broker executes the trade.

---

### Trade Tracking

Trade Tracking is responsible for maintaining the state of individual trades.

Responsibilities include:

- Trade creation
- Trade updates
- Trade closure
- Quantity tracking
- Fill aggregation

Tracking intentionally excludes analytics and reporting.

---

### Trade Matching

Trade Matching correlates trade entries and exits.

Responsibilities include:

- Entry matching
- Exit matching
- Partial fill matching
- Trade completion
- Fill correlation

Matching is isolated from tracking so that matching algorithms can evolve independently.

---

### Trade Lifecycle

Lifecycle management is isolated from trade tracking.

Responsibilities include:

- State validation
- State transitions
- Lifecycle events

Supported lifecycle states include:

- Pending
- Open
- Partially Filled
- Filled
- Closed
- Cancelled

Separating lifecycle management allows future workflows to evolve without changing tracking logic.

---

### Trade History

Trade History maintains an immutable audit trail.

Responsibilities include:

- Trade timeline
- Fill history
- Historical state
- Trade snapshots

History is append-only.

Historical records are never modified after creation.

---

### Trade Analytics

Trade Analytics derives statistics from completed trade history.

Responsibilities include:

- Holding time
- Trade duration
- Gross profit
- Net profit
- Win/Loss statistics
- Trade analytics

Analytics are always derived from immutable historical records rather than stored independently.

---

### Atomic Trade Updates

Trade updates occur atomically.

The Trade Manager coordinates:

Position Update

↓

Tracker

↓

Matcher

↓

Lifecycle

↓

History

↓

Analytics

↓

Updated Trade

If any stage fails, the previous trade state remains unchanged.

Partial updates are never persisted.

---

### Dependency Injection

All framework components are resolved through the existing Dependency Injection container.

Dependencies include:

- Trade Engine
- Trade Manager
- Trade Tracker
- Trade Matcher
- Trade Lifecycle
- Trade History
- Trade Analytics
- Event Bus
- LoggerFactory

No infrastructure is instantiated manually.

---

### Event-Driven Architecture

The framework publishes trade lifecycle events through the existing Event Bus.

Examples include:

- TradeOpened
- TradeUpdated
- TradeMatched
- TradePartiallyFilled
- TradeFilled
- TradeClosed
- TradeHistoryUpdated
- TradeAnalyticsUpdated
- TradeStateChanged
- TradeErrorOccurred

Consumers subscribe to these events without requiring direct coupling to the framework.

---

### Thread Safety

The framework supports concurrent trade updates.

Thread safety is achieved through:

- Stateless matcher
- Stateless history service
- Stateless analytics service
- Thread-safe registry
- Atomic trade updates
- Protected mutable state

Shared mutable state is minimized.

---

### Testability

The framework is fully testable without external services.

Tests use:

- Fake position updates
- Fake trade components
- Standardized trade models

No exchange connectivity is required.

All tests remain deterministic.

---

## Alternatives Considered

### Trade Logic Inside Position Framework

Rejected.

Position Management and Trade Lifecycle solve different problems.

Combining them would violate the Single Responsibility Principle and tightly couple position management with trade-level tracking.

---

### Trade Logic Inside Execution Framework

Rejected.

Execution is responsible for coordinating order execution.

Trade lifecycle begins only after completed position updates.

---

### Mutable Trade History

Rejected.

Historical records provide the audit trail for reporting, analytics, attribution, and replay.

Allowing modifications would compromise auditability and reproducibility.

---

## Consequences

### Positive

- Clear separation of responsibilities
- Exchange-independent trade management
- Immutable trade history
- Thread-safe updates
- Event-driven architecture
- High testability
- Easy extension for advanced trade capabilities

### Negative

- Additional architectural layer
- Increased coordination between framework components

These trade-offs are acceptable because they preserve scalability, maintainability, and modularity.

---

## Related Components

- trades/
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

**Sprint 3 – Task 21**

Key components include:

- DefaultTradeEngine
- DefaultTradeManager
- DefaultTradeTracker
- DefaultTradeMatcher
- DefaultTradeLifecycle
- DefaultTradeHistory
- DefaultTradeAnalytics
- InMemoryTradeRegistry

Supporting capabilities include:

- Trade tracking
- Fill aggregation
- Entry and exit matching
- Lifecycle management
- Trade history
- Trade analytics
- Trade snapshots
- Structured logging
- Event publication

The framework integrates with:

- Position Management Framework
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

Future trade capabilities may include:

- Multi-leg Trades
- Basket Trades
- Options Trades
- Futures Trades
- Smart Execution Analytics
- Trade Attribution
- Trade Replay
- Compliance Reporting
- Advanced Performance Reporting
- Cross-Account Trade Tracking

These features should extend the existing framework without requiring architectural changes.

---

## Decision Summary

The Trade Lifecycle Framework introduces a dedicated, exchange-independent layer responsible for managing the complete lifecycle of individual trades.

By separating trade tracking, matching, lifecycle management, history, and analytics into independent components while integrating through dependency injection and event-driven communication, the AI Trading Operating System remains modular, scalable, thread-safe, and ready for advanced trading capabilities without modifying existing frameworks.