# Task 18 — Binance Spot Adapter

## Objective

Implement the Binance Spot Adapter.

The Binance Spot Adapter is the first concrete implementation of the Exchange Adapter Framework.

It must inherit from the Exchange Adapter abstractions created in Task 17.

It must not modify the Exchange Adapter Framework.

The adapter should implement Binance Spot API integration while keeping the rest of the AI Trading Operating System completely exchange independent.

---

## Responsibilities

The Binance Spot Adapter is responsible for:

- Binance authentication
- REST API communication
- WebSocket communication
- Request signing
- Request translation
- Response parsing
- Connection management
- Account information
- Balance retrieval
- Order submission
- Order cancellation
- Exchange event publication

The adapter is **not** responsible for:

- Trading strategies
- Risk management
- Order creation
- Execution coordination
- Portfolio management
- Market data normalization
- Position management

---

## Files To Populate

Populate only the existing files inside:

adapters/binance/

Do not create additional framework modules.

Do not rename existing files.

---

## Required Components

Implement the following components.

### Binance Adapter

Concrete implementation of the BaseExchangeAdapter.

Responsibilities:

- Submit requests
- Receive responses
- Coordinate Binance services
- Publish adapter events

---

### Authentication

Implement Binance API authentication.

Responsibilities:

- API Key
- Secret Key
- Request signing
- Authentication validation

---

### REST Client

Implement a reusable Binance REST client.

Responsibilities:

- GET requests
- POST requests
- DELETE requests
- Error translation
- Response handling

---

### WebSocket Client

Implement Binance Spot WebSocket client.

Responsibilities:

- Connect
- Disconnect
- Subscribe
- Unsubscribe
- Receive events
- Reconnect

---

### Connection

Manage Binance connectivity.

Responsibilities:

- Connection state
- Reconnection
- Heartbeat support

---

### Request Translator

Translate standardized ExchangeRequest objects into Binance Spot API requests.

---

### Response Parser

Translate Binance Spot responses into standardized ExchangeResponse objects.

---

### Validator

Validate Binance requests before transmission.

---

### Configuration

Configuration model containing:

- API Key
- Secret Key
- Base URL
- WebSocket URL
- Timeout
- Retry settings

---

### Events

Implement Binance-specific adapter events.

---

### Exceptions

Implement Binance adapter exceptions.

---

### Models

Implement Binance-specific request and response models while preserving standardized ExchangeResponse compatibility.
# Architecture Requirements

The Binance Spot Adapter is the first concrete implementation of the Exchange Adapter Framework.

It must inherit from the abstractions created in Task 17.

The Exchange Adapter Framework must not be modified.

Future adapters such as:

- Zerodha
- Interactive Brokers
- Coinbase
- Alpaca
- Paper Trading

must be able to plug into the framework using the same architecture.

---

# Framework Flow

ExecutionResult

↓

Exchange Context

↓

Binance Authentication

↓

Binance Connection

↓

Binance Validator

↓

Binance Request Translator

↓

REST / WebSocket Client

↓

Binance API

↓

Response Parser

↓

ExchangeResponse

↓

Exchange Events

↓

Event Bus

Each component has one responsibility.

No component should bypass another.

---

# Binance Adapter

The Binance Adapter is the public implementation of BaseExchangeAdapter.

Responsibilities:

- Submit ExchangeRequest
- Receive ExchangeResponse
- Coordinate authentication
- Coordinate connection
- Coordinate REST client
- Coordinate WebSocket client
- Publish adapter events

The adapter must never:

- Evaluate strategies
- Perform risk checks
- Create orders
- Coordinate execution
- Manage portfolios

---

# Binance Authentication

Implement Binance Spot authentication.

Responsibilities:

- Store API Key
- Store Secret Key
- Create request signatures
- Validate credentials

Support Binance HMAC SHA256 request signing.

Authentication should expose:

- authenticate()
- sign_request()
- validate_credentials()

Authentication must not communicate directly with the REST client.

---

# REST Client

Implement a reusable REST client.

Support:

- GET
- POST
- PUT
- DELETE

The REST client must support:

- Timeouts
- Retry policy
- Error translation
- Response parsing

Do not duplicate request logic across endpoints.

---

# WebSocket Client

Implement Binance Spot WebSocket support.

Responsibilities:

- Connect
- Disconnect
- Subscribe
- Unsubscribe
- Automatic reconnect
- Message handling

The WebSocket client should remain independent from the REST client.

---

# Request Translation

Translate standardized ExchangeRequest objects into Binance Spot REST requests.

Translation should include:

- Symbol
- Side
- Quantity
- Price
- Order Type
- Time In Force

No business logic should exist here.

Translation only prepares Binance request objects.

---

# Response Parsing

Translate Binance API responses into standardized ExchangeResponse models.

The parser should hide Binance-specific payloads from the rest of the application.

Future components should consume only standardized models.

---

# Connection

Connection management should include:

- Connected
- Disconnected
- Connecting
- Reconnecting

Support heartbeat monitoring.

Support automatic reconnection.

Do not expose transport details outside the adapter.

---

# Configuration

Configuration should include:

- API Key
- Secret Key
- REST Base URL
- WebSocket URL
- Request Timeout
- Retry Count
- Rate Limit Configuration

Configuration should be immutable after initialization.

---

# Validation

Validate requests before sending them.

Validation includes:

- Required fields
- Symbol
- Quantity
- Price
- Order Type
- Time In Force

Validation must not:

- Perform risk checks
- Evaluate strategies
- Communicate with Binance

---

# Events

Publish Binance-specific events.

Examples:

- BinanceAuthenticated
- BinanceDisconnected
- BinanceConnected
- BinanceRequestSent
- BinanceResponseReceived
- BinanceOrderSubmitted
- BinanceOrderCancelled
- BinanceReconnectStarted
- BinanceReconnectSucceeded
- BinanceErrorOccurred

Every event must inherit from the existing Event base class.

---

# Exceptions

Implement adapter-specific exceptions.

Examples:

- BinanceAuthenticationError
- BinanceConnectionError
- BinanceRateLimitError
- BinanceRequestError
- BinanceResponseError
- BinanceTimeoutError
- BinanceWebSocketError

Exceptions should translate Binance errors into framework exceptions.

Do not expose raw Binance exceptions outside the adapter.
# Dependency Injection

The Binance Spot Adapter must fully reuse the existing Dependency Injection container.

Do not instantiate infrastructure manually.

All components must receive dependencies through constructor injection.

Dependencies include:

- EventBus
- LoggerFactory
- TradingEngine
- ExecutionEngine
- ExchangeEngine
- ExchangeManager
- BinanceAuthentication
- BinanceConnection
- BinanceRESTClient
- BinanceWebSocketClient
- BinanceValidator
- BinanceRequestTranslator
- BinanceResponseParser

Future dependencies should also be injectable:

- MetricsCollector
- NotificationService
- AuditService
- SecretsManager
- CredentialProvider

Everything must be resolved through the existing Dependency Injection container.

---

# Event Driven Architecture

Reuse the existing Event Bus.

Do not modify the Event Bus.

Publish Binance-specific adapter events only.

Examples:

- BinanceAuthenticated
- BinanceAuthenticationFailed
- BinanceConnected
- BinanceDisconnected
- BinanceReconnectStarted
- BinanceReconnectSucceeded
- BinanceRequestSent
- BinanceResponseReceived
- BinanceOrderSubmitted
- BinanceOrderCancelled
- BinanceWebSocketConnected
- BinanceWebSocketDisconnected
- BinanceHeartbeatReceived
- BinanceRateLimitReached
- BinanceErrorOccurred

Every event must inherit from the existing Event base class.

Do not publish:

- Strategy events
- Risk events
- Order Management events
- Execution events
- Portfolio events

---

# Logging

Reuse the existing LoggerFactory.

Use structured logging.

Log:

- Authentication
- Connection lifecycle
- REST requests
- REST responses
- WebSocket connection
- WebSocket messages
- Order submission
- Order cancellation
- Reconnection attempts
- Errors

Support correlation IDs.

Do not log:

- API Secret
- Secret signatures
- Authentication tokens
- Sensitive account information

Sensitive information must always be masked.

---

# Error Handling

Translate Binance API failures into framework exceptions.

Examples:

Authentication failure

↓

BinanceAuthenticationError

↓

ExchangeResult

Connection failure

↓

BinanceConnectionError

↓

ExchangeResult

REST timeout

↓

BinanceTimeoutError

↓

ExchangeResult

Rate limit

↓

BinanceRateLimitError

↓

ExchangeResult

No raw Binance exceptions should escape outside the adapter.

---

# Thread Safety

The adapter must support concurrent requests.

The following components should remain stateless:

- Validator
- Request Translator
- Response Parser

REST client should support concurrent requests.

WebSocket client should support concurrent subscriptions.

Avoid shared mutable state.

Protect connection state appropriately.

---

# Performance Requirements

Support:

- Connection reuse
- HTTP keep-alive
- Automatic reconnect
- Retry policies
- Timeout configuration
- Rate-limit awareness

Avoid unnecessary object allocation.

Avoid duplicate request construction.

---

# Security Requirements

Never expose:

- API Secret
- Secret Key
- Request Signature
- Authentication headers

Secrets must never appear in:

- Logs
- Exceptions
- Events

All request signing should use HMAC SHA256 as required by Binance Spot API.

---

# Testing Requirements

Reuse the existing testing framework.

Create fake Binance clients.

Do not contact the real Binance API during tests.

Required unit tests:

- Authentication
- REST Client
- WebSocket Client
- Request Translator
- Response Parser
- Validator
- Connection
- Adapter
- Models
- Events
- Exceptions
- Dependency Injection registration

Required integration tests:

- Exchange Framework → Binance Adapter
- Authentication → REST
- Authentication → WebSocket
- Request Translation → REST
- REST → Response Parser
- Connection Lifecycle
- Event Bus integration
- Order submission flow
- Order cancellation flow

All tests must be deterministic.

No sleep().

No live network calls.

Use fake responses wherever possible.

---

# Constraints

The Binance Spot Adapter must not modify:

- Trading Engine
- Market Data Framework
- Strategy Framework
- Risk Framework
- Order Management Framework
- Execution Framework
- Exchange Adapter Framework

Reuse all existing infrastructure.

If any existing framework must be modified, explain why before making changes.

Future adapters should be able to reuse the same architecture with minimal implementation effort.
# Expected Output

After completing Task 18, provide a comprehensive architectural explanation.

Do not simply list files.

Explain the architecture and design decisions.

The explanation must include the following sections.

---

# 1. Architecture Overview

Explain:

- Why the Binance Spot Adapter exists.
- Why it is separated from the Exchange Adapter Framework.
- Why it does not modify the framework.
- Why the adapter isolates Binance-specific implementation.
- How it integrates into the AI Trading Operating System.

---

# 2. Binance Spot Adapter

Explain:

Responsibilities of:

- Binance Adapter
- Authentication
- REST Client
- WebSocket Client
- Connection
- Request Translator
- Response Parser
- Validator

Describe how they collaborate.

---

# 3. Authentication

Explain:

How Binance authentication works.

Describe:

API Key

↓

Secret Key

↓

HMAC SHA256 Signature

↓

Authenticated Request

Explain how secrets remain protected.

---

# 4. REST Client

Explain:

How REST communication is organized.

Describe:

- GET
- POST
- PUT
- DELETE

Explain timeout handling.

Explain retry policy.

Explain error translation.

---

# 5. WebSocket Client

Explain:

Connection lifecycle.

Describe:

Connect

↓

Authenticate

↓

Subscribe

↓

Receive Messages

↓

Reconnect

↓

Disconnect

Explain automatic reconnection.

---

# 6. Request Translation

Explain how ExchangeRequest becomes a Binance request.

Describe:

ExchangeRequest

↓

Translation

↓

Binance Request

↓

REST Client

Explain why business logic is excluded.

---

# 7. Response Parsing

Explain how Binance responses become standardized ExchangeResponse models.

Describe:

REST Response

↓

Parser

↓

ExchangeResponse

Explain why Binance payloads never leave the adapter.

---

# 8. Connection Management

Explain:

Connection lifecycle.

Describe:

Connecting

↓

Connected

↓

Disconnected

↓

Reconnect

↓

Connected

Explain heartbeat support.

---

# 9. Dependency Injection

Explain:

How the adapter reuses the existing Dependency Injection container.

Describe:

- Authentication Injection
- REST Client Injection
- WebSocket Injection
- Validator Injection
- Parser Injection
- Event Bus Injection
- Logger Injection
- Exchange Framework Injection

Explain why future adapters reuse the same architecture.

---

# 10. Event Driven Architecture

Explain:

How the adapter integrates with the Event Bus.

Describe:

- BinanceAuthenticated
- BinanceAuthenticationFailed
- BinanceConnected
- BinanceDisconnected
- BinanceRequestSent
- BinanceResponseReceived
- BinanceOrderSubmitted
- BinanceOrderCancelled
- BinanceReconnectStarted
- BinanceReconnectSucceeded
- BinanceHeartbeatReceived
- BinanceErrorOccurred

Explain why events remain localized to the adapter.

---

# 11. Logging

Explain:

How LoggerFactory is reused.

Describe:

- Authentication logging
- REST logging
- WebSocket logging
- Connection logging
- Order logging
- Error logging

Explain why secrets are never logged.

---

# 12. Error Handling

Explain:

Authentication failures

↓

Connection failures

↓

Timeouts

↓

Rate limits

↓

REST failures

↓

WebSocket failures

↓

Framework exceptions

Explain how Binance exceptions are translated into framework exceptions.

---

# 13. Future Extension

Explain how future capabilities integrate without modifying the adapter.

Examples:

- Margin Trading
- Futures Trading
- OCO Orders
- User Data Streams
- Listen Keys
- Portfolio Margin
- Smart Order Routing
- Advanced Order Types

---

# Implementation Summary

Provide:

- Files populated
- Classes added
- Interfaces implemented
- Events implemented
- REST client
- WebSocket client
- Authentication
- Parser
- Validator
- Dependency Injection registrations
- Tests created
- Existing tests passed

---

# Acceptance Criteria

Task 18 is complete only if all of the following are satisfied.

✓ Existing infrastructure reused

✓ Exchange Adapter Framework unchanged

✓ Binance Spot Adapter implemented

✓ REST Client implemented

✓ WebSocket Client implemented

✓ API Key authentication implemented

✓ HMAC SHA256 signing implemented

✓ Connection management implemented

✓ Request translation implemented

✓ Response parsing implemented

✓ Validator implemented

✓ Event Bus integrated

✓ LoggerFactory reused

✓ Dependency Injection used

✓ Thread-safe implementation

✓ Unit tests implemented

✓ Integration tests implemented

✓ Existing tests continue to pass

✓ No unrelated modules modified

---

# Files That Must Not Be Modified

Unless absolutely required for integration, do not modify:

- core/
- events/
- database/
- trading/
- market_data/
- strategies/
- risk/
- order_management/
- execution/
- exchange_adapters/

Reuse existing infrastructure exactly as implemented.

If an existing module must be modified for integration, explain why before making the change.

---

# Stop Condition

Stop immediately after Task 18 is complete.

Do not begin Task 19.

Do not implement:

- Zerodha Adapter
- Interactive Brokers Adapter
- Coinbase Adapter
- Paper Trading
- Backtesting

Only implement the Binance Spot Adapter.

End the response with:

"Task 18 complete. Standing by for review."