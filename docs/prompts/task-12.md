# Project Context

Project: AI Trading Operating System

Version: Sprint 2

Task: 12

---

# Background

Sprint 1 established the infrastructure layer:

- Domain Models
- Event Bus
- Dependency Injection
- Logging
- Repository Pattern
- Persistence Service
- Testing Framework

Sprint 2 Task 11 established the Trading Engine.

The Trading Engine now requires a Market Data Pipeline capable of supplying normalized market data through the existing Event Bus.

The Market Data Pipeline must remain exchange independent.

It must support future implementations for:

- Binance
- Zerodha
- Paper Trading
- Historical Replay
- Backtesting
- CSV Imports

without changing its public API.

---

# Purpose

The Market Data Pipeline is responsible for:

Receiving market data

Normalizing exchange-specific payloads

Maintaining the latest market snapshot

Publishing standardized market events

Providing data to the Trading Engine

It is NOT responsible for:

Trading

Strategies

Risk calculations

Order execution

Portfolio calculations

Persistence

Notifications

---

# Design Philosophy

The Market Data Pipeline must be completely exchange agnostic.

Exchange-specific parsing belongs inside adapters.

The Market Data Pipeline only understands normalized domain models.

---

# Mandatory Architecture Review

Before implementing any code:

Review the existing project.

Search for:

market_data

provider

normalizer

cache

events

models

interfaces

Determine:

What already exists

What should be reused

What should be extended

Whether any implementation would duplicate functionality

Present the review before writing code.

Do not duplicate existing infrastructure.

Reuse:

Event Bus

Dependency Injection

LoggerFactory

Trading Engine

Persistence abstractions

Testing framework

---

# Current Task

Populate only the existing files inside:

market_data/

Do not create additional packages.

Do not implement exchange-specific providers.

Do not implement Binance.

Stop after Task 12.
# Files to Populate

Populate only:

market_data/

├── __init__.py
├── cache.py
├── events.py
├── exceptions.py
├── interfaces.py
├── models.py
├── normalizer.py
├── provider.py
└── service.py

No additional modules.

---

# File Responsibilities

## __init__.py

Expose the Market Data public API.

No logic.

---

## models.py

Contains normalized domain models.

Examples:

MarketSnapshot

PriceTick

OHLCV

OrderBookSnapshot

TradeTick

ConnectionStatus

No exchange fields.

No Binance-specific names.

Immutable dataclasses.

---

## interfaces.py

Contains only interfaces.

Examples:

MarketDataProvider

MarketDataNormalizer

MarketDataCache

MarketDataService

No implementations.

---

## provider.py

Coordinates incoming data sources.

Receives raw payloads.

Nothing else.

No parsing.

No caching.

No event publishing.

---

## normalizer.py

Converts raw provider payloads into domain models.

Must support future exchanges.

No EventBus.

No persistence.

---

## cache.py

Stores latest normalized market snapshot.

Memory only.

No database.

Supports:

update()

get()

clear()

snapshot()

Thread-safe.

---

## events.py

Trading-independent market events.

Examples:

MarketDataReceived

PriceUpdated

CandleClosed

OrderBookUpdated

ConnectionEstablished

ConnectionLost

ReconnectAttempt

---

## exceptions.py

Contains only market-data exceptions.

Examples:

MarketDataError

ProviderError

NormalizationError

CacheError

ConnectionError

---

## service.py

Coordinates:

Provider

Normalizer

Cache

Event Bus

Logger

Publishes normalized events.

Nothing else.

No trading logic.

No Binance logic.

No strategy logic.
# Dependency Injection

The Market Data Pipeline must reuse the existing Dependency Injection container.

Do not instantiate dependencies directly.

Every dependency must be supplied through constructor injection.

The Market Data Service should depend only on abstractions.

Dependencies should include:

- EventBus
- LoggerFactory
- TradingEngine (through its public interface only)
- MarketDataProvider
- MarketDataNormalizer
- MarketDataCache

Future dependencies that must be injectable:

- HistoricalReplayProvider
- PaperTradingProvider
- CSVReplayProvider
- MultiExchangeProvider

No dependency should be manually created inside the Market Data Pipeline.

---

# Event Driven Architecture

Reuse the existing Event Bus created during Sprint 1.

Do not modify the Event Bus.

The Market Data Pipeline publishes market events only.

It must never publish:

- trading signals
- orders
- portfolio events
- risk events

Market events should include:

- MarketDataReceived
- PriceUpdated
- CandleOpened
- CandleUpdated
- CandleClosed
- OrderBookUpdated
- TradeReceived
- ProviderConnected
- ProviderDisconnected
- ProviderReconnectAttempt
- ProviderError

Each event should inherit from the existing Event base class.

---

# Market Data Flow

The complete processing pipeline should be:

Raw Provider Data

↓

Provider

↓

Normalizer

↓

Domain Model

↓

Cache

↓

Market Event

↓

Event Bus

↓

Trading Engine

↓

Strategy Framework (future)

Every stage should have one responsibility.

No stage should bypass another.

---

# Cache Design

The cache stores only the latest normalized market state.

The cache is NOT persistence.

The cache should support:

update()

get()

exists()

clear()

snapshot()

Cache entries should be keyed by:

Exchange

Symbol

Timeframe (where applicable)

The cache must be thread-safe.

No database access is allowed.

---

# Replay Compatibility

The Market Data Pipeline must support future replay without architectural changes.

The Market Data Service should not know whether data comes from:

- Binance
- Zerodha
- CSV
- Replay
- Backtesting
- Paper Trading

All providers must expose the same interface.

The Trading Engine must not require modification when replay is introduced.

---

# Normalization Rules

The Normalizer is responsible for converting provider-specific payloads into standardized domain models.

Examples:

Binance JSON

↓

PriceTick

CSV Row

↓

PriceTick

Historical Database Row

↓

PriceTick

Every downstream component must consume only normalized domain models.

No exchange-specific fields may leave the normalizer.

---

# Logging

Reuse the existing LoggerFactory.

Log only infrastructure events.

Examples:

Provider connected

Provider disconnected

Normalization completed

Cache updated

Market event published

Provider failure

Do not log inside models.

Do not log inside cache objects.

Use structured logging.

Correlation IDs must continue to function.

---

# Error Handling

Failures should be isolated.

Provider failures must not crash the Trading Engine.

Normalization failures should produce structured errors.

Cache failures should raise MarketData exceptions.

Provider disconnects should publish ProviderDisconnected events.

Unexpected failures should be logged.

---

# Thread Safety

The Market Data Pipeline must support concurrent updates.

Cache operations must be synchronized.

Event publishing must remain asynchronous.

Avoid race conditions.

Do not create unmanaged background threads.

Future async providers should integrate naturally.

---

# Testing Requirements

Reuse the existing testing framework.

Do not introduce another testing framework.

Required unit tests:

MarketDataService

Provider

Normalizer

Cache

Events

Exceptions

Dependency Injection registration

Required integration tests:

Provider → Normalizer

Normalizer → Cache

Cache → EventBus

MarketDataService → TradingEngine

Replay compatibility

Use fake providers.

Use fake EventBus where appropriate.

Avoid timing-based assertions.

Do not use sleep().

All tests must be deterministic.

---

# Constraints

The Market Data Pipeline must NOT:

Connect directly to Binance.

Contain Binance SDK code.

Contain Zerodha SDK code.

Contain WebSocket implementations.

Contain REST API implementations.

Contain strategy logic.

Contain indicator calculations.

Contain trading logic.

Contain risk calculations.

Contain order execution.

Contain persistence logic.

Contain notification logic.

Contain portfolio calculations.

Read configuration files directly.

Instantiate dependencies manually.

Everything must be coordinated through Dependency Injection and abstractions.

---

# Future Extension Points

The architecture should allow future implementation of:

Binance Live Feed

Zerodha Live Feed

Historical Replay

CSV Replay

Database Replay

Paper Trading

Multi-Exchange Aggregation

Market Depth

Funding Rates

Open Interest

Options Data

Futures Data

Without modifying the Market Data Service.
# Expected Output

After completing Task 12, provide a complete architectural explanation.

Do not simply list files.

Explain the design decisions.

The explanation must contain the following sections.

---

# 1. Architecture Overview

Explain:

- Why the Market Data Pipeline exists.
- Why it is exchange agnostic.
- Why it is separate from the Trading Engine.
- Why it contains no trading logic.

Describe how it integrates with the rest of the AI Trading Operating System.

---

# 2. Provider Architecture

Explain:

Why providers exist.

How providers receive raw market data.

Why providers must not normalize data.

Why future providers (Binance, Zerodha, Replay, CSV) can be added without changing the Market Data Service.

---

# 3. Normalization

Explain:

Why every exchange uses different payloads.

Why the Normalizer converts everything into domain models.

Describe how normalized models reduce coupling.

Explain why no exchange-specific fields leave the normalizer.

---

# 4. Cache

Explain:

Why a cache exists.

Difference between cache and persistence.

Describe:

- update()
- get()
- exists()
- clear()
- snapshot()

Explain why the cache remains memory-only.

---

# 5. Event Driven Architecture

Explain:

How market events are published.

Describe:

MarketDataReceived

PriceUpdated

CandleOpened

CandleUpdated

CandleClosed

OrderBookUpdated

TradeReceived

ProviderConnected

ProviderDisconnected

ProviderReconnectAttempt

ProviderError

Explain how the Event Bus distributes these events.

---

# 6. Dependency Injection

Explain:

How the Market Data Service uses Dependency Injection.

Describe:

constructor injection

provider registration

cache registration

logger registration

Explain why this architecture is easy to extend.

---

# 7. Trading Engine Integration

Explain:

How the Trading Engine receives market data.

Describe the complete flow:

Provider

↓

Normalizer

↓

Cache

↓

Market Event

↓

Event Bus

↓

Trading Engine

Explain why the Trading Engine never communicates directly with providers.

---

# 8. Replay Support

Explain:

How replay compatibility was designed.

Describe how future replay providers can use exactly the same interfaces.

Explain why this architecture supports:

Historical Replay

Backtesting

Paper Trading

Simulation

without changing the Market Data Pipeline.

---

# 9. Future Extension

Explain how future components can integrate.

Examples:

Binance Provider

Zerodha Provider

CSV Replay

Database Replay

Market Depth

Funding Rates

Open Interest

Options Data

Multi-Exchange Aggregation

AI Prediction Engines

without modifying the Market Data Service.

---

# Implementation Summary

Provide a concise summary including:

Files populated

Classes added

Interfaces added

Events added

Dependency Injection registrations

Cache implementation

Normalizer implementation

Tests created

No unrelated modules modified

---

# Acceptance Criteria

Task 12 is complete only if all of the following are satisfied.

✓ Existing infrastructure reused

✓ No duplicate implementations

✓ Exchange agnostic architecture

✓ Dependency Injection used

✓ Event Bus integrated

✓ LoggerFactory reused

✓ Trading Engine integration completed

✓ Cache implemented

✓ Normalizer implemented

✓ Provider abstraction implemented

✓ Thread-safe cache

✓ Replay compatible design

✓ Unit tests implemented

✓ Integration tests implemented

✓ Existing tests continue to pass

✓ No unrelated modules modified

---

# Files That Must Not Be Modified

Unless absolutely required for integration, do not modify:

core/

events/

database/

models/

trading/

adapters/

tests/

Reuse existing infrastructure exactly as implemented.

If an existing module must be modified, explain why before making the change.

---

# Stop Condition

Stop immediately after Task 12 is complete.

Do not begin Task 13.

Do not implement:

Strategies

Risk Engine

Order Manager

Portfolio Manager

Paper Trading

Backtesting

Exchange Connectivity

AI Models

Dashboard

Notifications

Only implement the Market Data Framework.

End the response with:

"Task 12 complete. Standing by for review."