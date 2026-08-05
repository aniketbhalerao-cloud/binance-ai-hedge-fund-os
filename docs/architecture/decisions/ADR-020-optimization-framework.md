# ADR-020: Optimization Framework

## Status

Accepted

## Date

2026-08-05

## Context

The AI Trading Operating System now includes dedicated frameworks for market data, trading, strategies, risk management, order management, execution, exchange adapters, broker integration, portfolio management, position management, trade lifecycle management, performance analytics, historical backtesting, live paper trading, autonomous AI decision-making, and learning from completed activity.

While the Learning Framework evaluates what performed and generates feedback, it does not turn that feedback into a structured plan of proposed improvements.

Deriving optimization targets, ranking them, planning proposed adjustments, and producing recommendations — without ever applying them — is a distinct concern that must not be mixed into any trading, decision, or learning framework, must never touch an exchange, and must never modify strategies, agents, or portfolios.

The system therefore requires a dedicated Optimization Framework responsible for producing deterministic optimization plans and recommendations from learning outputs, completely independent of any exchange and of any machine-learning provider, and strictly proposal-only.

---

## Decision

Introduce a standalone Optimization Framework that consumes the Learning Framework outputs and turns them into optimization plans, recommendations, and metrics.

The framework consists of:

- Optimization Engine
- Optimization Manager
- Planner
- Optimizer
- Recommendations
- Metrics
- Registry
- Optimization Models
- Optimization Events

The framework consumes standardized domain models (strategy evaluations, agent evaluations, feedback, and learning metrics) assembled into an optimization context. It never places an order, never applies a change, and never trains a model, calls a provider, or performs network communication.

No existing framework requires modification.

---

## Rationale

### Separation of Responsibilities

Each framework within the AI Trading Operating System owns a single responsibility.

The Learning Framework answers:

**"What performed, and what should improve?"**

The Optimization Framework answers:

**"Given that, what is the concrete plan of proposed changes?"**

Separating optimization from the frameworks being optimized prevents the optimization layer from becoming tightly coupled with strategy, decision, or learning logic.

---

### Optimization Independence

The Optimization Framework never communicates directly with:

- Binance or any exchange
- REST APIs
- WebSockets
- Model or ML providers
- External libraries beyond the standard library

Instead, it consumes standardized domain models such as:

- StrategyEvaluation
- AgentEvaluation
- FeedbackRecommendation
- LearningMetrics

Planning and optimization are deterministic and rule-based, derived only from the learning outputs. The framework core makes no model, provider, or network call, so optimization behaves identically and reproducibly under test.

---

### Planner Design

The Planner derives and ranks optimization targets.

Responsibilities include:

- Deriving targets
- Ranking underperforming subjects
- Proposing steps
- Building the plan

The planner is stateless and deterministic. It ranks targets worst-first with a stable tiebreak and proposes a step per target relative to the score threshold. It only proposes and never modifies a subject.

---

### Optimizer Design

The Optimizer resolves the plan.

Responsibilities include:

- Evaluating the plan
- Scoring candidate optimizations
- Resolving to actionable proposals

The optimizer is stateless and deterministic, keeping only actionable steps. It never applies a change — resolution produces proposals, not mutations.

---

### Recommendations Design

The Recommendation generator turns the resolved plan into recommendations.

Responsibilities include:

- Recommendation generation
- Proposed weight and confidence changes
- Improvement suggestions

The recommendation generator is stateless and deterministic. It proposes changes only and never modifies strategies, agents, or portfolios and never executes a recommendation.

---

### Metrics Design

Optimization Metrics derives aggregate figures over the record.

Responsibilities include:

- Plan and recommendation counts
- Average score
- Best and worst target
- Improvement potential
- Applied and pending counts

Metrics are derived from the record rather than stored independently. The applied count is always zero by design, since the framework only proposes.

---

### Atomic Optimization Processing

Each input is processed atomically.

The Optimization Manager coordinates:

Optimization Context

↓

Load Record

↓

Planner

↓

Optimizer

↓

Recommendations

↓

Optimization Metrics

↓

New Immutable Record

If the update fails, the record is not overwritten.

Partial optimization state is never persisted.

---

### Immutability

All optimization models are immutable frozen dataclasses.

Immutability applies to:

- Optimization Context
- Targets, steps, and plans
- Recommendations
- The optimization record, snapshots, and results

Scores use Decimal, and metadata is exposed as a read-only mapping. Each update produces a new immutable record; existing records and snapshots are never mutated, which guarantees that a reported plan is safe to share, log, and reproduce.

---

### Error Handling

Optimization failures are isolated inside the framework.

Stage failures are translated into framework exceptions:

- PlanningError
- OptimizerError
- RecommendationError
- MetricsError
- RegistryError

Any failure is published as an OptimizationErrorOccurred event and returned as a failed OptimizationResult. Internal implementation details never escape the framework, and no partial record is written on failure.

---

### Dependency Injection

All framework components are resolved through the existing Dependency Injection container.

Dependencies include:

- Optimization Engine
- Optimization Manager
- Planner
- Optimizer
- Recommendations
- Metrics
- Registry
- Event Bus
- LoggerFactory

Every implementation is bound to its abstraction. No infrastructure is instantiated manually, and the framework never instantiates a model, provider, or network client.

---

### Event-Driven Architecture

The framework publishes optimization events through the existing Event Bus.

Examples include:

- OptimizationStarted
- PlanCreated
- OptimizationEvaluated
- RecommendationsGenerated
- OptimizationSnapshotCreated
- OptimizationMetricsUpdated
- OptimizationCompleted
- OptimizationCancelled
- OptimizationErrorOccurred

Events are published only after a consistent state, and consumers subscribe without requiring direct coupling to the framework.

---

### Thread Safety

The framework supports concurrent optimization.

Thread safety is achieved through:

- Stateless planner
- Stateless optimizer
- Stateless recommendation generator
- Stateless metrics calculator
- Thread-safe registry
- Atomic per-input processing
- Immutable context, record, models, and events

Shared mutable state is minimized, and one input is processed atomically before the next begins.

---

### Testability

The framework is fully testable without external services.

Tests use:

- Deterministic learning evaluations
- Deterministic optimization contexts
- The deterministic default components

No exchange connectivity is required, and no machine-learning provider is involved.

All tests remain deterministic, with no sleeps and no randomness, and no model training or network calls.

---

## Alternatives Considered

### Optimization Logic Inside the Learning Framework

Rejected.

The Learning Framework is responsible for evaluation and feedback.

Embedding target ranking, planning, and recommendation generation would violate the Single Responsibility Principle and couple learning with optimization.

---

### Applying Recommendations Automatically

Rejected.

Automatically modifying strategies, agent weights, or portfolios would couple optimization to execution, remove human oversight, and make the framework unsafe.

The framework instead only proposes; an applier, if ever wanted, is a separate opt-in concern.

---

### Training a Model Inside the Framework Core

Rejected.

Training a model or calling a provider would make optimization non-deterministic, tie the system to a provider, and prevent deterministic testing.

Planning and optimization instead remain deterministic and rule-based.

---

### Mutable or Externally Persisted Optimization State

Rejected.

The optimization record is the reproducible basis for the plan and its recommendations.

Allowing mutation, or delegating persistence to an external store inside the framework, would compromise reproducibility and determinism and violate the framework's immutable, registry-owned design.

---

## Consequences

### Positive

- Clear separation of optimization from learning and execution
- Exchange-independent and provider-independent optimization
- Deterministic, reproducible plans and recommendations
- Proposal-only safety: nothing is applied automatically
- Full reuse of the existing frameworks
- Immutable, append-only plan history
- Thread-safe, atomic per-input processing
- Event-driven architecture
- High testability
- Easy extension for richer optimization

### Negative

- Additional architectural layer
- Recommendations require a separate opt-in step to ever be applied

These trade-offs are acceptable because they preserve scalability, maintainability, modularity, and safety.

---

## Related Components

- optimization/
- strategies/
- agents/
- learning/
- events/
- core/

---

## Implementation

Implemented during:

**Sprint 7 – Task 27**

Key components include:

- DefaultOptimizationEngine
- DefaultOptimizationManager
- DefaultPlanner
- DefaultOptimizer
- DefaultRecommendations
- DefaultOptimizationMetrics
- InMemoryOptimizationRegistry

Supporting capabilities include:

- Optimization planning
- Plan resolution
- Recommendation generation
- Optimization metrics
- Registry-owned optimization records
- Snapshot creation
- Structured logging
- Event publication

The framework integrates with:

- Strategy Framework
- AI Decision Engine
- Learning Framework
- Dependency Injection Container
- Event Bus
- LoggerFactory

No modifications to existing frameworks were required.

---

## Future Considerations

Future optimization capabilities may include:

- An opt-in recommendation applier
- Additional optimization objectives
- Alternative planning and scoring policies
- Multi-objective optimization
- Constraint-aware optimization
- Record persistence and replay
- Advanced reporting
- A closed, human-supervised improvement loop

These features should extend the existing framework without requiring architectural changes.

---

## Decision Summary

The Optimization Framework introduces a dedicated, exchange-independent and provider-independent layer that turns learning outputs into deterministic optimization plans and recommendations, strictly proposing improvements without ever applying them.

By separating planning, optimization, recommendation generation, metrics, and registration into independent components while reusing the real frameworks through dependency injection and event-driven communication, the AI Trading Operating System remains modular, scalable, thread-safe, deterministic, and safe, and ready for richer optimization without modifying existing frameworks.
