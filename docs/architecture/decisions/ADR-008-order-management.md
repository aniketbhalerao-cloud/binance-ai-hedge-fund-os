# ADR-008: Order Management Framework

## Status

Accepted

## Date

2026-08-02

## Context

The AI Trading Operating System separates trading into independent architectural layers.

Strategies determine trading opportunities.

The Risk Framework determines whether a trading opportunity is permitted.

However, neither of these components should create or submit exchange-specific orders.

Without a dedicated Order Management Framework:

- Strategies would need to understand broker order formats.
- Risk Framework would become responsible for execution preparation.
- Exchange adapters would receive inconsistent order structures.
- Order lifecycle management would be distributed across multiple components.

To maintain separation of concerns, the system requires a dedicated Order Management Framework positioned between the Risk Framework and the future Execution Layer.

---

## Decision

The system will implement a reusable Order Management Framework responsible for converting approved Risk Decisions into standardized, validated, exchange-independent order requests.

The framework consists of:

- Order Engine
- Order Manager
- Order Factory
- Order Validator
- Order Router
- Order Context
- Order Models
- Order Events

The framework prepares orders for execution but never submits them.

Execution is delegated to the future Execution Layer.

---

## Rationale

Separating order preparation from execution provides several architectural benefits.

### Separation of Responsibilities

Strategies decide:

**"What should we trade?"**

Risk Framework decides:

**"Are we allowed to trade?"**

Order Management decides:

**"What order should be created?"**

Execution Layer decides:

**"How should the order be executed?"**

Exchange Adapter decides:

**"Where should the order be sent?"**

Each layer has exactly one responsibility.

---

### Exchange Independence

The Order Management Framework produces standardized order models that are independent of any broker or exchange.

Exchange-specific translation occurs only inside future Exchange Adapters.

This allows the same OrderRequest to be used with:

- Binance
- Zerodha
- Interactive Brokers
- Alpaca
- Coinbase
- Future broker integrations

without modifying the Order Management Framework.

---

### Open/Closed Principle

Future order types can be introduced without modifying the framework.

Examples include:

- Market Orders
- Limit Orders
- Stop Orders
- Stop Limit Orders
- Trailing Stop Orders
- OCO Orders
- Iceberg Orders
- TWAP Orders
- VWAP Orders

The framework remains closed for modification while remaining open for extension.

---

### Event-Driven Architecture

The Order Management Framework publishes order lifecycle events through the existing Event Bus.

Examples include:

- OrderCreated
- OrderValidated
- OrderValidationFailed
- OrderRouted
- OrderReadyForExecution
- OrderRejected
- OrderEngineStarted
- OrderEngineStopped
- OrderErrorOccurred

Future execution engines subscribe to these events rather than being called directly.

---

### Dependency Injection

The framework reuses the existing Dependency Injection container.

All components receive dependencies through constructor injection.

The framework depends only on abstractions, allowing future execution engines, routers, validators, and factories to be replaced without modifying existing components.

---

### Testability

Every framework component is deterministic and independently testable.

Factories, validators, routers, and managers can be tested using fake implementations without requiring:

- Exchange APIs
- REST services
- WebSockets
- Live accounts

This enables fast, repeatable unit and integration testing.

---

## Alternatives Considered

### Strategies Creating Orders

Rejected.

Strategies should generate trading intent rather than exchange-ready orders.

Combining these responsibilities increases coupling and reduces reusability.

---

### Risk Framework Creating Orders

Rejected.

Risk evaluation should remain independent from execution preparation.

Combining the two would violate the Single Responsibility Principle.

---

### Execution Layer Creating Orders

Rejected.

Execution should submit standardized orders rather than constructing them.

Separating preparation from execution improves portability and simplifies broker integrations.

---

## Consequences

### Positive

- Clear separation of responsibilities
- Exchange-independent order models
- Reusable order lifecycle
- Standardized order validation
- Event-driven integration
- Improved testing
- Future broker portability
- Extensible routing architecture

### Negative

- Additional framework layer
- More framework components
- Additional event definitions

These trade-offs are acceptable because they improve maintainability, extensibility, and long-term scalability.

---

## Related Components

- order_management/
- risk/
- strategies/
- trading/
- market_data/
- events/
- core/

---

## Implementation

Implemented during:

**Sprint 2 – Task 15**

Key components include:

- DefaultOrderEngine
- DefaultOrderManager
- DefaultOrderFactory
- DefaultOrderValidator
- DefaultOrderRouter
- OrderContext
- OrderRequest
- OrderRoute
- OrderResult
- Order Events

The framework integrates with:

- Trading Engine
- Strategy Framework
- Risk Framework
- Event Bus
- Dependency Injection Container

No exchange connectivity was implemented.

---

## Future Considerations

Future enhancements include:

- Smart Order Routing
- Multi-Exchange Routing
- Broker-specific Adapters
- Order Retry Policies
- Order Scheduling
- Advanced Order Types
- Execution Engine Integration
- Paper Trading Support
- Backtesting Support
- Audit Logging
- Distributed Order Processing

These capabilities should integrate without modifying the Order Management Framework itself.

---

## Decision Summary

The Order Management Framework establishes a dedicated, exchange-independent layer responsible for preparing standardized orders for execution.

By separating order preparation from execution, the system remains modular, testable, reusable, and compatible with multiple brokers and execution engines while preserving the overall event-driven architecture of the AI Trading Operating System.