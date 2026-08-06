# ADR-023: Notification Framework

## Status

Accepted

## Date

2026-08-07

## Context

The AI Trading Operating System now includes dedicated frameworks for market data, trading, strategies, risk management, order management, execution, exchange adapters, broker integration, portfolio management, position management, trade lifecycle management, performance analytics, historical backtesting, live paper trading, autonomous AI decision-making, learning from completed activity, optimization of learning outputs, monitoring of system health, and presentation of the system state.

While each framework produces its own results, no framework turns those outputs into standardized notification requests that describe what should be delivered and through which channel.

Collecting system outputs, formatting them into notifications, routing them to channels, and generating requests — without ever sending them — is a distinct concern that must not be mixed into any trading, decision, learning, optimization, monitoring, or dashboard framework, must never touch an exchange, and must never modify strategies, agents, or portfolios.

The system therefore requires a dedicated Notification Framework responsible for producing deterministic notification requests from system outputs, completely independent of any exchange and of any delivery provider, and strictly request-only.

---

## Decision

Introduce a standalone Notification Framework that consumes standardized system outputs and turns them into notification batches, requests, and metrics.

The framework consists of:

- Notification Engine
- Notification Manager
- Collector
- Formatter
- Dispatcher
- Metrics
- Registry
- Notification Models
- Notification Events

The framework consumes standardized domain models (monitoring sources, dashboard sources, optimization sources, and learning sources) assembled into a notification context. It never places an order, never sends a notification, and never trains a model, calls a provider, or performs network communication.

No existing framework requires modification.

---

## Rationale

### Separation of Responsibilities

Each framework within the AI Trading Operating System owns a single responsibility.

The Dashboard Framework answers:

**"How is the system presented at a glance?"**

The Notification Framework answers:

**"Given all of that, what should be delivered, and through which channel?"**

Separating notifications from the frameworks being reported prevents the notification layer from becoming tightly coupled with dashboard, monitoring, optimization, or learning logic.

---

### Notification Independence

The Notification Framework never communicates directly with:

- Binance or any exchange
- REST APIs
- WebSockets
- Delivery or model providers
- External libraries beyond the standard library

Instead, it consumes standardized domain models such as:

- NotificationSource
- Notification
- NotificationBatch
- NotificationRequest

Collection and formatting are deterministic and rule-based, derived only from the system outputs. The framework core makes no delivery, provider, or network call, so notifications behave identically and reproducibly under test.

---

### Collector Design

The Collector derives and normalizes notification events.

Responsibilities include:

- Gathering outputs
- Normalizing notification sources
- Deriving notification events
- Building the batch

The collector is stateless and deterministic. It normalizes readings highest-priority-first with a stable tiebreak and builds one notification per source. It only requests and never modifies a subject.

---

### Formatter Design

The Formatter component formats the batch.

Responsibilities include:

- Formatting the batch
- Arranging channels and severities
- Resolving the notification requests

The formatter is stateless and deterministic, resolving each notification's delivery against the priority threshold. It never sends a notification — formatting produces routing, not deliveries.

---

### Dispatcher Design

The Dispatcher generator turns the formatted batch into notification requests.

Responsibilities include:

- Notification request generation
- Channel routing
- Delivery suggestions

The dispatcher is stateless and deterministic. It produces request objects only and never modifies strategies, agents, or portfolios and never sends a real notification.

---

### Metrics Design

Notification Metrics derives aggregate figures over the record.

Responsibilities include:

- Notification and request counts
- Average priority score
- Highest and lowest priority notification
- Delivery ratio
- Pending and suppressed request counts

Metrics are derived from the record rather than stored independently. The suppressed request count reflects the notifications that produced no request, since the framework only requests deliverable notifications.

---

### Atomic Notification Processing

Each input is processed atomically.

The Notification Manager coordinates:

Notification Context

↓

Load Record

↓

Collector

↓

Formatter

↓

Dispatcher

↓

Notification Metrics

↓

New Immutable Record

If the update fails, the record is not overwritten.

Partial notification state is never persisted.

---

### Immutability

All notification models are immutable frozen dataclasses.

Immutability applies to:

- Notification Context
- Sources, notifications, and batches
- Notification requests
- The notification record, snapshots, and results

Scores use Decimal, and metadata is exposed as a read-only mapping. Each update produces a new immutable record; existing records and snapshots are never mutated, which guarantees that a produced request is safe to share, log, and reproduce.

---

### Error Handling

Notification failures are isolated inside the framework.

Stage failures are translated into framework exceptions:

- CollectionError
- FormattingError
- DispatchError
- MetricsError
- RegistryError

Any failure is published as a NotificationErrorOccurred event and returned as a failed NotificationResult. Internal implementation details never escape the framework, and no partial record is written on failure.

---

### Dependency Injection

All framework components are resolved through the existing Dependency Injection container.

Dependencies include:

- Notification Engine
- Notification Manager
- Collector
- Formatter
- Dispatcher
- Metrics
- Registry
- Event Bus
- LoggerFactory

Every implementation is bound to its abstraction. No infrastructure is instantiated manually, and the framework never instantiates a model, provider, or network client.

---

### Event-Driven Architecture

The framework publishes notification events through the existing Event Bus.

Examples include:

- NotificationStarted
- NotificationCollected
- NotificationFormatted
- RequestsGenerated
- NotificationSnapshotCreated
- NotificationMetricsUpdated
- NotificationCompleted
- NotificationCancelled
- NotificationErrorOccurred

Events are published only after a consistent state, and consumers subscribe without requiring direct coupling to the framework.

---

### Thread Safety

The framework supports concurrent notification.

Thread safety is achieved through:

- Stateless collector
- Stateless formatter
- Stateless dispatcher
- Stateless metrics calculator
- Thread-safe registry
- Atomic per-input processing
- Immutable context, record, models, and events

Shared mutable state is minimized, and one input is processed atomically before the next begins.

---

### Testability

The framework is fully testable without external services.

Tests use:

- Deterministic source readings
- Deterministic notification contexts
- The deterministic default components

No exchange connectivity is required, and no delivery provider is involved.

All tests remain deterministic, with no sleeps and no randomness, and no model training or network calls.

---

## Alternatives Considered

### Notification Logic Inside the Dashboard Framework

Rejected.

The Dashboard Framework is responsible for view aggregation, composition, and widget generation.

Embedding notification collection, formatting, and request generation would violate the Single Responsibility Principle and couple presentation with delivery.

---

### Sending Notifications Automatically

Rejected.

Automatically delivering to a channel would couple the notification layer to an external provider, remove human oversight, and make the framework unsafe.

The framework instead only produces request objects; a sender, if ever wanted, is a separate opt-in concern.

---

### Training a Model Inside the Framework Core

Rejected.

Training a model or calling a provider would make formatting non-deterministic, tie the system to a provider, and prevent deterministic testing.

Collection and formatting instead remain deterministic and rule-based.

---

### Mutable or Externally Persisted Notification State

Rejected.

The notification record is the reproducible basis for the batch and its requests.

Allowing mutation, or delegating persistence to an external store inside the framework, would compromise reproducibility and determinism and violate the framework's immutable, registry-owned design.

---

## Consequences

### Positive

- Clear separation of notifications from the dashboard and execution
- Exchange-independent and provider-independent request generation
- Deterministic, reproducible batches and requests
- Request-only safety: nothing is sent automatically
- Full reuse of the existing frameworks
- Immutable, append-only batch history
- Thread-safe, atomic per-input processing
- Event-driven architecture
- High testability
- Easy extension for richer notifications

### Negative

- Additional architectural layer
- Requests require a separate opt-in step to ever be sent

These trade-offs are acceptable because they preserve scalability, maintainability, modularity, and safety.

---

## Related Components

- notification/
- monitoring/
- dashboard/
- optimization/
- learning/
- events/
- core/

---

## Implementation

Implemented during:

**Sprint 10 – Task 30**

Key components include:

- DefaultNotificationEngine
- DefaultNotificationManager
- DefaultCollector
- DefaultFormatter
- DefaultDispatcher
- DefaultNotificationMetrics
- InMemoryNotificationRegistry

Supporting capabilities include:

- Notification collection
- Notification formatting
- Request generation
- Notification metrics
- Registry-owned notification records
- Snapshot creation
- Structured logging
- Event publication

The framework integrates with:

- Monitoring Framework
- Dashboard Framework
- Optimization Framework
- Learning Framework
- AI Decision Engine
- Dependency Injection Container
- Event Bus
- LoggerFactory

No modifications to existing frameworks were required.

---

## Future Considerations

Future notification capabilities may include:

- An opt-in delivery sender
- Additional channels
- Alternative formatting and routing policies
- Rate limiting
- Constraint-aware suppression
- Record persistence and replay
- Advanced reporting
- A closed, human-supervised delivery loop

These features should extend the existing framework without requiring architectural changes.

---

## Decision Summary

The Notification Framework introduces a dedicated, exchange-independent and provider-independent layer that turns system outputs into deterministic notification requests, strictly requesting delivery without ever sending it.

By separating notification collection, formatting, request generation, metrics, and registration into independent components while reusing the real frameworks through dependency injection and event-driven communication, the AI Trading Operating System remains modular, scalable, thread-safe, deterministic, and safe, and ready for richer notifications without modifying existing frameworks.
