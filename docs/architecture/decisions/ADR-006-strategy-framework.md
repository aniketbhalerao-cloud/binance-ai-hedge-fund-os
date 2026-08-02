# ADR-006: Strategy Framework

## Status

Accepted

## Date

2026-08-02

## Context

The AI Trading Operating System is designed to support multiple trading strategies, including:

- RSI
- EMA
- MACD
- Bollinger Bands
- SuperTrend
- VWAP
- Turtle Trading
- AI Strategies
- Machine Learning Models
- Reinforcement Learning Models
- Composite Strategies

Each strategy implements different trading logic while sharing the same execution infrastructure.

Without a common framework, each strategy would need to manage:

- Market Data integration
- Lifecycle management
- Dependency Injection
- Logging
- Event publishing
- Signal creation
- Registration
- Configuration

This would result in duplicated infrastructure code, inconsistent implementations, and tight coupling between strategies and the rest of the trading platform.

The architecture therefore requires a generic Strategy Framework that provides common infrastructure while allowing strategies to remain independent and interchangeable.

---

## Decision

The system will implement a Strategy Framework that separates strategy infrastructure from trading algorithms.

The Strategy Framework consists of:

- Strategy Base Class
- Strategy Manager
- Strategy Registry
- Strategy Factory
- Strategy Context
- Trading Signal Models
- Strategy Events

The framework coordinates strategy execution but never contains trading algorithms.

Each concrete strategy is responsible only for analyzing market data and generating trading signals.

Strategies do not execute trades.

Strategies do not communicate directly with exchanges.

Strategies do not perform risk management.

Strategies remain independent and replaceable.

---

## Rationale

The Strategy Framework provides several architectural benefits.

### Separation of Concerns

The framework manages:

- Registration
- Discovery
- Lifecycle
- Execution
- Logging
- Event publishing

Individual strategies manage only trading logic.

This prevents duplication across strategy implementations.

---

### Pluggable Architecture

Strategies become plugins.

Adding a new strategy requires:

1. Creating a new strategy class.
2. Registering it with the Strategy Registry.

No existing framework code requires modification.

This satisfies the Open/Closed Principle.

---

### Stateless Execution

Strategies operate using a supplied immutable StrategyContext.

The StrategyContext contains all required market information, including:

- Market Snapshot
- Symbol
- Exchange
- Timeframe
- Recent Candles
- Recent Trades
- Order Book
- Timestamp
- Metadata

Strategies do not access infrastructure directly.

They never query caches or repositories.

This enables deterministic execution, replay compatibility, and easier testing.

---

### Standardized Signals

Strategies produce standardized TradingSignal objects.

Signals represent trading intent only.

Examples include:

- BUY
- SELL
- HOLD
- CLOSE
- REDUCE
- INCREASE

Signals contain metadata such as:

- Signal ID
- Strategy Name
- Symbol
- Direction
- Confidence
- Timestamp
- Additional Metadata

Signals remain immutable.

No strategy produces executable orders.

---

### Strategy Independence

Strategies never communicate with each other.

Each enabled strategy evaluates the same StrategyContext independently.

The Strategy Manager coordinates execution and collects generated signals.

This avoids hidden dependencies and keeps strategies modular.

---

### Testability

Strategies can be tested independently by providing a StrategyContext and verifying the resulting TradingSignal.

No Event Bus, database, exchange, or network connection is required.

Framework components can also be tested independently using fake strategies.

---

## Alternatives Considered

### Hardcoded Strategies

Advantages:

- Simple initial implementation.

Disadvantages:

- Difficult to extend.
- Requires modifying framework code for every new strategy.
- Violates Open/Closed Principle.

Rejected.

---

### Strategies Executing Orders

Advantages:

- Fewer processing stages.

Disadvantages:

- Couples decision-making with execution.
- Bypasses risk management.
- Difficult testing.
- Poor maintainability.

Rejected.

---

### Exchange-Specific Strategies

Advantages:

- Direct access to exchange features.

Disadvantages:

- Vendor lock-in.
- Reduced portability.
- Strategies become dependent on exchange APIs.

Rejected.

---

## Consequences

### Positive

- Modular strategy architecture.
- Easy strategy replacement.
- Exchange independence.
- Replay compatibility.
- Improved testability.
- Consistent execution flow.
- Supports unlimited future strategies.
- Clear separation between decision-making and execution.

### Negative

- Additional framework components.
- More interfaces to maintain.
- Slight increase in abstraction.

These trade-offs are acceptable because they significantly improve maintainability, extensibility, and long-term scalability.

---

## Related Components

- strategies/
- strategies/base.py
- strategies/manager.py
- strategies/registry.py
- strategies/factory.py
- strategies/context.py
- strategies/signals.py
- strategies/interfaces.py
- strategies/events.py
- market_data/
- trading/
- events/
- core/

---

## Implementation

Implemented during:

Sprint 2 – Task 13

Key components include:

- Base Strategy
- Strategy Manager
- Strategy Registry
- Strategy Factory
- Strategy Context
- Trading Signals
- Strategy Events
- Dependency Injection Integration

The Strategy Framework provides reusable infrastructure for all future trading strategies while remaining independent of any specific trading algorithm.

---

## Future Considerations

Future enhancements may include:

- Strategy configuration profiles
- Dynamic strategy loading
- Plugin marketplace
- Strategy versioning
- Multi-timeframe execution
- Composite strategies
- Ensemble AI strategies
- Distributed strategy execution
- Strategy performance metrics
- Strategy sandboxing
- Hot reloading of strategies

These enhancements should preserve the framework's core principle of separating strategy infrastructure from trading algorithms and maintaining standardized TradingSignal outputs.