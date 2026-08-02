# ADR-011: Binance Spot Adapter

## Status

Accepted

## Date

2026-08-02

## Context

The AI Trading Operating System now includes a complete broker-independent Exchange Adapter Framework that defines common interfaces for authentication, connection management, request translation, validation, routing, and event publication.

While the framework provides reusable abstractions, it intentionally contains no exchange-specific implementation.

A concrete broker implementation is required to connect the system to a real trading venue.

Binance Spot Exchange was selected as the first implementation because it provides a mature API, comprehensive documentation, high market liquidity, and supports both REST and WebSocket communication.

The implementation must preserve the existing architecture without introducing exchange-specific logic into the core frameworks.

---

## Decision

Implement Binance Spot as the first concrete adapter by extending the Exchange Adapter Framework.

The adapter is implemented entirely within:

```
adapters/binance/
```

The adapter integrates with the existing framework through:

- BaseExchangeAdapter
- Exchange Engine
- Exchange Manager
- Event Bus
- Dependency Injection
- LoggerFactory

No modifications are made to the Exchange Adapter Framework itself.

---

## Rationale

### Separation of Responsibilities

The Exchange Adapter Framework defines **how broker adapters integrate**.

The Binance Spot Adapter defines **how Binance communicates**.

Keeping these responsibilities separate ensures that broker-specific implementation details never leak into the framework.

---

### Broker Isolation

Binance-specific concepts including:

- REST endpoints
- WebSocket endpoints
- Authentication
- Request signing
- Response payloads
- Error codes

remain isolated inside the Binance adapter.

The remainder of the AI Trading Operating System continues to operate only with standardized ExchangeRequest and ExchangeResponse models.

---

### Request Signing

Binance Spot requires every signed request to use HMAC SHA256.

Request signing is isolated inside the BinanceAuthentication and BinanceSigner components.

No other framework component is responsible for request signing.

This prevents cryptographic logic from spreading across the application.

---

### REST and WebSocket Separation

REST communication and WebSocket communication are implemented as independent components.

REST is responsible for:

- Account information
- Order placement
- Order cancellation
- Balance retrieval

WebSocket is responsible for:

- Streaming events
- Order updates
- Heartbeats
- Reconnection

Separating these concerns improves maintainability and allows each communication channel to evolve independently.

---

### Transport Abstraction

The adapter communicates through injectable transport interfaces.

Production implementations may use HTTP and WebSocket libraries.

Testing implementations use fake transports.

This enables deterministic testing without contacting Binance.

---

### Dependency Injection

Every Binance component is resolved through the existing Dependency Injection container.

Examples include:

- BinanceAuthentication
- BinanceRESTClient
- BinanceWebSocketClient
- BinanceConnection
- BinanceRequestTranslator
- BinanceResponseParser
- BinanceRequestValidator

No infrastructure is manually instantiated.

---

### Event-Driven Architecture

The adapter publishes Binance-specific lifecycle events through the existing Event Bus.

Examples include:

- BinanceAuthenticated
- BinanceConnected
- BinanceDisconnected
- BinanceRequestSent
- BinanceResponseReceived
- BinanceOrderSubmitted
- BinanceOrderCancelled
- BinanceReconnectStarted
- BinanceReconnectSucceeded
- BinanceHeartbeatReceived
- BinanceRateLimitReached
- BinanceErrorOccurred

The adapter never communicates directly with higher-level components.

Consumers subscribe to events instead.

---

### Security

Sensitive information must never leave the adapter.

The following are never logged:

- API Secret
- Secret Key
- Request Signature
- Authentication Headers
- Signed Query Parameters

Secrets are masked before logging.

Cryptographic operations are performed using HMAC SHA256.

---

### Error Translation

Raw Binance API errors are translated into framework-specific exceptions.

Examples include:

- BinanceAuthenticationError
- BinanceConnectionError
- BinanceTimeoutError
- BinanceRateLimitError
- BinanceRequestError
- BinanceResponseError
- BinanceWebSocketError

Higher-level components never receive raw Binance exceptions.

---

### Testability

The adapter was designed for deterministic testing.

Tests use:

- Fake HTTP transports
- Fake WebSocket transports
- Fake responses

No live Binance account is required.

No external network communication occurs during testing.

---

## Alternatives Considered

### Direct Binance Integration Inside Execution Framework

Rejected.

Embedding Binance-specific communication inside the Execution Framework would violate the separation of responsibilities established throughout the architecture.

---

### REST-Only Implementation

Rejected.

Although simpler, it would not support streaming updates or future real-time trading capabilities.

---

### WebSocket-Only Implementation

Rejected.

Many Binance operations require REST endpoints.

Both communication mechanisms are required.

---

## Consequences

### Positive

- First production-ready broker integration
- Broker-specific logic fully isolated
- Exchange Adapter Framework remains unchanged
- Request signing centralized
- REST and WebSocket responsibilities separated
- Secure handling of credentials
- Deterministic testing
- Future broker implementations follow the same architecture

### Negative

- Additional adapter-specific codebase
- Separate maintenance for REST and WebSocket clients
- Binance-specific request and response models

These trade-offs are acceptable because they preserve the modularity and scalability of the AI Trading Operating System.

---

## Related Components

- adapters/binance/
- exchange_adapters/
- execution/
- order_management/
- risk/
- strategies/
- trading/
- events/
- core/

---

## Implementation

Implemented during:

**Sprint 3 – Task 18**

Key components include:

- BinanceSpotAdapter
- BinanceAuthentication
- BinanceSigner
- BinanceRESTClient
- BinanceWebSocketClient
- BinanceConnection
- BinanceRequestTranslator
- BinanceResponseParser
- BinanceRequestValidator

Supporting features include:

- API Key authentication
- HMAC SHA256 request signing
- REST communication
- WebSocket communication
- Retry support
- Timeout handling
- Connection lifecycle
- Structured logging
- Event publication

The adapter integrates with:

- Exchange Adapter Framework
- Execution Framework
- Dependency Injection Container
- Event Bus
- LoggerFactory

No modifications to existing framework components were required.

---

## Future Considerations

Future Binance capabilities may include:

- Margin Trading
- Futures Trading
- Options Trading
- OCO Orders
- Advanced Order Types
- User Data Streams
- Listen Keys
- Portfolio Margin
- Smart Order Routing
- Multi-Account Support

These features should extend the existing adapter without requiring changes to the Exchange Adapter Framework.

---

## Decision Summary

The Binance Spot Adapter is implemented as the first concrete broker integration built on top of the Exchange Adapter Framework.

By isolating all Binance-specific behavior inside a dedicated adapter package while preserving standardized models, dependency injection, and event-driven communication, the AI Trading Operating System remains modular, scalable, secure, and ready to support additional exchanges without architectural modification.