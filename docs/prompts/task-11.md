# Project Context

Project: AI Trading Operating System

Version: Sprint 2

---

# Background

Sprint 1 established the complete infrastructure layer of the system.

The following components already exist and must be reused.

## Completed Components

- Domain Models
- Exchange Interface
- Event Bus
- Dependency Injection Container
- Structured Logging
- Repository Pattern
- Persistence Service
- Testing Framework

The Trading Engine must build on top of these components.

It must not replace, duplicate, or bypass any existing infrastructure.

---

# Purpose

The Trading Engine is the orchestration layer of the AI Trading Operating System.

It is responsible for coordinating the lifecycle of the application and connecting infrastructure components together.

It is **not responsible** for:

- strategy calculations
- technical indicators
- exchange communication
- order execution
- risk calculations
- portfolio calculations
- notification delivery

Those responsibilities belong to dedicated components that will be implemented in later tasks.

---

# Design Philosophy

The Trading Engine must remain extremely small.

Its purpose is orchestration only.

Every business decision must be delegated to another component.

The engine should be considered the operating system of the application.

It coordinates services but performs no trading logic.

---

# Architecture Principles

The implementation must continue following the same principles established during Sprint 1.

## Single Responsibility Principle

Each class must perform only one responsibility.

## Dependency Inversion Principle

The Trading Engine must depend only on interfaces and abstractions.

No component may instantiate its own dependencies.

Everything must be supplied through Dependency Injection.

## Open / Closed Principle

The engine must be extendable without modification.

Future services should plug into the engine without requiring changes to the engine itself.

## Event Driven Architecture

The Trading Engine communicates lifecycle changes through the existing Event Bus.

Components must remain loosely coupled.

## Repository Pattern

The Trading Engine must never communicate directly with storage.

Persistence must occur only through the existing Persistence Service.

---

# Mandatory Architecture Review

Before implementing any code, perform a complete review of the existing project.

Search for existing implementations related to:

- trading
- engine
- coordinator
- lifecycle
- state
- orchestration
- services

Explain:

1. What already exists.
2. What should be reused.
3. What should be extended.
4. What new files are actually required.
5. Whether implementing Task 11 would duplicate existing functionality.

Present the review before writing any code.

If duplicate functionality already exists, extend it instead of replacing it.

---

# Current Task

Implement the Trading Engine Core.

The Trading Engine must coordinate the existing infrastructure built during Sprint 1.

The implementation must populate only the existing files inside:

```
trading/
```

Do not rename files.

Do not move files.

Do not create additional packages unless absolutely required.

Stop after Task 11 is complete.
# Files to Populate

Populate only the existing files inside the `trading/` package.

Do not create additional modules unless absolutely necessary.

The existing package structure is:

trading/
├── __init__.py
├── engine.py
├── coordinator.py
├── lifecycle.py
├── state.py
├── interfaces.py
└── exceptions.py

No other files should be created.

---

# File Responsibilities

## trading/__init__.py

Purpose:

Expose the Trading Engine public API.

Re-export only the primary public classes.

No implementation logic.

No business logic.

---

## trading/state.py

Purpose:

Maintain the runtime state of the Trading Engine.

This module represents runtime information only.

It must not contain business logic.

Suggested contents:

- EngineState enumeration
- RuntimeState dataclass
- Engine statistics
- Current lifecycle state
- Started timestamp
- Last activity timestamp
- Last error
- Orders processed counter
- Trades processed counter
- Signals processed counter

Runtime state should be immutable where practical.

The Trading Engine owns the RuntimeState.

Other components may read it but must not modify it directly.

---

## trading/exceptions.py

Purpose:

Contain only Trading Engine specific exceptions.

Examples:

TradingEngineError

EngineAlreadyRunningError

EngineNotRunningError

EngineInitializationError

LifecycleTransitionError

CoordinatorError

ServiceRegistrationError

No exception handling logic belongs here.

Only exception definitions.

---

## trading/interfaces.py

Purpose:

Define abstractions required by the Trading Engine.

Only Protocols or Abstract Base Classes.

No implementations.

Interfaces should include:

Lifecycle

Coordinator

StrategyManager

RiskManager

OrderManager

PortfolioManager

MarketDataService

NotificationService

ExchangeService

PersistenceService

Every future implementation must satisfy these interfaces.

The Trading Engine depends only on these abstractions.

---

## trading/lifecycle.py

Purpose:

Manage engine lifecycle transitions.

Responsibilities:

Validate state transitions.

Prevent invalid transitions.

Maintain lifecycle state.

Publish lifecycle events.

No coordination logic.

No trading logic.

Supported lifecycle:

CREATED

INITIALIZING

STARTING

RUNNING

PAUSED

STOPPING

STOPPED

FAILED

Allowed transitions should be explicitly defined.

Invalid transitions should raise TradingEngine exceptions.

The lifecycle manager must be thread-safe.

---

## trading/coordinator.py

Purpose:

Coordinate infrastructure components.

This class orchestrates communication between services.

It must never perform business decisions.

Responsibilities:

Start infrastructure services.

Stop infrastructure services.

Coordinate lifecycle.

Publish events.

Write logs.

Coordinate persistence.

Coordinate notifications.

Delegate work to other components.

It must never:

calculate indicators

calculate signals

place trades

evaluate strategies

calculate risk

communicate with exchanges

manage positions

Everything should be delegated.

---

## trading/engine.py

Purpose:

The Trading Engine.

This is the public entry point.

Responsibilities:

Start engine

Stop engine

Pause engine

Resume engine

Health check

Status reporting

Runtime statistics

Coordinate through the Coordinator.

Maintain RuntimeState.

Use Dependency Injection exclusively.

Never instantiate collaborators.

Never communicate directly with:

Binance

Zerodha

SQLite

Redis

Telegram

Discord

Email

Everything must pass through interfaces.

The engine should remain intentionally small.

It is an orchestrator.

Nothing more.

---

# Public Methods

TradingEngine

start()

stop()

pause()

resume()

status()

health()

uptime()

state()

statistics()

---

TradingCoordinator

start_services()

stop_services()

register_service()

unregister_service()

publish_event()

---

LifecycleManager

transition()

current_state()

can_transition()

reset()
# Dependency Injection

The Trading Engine must use the existing Dependency Injection container created during Sprint 1.

Do not instantiate dependencies directly.

Do not use global objects.

Every dependency must be injected through constructors.

The Trading Engine must depend only on abstractions.

The following components should be resolved through the existing DI container:

- EventBus
- LoggerFactory
- PersistenceService
- TradingCoordinator
- LifecycleManager

Future components that must also be injectable:

- StrategyManager
- RiskManager
- OrderManager
- PortfolioManager
- MarketDataService
- NotificationService
- ExchangeService

No dependency should be manually constructed inside the Trading Engine.

---

# Event Driven Architecture

The Trading Engine must integrate with the existing Event Bus.

It must publish lifecycle events only.

It must not publish trading events.

Create Trading Engine specific lifecycle events.

Examples:

EngineInitializing

EngineStarting

EngineStarted

EnginePaused

EngineResumed

EngineStopping

EngineStopped

EngineFailed

These events should inherit from the existing Event base class.

Do not modify the Event Bus implementation.

Reuse it exactly as implemented during Sprint 1.

---

# Logging

Reuse the existing LoggerFactory.

Every lifecycle transition should be logged.

Examples:

Engine initializing

Engine started

Engine paused

Engine resumed

Engine stopping

Engine stopped

Engine failure

All logs should use structured logging.

Correlation IDs must continue working without modification.

The Trading Engine must never write directly to files.

Logging must occur only through LoggerFactory.

---

# Persistence Integration

Reuse the existing Persistence Service.

The Trading Engine must not access repositories directly.

The Trading Engine must never communicate directly with:

- MemoryRepository
- SQLite
- PostgreSQL
- Redis

Future persistence operations must occur through the existing PersistenceService abstraction.

Task 11 should only keep a reference to PersistenceService.

No persistence logic should be implemented yet.

---

# Configuration

Reuse the existing configuration infrastructure.

Do not create another configuration system.

Configuration should always be injected.

Never read configuration directly from files inside the Trading Engine.

---

# Error Handling

The Trading Engine should fail safely.

Unexpected failures should:

Log the exception.

Publish an EngineFailed event.

Move the LifecycleManager into FAILED state.

Avoid leaving partially initialized services.

Do not terminate the application unexpectedly.

---

# Thread Safety

Lifecycle transitions must be thread-safe.

State updates must be synchronized.

Avoid race conditions.

The Trading Engine should be designed for future concurrent workloads.

---

# Testing Requirements

Reuse the existing testing framework.

Do not introduce another testing framework.

Tests should include:

## Unit Tests

TradingEngine

TradingCoordinator

LifecycleManager

RuntimeState

Engine exceptions

Dependency Injection registration

Lifecycle transitions

## Integration Tests

TradingEngine + EventBus

TradingEngine + LoggerFactory

TradingEngine + PersistenceService

TradingEngine + DI Container

Use fake implementations where appropriate.

Avoid timing-based assertions.

Do not use sleep().

Use deterministic testing.

---

# Constraints

The Trading Engine must NOT:

Connect to Binance.

Connect to Zerodha.

Perform paper trading.

Evaluate strategies.

Calculate indicators.

Generate signals.

Approve trades.

Reject trades.

Calculate portfolio values.

Manage positions.

Execute orders.

Send notifications.

Perform database operations.

Read configuration files.

Create threads manually.

Contain business logic.

Its only responsibility is orchestration.

---

# Future Extension Points

The Trading Engine should be designed so the following future components can plug in without modifying the engine:

Market Data Pipeline

Strategy Framework

Risk Engine

Order Manager

Portfolio Manager

Paper Trading Engine

Backtesting Engine

Live Exchange Adapter

Notification Services

Analytics

Dashboard

Monitoring

The engine should remain closed for modification but open for extension.
# Expected Output

After completing Task 11, provide a comprehensive explanation of the implementation.

Do not only list files.

Explain the architecture.

The explanation must include the following sections.

---

## 1. Architecture Overview

Explain:

- Why the Trading Engine exists.
- Why it is an orchestration layer.
- Why it contains no business logic.
- How it coordinates existing infrastructure.

---

## 2. Dependency Injection

Explain:

How the Trading Engine uses the existing Dependency Injection container.

Describe:

- constructor injection
- service registration
- singleton usage
- dependency resolution

Explain why Dependency Injection makes the Trading Engine easier to test and extend.

---

## 3. Event Driven Architecture

Explain:

How the Trading Engine integrates with the existing Event Bus.

Describe:

- lifecycle events
- event publishing
- loose coupling
- future event expansion

Do not discuss trading events.

Only explain lifecycle events.

---

## 4. Lifecycle Management

Explain:

The lifecycle state machine.

Describe every state.

Explain:

- valid transitions
- invalid transitions
- failure handling
- restart behavior

---

## 5. Coordinator

Explain why orchestration is delegated to TradingCoordinator.

Describe:

- responsibilities
- interactions
- delegation

Explain why business logic does not belong inside the coordinator.

---

## 6. Runtime State

Explain:

How RuntimeState represents the current status of the engine.

Describe:

- timestamps
- counters
- lifecycle
- statistics
- error tracking

Explain why RuntimeState should remain lightweight.

---

## 7. Logging

Explain:

How LoggerFactory is reused.

Describe:

- structured logging
- lifecycle logging
- correlation IDs

Explain why the Trading Engine should never log directly.

---

## 8. Persistence

Explain:

Why PersistenceService is injected instead of repositories.

Explain how future persistence will integrate without changing the Trading Engine.

---

## 9. Future Extension

Explain how the following future components can integrate without modifying the Trading Engine.

- Market Data
- Strategy Framework
- Risk Engine
- Order Manager
- Portfolio Manager
- Paper Trading
- Backtesting
- Live Trading
- Notifications
- Dashboard
- Analytics

---

# Implementation Summary

Provide a concise summary of:

Files populated

Classes added

Public APIs

Dependency Injection registrations

Lifecycle events

Tests created

No unrelated modules modified

---

# Acceptance Criteria

Task 11 is considered complete only if all of the following are true.

✓ Existing infrastructure reused

✓ No duplicate implementations

✓ Trading Engine contains no business logic

✓ Dependency Injection used throughout

✓ Event Bus integrated

✓ LoggerFactory integrated

✓ PersistenceService integrated

✓ RuntimeState implemented

✓ LifecycleManager implemented

✓ Coordinator implemented

✓ Thread-safe lifecycle transitions

✓ Trading Engine specific lifecycle events

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

adapters/

tests/

Do not refactor existing infrastructure.

Reuse it exactly as implemented.

If integration requires a minimal change to an existing module, explain why before making the change.

---

# Stop Condition

Stop immediately after Task 11 is complete.

Do not begin Task 12.

Do not implement:

Market Data

Strategies

Risk Engine

Order Management

Portfolio Management

Paper Trading

Backtesting

Live Exchange Integration

Notifications

Dashboard

Analytics

Only complete the Trading Engine Core.

End your response with:

"Task 11 complete. Standing by for review."