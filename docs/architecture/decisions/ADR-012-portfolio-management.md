# ADR-012: Portfolio Management Framework

## Status

Accepted

## Date

2026-08-02

## Context

The AI Trading Operating System now includes frameworks for market data, trading, strategies, risk management, order management, execution, exchange adapters, and broker integration through the Binance Spot Adapter.

After a trade has been successfully executed, the system requires a dedicated framework responsible for maintaining portfolio state, including holdings, cash balances, portfolio valuation, allocations, accounting, and performance.

These responsibilities are fundamentally different from trade execution and therefore should not be implemented within the Execution Framework or Exchange Adapter Framework.

A dedicated Portfolio Management Framework is required to provide a standardized, exchange-independent representation of portfolio state across the entire trading system.

---

## Decision

Introduce a standalone Portfolio Management Framework responsible for maintaining portfolio state after completed executions.

The framework consists of:

- Portfolio Engine
- Portfolio Manager
- Holdings Manager
- Cash Manager
- Portfolio Accounting
- Portfolio Valuation
- Portfolio Allocation
- Portfolio Performance
- Portfolio Registry
- Portfolio Models
- Portfolio Events

The framework consumes standardized `ExecutionResult` objects and updates immutable portfolio models.

It remains completely independent of exchanges, execution engines, and trading strategies.

---

## Rationale

### Separation of Responsibilities

Each framework within the AI Trading Operating System owns one responsibility.

Execution Framework answers:

**"How should orders be executed?"**

Portfolio Management Framework answers:

**"What does the portfolio look like after execution?"**

Keeping these responsibilities separate prevents execution logic from becoming coupled with accounting and valuation.

---

### Exchange Independence

The Portfolio Management Framework never communicates directly with:

- Binance
- REST APIs
- WebSockets
- Broker SDKs

Instead, it consumes standardized domain models such as:

- ExecutionResult
- PortfolioContext
- Market Prices

This allows identical portfolio calculations regardless of which broker executes trades.

---

### Holdings Management

Holdings represent the current ownership of assets.

Responsibilities include:

- Position creation
- Quantity updates
- Position closure
- Average cost calculation
- Cost basis maintenance

Holdings intentionally exclude:

- Market prices
- Portfolio valuation
- Performance calculations

This separation keeps holdings deterministic and reusable.

---

### Cash Management

Cash is managed independently from holdings.

Responsibilities include:

- Available cash
- Reserved cash
- Deposits
- Withdrawals
- Trade settlements

Separating cash from holdings simplifies accounting and prevents unnecessary coupling.

---

### Portfolio Valuation

Portfolio valuation calculates the current financial value of the portfolio.

Inputs include:

- Holdings
- Cash balances
- Standardized market prices

Outputs include:

- Market value
- Cost basis
- Unrealized P&L
- Realized P&L
- Total portfolio value

Valuation consumes standardized market prices rather than exchange-specific data.

---

### Portfolio Accounting

Accounting records completed executions.

Responsibilities include:

- Portfolio ledger
- Trade accounting
- Cost basis tracking
- Cash accounting

Accounting records historical facts.

It deliberately does not calculate current market value.

---

### Asset Allocation

Portfolio allocation is derived from the current portfolio state.

Examples include:

- Position weight
- Cash allocation
- Asset allocation
- Portfolio concentration

Allocation is never treated as persistent source data.

Instead, it is recalculated from current portfolio values whenever required.

---

### Portfolio Performance

Performance calculations are separated from valuation.

Responsibilities include:

- Daily return
- Portfolio return
- ROI
- Cumulative return

Performance consumes valuation output rather than holdings directly.

This avoids duplicated valuation logic.

---

### Atomic Portfolio Updates

Portfolio updates occur atomically.

The Portfolio Manager coordinates:

Execution

↓

Accounting

↓

Holdings

↓

Cash

↓

Valuation

↓

Allocation

↓

Performance

↓

Updated Portfolio

If any stage fails, the previous portfolio state remains unchanged.

Partial updates are never persisted.

---

### Dependency Injection

All framework components are resolved through the existing Dependency Injection container.

Dependencies include:

- Portfolio Engine
- Portfolio Manager
- Holdings Manager
- Cash Manager
- Accounting
- Valuation
- Allocation
- Performance
- Event Bus
- LoggerFactory

No framework component instantiates infrastructure directly.

---

### Event-Driven Architecture

Portfolio lifecycle events are published through the existing Event Bus.

Examples include:

- PortfolioCreated
- PortfolioUpdated
- HoldingsUpdated
- CashUpdated
- PortfolioValuationCompleted
- AllocationUpdated
- PerformanceUpdated
- PortfolioSnapshotCreated
- PortfolioClosed
- PortfolioErrorOccurred

The framework never communicates directly with external consumers.

Subscribers receive updates asynchronously.

---

### Thread Safety

The framework supports concurrent portfolio updates.

Thread safety is achieved by:

- Stateless valuation
- Stateless accounting
- Stateless allocation
- Stateless performance services
- Thread-safe registry
- Atomic portfolio updates

Shared mutable state is minimized.

---

### Testability

The framework is fully testable without external services.

Tests use:

- Fake portfolio components
- Fake executions
- Standardized market prices

No exchange connectivity is required.

All tests remain deterministic.

---

## Alternatives Considered

### Portfolio Logic Inside Execution Framework

Rejected.

Execution and portfolio management solve different problems.

Combining them would violate the Single Responsibility Principle and tightly couple execution with accounting.

---

### Portfolio Logic Inside Exchange Adapter

Rejected.

Portfolio calculations should not depend on a specific broker implementation.

Keeping portfolio logic exchange-independent allows multiple brokers to reuse the same framework.

---

### Persistent Allocation Storage

Rejected.

Asset allocation is derived from current portfolio values.

Persisting allocations introduces unnecessary duplication and consistency challenges.

---

## Consequences

### Positive

- Clear separation of concerns
- Exchange-independent portfolio representation
- Reusable accounting pipeline
- Thread-safe updates
- Immutable portfolio models
- Event-driven integration
- Easy extension for future portfolio features
- High testability

### Negative

- Additional architectural layer
- Increased coordination between framework components

These trade-offs are acceptable because they improve modularity, maintainability, and scalability.

---

## Related Components

- portfolio/
- execution/
- exchange_adapters/
- adapters/binance/
- market_data/
- trading/
- events/
- core/

---

## Implementation

Implemented during:

**Sprint 3 – Task 19**

Key components include:

- DefaultPortfolioEngine
- DefaultPortfolioManager
- DefaultHoldingsManager
- DefaultCashManager
- DefaultPortfolioAccounting
- DefaultPortfolioValuation
- DefaultPortfolioAllocation
- DefaultPortfolioPerformance
- InMemoryPortfolioRegistry

Supporting capabilities include:

- Holdings tracking
- Cash accounting
- Cost basis calculation
- Portfolio valuation
- Realized P&L
- Unrealized P&L
- Portfolio allocation
- Portfolio performance
- Portfolio snapshots
- Structured logging
- Event publication

The framework integrates with:

- Execution Framework
- Exchange Adapter Framework
- Binance Spot Adapter
- Dependency Injection Container
- Event Bus
- LoggerFactory

No modifications to existing frameworks were required.

---

## Future Considerations

Future portfolio capabilities may include:

- Multiple Portfolios
- Portfolio Benchmarking
- Dividend Tracking
- Corporate Actions
- Tax Lot Accounting
- Multi-Currency Portfolios
- Portfolio Rebalancing
- Performance Attribution
- Risk Attribution
- Portfolio Analytics Dashboard

These features should extend the existing framework without requiring architectural changes.

---

## Decision Summary

The Portfolio Management Framework introduces a dedicated, exchange-independent layer responsible for maintaining portfolio state after completed executions.

By separating holdings, cash management, accounting, valuation, allocation, and performance into independent components while integrating through dependency injection and an event-driven architecture, the AI Trading Operating System remains modular, scalable, testable, and ready for advanced portfolio capabilities in future releases.