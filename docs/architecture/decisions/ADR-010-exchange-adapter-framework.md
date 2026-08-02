# ADR-010: Exchange Adapter Framework

## Status

Accepted

## Date

2026-08-02

## Context

The AI Trading Operating System now includes dedicated frameworks for market data, trading, strategies, risk management, order management, and execution.

Although the Execution Framework coordinates execution, it must not communicate directly with broker APIs or contain exchange-specific logic.

Different brokers expose different authentication methods, request formats, protocols, and APIs.

Embedding broker-specific implementations inside the Execution Framework would tightly couple the architecture to individual exchanges and reduce maintainability.

A dedicated Exchange Adapter Framework is therefore required.

---

## Decision

Introduce a broker-independent Exchange Adapter Framework positioned between the Execution Framework and concrete broker implementations.

The framework consists of:

- Exchange Engine
- Exchange Manager
- Base Exchange Adapter
- Authentication
- Connection
- Validator
- Router
- Registry
- Exchange Context
- Exchange Models
- Exchange Events

Concrete broker implementations will inherit from the framework without modifying it.

---

## Rationale

### Separation of Responsibilities

Execution Framework answers:

**"How should execution be coordinated?"**

Exchange Adapter Framework answers:

**"How should standardized execution requests be prepared for a broker?"**

Concrete Broker Adapter answers:

**"How does this broker actually execute the request?"**

Each layer owns one responsibility.

---

### Broker Independence

The framework contains no exchange-specific logic.

Future broker implementations may include:

- Binance
- Zerodha
- Interactive Brokers
- Alpaca
- Coinbase
- Paper Trading
- Backtesting

without modifying the framework.

---

### Authentication Abstraction

Authentication is defined as an interface only.

The framework intentionally avoids implementing:

- API Keys
- OAuth
- JWT
- HMAC
- Login APIs

Each broker supplies its own authentication mechanism.

---

### Connection Abstraction

Connection management is also abstract.

The framework does not implement:

- REST
- WebSockets
- SDKs
- Heartbeats

Future adapters provide concrete implementations.

---

### Event-Driven Architecture

The framework publishes lifecycle events through the existing Event Bus.

Examples include:

- ExchangeAdapterRegistered
- ExchangeAuthenticationStarted
- ExchangeConnectionOpened
- ExchangeValidationSucceeded
- ExchangeRoutingCompleted
- ExchangeEngineStarted
- ExchangeEngineStopped
- ExchangeErrorOccurred

Broker implementations remain loosely coupled.

---

### Dependency Injection

All framework components are resolved through the existing Dependency Injection container.

Future broker implementations integrate by registration rather than framework modification.

---

### Testability

The framework is fully testable using fake adapters.

No broker accounts or external services are required.

Deterministic testing is preserved.

---

## Alternatives Considered

### Direct Broker Integration

Rejected.

Embedding broker implementations inside the Execution Framework would violate separation of responsibilities and tightly couple the system to specific exchanges.

---

### One Adapter Per Broker Without a Common Framework

Rejected.

Duplicating authentication, connection management, routing, and validation across broker implementations would increase maintenance effort and reduce consistency.

---

## Consequences

### Positive

- Clear separation of concerns
- Broker-independent architecture
- Reusable adapter abstractions
- Consistent authentication and connection lifecycle
- Event-driven integration
- Easy addition of new brokers
- Improved testing and maintainability

### Negative

- Additional framework layer
- More abstractions to manage

These trade-offs are acceptable because they significantly improve extensibility and long-term scalability.

---

## Related Components

- exchange_adapters/
- execution/
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

**Sprint 3 – Task 17**

Key components include:

- DefaultExchangeEngine
- DefaultExchangeManager
- BaseExchangeAdapter
- DefaultExchangeAuthentication
- DefaultExchangeConnection
- DefaultExchangeValidator
- DefaultExchangeRouter
- ExchangeAdapterRegistry

The framework integrates with:

- Execution Framework
- Event Bus
- Dependency Injection Container

No broker-specific implementation was included.

---

## Future Considerations

Future broker implementations include:

- Binance Adapter
- Zerodha Adapter
- Interactive Brokers Adapter
- Alpaca Adapter
- Coinbase Adapter
- Paper Trading Adapter
- Backtesting Adapter
- FIX Protocol Adapter

All should integrate without modifying the Exchange Adapter Framework.

---

## Decision Summary

The Exchange Adapter Framework establishes a reusable, broker-independent abstraction layer responsible for authentication, connection management, request translation, validation, routing, and adapter coordination.

By separating broker-independent infrastructure from broker-specific implementations, the AI Trading Operating System remains modular, extensible, testable, and capable of supporting multiple exchanges without architectural changes.