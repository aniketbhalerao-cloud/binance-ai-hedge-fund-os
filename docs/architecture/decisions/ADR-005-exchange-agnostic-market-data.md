# ADR-005: Exchange-Agnostic Market Data

## Status

Accepted

## Date

2026-08-02

## Context

The AI Trading Operating System is designed to support multiple market data sources, including:

- Binance
- Zerodha
- Historical Replay
- CSV Imports
- Paper Trading
- Backtesting
- Future exchange integrations

Each provider exposes market data using different:

- JSON structures
- Field names
- Timestamp formats
- Price formats
- Symbol naming conventions
- Order book structures

Allowing these provider-specific formats to propagate throughout the application would tightly couple business logic to external APIs.

This would require every downstream component to understand multiple provider formats, significantly increasing complexity and maintenance cost.

The architecture therefore requires a standardized internal representation of market data.

---

## Decision

The system will normalize all provider-specific market data into exchange-independent domain models before it enters the rest of the application.

The Market Data Pipeline consists of four distinct stages:

Raw Provider Data

↓

Provider

↓

Normalizer

↓

Domain Models

↓

Cache

↓

Market Events

↓

Event Bus

↓

Trading Engine

Only normalized domain models may leave the Market Data Pipeline.

No provider-specific payloads or field names are allowed beyond the Normalizer.

---

## Rationale

Normalizing market data provides several architectural benefits.

### Exchange Independence

Business components never depend on a particular exchange.

Strategies, Risk Engine, Portfolio Manager, and Trading Engine consume identical domain models regardless of where the data originated.

Replacing or adding an exchange requires changes only within the provider implementation.

---

### Separation of Concerns

Each stage performs one responsibility:

Provider

- Receives raw market data.

Normalizer

- Converts provider-specific payloads into standardized domain models.

Cache

- Stores the latest normalized market state.

Market Data Service

- Coordinates the pipeline and publishes events.

Business components remain unaware of provider implementation details.

---

### Extensibility

New providers can be introduced without modifying existing consumers.

Examples include:

- Binance
- Zerodha
- Kraken
- Bybit
- Coinbase
- Historical Replay
- CSV Files
- Paper Trading

Each provider only needs to implement the MarketDataProvider interface.

---

### Replay Compatibility

Replay and live trading should behave identically.

Historical replay providers emit the same normalized domain models as live providers.

The Trading Engine and Strategy Framework therefore require no modifications to support replay or simulation.

---

### Testability

Fake providers can emit standardized domain models during testing.

Unit tests remain deterministic and independent of external exchanges.

No network connectivity is required.

---

## Alternatives Considered

### Exchange-Specific Business Logic

Advantages:

- Simple initial implementation.

Disadvantages:

- Tight coupling.
- Duplicate parsing logic.
- Difficult testing.
- Poor maintainability.

Rejected.

---

### Provider-Specific Strategies

Advantages:

- Direct access to exchange features.

Disadvantages:

- Strategies become exchange dependent.
- Difficult portability.
- Poor reuse.

Rejected.

---

### Exchange SDK Throughout Application

Advantages:

- Less initial abstraction.

Disadvantages:

- External API changes affect the entire application.
- Harder testing.
- Vendor lock-in.

Rejected.

---

## Consequences

### Positive

- Exchange-independent architecture.
- Replay compatibility.
- Easier testing.
- Clean separation of responsibilities.
- Simple provider replacement.
- Supports multiple exchanges.
- Consistent domain models.
- Future-proof design.

### Negative

- Additional normalization layer.
- More domain model classes.
- Small processing overhead during normalization.

These trade-offs are considered acceptable because they significantly improve maintainability and extensibility.

---

## Related Components

- market_data/
- market_data/provider.py
- market_data/normalizer.py
- market_data/cache.py
- market_data/service.py
- market_data/models.py
- market_data/events.py
- trading/
- strategies/

---

## Implementation

Implemented during:

Sprint 2 – Task 12

Key components include:

- MarketDataProvider
- DefaultNormalizer
- InMemoryMarketDataCache
- MarketDataPipelineService
- Market Data Events
- Exchange-independent Domain Models

The Market Data Framework ensures that every downstream component receives standardized market information regardless of the originating provider.

---

## Future Considerations

Future enhancements may include:

- Multi-exchange aggregation
- Instrument registry for canonical symbol mapping
- Market depth normalization
- Funding rate normalization
- Open interest normalization
- Options market support
- Futures market support
- Cross-exchange arbitrage feeds
- Time-series compression
- High-frequency market data optimization

These enhancements should preserve the exchange-agnostic architecture and continue exposing only standardized domain models to the rest of the AI Trading Operating System.