# Task 22 — Performance Analytics Framework

## Objective

Build the Performance Analytics Framework.

This framework is responsible for analyzing completed trading activity and producing standardized performance metrics for the entire trading system.

It must remain completely independent of any exchange, broker, strategy, portfolio implementation, or execution engine.

The framework consumes standardized outputs from previously completed frameworks and transforms them into immutable analytical models.

It must never execute trades.

It must never manage positions.

It must never modify portfolio state.

Its sole responsibility is performance analysis.

---

# Existing Architecture

The following frameworks already exist and MUST NOT be modified.

Core Infrastructure

Trading Engine

Market Data Framework

Strategy Framework

Risk Framework

Order Management Framework

Execution Framework

Exchange Adapter Framework

Binance Spot Adapter

Portfolio Management Framework

Position Management Framework

Trade Lifecycle Framework

The Performance Analytics Framework must integrate with them only through their public abstractions.

No existing framework may be edited.

---

# Architecture Position

Market Data
        │
        ▼
Trading Engine
        │
        ▼
Strategy
        │
        ▼
Risk
        │
        ▼
Order Management
        │
        ▼
Execution
        │
        ▼
Exchange Adapter
        │
        ▼
Portfolio
        │
        ▼
Position
        │
        ▼
Trade Lifecycle
        │
        ▼
Performance Analytics

Performance Analytics consumes completed trading activity.

It never feeds decisions back into execution.

It is read-only.

---

# Responsibilities

The framework shall calculate:

Returns

Profit & Loss

Risk Metrics

Trading Statistics

Portfolio Statistics

Position Statistics

Benchmark Comparison

Historical Performance

Performance Snapshots

Performance Reports

It never stores market data.

It never performs execution.

It never communicates directly with exchanges.

---

# Package Structure

Populate only the existing empty files.

performance/

__init__.py

state.py

models.py

context.py

interfaces.py

exceptions.py

events.py

returns.py

risk.py

statistics.py

benchmarking.py

registry.py

manager.py

engine.py

No new files.

No file renames.

No infrastructure changes.

---

# Infrastructure Reuse

Reuse all existing project infrastructure.

Do not duplicate anything already implemented.

Reuse:

EventBus

LoggerFactory

Dependency Injection Container

ExecutionResult

PortfolioResult

PositionResult

TradeResult

Decimal models

Immutable dataclasses

Registry pattern

Manager pattern

Engine pattern

Thread-safe locking

Structured logging

Event publishing

No duplicate abstractions.

---

# Framework Philosophy

The framework must be:

Exchange Independent

Broker Independent

Stateless where possible

Immutable

Thread Safe

Deterministic

Testable

Dependency Injected

Event Driven

Open for Extension

Closed for Modification

All calculations must use Decimal.

Never float.

---

# Components

The framework shall consist of:

PerformanceEngine

PerformanceManager

ReturnsCalculator

RiskCalculator

StatisticsCalculator

BenchmarkingService

PerformanceRegistry

PerformanceContext

PerformanceResult

Each component must have a single responsibility.

---

# Integration

Consume:

PortfolioResult

PositionResult

TradeResult

ExecutionResult

Consume market prices only through standardized models.

Never query exchanges.

Never call Binance.

Never access REST.

Never access WebSockets.

---

# Thread Safety

Returns

Risk

Statistics

Benchmarking

must remain completely stateless.

Registry must be protected with Lock.

Manager must execute atomically.

No shared mutable state outside registry.

---

# Logging

Reuse LoggerFactory.

Manager owns logging.

Calculators remain pure.

Never log raw financial datasets.

Log lifecycle only.

Use correlation IDs.

---

# Event Bus

Reuse EventBus.

Publish events only after successful calculations.

Never publish partial state.

Never publish failed calculations.

Performance subscribers must remain completely decoupled.

---

# Dependency Injection

Register every component through the existing container.

Register abstractions only.

Singleton registrations.

Constructor Injection only.

Never instantiate dependencies manually.

---

# General Rules

No network access.

No exchange SDKs.

No REST calls.

No WebSocket code.

No persistence layer.

No database.

No caching.

No sleeps.

No randomness.

No time delays.

No unrelated module modifications.

Only populate the existing performance package.
# Performance Context

Every calculation must execute using a single immutable PerformanceContext.

The context represents one complete analytical snapshot.

It contains:

ExecutionResult

PortfolioResult

PositionResult

TradeResult

Market Prices

Benchmark Prices

Timestamp

Correlation ID

Metadata

The context must never expose mutable state.

It must never access infrastructure.

It must never call external services.

All services operate only from PerformanceContext.

---

# Performance Models

Create immutable models.

PerformanceStatus

PerformanceSnapshot

PerformanceMetrics

ReturnsMetrics

RiskMetrics

StatisticsMetrics

BenchmarkMetrics

PerformanceResult

PerformanceMetadata

PerformanceIdentifier

PerformanceValue

PerformanceSummary

All models must use frozen dataclasses.

Every monetary value must use Decimal.

Never float.

---

# Returns Calculator

Responsible only for returns.

Input:

PerformanceContext

Output:

ReturnsMetrics

Calculate:

Daily Return

Weekly Return

Monthly Return

Quarterly Return

Yearly Return

Total Return

Compound Return

CAGR

Absolute Return

Percentage Return

Realized Return

Unrealized Return

Never calculate risk.

Never calculate statistics.

Remain stateless.

Pure function.

---

# Risk Calculator

Responsible only for risk analytics.

Input:

PerformanceContext

Output:

RiskMetrics

Calculate:

Volatility

Sharpe Ratio

Sortino Ratio

Calmar Ratio

Maximum Drawdown

Average Drawdown

Downside Deviation

Upside Capture

Risk Reward Ratio

Recovery Factor

Never calculate returns.

Never calculate statistics.

Remain completely stateless.

---

# Statistics Calculator

Responsible only for trading statistics.

Calculate:

Total Trades

Winning Trades

Losing Trades

Open Trades

Closed Trades

Win Rate

Loss Rate

Average Win

Average Loss

Largest Winner

Largest Loser

Average Holding Time

Profit Factor

Expectancy

Average Position Size

Average Trade Duration

Best Day

Worst Day

Remain stateless.

Pure calculations only.

---

# Benchmarking Service

Responsible only for benchmark comparison.

Never calculate returns.

Never calculate statistics.

Never calculate risk.

Input:

PerformanceContext

Output:

BenchmarkMetrics

Support:

Benchmark Return

Relative Return

Alpha

Beta

Tracking Error

Information Ratio

Benchmark Drawdown

Excess Return

The benchmark implementation must remain abstract.

Future benchmarks:

BTC

ETH

NIFTY

S&P500

NASDAQ

Paper Index

Custom Index

must plug in without modifying existing code.

---

# Performance Registry

Thread-safe.

Single responsibility.

Responsibilities:

Register

Unregister

Lookup

Exists

List

Clear

Duplicate registration raises:

DuplicatePerformanceError

Registry never creates objects.

Only stores references.

Protect with Lock.

---

# Performance Manager

Coordinates entire workflow.

Pipeline:

Receive PerformanceContext

↓

Returns Calculator

↓

Risk Calculator

↓

Statistics Calculator

↓

Benchmarking Service

↓

Performance Snapshot

↓

Performance Result

↓

Publish Events

↓

Return Result

Manager owns logging.

Manager owns orchestration.

Manager owns exception handling.

Never perform calculations itself.

---

# Performance Engine

Public entry point.

Responsibilities:

Start

Stop

Analyze

Delegate to Manager

Publish lifecycle events

Return PerformanceResult

No calculations.

No business logic.

Only orchestration.

Reuse Engine pattern from previous frameworks.

---

# Interfaces

Define abstractions only.

PerformanceEngine

PerformanceManager

ReturnsCalculator

RiskCalculator

StatisticsCalculator

BenchmarkingService

PerformanceRegistry

Every implementation depends upon interfaces.

No concrete dependency references.

Constructor Injection only.

---

# Events

Create immutable events.

PerformanceAnalysisStarted

PerformanceAnalysisCompleted

ReturnsCalculated

RiskCalculated

StatisticsCalculated

BenchmarkCalculated

PerformanceSnapshotCreated

PerformanceEngineStarted

PerformanceEngineStopped

PerformanceErrorOccurred

Every event inherits Event.

Publish only after successful stage completion.

Never publish partial calculations.

---

# Exceptions

PerformanceError

ReturnsCalculationError

RiskCalculationError

StatisticsCalculationError

BenchmarkCalculationError

PerformanceRegistryError

DuplicatePerformanceError

PerformanceNotFoundError

Every framework exception derives from PerformanceError.

No internal exceptions escape the framework.

Manager always returns PerformanceResult.
# Dependency Injection

Reuse the existing Dependency Injection Container.

Create:

register_performance(container)

Register the following as singleton services:

ReturnsCalculator

RiskCalculator

StatisticsCalculator

BenchmarkingService

PerformanceRegistry

PerformanceManager

PerformanceEngine

Bind every implementation to its interface.

Use Constructor Injection only.

Never instantiate dependencies manually.

Never create global objects.

Never create service locators.

Future implementations must replace components through DI only.

---

# Event Driven Architecture

Reuse the shared EventBus.

The Performance Framework must publish events only.

It never directly invokes subscribers.

Events shall be published in the following order.

PerformanceAnalysisStarted

ReturnsCalculated

RiskCalculated

StatisticsCalculated

BenchmarkCalculated

PerformanceSnapshotCreated

PerformanceAnalysisCompleted

If an exception occurs:

PerformanceErrorOccurred

No partial events.

No duplicate events.

Every event must be immutable.

Every event inherits the project's Event base class.

---

# Performance Snapshot

Every completed analysis creates one immutable snapshot.

Snapshot contains:

Performance Identifier

Timestamp

Returns Metrics

Risk Metrics

Trading Statistics

Benchmark Metrics

Portfolio Summary

Position Summary

Trade Summary

Correlation ID

Metadata

Snapshots are read-only.

Never mutate an existing snapshot.

---

# Error Handling

The Manager coordinates exception handling.

Stage failures:

Returns → ReturnsCalculationError

Risk → RiskCalculationError

Statistics → StatisticsCalculationError

Benchmark → BenchmarkCalculationError

Registry → PerformanceRegistryError

Unexpected exceptions shall be wrapped inside PerformanceError.

Manager publishes:

PerformanceErrorOccurred

Return:

PerformanceResult(status=FAILED)

Framework exceptions must never escape into callers.

---

# Thread Safety

Returns Calculator

Risk Calculator

Statistics Calculator

Benchmarking Service

must remain stateless.

Registry protected with Lock.

Manager executes entire workflow atomically.

PerformanceContext immutable.

Performance models immutable.

No shared mutable state.

---

# Logging

Reuse LoggerFactory.

Logger Names:

performance.engine

performance.manager

Manager owns narrative.

Calculators never log.

Never log:

Portfolio contents

Trade lists

Benchmark datasets

Large price history

Log:

Lifecycle

Identifiers

Timing

Correlation IDs

Errors

---

# Testing

Create support fakes.

tests/support/performance_fakes.py

Create unit tests.

tests/unit/test_performance.py

Test:

Returns calculations

Risk calculations

Statistics calculations

Benchmark calculations

Registry

Manager

Engine

Events

Exceptions

Dependency Injection

Create integration tests.

tests/integration/test_performance_flow.py

Verify:

Portfolio → Performance

Position → Performance

Trade → Performance

Execution → Performance

EventBus integration

Thread safety

Manager orchestration

Registry lifecycle

Framework startup

Framework shutdown

No live network.

No randomness.

No sleeps.

Deterministic execution.

Reuse project testing patterns.

---

# Implementation Rules

Populate only the existing empty files.

Do not modify unrelated modules.

Do not modify previous frameworks.

Do not duplicate infrastructure.

Reuse existing abstractions.

Reuse EventBus.

Reuse LoggerFactory.

Reuse Dependency Injection.

Reuse immutable models where appropriate.

All calculations must use Decimal.

No float.

No external dependencies.

No exchange SDK.

No REST.

No WebSocket.

No persistence.

No database.

No cache.

No multiprocessing.

No asyncio unless existing infrastructure already requires it.

Framework must remain exchange independent.

---

# Acceptance Criteria

✓ Existing frameworks unchanged

✓ Infrastructure reused

✓ Engine implemented

✓ Manager implemented

✓ Returns Calculator implemented

✓ Risk Calculator implemented

✓ Statistics Calculator implemented

✓ Benchmarking Service implemented

✓ Registry implemented

✓ Immutable models

✓ Performance Context

✓ EventBus integration

✓ LoggerFactory integration

✓ Dependency Injection

✓ Thread-safe Registry

✓ Thread-safe Manager

✓ Stateless calculators

✓ Unit Tests

✓ Integration Tests

✓ Existing tests continue passing

✓ No unrelated module modifications

---

# Claude Execution Instructions

Read every file before writing.

Populate only the existing empty files.

Write in dependency order.

Do not skip interfaces.

Do not skip models.

Do not skip events.

Do not skip tests.

Create support fakes.

Create unit tests.

Create integration tests.

Run the complete test suite.

Report:

Files created

Classes

Interfaces

Events

Models

Dependency Injection

Testing

Architecture Summary

Acceptance Criteria

Do not stop until the entire framework is complete and all tests pass.

Expected final output:

Performance Analytics Framework complete.

Ready for review.