# Project Context

Project: AI Trading Operating System

Version: Sprint 2

Task: 13

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

Sprint 2 has established:

- Trading Engine
- Market Data Framework

The next layer is the Strategy Framework.

The Strategy Framework consumes normalized market data and produces standardized trading signals.

It must remain independent of:

- exchanges
- order execution
- risk management
- portfolio management

---

# Purpose

The Strategy Framework is responsible for:

- Receiving normalized market events
- Executing one or more trading strategies
- Producing standardized trading signals
- Publishing strategy events
- Remaining completely strategy-independent

The framework must never contain exchange-specific logic.

It must allow unlimited future strategies without modification.

---

# Design Philosophy

The Strategy Framework is an execution framework.

Individual strategies contain business logic.

The framework coordinates strategies.

It never performs technical analysis itself.

It must follow the Open/Closed Principle.

Adding a strategy should require:

1. Creating a new strategy class.
2. Registering it.
3. No modifications to existing framework code.

---

# Mandatory Architecture Review

Before implementing any code:

Review the existing project.

Search for:

- strategies
- strategy
- registry
- manager
- signals
- context
- events

Determine:

- What already exists
- What should be reused
- What should be extended
- Whether implementation would duplicate functionality

Present the review before writing code.

Reuse:

- Event Bus
- Trading Engine
- Market Data Framework
- Dependency Injection
- LoggerFactory
- Testing Framework

Do not duplicate existing infrastructure.

---

# Current Task

Populate only the existing files inside:

strategies/

Do not create additional packages.

Do not implement RSI.

Do not implement EMA.

Do not implement MACD.

Do not implement AI strategies.

Only implement the Strategy Framework.

Stop immediately after Task 13 is complete.
# Files to Populate

Populate only the existing files inside:

strategies/

├── __init__.py
├── base.py
├── context.py
├── events.py
├── exceptions.py
├── factory.py
├── interfaces.py
├── manager.py
├── registry.py
└── signals.py

Do not create additional modules.

Do not create strategy implementations.

---

# File Responsibilities

## __init__.py

Purpose:

Expose the Strategy Framework public API.

Re-export only the primary public classes.

No implementation logic.

---

## base.py

Purpose:

Contains the abstract base class for all strategies.

Responsibilities:

- Define the common strategy lifecycle.
- Define the standard execution interface.
- Provide shared validation hooks.
- Define metadata.

Every future strategy must inherit from this base class.

No concrete trading logic.

---

## context.py

Purpose:

Provide a standardized execution context.

The StrategyContext should contain everything required for a strategy to make a decision.

Examples:

- Market Snapshot
- Current Symbol
- Exchange
- Timeframe
- Latest Candle
- Recent Candles
- Order Book Snapshot
- Recent Trades
- Timestamp
- Optional metadata

Strategies receive one StrategyContext.

Strategies must never access the Market Data Cache directly.

---

## signals.py

Purpose:

Define standardized trading signals.

Examples:

SignalDirection

- BUY
- SELL
- HOLD
- CLOSE
- REDUCE
- INCREASE

TradingSignal

SignalMetadata

Signals should be immutable.

Signals should never contain exchange-specific fields.

Signals represent decisions only.

They never execute trades.

---

## interfaces.py

Purpose:

Define Strategy Framework interfaces.

Examples:

Strategy

StrategyManager

StrategyRegistry

StrategyFactory

SignalPublisher

No implementations.

Only Protocols or Abstract Base Classes.

---

## registry.py

Purpose:

Maintain available strategies.

Responsibilities:

Register strategy

Unregister strategy

Enable strategy

Disable strategy

List strategies

Retrieve strategy

The registry must never execute strategies.

It only manages registration.

---

## manager.py

Purpose:

Coordinate strategy execution.

Responsibilities:

Receive StrategyContext.

Retrieve enabled strategies.

Execute strategies.

Collect signals.

Publish strategy events.

Return generated signals.

The manager never evaluates indicators itself.

The manager never decides BUY or SELL.

That responsibility belongs to individual strategies.

---

## factory.py

Purpose:

Create strategy instances.

The factory must support future Dependency Injection.

It should isolate construction from execution.

The manager must never manually instantiate strategies.

---

## events.py

Purpose:

Define Strategy Framework events.

Examples:

StrategyRegistered

StrategyEnabled

StrategyDisabled

StrategyStarted

StrategyStopped

SignalGenerated

StrategyError

Every event must inherit from the existing Event base class.

---

## exceptions.py

Purpose:

Contain Strategy Framework exceptions.

Examples:

StrategyError

StrategyRegistrationError

StrategyExecutionError

InvalidStrategyError

DuplicateStrategyError

StrategyDisabledError

No handling logic.

Only exception definitions.
# Dependency Injection

The Strategy Framework must reuse the existing Dependency Injection container.

Do not instantiate strategies manually.

Do not instantiate dependencies directly.

Every dependency must be supplied through constructor injection.

The Strategy Manager should depend only on abstractions.

Dependencies should include:

- EventBus
- LoggerFactory
- TradingEngine
- MarketDataService
- StrategyRegistry
- StrategyFactory

Future dependencies that must also be injectable:

- RiskEngine
- PortfolioManager
- NotificationService
- MetricsCollector

The Strategy Framework must never manually create:

- strategies
- loggers
- event buses
- providers

Everything must be resolved through the existing DI container.

---

# Event Driven Architecture

Reuse the existing Event Bus.

Do not modify the Event Bus.

The Strategy Framework publishes strategy events only.

Examples:

StrategyRegistered

StrategyEnabled

StrategyDisabled

StrategyStarted

StrategyStopped

SignalGenerated

StrategyError

Do not publish:

Orders

Trades

Portfolio updates

Risk decisions

Execution events

Every strategy event must inherit from the existing Event base class.

---

# Strategy Execution Flow

The Strategy Framework should process market data in the following order.

Market Data Event

↓

Trading Engine

↓

Strategy Manager

↓

Strategy Registry

↓

Enabled Strategies

↓

Trading Signals

↓

Signal Events

↓

Event Bus

↓

Risk Engine (future)

Each stage has one responsibility.

No stage should bypass another.

---

# Strategy Registry

The registry is responsible only for managing strategies.

Supported operations:

register()

unregister()

enable()

disable()

exists()

list()

get()

The registry must never:

Execute strategies

Generate signals

Publish events

Perform calculations

Its only responsibility is registration and lookup.

---

# Strategy Manager

The Strategy Manager coordinates execution.

Responsibilities:

Receive StrategyContext

Retrieve enabled strategies

Execute each enabled strategy

Collect generated TradingSignals

Publish SignalGenerated events

Return generated signals

The Strategy Manager must never:

Calculate indicators

Make BUY or SELL decisions

Contain trading algorithms

Manage risk

Execute orders

The Strategy Manager coordinates only.

---

# Strategy Factory

The factory isolates object creation.

Responsibilities:

Construct strategies

Inject dependencies

Support future plugin loading

Support Dependency Injection

The factory must never:

Execute strategies

Store strategies

Register strategies

The factory only creates strategy instances.

---

# StrategyContext

Every strategy receives one immutable StrategyContext.

The StrategyContext should contain:

Current Market Snapshot

Recent Candles

Recent Trades

Order Book Snapshot

Exchange

Symbol

Timeframe

Timestamp

Optional metadata

Strategies must never read directly from:

Market Data Cache

Trading Engine

Repositories

Databases

They operate only on the supplied StrategyContext.

---

# Trading Signals

Signals represent trading intent only.

Signals must never:

Execute orders

Modify positions

Access exchanges

Perform persistence

Every signal should include:

Signal ID

Strategy Name

Symbol

Direction

Confidence

Timestamp

Metadata

Signals should be immutable.

Confidence must remain between 0.0 and 1.0.

---

# Logging

Reuse the existing LoggerFactory.

Log framework events only.

Examples:

Strategy registered

Strategy enabled

Strategy disabled

Strategy started

Strategy stopped

Signal generated

Strategy failure

Use structured logging.

Correlation IDs must continue functioning.

Strategies themselves should avoid excessive logging.

---

# Error Handling

Strategy failures must not stop the framework.

If one strategy fails:

Log the error.

Publish StrategyError.

Continue executing remaining strategies.

No single strategy should crash the Strategy Manager.

---

# Thread Safety

The registry must be thread-safe.

The Strategy Manager should safely execute multiple strategies.

Future concurrent execution should be possible without redesign.

Do not manually create unmanaged threads.

---

# Testing Requirements

Reuse the existing testing framework.

Required unit tests:

StrategyRegistry

StrategyManager

StrategyFactory

StrategyContext

TradingSignal

Framework events

Exceptions

Dependency Injection registration

Required integration tests:

MarketDataService → StrategyManager

StrategyManager → Registry

Registry → Factory

StrategyManager → EventBus

Signal generation flow

Use fake strategies.

Do not implement RSI or EMA.

Avoid timing-based assertions.

Do not use sleep().

All tests must be deterministic.

---

# Constraints

The Strategy Framework must NOT:

Implement RSI

Implement EMA

Implement MACD

Implement AI strategies

Implement Turtle Trading

Connect to exchanges

Access Market Data Cache directly

Manage risk

Execute orders

Persist signals

Calculate portfolio values

Read configuration files directly

Instantiate dependencies manually

Contain exchange-specific logic

Everything must remain framework-only.

---

# Future Extension Points

The framework should support future implementation of:

RSI Strategy

EMA Strategy

MACD Strategy

Bollinger Bands Strategy

Ichimoku Strategy

VWAP Strategy

SuperTrend Strategy

Volume Profile Strategy

AI Strategy

Machine Learning Strategy

Reinforcement Learning Strategy

Multi-Timeframe Strategies

Composite Strategies

without modifying the Strategy Framework.
# Dependency Injection

The Strategy Framework must reuse the existing Dependency Injection container.

Do not instantiate strategies manually.

Do not instantiate dependencies directly.

Every dependency must be supplied through constructor injection.

The Strategy Manager should depend only on abstractions.

Dependencies should include:

- EventBus
- LoggerFactory
- TradingEngine
- MarketDataService
- StrategyRegistry
- StrategyFactory

Future dependencies that must also be injectable:

- RiskEngine
- PortfolioManager
- NotificationService
- MetricsCollector

The Strategy Framework must never manually create:

- strategies
- loggers
- event buses
- providers

Everything must be resolved through the existing DI container.

---

# Event Driven Architecture

Reuse the existing Event Bus.

Do not modify the Event Bus.

The Strategy Framework publishes strategy events only.

Examples:

StrategyRegistered

StrategyEnabled

StrategyDisabled

StrategyStarted

StrategyStopped

SignalGenerated

StrategyError

Do not publish:

Orders

Trades

Portfolio updates

Risk decisions

Execution events

Every strategy event must inherit from the existing Event base class.

---

# Strategy Execution Flow

The Strategy Framework should process market data in the following order.

Market Data Event

↓

Trading Engine

↓

Strategy Manager

↓

Strategy Registry

↓

Enabled Strategies

↓

Trading Signals

↓

Signal Events

↓

Event Bus

↓

Risk Engine (future)

Each stage has one responsibility.

No stage should bypass another.

---

# Strategy Registry

The registry is responsible only for managing strategies.

Supported operations:

register()

unregister()

enable()

disable()

exists()

list()

get()

The registry must never:

Execute strategies

Generate signals

Publish events

Perform calculations

Its only responsibility is registration and lookup.

---

# Strategy Manager

The Strategy Manager coordinates execution.

Responsibilities:

Receive StrategyContext

Retrieve enabled strategies

Execute each enabled strategy

Collect generated TradingSignals

Publish SignalGenerated events

Return generated signals

The Strategy Manager must never:

Calculate indicators

Make BUY or SELL decisions

Contain trading algorithms

Manage risk

Execute orders

The Strategy Manager coordinates only.

---

# Strategy Factory

The factory isolates object creation.

Responsibilities:

Construct strategies

Inject dependencies

Support future plugin loading

Support Dependency Injection

The factory must never:

Execute strategies

Store strategies

Register strategies

The factory only creates strategy instances.

---

# StrategyContext

Every strategy receives one immutable StrategyContext.

The StrategyContext should contain:

Current Market Snapshot

Recent Candles

Recent Trades

Order Book Snapshot

Exchange

Symbol

Timeframe

Timestamp

Optional metadata

Strategies must never read directly from:

Market Data Cache

Trading Engine

Repositories

Databases

They operate only on the supplied StrategyContext.

---

# Trading Signals

Signals represent trading intent only.

Signals must never:

Execute orders

Modify positions

Access exchanges

Perform persistence

Every signal should include:

Signal ID

Strategy Name

Symbol

Direction

Confidence

Timestamp

Metadata

Signals should be immutable.

Confidence must remain between 0.0 and 1.0.

---

# Logging

Reuse the existing LoggerFactory.

Log framework events only.

Examples:

Strategy registered

Strategy enabled

Strategy disabled

Strategy started

Strategy stopped

Signal generated

Strategy failure

Use structured logging.

Correlation IDs must continue functioning.

Strategies themselves should avoid excessive logging.

---

# Error Handling

Strategy failures must not stop the framework.

If one strategy fails:

Log the error.

Publish StrategyError.

Continue executing remaining strategies.

No single strategy should crash the Strategy Manager.

---

# Thread Safety

The registry must be thread-safe.

The Strategy Manager should safely execute multiple strategies.

Future concurrent execution should be possible without redesign.

Do not manually create unmanaged threads.

---

# Testing Requirements

Reuse the existing testing framework.

Required unit tests:

StrategyRegistry

StrategyManager

StrategyFactory

StrategyContext

TradingSignal

Framework events

Exceptions

Dependency Injection registration

Required integration tests:

MarketDataService → StrategyManager

StrategyManager → Registry

Registry → Factory

StrategyManager → EventBus

Signal generation flow

Use fake strategies.

Do not implement RSI or EMA.

Avoid timing-based assertions.

Do not use sleep().

All tests must be deterministic.

---

# Constraints

The Strategy Framework must NOT:

Implement RSI

Implement EMA

Implement MACD

Implement AI strategies

Implement Turtle Trading

Connect to exchanges

Access Market Data Cache directly

Manage risk

Execute orders

Persist signals

Calculate portfolio values

Read configuration files directly

Instantiate dependencies manually

Contain exchange-specific logic

Everything must remain framework-only.

---

# Future Extension Points

The framework should support future implementation of:

RSI Strategy

EMA Strategy

MACD Strategy

Bollinger Bands Strategy

Ichimoku Strategy

VWAP Strategy

SuperTrend Strategy

Volume Profile Strategy

AI Strategy

Machine Learning Strategy

Reinforcement Learning Strategy

Multi-Timeframe Strategies

Composite Strategies

without modifying the Strategy Framework.