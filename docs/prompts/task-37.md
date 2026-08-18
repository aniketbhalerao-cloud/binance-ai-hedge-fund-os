# Task 37 — Workflow Orchestration Framework

---

# Sprint 17

## Framework

Workflow Orchestration Framework

---

# Objective

Design and implement a standalone Workflow Orchestration Framework that collects declarative workflow definitions from the running system and produces deterministic, immutable workflow plan and workflow request objects using the existing architecture without modifying any previous framework.

The framework consumes workflow definitions describing multi-step compositions whose steps reference the existing Scheduler, Workers, Agents, and Model Provider Gateway frameworks as handoff targets, collects and orders them into a declarative `WorkflowPlan`, and produces immutable `WorkflowRequest` objects only.

It must integrate seamlessly with:

* Scheduler Framework
* Workers Framework
* Agents Framework
* Model Provider Gateway Framework

Supported handoff targets:

* Agents
* Model Provider Gateway
* Scheduler
* Workers

The framework must never communicate directly with Binance or any exchange, and must never modify strategies, agent weights, or portfolios automatically. It never executes a workflow step, triggers an Agent, calls `ModelGatewayManager.invoke()`, `SchedulerManager.schedule()`, or `WorkerManager.enqueue()`, executes a trade, performs inference, or makes a real network call. Collection and ordering are deterministic; the framework core is reproducible under test.

---

# Architecture Requirements

The framework must follow the project's established architecture:

* Clean Architecture
* Domain Driven Design
* SOLID Principles
* Immutable Models
* Dependency Injection
* Event Driven Architecture
* Thread Safety
* Deterministic Processing
* Registry-Owned State

No shortcuts.

---

# Package Structure

Create a new package:

workflows/

containing exactly the following files:

```text
workflows/
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

## Workflow Engine

Public entry point.

Responsibilities:

* start()
* stop()
* compose()

Must delegate all work to the manager.

`compose()` only produces a declarative `WorkflowPlan` and immutable `WorkflowRequest` handoff-intent objects — it never executes a step, never triggers an Agent, and never calls `ModelGatewayManager.invoke()`, `SchedulerManager.schedule()`, or `WorkerManager.enqueue()`.

---

## Workflow Manager

Coordinates the complete workflow.

Pipeline:

Workflow Context

↓

Collector

↓

Planner

↓

Dispatcher

↓

Metrics

↓

Workflow Result

Must load the running workflow record, process one input atomically, create a new immutable record, and write it back.

The manager must:

* validate the supplied context
* invoke the collector
* pass the collected batch to the planner
* pass the planned `WorkflowPlan` to the dispatcher
* calculate derived metrics
* create an immutable snapshot
* create a new immutable record
* replace the registry record atomically
* publish events only after the corresponding state transition is consistent
* isolate component failures
* return `WorkflowResult(status=FAILED)` on failure
* never expose internal exceptions

The manager must not execute a step, trigger an Agent, or call another framework's manager method.

---

## Collector

Responsible for:

* gathering declarative workflow definitions supplied on the context
* normalizing workflow steps and dependency edges
* deriving workflow events
* building the workflow batch
* preserving deterministic step and dependency ordering

The collector must not resolve ordering, validate the dependency graph, or select a handoff target — those are the Planner's and Dispatcher's jobs.

Deterministic.

Stateless.

---

## Planner

Responsible for:

* validating step identifier uniqueness
* validating that every dependency references an existing step
* rejecting self-dependencies
* rejecting cyclic dependency graphs
* resolving deterministic topological step ordering
* applying step-ordering tie-breaking
* producing the immutable `WorkflowPlan`

Never applies changes.

Never executes a step or calls another framework.

Stateless.

---

## Dispatcher

Responsible for:

* workflow request generation from an already-ordered `WorkflowPlan`
* handoff-target routing (Agents / Model Provider Gateway / Scheduler / Workers)
* handoff suggestions

The dispatcher is a planning boundary only.

It does not execute a step, trigger an Agent, or call another framework's manager method.

It must never:

* execute a workflow step
* trigger an Agent
* call `ModelGatewayManager.invoke()`
* call `SchedulerManager.schedule()`
* call `WorkerManager.enqueue()`
* execute trades
* perform inference
* make network calls
* modify strategies
* modify agents
* modify portfolios
* mutate another framework's state

Deterministic.

Stateless.

---

# Deterministic Workflow Ordering

Ordering is resolved at two independent levels: the **workflow level** (which `WorkflowDefinition` in a `WorkflowBatch` is resolved first) and the **step level** (the order of steps within one `WorkflowDefinition`). The two levels must never be conflated.

## Workflow-Level Ordering

1. Every `WorkflowDefinition` owns an independent dependency graph. Dependencies may reference steps only within the same `WorkflowDefinition`.
2. Cross-workflow dependency references are invalid and must raise `PlanningError`.
3. Each `WorkflowDefinition` must be validated and topologically resolved independently of every other `WorkflowDefinition` in the batch.
4. If a `WorkflowBatch` contains multiple `WorkflowDefinition` objects, the resulting workflows are ordered deterministically by:
   a. workflow priority — higher first
   b. stable workflow identifier — lexical ascending
5. Workflow priority is workflow-level metadata and must never be used to order steps inside a `WorkflowDefinition`.

## Step-Level Ordering

For each `WorkflowDefinition`, independently of every other `WorkflowDefinition`:

1. Validate all step identifiers are unique within that `WorkflowDefinition`.
2. Validate every dependency references an existing step within the same `WorkflowDefinition`.
3. Reject self-dependencies.
4. Reject cyclic dependency graphs.
5. Resolve steps using deterministic topological ordering.
6. Among simultaneously-ready steps, order by:
   a. step priority — higher first
   b. stable step identifier — lexical ascending
7. Identical immutable input must always produce identical step ordering.

Step priority and step identifiers are scoped to their own `WorkflowDefinition`; they never influence, and are never influenced by, another `WorkflowDefinition`'s ordering.

No timestamps, randomness, dictionary/set iteration order, process state, network state, or external service state may influence ordering at either level.

Workflow ordering must therefore produce the same result when given the same:

* workflow definitions (as a set)
* workflow priority per definition
* stable workflow identifiers
* step set per definition
* dependency edges per definition
* step priorities
* deterministic ordering inputs

---

# Dependency Validation Rules

Steps are treated as immutable graph nodes; dependencies are treated as immutable directed edges. Each `WorkflowDefinition` owns its own independent graph — nodes and edges never span more than one `WorkflowDefinition`.

A step identifier that is not unique within its `WorkflowDefinition` invalidates the definition — it must not be silently deduplicated.

A dependency edge referencing a step identifier that does not exist **within the same `WorkflowDefinition`** invalidates the definition. A dependency edge referencing a step identifier that belongs to a *different* `WorkflowDefinition` is a cross-workflow dependency reference and is invalid for the same reason — the graphs are independent by design and must never be joined.

A dependency edge whose `depends_on` equals its own `step_id` (a self-dependency) invalidates the definition.

A dependency graph containing a cycle invalidates the definition — no partial ordering may be returned for an invalid definition.

Each `WorkflowDefinition` must be validated and topologically resolved independently; a validation failure in one `WorkflowDefinition` must never affect the validation or ordering of any other `WorkflowDefinition` in the same `WorkflowBatch`.

A `WorkflowStep` whose handoff target is not one of the exactly four supported domain values (`agents`, `model_gateway`, `scheduler`, `workers`) invalidates the definition — invalid handoff targets are rejected deterministically before any `WorkflowRequest` is generated.

Validation failures — duplicate identifiers, missing dependencies, cross-workflow references, self-dependencies, cycles, and invalid handoff targets — are reported through `PlanningError`; they must never produce a partially ordered `WorkflowPlan`.

No step may be ordered solely because it appears first in a collection.

All collections used for ordering must be normalized into a stable deterministic ordering before final resolution.

---

# Step Ordering Tie-Breaking

## Workflow-Level Tie-Breaking (ordering workflows within a `WorkflowBatch`)

When two or more `WorkflowDefinition` objects could be ordered next:

1. Compare workflow priority (higher preferred).
2. If equal, compare the stable workflow identifier lexically.

## Step-Level Tie-Breaking (ordering steps within one `WorkflowDefinition`)

When two or more simultaneously-ready steps could be ordered next:

1. Compare step priority (higher preferred).
2. If equal, compare the stable step identifier lexically.

Workflow priority must never be used to break a step-level tie, and step priority must never be used to break a workflow-level tie — the two levels are independent.

The framework must never use, at either level:

* object identity
* memory address
* hash randomization
* insertion order
* current time
* random numbers

as an ordering tie-breaker.

---

# Workflow Plan Result

Workflow ordering must produce a deterministic plan represented only through immutable domain objects.

A resolved `WorkflowPlan` reflects one `WorkflowBatch`: an ordered sequence of resolved workflows (ordered per the Workflow-Level Ordering rules), each carrying its own independently-resolved step order (per the Step-Level Ordering rules) for that workflow's own steps only. A step's resolved position is never influenced by another `WorkflowDefinition`'s steps, priority, or identifier.

`WorkflowPlan` must contain sufficient metadata to explain:

* the resolved workflow order (when the batch contains multiple `WorkflowDefinition` objects), including the workflow priority and workflow identifier that decided it
* the resolved step order within each workflow
* each step's handoff target
* each step's dependencies
* workflow priority
* step priority
* deterministic resolution outcome

`WorkflowPlan` is declarative only — it describes an order and intended handoffs; it never executes anything.

---

# Metrics

Calculate:

* Total Steps
* Total Requests
* Average Step Score
* Highest Priority Step
* Lowest Priority Step
* Dispatch Ratio
* Pending Requests Count
* Suppressed Requests Count

Metrics are derived only from the current immutable state and processing result.

Metrics must never be stored independently.

Metrics must never become a second source of truth.

Metrics calculation must be deterministic.

Metrics calculators must be stateless.

---

# Registry

Thread-safe.

Responsibilities:

* register()
* unregister()
* get()
* exists()
* list()
* clear()

Protected using `Lock`.

The registry owns the running workflow records and never creates them.

The registry must:

* reject invalid registrations
* provide atomic replacement semantics
* never mutate an existing immutable record
* never expose mutable internal state
* return immutable records or immutable views
* remain safe for concurrent access

The registry must not perform persistence.

The registry must not write files.

The registry must not write databases.

---

# Models

All models must be:

* frozen dataclasses
* Decimal only for numeric domain values
* MappingProxyType metadata
* immutable

Required models include:

* WorkflowState
* WorkflowParameters
* WorkflowDefinition
* WorkflowStep
* WorkflowDependency
* WorkflowBatch
* WorkflowPlan
* WorkflowRequest
* WorkflowRecord
* WorkflowMetrics
* WorkflowSnapshot
* WorkflowHistory
* WorkflowResult

Numeric fields representing domain values must use `Decimal` rather than floating-point values.

Metadata must be immutable and exposed through `MappingProxyType`.

Collections contained by models must be immutable.

No model may expose mutable internal collections.

---

# WorkflowStep & WorkflowDependency

`WorkflowStep` and `WorkflowDependency` represent workflow graph structure only, scoped to exactly one `WorkflowDefinition`.

`WorkflowStep` may contain information such as:

* stable step identifier, unique within its `WorkflowDefinition`
* handoff-target identifier — an immutable string equal to exactly one of the four supported domain values: `agents`, `model_gateway`, `scheduler`, `workers`; any other value is invalid and must be rejected deterministically before `WorkflowRequest` generation
* step priority
* descriptive detail
* immutable metadata

`WorkflowStep` must store only the immutable handoff-target identifier string above — it must never store a framework `Manager`, `Engine`, callable, client, or service instance in its place.

`WorkflowDependency` may contain information such as:

* the dependent step identifier
* the step identifier it depends on

Both identifiers on a `WorkflowDependency` must resolve to steps within the same `WorkflowDefinition`; a `WorkflowDependency` referencing a step identifier belonging to a different `WorkflowDefinition` is a cross-workflow dependency reference and is invalid.

Neither may ever contain:

* a callable reference to another framework's manager or engine
* a network client
* a database client
* credentials, API keys, or secrets
* mutable framework state

---

# WorkflowRequest

`WorkflowRequest` is an immutable domain object describing handoff intent for one ordered step.

It must not execute the step.

It must contain only the information a downstream adapter or caller needs to eventually perform the handoff.

The request may identify:

* subject (the step identifier)
* source (the workflow/definition identifier)
* handoff-target identifier — one of the four supported domain values: `agents`, `model_gateway`, `scheduler`, `workers`
* priority
* deterministic ordering position
* descriptive detail

A `WorkflowRequest` is generated only for a step whose handoff target has already passed validation; an invalid handoff target must never reach `WorkflowRequest` generation.

It must never contain:

* a callable reference to `AgentEngine`, `ModelGatewayManager`, `SchedulerManager`, `WorkerManager`, or any other framework's manager/engine
* credentials, API keys, or secrets
* network connections

`WorkflowRequest` objects may describe handoff intent to Agents, Model Provider Gateway, Scheduler, and Workers, but the framework must never call those frameworks directly.

---

# Context

`WorkflowContext` must contain:

* workflow definitions
* workflow parameters
* metadata

Immutable.

The context must not contain:

* a callable reference to another framework's manager or engine
* network clients
* credentials
* mutable framework state

The context must be safe to reuse across deterministic test executions.

---

# Interfaces

Define abstractions only.

* Collector
* Planner
* Dispatcher
* WorkflowMetricsCalculator
* WorkflowRegistry
* WorkflowManager
* WorkflowEngine

Every implementation depends upon interfaces.

No concrete dependency references.

Constructor Injection only.

Implementations must not instantiate their own infrastructure dependencies.

---

# Events

Implement:

* WorkflowStarted
* StepsCollected
* WorkflowPlanned
* RequestsDispatched
* WorkflowSnapshotCreated
* WorkflowMetricsUpdated
* WorkflowCompleted
* WorkflowCancelled
* WorkflowErrorOccurred

All inherit from `Event`.

Publish only after consistent state.

Events must be immutable.

Events must not contain:

* callable references to another framework's manager or engine
* credentials
* network clients
* mutable state

Event payloads must contain only the domain information necessary to describe the transition.

---

# Dependency Injection

Create:

`register_workflows(container)`

Register:

* Collector
* Planner
* Dispatcher
* Metrics
* Registry
* Manager
* Engine

Reuse:

* LoggerFactory
* EventBus
* ServiceContainer

The framework must never instantiate:

* an Agent, Scheduler, Worker, or Model Gateway manager or engine
* a network client
* a database client

All dependencies must enter through constructor injection.

---

# Logging

Use `LoggerFactory`.

Logger names:

* `workflows.engine`
* `workflows.manager`

Collectors and calculators must never log.

Never log:

* raw step content beyond safe identifiers
* credentials
* API keys
* sensitive financial detail

---

# Error Handling

Create:

* WorkflowError
* CollectionError
* PlanningError
* DispatchError
* MetricsError
* RegistryError
* WorkflowCancelledError

Manager must isolate failures.

Return:

`WorkflowResult(status=FAILED)`

Never leak exceptions.

Errors must not expose:

* credentials
* internal connection details
* sensitive financial details

---

# Failure Isolation

Collection failures must not mutate registry state.

Planning failures (including cycle/self-dependency/missing-dependency/duplicate-identifier rejection) must not mutate registry state.

Dispatch failures must not mutate registry state.

Metrics failures must not partially update the running record.

Registry failures must not expose partially written state.

The manager must commit the new immutable record only after all required processing succeeds.

Events must be published only after consistent state.

---

# Thread Safety

Stateless:

* Collector
* Planner
* Dispatcher
* Metrics

Thread-safe:

* Registry
* Manager

Immutable:

* Context
* Models
* Events

The framework must never:

* spawn a thread
* spawn a process
* sleep
* block on external I/O
* perform background work
* create asynchronous calls into another framework

---

# Testing

Create:

```text
tests/support/workflow_fakes.py
tests/unit/test_workflows.py
tests/integration/test_workflow_flow.py
```

Requirements:

* deterministic
* no sleeps
* no randomness
* no network
* no model training

Unit tests must verify:

* immutable models
* Decimal numeric fields
* immutable metadata
* deterministic topological ordering
* dependency validation
* missing dependency rejection
* self-dependency rejection
* cycle detection
* stable tie-breaking
* input-order independence
* multiple `WorkflowDefinition` objects resolved independently within one `WorkflowBatch`
* workflow priority ordering across multiple `WorkflowDefinition` objects
* workflow-identifier lexical tie-breaking when workflow priority ties
* step-priority ordering within one `WorkflowDefinition`
* step-identifier lexical tie-breaking when step priority ties
* cross-workflow dependency reference rejection
* invalid handoff-target rejection
* metrics calculation
* registry thread safety
* registry atomicity
* failure isolation
* event publication
* dependency injection

Integration tests must verify:

* context → collector
* collector → planner
* planner → dispatcher
* dispatcher → metrics
* metrics → immutable result
* registry state replacement
* event sequence
* deterministic repeated execution
* no direct calls into Scheduler, Workers, Agents, or Model Provider Gateway
* a `WorkflowBatch` containing multiple `WorkflowDefinition` objects resolves each graph independently end to end

Tests must verify that identical inputs produce identical `WorkflowPlan` ordering and identical `WorkflowRequest` objects.

Tests must verify that ordering does not depend on step, dependency, or workflow-definition collection insertion order — this applies to both workflow-level ordering (within a `WorkflowBatch`) and step-level ordering (within a `WorkflowDefinition`).

---

# Determinism Requirements

For identical immutable inputs, the framework must produce identical:

* collection results
* validation results
* workflow-level ordering results (which `WorkflowDefinition` resolves first within a `WorkflowBatch`)
* topological ordering results (step order within each `WorkflowDefinition`)
* `WorkflowPlan` objects
* `WorkflowRequest` objects
* metrics
* snapshots
* history entries
* result status

Determinism must not depend on:

* current time
* random values
* UUID generation without deterministic input
* memory addresses
* object identity
* hash iteration order
* dictionary insertion order
* process ID
* hostname
* environment variables
* network state
* external framework state

Where identifiers are required for deterministic test output, they must be derived from supplied immutable domain inputs or supplied explicitly by the caller.

---

# Constraints

Do NOT modify:

* market_data
* strategies
* risk
* order_management
* execution
* portfolio
* positions
* trades
* performance
* backtesting
* paper_trading
* agents
* learning
* optimization
* monitoring
* dashboard
* notification
* reporting
* storage
* scheduler
* workers
* memory
* model_gateway

Reuse existing infrastructure only.

The framework must never modify strategies, agent weights, or portfolios automatically.

The framework must never:

* execute a workflow step
* trigger an Agent
* call `ModelGatewayManager.invoke()`
* call `SchedulerManager.schedule()`
* call `WorkerManager.enqueue()`
* execute trades
* perform inference
* train models
* make network calls
* spawn a thread
* spawn a process
* sleep
* block on external I/O
* write files
* write to a database
* mutate another framework's state
* directly mutate agent state
* directly mutate learning state
* directly mutate optimization state
* directly mutate strategy state
* directly mutate portfolio state

`WorkflowRequest` objects are immutable domain requests only.

A `WorkflowDefinition`'s dependency graph must never be joined with, or resolved using, another `WorkflowDefinition`'s steps or dependencies. A handoff target outside the four supported domain values (`agents`, `model_gateway`, `scheduler`, `workers`) must never reach `WorkflowRequest` generation.

Workflow ordering must never depend on:

* current time
* randomness
* external framework state
* network state
* process state
* machine state
* non-deterministic collection ordering

---

# Deliverables

Populate only the files listed above.

Implement:

* Engine
* Manager
* Collector
* Planner
* Dispatcher
* Metrics
* Registry

Integrate using Dependency Injection.

Publish Events.

Implement deterministic dependency validation and topological ordering.

Implement immutable `WorkflowPlan` objects.

Implement immutable `WorkflowRequest` objects.

Add unit tests.

Add integration tests.

Run the complete test suite.

All existing tests must continue passing.

Verify that no unrelated modules are modified.

Verify that no step is executed, no Agent is triggered, and no other framework's manager method is called.

---

# Acceptance Criteria

✓ Standalone Workflow Orchestration Framework

✓ Deterministic workflow request generation

✓ Deterministic dependency validation

✓ Independent workflow dependency graphs

✓ Deterministic multiple-workflow ordering

✓ Workflow-priority ordering

✓ Workflow-id lexical tie-breaking

✓ Deterministic topological step ordering

✓ Step-priority ordering

✓ Step-id lexical tie-breaking

✓ Stable step-ordering tie-breaking

✓ Duplicate step identifier rejection

✓ Missing dependency rejection

✓ Self-dependency rejection

✓ Cyclic dependency rejection

✓ Cross-workflow dependency rejection

✓ Invalid handoff-target rejection

✓ Immutable Models

✓ Immutable WorkflowPlan

✓ Immutable WorkflowRequest

✓ Registry

✓ Dependency Injection

✓ Event Driven Architecture

✓ Thread-safe Components

✓ Unit Tests

✓ Integration Tests

✓ Existing Tests Passing

✓ No Step Execution or Agent Triggering

✓ No Calls into SchedulerManager, WorkerManager, or ModelGatewayManager

✓ No Network Calls

✓ No Database or File Writes

✓ No Automatic Modification of Any Other Framework's State

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
6. Deterministic Workflow Ordering (workflow-level and step-level)
7. Step Ordering Tie-Breaking (workflow-level and step-level)
8. Metrics Design
9. Dependency Injection
10. Event Driven Architecture
11. Logging
12. Error Handling
13. Failure Isolation
14. Thread Safety
15. Testing Strategy
16. Future Extensions

Implementation Summary

Acceptance Criteria Checklist

Stop after reporting completion.
