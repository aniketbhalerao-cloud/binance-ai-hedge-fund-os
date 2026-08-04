# Task 25 — AI Decision Engine

---

# Sprint 5

## Framework

AI Decision Engine

---

# Objective

Design and implement a standalone AI Decision Engine that coordinates autonomous AI agents to produce standardized trading decisions using the existing architecture without modifying any previous framework.

The framework consumes standardized domain models produced by the existing system, orchestrates a set of specialised agents (Market, Strategy, Risk, Portfolio, and a coordinating CEO agent), aggregates their opinions into a single immutable decision, and remains completely independent of any exchange and of any specific AI provider.

It must integrate seamlessly with:

- Market Data Framework
- Strategy Framework
- Risk Framework
- Portfolio Management Framework
- Position Management Framework
- Performance Analytics Framework

The framework must never communicate directly with Binance or any exchange, and must never make a real LLM, model, API, or network call. Every agent is an injected abstraction; the framework core is deterministic.

---

# Architecture Requirements

The framework must follow the project's established architecture:

- Clean Architecture
- Domain Driven Design
- Dependency Injection
- Event Driven Architecture
- Immutable Models
- Thread-safe Components
- SOLID Principles

No shortcuts.

---

# Package Structure

Create a new package:

agents/

containing exactly the following files:

```
agents/
    __init__.py
    state.py
    models.py
    context.py
    interfaces.py
    exceptions.py
    events.py
    agent.py
    consensus.py
    engine.py
    manager.py
    registry.py
    metrics.py
    history.py
```

No additional files.

---

# Responsibilities

## Decision Engine

Public entry point.

Responsibilities:

- start()
- stop()
- decide()

Must delegate all work to the manager.

---

## Decision Manager

Coordinates the complete workflow.

Pipeline:

Decision Context

↓

Market Agent

↓

Strategy Agent

↓

Risk Agent

↓

Portfolio Agent

↓

CEO Agent

↓

Consensus

↓

Decision

↓

Decision Metrics

↓

Decision Result

Must execute atomically.

---

## Agents

Responsible for:

- market analysis
- strategy analysis
- risk analysis
- portfolio analysis
- decision arbitration

Each agent produces an immutable opinion.

Agents are abstractions. Concrete agents are injected. The framework must never make a real LLM, model, API, or network call, and agents must remain deterministic under test.

---

## Consensus

Responsible for:

- opinion aggregation
- weighting
- arbitration
- decision resolution

No agent logic.

Stateless.

---

## History

Responsible for:

- completed decisions
- snapshots
- decision timeline
- historical records

Append-only.

---

## Metrics

Calculate:

- Total Decisions
- Approval Rate
- Rejection Rate
- Agreement Rate
- Average Confidence
- Buy Decisions
- Sell Decisions
- Hold Decisions
- Average Agent Count

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

The registry stores agents by role and never creates them.

---

# Models

All models must be:

- frozen dataclasses
- Decimal only
- MappingProxyType metadata
- immutable

Required models include:

- AgentRole
- AgentOpinion
- ConsensusResult
- Decision
- DecisionResult
- DecisionSummary
- DecisionMetrics
- DecisionSnapshot
- DecisionHistory
- DecisionState

---

# Context

DecisionContext must contain:

- market snapshot
- strategy signals
- risk decision
- portfolio result
- position result
- performance result
- decision parameters
- metadata

Immutable.

---

# Dependency Injection

Create:

register_agents(container)

Register:

- Agents
- Consensus
- Metrics
- History
- Registry
- Manager
- Engine

Reuse LoggerFactory.

Reuse EventBus.

Reuse ServiceContainer.

Concrete agents must be injected through the container. The framework must never instantiate a model, provider, or network client.

---

# Events

Implement:

DecisionRequested

AgentEvaluated

ConsensusReached

DecisionMade

DecisionRejected

DecisionSnapshotCreated

DecisionMetricsUpdated

DecisionCancelled

AgentErrorOccurred

DecisionErrorOccurred

All inherit from Event.

Publish only after consistent state.

---

# Logging

Use LoggerFactory.

Logger names:

agents.engine

agents.manager

Agents and calculators must never log.

Never log prompts, model outputs, or sensitive financial detail.

---

# Error Handling

Create:

DecisionError

AgentError

ConsensusError

MetricsError

HistoryError

RegistryError

DecisionRejectedError

Manager must isolate failures.

Return:

DecisionResult(status=FAILED)

Never leak exceptions.

---

# Thread Safety

Stateless:

- Agents
- Consensus
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

tests/support/agents_fakes.py

tests/unit/test_agents.py

tests/integration/test_agents_flow.py

Requirements:

- deterministic
- no sleeps
- no randomness
- no network
- no real LLM or model calls

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

Reuse existing infrastructure only.

---

# Deliverables

Populate only the files listed above.

Implement:

- Engine
- Manager
- Agents
- Consensus
- Metrics
- History
- Registry

Integrate using Dependency Injection.

Publish Events.

Add unit tests.

Add integration tests.

Run the complete test suite.

All existing tests must continue passing.

---

# Acceptance Criteria

✓ Standalone AI Decision Engine

✓ Immutable Models

✓ Thread-safe Components

✓ Dependency Injection

✓ Event Driven Architecture

✓ Deterministic Agent Abstractions

✓ Opinion Aggregation

✓ Consensus Resolution

✓ Metrics Calculation

✓ Append-only History

✓ Registry

✓ Unit Tests

✓ Integration Tests

✓ Existing Tests Passing

✓ No Real LLM or Network Calls

✓ No Unrelated Modules Modified

---

# Completion

After implementation, stop.

Provide:

1. Architecture Overview

2. Component Collaboration

3. Agent Design

4. Consensus Design

5. Metrics Design

6. History Design

7. Dependency Injection

8. Event Driven Architecture

9. Logging

10. Error Handling

11. Thread Safety

12. Future Extensions

Implementation Summary

Acceptance Criteria Checklist

Stop after reporting completion.
