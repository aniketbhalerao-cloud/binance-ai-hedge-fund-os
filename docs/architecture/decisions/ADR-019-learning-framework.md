# ADR-019: Learning Framework

## Status

Accepted

## Date

2026-08-04

## Context

The AI Trading Operating System now includes dedicated frameworks for market data, trading, strategies, risk management, order management, execution, exchange adapters, broker integration, portfolio management, position management, trade lifecycle management, performance analytics, historical backtesting, live paper trading, and autonomous AI decision-making.

While these frameworks decide and act, none of them closes the loop by learning from what actually happened.

Recording completed outcomes, evaluating which strategies and agents performed, and generating feedback to improve future behaviour is a distinct concern that must not be mixed into any trading framework, must never touch an exchange, and must never depend on training a real model.

The system therefore requires a dedicated Learning Framework responsible for learning from completed trading activity across the existing architecture, deterministically and completely independent of any exchange and of any machine-learning provider.

---

## Decision

Introduce a standalone Learning Framework that consumes the standardized outcomes the existing frameworks produce and turns them into evaluations, feedback, and learning metrics.

The framework consists of:

- Learning Engine
- Learning Manager
- Journal
- Evaluator
- Feedback
- Metrics
- Registry
- Learning Models
- Learning Events

The framework consumes standardized domain models (decision, trade, and performance results) assembled into a learning context. It never places an order and never trains a model, calls a provider, or uses an external machine-learning library.

No existing framework requires modification.

---

## Rationale

### Separation of Responsibilities

Each framework within the AI Trading Operating System owns a single responsibility.

The existing frameworks answer:

**"What should happen, and what did happen?"**

The Learning Framework answers:

**"Given what happened, what should improve?"**

Separating learning from the frameworks being learned from prevents the learning layer from becoming tightly coupled with strategy, trade, performance, or decision logic.

---

### Learning Independence

The Learning Framework never communicates directly with:

- Binance or any exchange
- REST APIs
- WebSockets
- Model or ML providers
- External machine-learning libraries

Instead, it consumes standardized domain models such as:

- DecisionResult
- TradeResult
- PerformanceResult

Evaluation and feedback are deterministic and rule-based, derived only from the recorded outcomes. The framework core makes no model, training, provider, or network call, so learning behaves identically and reproducibly under test regardless of environment.

---

### Journal Design

The Journal records completed outcomes.

Responsibilities include:

- Recording outcomes
- Outcome timeline
- Historical records

The journal is append-only and stateless — it returns a new history and never mutates existing entries — so the outcome timeline is immutable and provides a reproducible basis for evaluation.

---

### Evaluator Design

The Evaluator derives evaluations from the journal.

Responsibilities include:

- Strategy evaluation
- Agent evaluation
- Model benchmarking
- Scoring

The evaluator is stateless and reads only the journal, scoring each strategy and agent by its realized outcomes (expectancy). "Model benchmarking" is realized deterministically, without any machine-learning model, training, or network involved.

---

### Feedback Design

The Feedback generator turns evaluations into recommendations.

Responsibilities include:

- Feedback generation
- Weight and confidence recommendations
- Improvement suggestions

The feedback generator is stateless and deterministic. Recommendations are gated by a minimum-sample threshold and derived purely from the evaluations, so identical inputs always yield identical feedback, and no model is ever trained.

---

### Metrics Design

Learning Metrics derives aggregate figures over the record.

Responsibilities include:

- Outcome counts and win rate
- Average score and average P&L
- Best and worst strategy
- Improvement rate and feedback count

Metrics are derived from the learning record and its journal rather than stored independently, reusing the recorded outcomes and avoiding duplication.

---

### Atomic Learning Processing

Each outcome is processed atomically.

The Learning Manager coordinates:

Learning Context

↓

Load Record

↓

Journal

↓

Evaluator

↓

Feedback

↓

Learning Metrics

↓

New Immutable Record

If the update fails, the record is not overwritten.

Partial learning state is never persisted.

---

### Immutability

All learning models are immutable frozen dataclasses.

Immutability applies to:

- Learning Context
- Outcomes and journal entries
- Strategy and agent evaluations
- Feedback recommendations
- The learning record, snapshots, and results

Scores and monetary figures use Decimal, and metadata is exposed as a read-only mapping. Each update produces a new immutable record; existing records and snapshots are never mutated, which guarantees that reported learning state is safe to share, log, and reproduce.

---

### Error Handling

Learning failures are isolated inside the framework.

Stage failures are translated into framework exceptions:

- JournalError
- EvaluationError
- FeedbackError
- MetricsError
- RegistryError

Any failure is published as a LearningErrorOccurred event and returned as a failed LearningResult. Internal implementation details never escape the framework, and no partial record is written on failure.

---

### Dependency Injection

All framework components are resolved through the existing Dependency Injection container.

Dependencies include:

- Learning Engine
- Learning Manager
- Journal
- Evaluator
- Feedback
- Metrics
- Registry
- Event Bus
- LoggerFactory

Every implementation is bound to its abstraction. No infrastructure is instantiated manually, and the framework never instantiates a model, trainer, provider, or network client.

---

### Event-Driven Architecture

The framework publishes learning events through the existing Event Bus.

Examples include:

- LearningStarted
- OutcomeRecorded
- StrategyEvaluated
- AgentEvaluated
- FeedbackGenerated
- LearningSnapshotCreated
- LearningMetricsUpdated
- LearningCompleted
- LearningCancelled
- LearningErrorOccurred

Events are published only after a consistent state, and consumers subscribe without requiring direct coupling to the framework.

---

### Thread Safety

The framework supports concurrent learning.

Thread safety is achieved through:

- Stateless evaluator
- Stateless feedback generator
- Stateless metrics calculator
- Thread-safe registry
- Atomic per-outcome processing
- Immutable context, record, models, and events

Shared mutable state is minimized, and one outcome is processed atomically before the next begins.

---

### Testability

The framework is fully testable without external services.

Tests use:

- Deterministic standardized outcomes
- Deterministic learning contexts
- The deterministic default components

No exchange connectivity is required, and no machine-learning provider is involved.

All tests remain deterministic, with no sleeps and no randomness, and no real model training or network calls.

---

## Alternatives Considered

### Learning Logic Inside the Performance Framework

Rejected.

The Performance Analytics Framework is responsible for measuring performance.

Embedding outcome recording, evaluation, and feedback would violate the Single Responsibility Principle and couple measurement with learning.

---

### Training a Real Model Inside the Framework Core

Rejected.

Training a model or calling an ML provider from the framework core would make learning non-deterministic, tie the system to a specific provider, and prevent deterministic testing.

Evaluation and feedback instead remain deterministic and rule-based, and the core stays reproducible.

---

### Stateful Evaluators or Feedback

Rejected.

Holding mutable state inside the evaluator or feedback generator would couple them to a session and obscure responsibility.

The Registry instead owns the running record, and the calculators reason only from the journal, so they stay stateless and reproducible.

---

### Mutable or Externally Persisted Learning State

Rejected.

The learning record is the reproducible basis for evaluation and feedback.

Allowing mutation, or delegating persistence to an external store inside the framework, would compromise reproducibility and determinism and violate the framework's immutable, registry-owned design.

---

## Consequences

### Positive

- Clear separation of learning from trading and measurement
- Exchange-independent and provider-independent learning
- Deterministic, reproducible evaluation and feedback
- Full reuse of the existing frameworks
- Immutable, append-only journal and record
- Thread-safe, atomic per-outcome processing
- Event-driven architecture
- High testability
- Easy extension for richer evaluation and feedback

### Negative

- Additional architectural layer
- Additional coordination across the components the manager drives per outcome

These trade-offs are acceptable because they preserve scalability, maintainability, and modularity.

---

## Related Components

- learning/
- strategies/
- trades/
- performance/
- agents/
- events/
- core/

---

## Implementation

Implemented during:

**Sprint 6 – Task 26**

Key components include:

- DefaultLearningEngine
- DefaultLearningManager
- DefaultJournal
- DefaultEvaluator
- DefaultFeedback
- DefaultLearningMetrics
- InMemoryLearningRegistry

Supporting capabilities include:

- Outcome recording
- Strategy and agent evaluation
- Deterministic feedback generation
- Learning metrics
- Registry-owned learning records
- Snapshot creation
- Structured logging
- Event publication

The framework integrates with:

- Strategy Framework
- Trade Lifecycle Framework
- Performance Analytics Framework
- AI Decision Engine
- Dependency Injection Container
- Event Bus
- LoggerFactory

No modifications to existing frameworks were required.

---

## Future Considerations

Future learning capabilities may include:

- Applying learned weights back into strategies and agents
- Additional evaluation dimensions
- Alternative feedback policies
- Prompt optimisation
- Record persistence and replay
- Confidence calibration
- Advanced reporting
- A closed autonomous improvement loop

These features should extend the existing framework without requiring architectural changes.

---

## Decision Summary

The Learning Framework introduces a dedicated, exchange-independent and provider-independent layer that learns from the existing standardized outcomes to enable continuous improvement.

By separating outcome recording, evaluation, feedback, metrics, and registration into independent components while reusing the real frameworks through dependency injection and event-driven communication, the AI Trading Operating System remains modular, scalable, thread-safe, deterministic, and ready for richer learning without modifying existing frameworks.
