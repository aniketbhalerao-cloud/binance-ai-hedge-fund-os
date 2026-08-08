# Task 34 — Background Workers Framework

---

# Sprint 14

## Framework

Background Workers Framework

---

# Objective

Design and implement a standalone Background Workers Framework that collects the running system's standardized outputs and produces deterministic, immutable worker request objects using the existing architecture without modifying any previous framework.

The framework consumes standardized outputs produced by the existing system (storage requests, report objects, notification requests, monitoring reports, and schedule requests), collects and plans them into worker requests, and produces immutable worker request objects only.

It must integrate seamlessly with:

- Storage Framework
- Reporting Framework
- Notification Framework
- Monitoring Framework
- Scheduler Framework

Supported worker queues:

- Immediate
- Delayed
- Scheduled
- Retry
- Priority
- Batch

The framework must never communicate directly with Binance or any exchange, and must never modify strategies, agent weights, or portfolios automatically. It never trains a model, makes a real network or API call, executes a background job, or calls an AI provider. Collection and planning are deterministic; the framework core is reproducible under test.

---

# Architecture Requirements

The framework must follow the project's established architecture:

- Clean Architecture
- Domain Driven Design
- SOLID Principles
- Immutable Models
- Dependency Injection
- Event Driven Architecture
- Thread Safety
- Deterministic Processing
- Registry-Owned State

No shortcuts.

---

# Package Structure

Create a new package:

workers/

containing exactly the following files:

```
workers/
    __init__.py
    state.py
    models.py
    context.py
    interfaces.py
    exceptions.py
    events.py
    collector.py
    planner.py
    dispatcher.py
    metrics.py
    registry.py
    manager.py
    engine.py
```

No additional files.

---

# Responsibilities

## Worker Engine

Public entry point.

Responsibilities:

- start()
- stop()
- enqueue()

Must delegate all work to the manager.

---

## Worker Manager

Coordinates the complete workflow.

Pipeline:

Worker Context

↓

Collector

↓

Planner

↓

Dispatcher

↓

Metrics

↓

Worker Result

Must load the running worker record, process one input atomically, create a new immutable record, and write it back.

---

## Collector

Responsible for:

- gathering standardized outputs from system frameworks
- normalizing job sources
- deriving job events
- building the job batch

Deterministic.

Stateless.

---

## Planner

Responsible for:

- planning the job content
- arranging job entries and queues
- ordering job elements
- resolving the worker requests

Never applies changes.

Stateless.

---

## Dispatcher

Responsible for:

- worker request generation
- job queue routing
- dispatch suggestions

Deterministic.

Never modifies strategies, agents, or portfolios.

Never executes, runs, or triggers a background job.

Stateless.

---

## Metrics

Calculate:

- Total Jobs
- Total Requests
- Average Job Score
- Highest Priority Job
- Lowest Priority Job
- Dispatch Ratio
- Pending Requests Count
- Suppressed Requests Count

Derived only.

Never stored independently.

---

## Registry

Thread-safe.

Responsibilities:

- register()
- unregister()
- get()
- exists()
- list()
- clear()

Protected using Lock.

The registry owns the running worker records and never creates them.

---

# Models

All models must be:

- frozen dataclasses
- Decimal only
- MappingProxyType metadata
- immutable

Required models include:

- WorkerState
- WorkerParameters
- JobSource
- JobBatch
- JobEntry
- WorkerRequest
- WorkerRecord
- WorkerMetrics
- WorkerSnapshot
- WorkerHistory
- WorkerResult

---

# Context

WorkerContext must contain:

- storage sources
- reporting sources
- notification sources
- monitoring sources
- scheduler sources
- worker parameters
- metadata

Immutable.

---

# Interfaces

Define abstractions only.

- Collector
- Planner
- Dispatcher
- WorkerMetricsCalculator
- WorkerRegistry
- WorkerManager
- WorkerEngine

Every implementation depends upon interfaces.

No concrete dependency references.

Constructor Injection only.

---

# Events

Implement:

WorkerStarted

JobsCollected

JobsQueued

RequestsDispatched

WorkerSnapshotCreated

WorkerMetricsUpdated

WorkerCompleted

WorkerCancelled

WorkerErrorOccurred

All inherit from Event.

Publish only after consistent state.

---

# Dependency Injection

Create:

register_workers(container)

Register:

- Collector
- Planner
- Dispatcher
- Metrics
- Registry
- Manager
- Engine

Reuse LoggerFactory.

Reuse EventBus.

Reuse ServiceContainer.

The framework must never instantiate a model, provider, or network client.

---

# Logging

Use LoggerFactory.

Logger names:

workers.engine

workers.manager

Collectors and calculators must never log.

Never log raw job datasets or sensitive financial detail.

---

# Error Handling

Create:

WorkerError

CollectionError

PlanningError

DispatchError

MetricsError

RegistryError

WorkerCancelledError

Manager must isolate failures.

Return:

WorkerResult(status=FAILED)

Never leak exceptions.

---

# Thread Safety

Stateless:

- Collector
- Planner
- Dispatcher
- Metrics

Thread-safe:

- Registry
- Manager

Immutable:

- Context
- Models
- Events

---

# Testing

Create:

tests/support/workers_fakes.py

tests/unit/test_workers.py

tests/integration/test_workers_flow.py

Requirements:

- deterministic
- no sleeps
- no randomness
- no network
- no model training

---

# Constraints

Do NOT modify:

- market_data
- strategies
- risk
- order_management
- execution
- portfolio
- positions
- trades
- performance
- backtesting
- paper_trading
- agents
- learning
- optimization
- monitoring
- dashboard
- notification
- reporting
- storage
- scheduler

Reuse existing infrastructure only.

The framework must never modify strategies, agent weights, or portfolios automatically, never train models, never sleep or block, never spawn a thread or process, never run a background job, never execute a queued job, never open a socket, never execute a trade, and never call external APIs or AI providers. WorkerRequest objects are immutable domain models only.

---

# Deliverables

Populate only the files listed above.

Implement:

- Engine
- Manager
- Collector
- Planner
- Dispatcher
- Metrics
- Registry

Integrate using Dependency Injection.

Publish Events.

Add unit tests.

Add integration tests.

Run the complete test suite.

All existing tests must continue passing.

---

# Acceptance Criteria

✓ Standalone Background Workers Framework

✓ Deterministic worker request generation

✓ Immutable Models

✓ Registry

✓ Dependency Injection

✓ Event Driven Architecture

✓ Thread-safe Components

✓ Unit Tests

✓ Integration Tests

✓ Existing Tests Passing

✓ No Model Training

✓ No Network or API Calls

✓ No Job Execution or Queue Triggering

✓ No Automatic Modification of Strategies or Agents

✓ No Unrelated Modules Modified

---

# Completion Checklist

After implementation, stop.

Provide:

1. Architecture Overview

2. Component Collaboration

3. Collector Design

4. Planner Design

5. Dispatcher Design

6. Metrics Design

7. Dependency Injection

8. Event Driven Architecture

9. Logging

10. Error Handling

11. Thread Safety

12. Future Extensions

Implementation Summary

Acceptance Criteria Checklist

Stop after reporting completion.
