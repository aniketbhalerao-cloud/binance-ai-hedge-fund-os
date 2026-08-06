# ADR-021: Monitoring Framework

## Status

Accepted

## Date

2026-08-06

## Context

The AI Trading Operating System now includes dedicated frameworks for market data, trading, strategies, risk management, order management, execution, exchange adapters, broker integration, portfolio management, position management, trade lifecycle management, performance analytics, historical backtesting, live paper trading, autonomous AI decision-making, learning from completed activity, and optimization of learning outputs.

While each framework produces its own results, no framework observes the health of the running system as a whole, detects when a component degrades, or surfaces alerts.

Collecting health signals, evaluating them, detecting threshold breaches, and generating alerts — without ever acting on them — is a distinct concern that must not be mixed into any trading, decision, learning, or optimization framework, must never touch an exchange, and must never modify strategies, agents, or portfolios.

The system therefore requires a dedicated Monitoring Framework responsible for producing deterministic health reports and alerts from system signals, completely independent of any exchange and of any notification provider, and strictly observe-only.

---

## Decision

Introduce a standalone Monitoring Framework that consumes standardized system signals and turns them into health reports, alerts, and metrics.

The framework consists of:

- Monitoring Engine
- Monitoring Manager
- Health
- Diagnostics
- Alerts
- Metrics
- Registry
- Monitoring Models
- Monitoring Events

The framework consumes standardized domain models (strategy signals, agent signals, performance metrics, and optimization signals) assembled into a monitoring context. It never places an order, never sends a notification, and never trains a model, calls a provider, or performs network communication.

No existing framework requires modification.

---

## Rationale

### Separation of Responsibilities

Each framework within the AI Trading Operating System owns a single responsibility.

The Optimization Framework answers:

**"Given the learning outputs, what is the concrete plan of proposed changes?"**

The Monitoring Framework answers:

**"Is the running system healthy, and what needs attention?"**

Separating monitoring from the frameworks being monitored prevents the monitoring layer from becoming tightly coupled with strategy, decision, learning, or optimization logic.

---

### Monitoring Independence

The Monitoring Framework never communicates directly with:

- Binance or any exchange
- REST APIs
- WebSockets
- Notification or model providers
- External libraries beyond the standard library

Instead, it consumes standardized domain models such as:

- MonitoredComponent
- HealthCheck
- HealthReport
- Alert

Health evaluation and alerting are deterministic and rule-based, derived only from the system signals. The framework core makes no notification, provider, or network call, so monitoring behaves identically and reproducibly under test.

---

### Health Design

The Health collector derives and normalizes health signals.

Responsibilities include:

- Gathering signals
- Normalizing component observations
- Deriving observed indicators
- Building the report

The health collector is stateless and deterministic. It normalizes readings worst-first with a stable tiebreak and builds one check per component. It only observes and never modifies a subject.

---

### Diagnostics Design

The Diagnostics component evaluates the report.

Responsibilities include:

- Evaluating the report
- Detecting threshold breaches
- Scoring component and system health

The diagnostics is stateless and deterministic, classifying each component against the health and critical thresholds. It never acts on a breach — evaluation produces verdicts, not mutations.

---

### Alerts Design

The Alert generator turns the evaluated report into alerts.

Responsibilities include:

- Alert generation
- Severity classification
- Notification suggestions

The alert generator is stateless and deterministic. It proposes alerts only and never modifies strategies, agents, or portfolios and never sends a real notification.

---

### Metrics Design

Monitoring Metrics derives aggregate figures over the record.

Responsibilities include:

- Check and alert counts
- Average health score
- Best and worst component
- Uptime ratio
- Active and resolved alert counts

Metrics are derived from the record rather than stored independently. The resolved alert count is always zero by design, since the framework only observes.

---

### Atomic Monitoring Processing

Each input is processed atomically.

The Monitoring Manager coordinates:

Monitoring Context

↓

Load Record

↓

Health

↓

Diagnostics

↓

Alerts

↓

Monitoring Metrics

↓

New Immutable Record

If the update fails, the record is not overwritten.

Partial monitoring state is never persisted.

---

### Immutability

All monitoring models are immutable frozen dataclasses.

Immutability applies to:

- Monitoring Context
- Components, checks, and reports
- Alerts
- The monitoring record, snapshots, and results

Scores use Decimal, and metadata is exposed as a read-only mapping. Each update produces a new immutable record; existing records and snapshots are never mutated, which guarantees that a reported health report is safe to share, log, and reproduce.

---

### Error Handling

Monitoring failures are isolated inside the framework.

Stage failures are translated into framework exceptions:

- CollectionError
- EvaluationError
- AlertError
- MetricsError
- RegistryError

Any failure is published as a MonitoringErrorOccurred event and returned as a failed MonitoringResult. Internal implementation details never escape the framework, and no partial record is written on failure.

---

### Dependency Injection

All framework components are resolved through the existing Dependency Injection container.

Dependencies include:

- Monitoring Engine
- Monitoring Manager
- Health
- Diagnostics
- Alerts
- Metrics
- Registry
- Event Bus
- LoggerFactory

Every implementation is bound to its abstraction. No infrastructure is instantiated manually, and the framework never instantiates a model, provider, or network client.

---

### Event-Driven Architecture

The framework publishes monitoring events through the existing Event Bus.

Examples include:

- MonitoringStarted
- HealthReportCreated
- HealthEvaluated
- AlertsGenerated
- MonitoringSnapshotCreated
- MonitoringMetricsUpdated
- MonitoringCompleted
- MonitoringCancelled
- MonitoringErrorOccurred

Events are published only after a consistent state, and consumers subscribe without requiring direct coupling to the framework.

---

### Thread Safety

The framework supports concurrent monitoring.

Thread safety is achieved through:

- Stateless health collector
- Stateless diagnostics
- Stateless alert generator
- Stateless metrics calculator
- Thread-safe registry
- Atomic per-input processing
- Immutable context, record, models, and events

Shared mutable state is minimized, and one input is processed atomically before the next begins.

---

### Testability

The framework is fully testable without external services.

Tests use:

- Deterministic component readings
- Deterministic monitoring contexts
- The deterministic default components

No exchange connectivity is required, and no notification provider is involved.

All tests remain deterministic, with no sleeps and no randomness, and no model training or network calls.

---

## Alternatives Considered

### Monitoring Logic Inside the Optimization Framework

Rejected.

The Optimization Framework is responsible for planning and recommendation generation.

Embedding health collection, diagnostics, and alerting would violate the Single Responsibility Principle and couple optimization with monitoring.

---

### Sending Alerts Automatically

Rejected.

Automatically dispatching notifications would couple monitoring to an external provider, remove human oversight, and make the framework unsafe.

The framework instead only proposes; a dispatcher, if ever wanted, is a separate opt-in concern.

---

### Training a Model Inside the Framework Core

Rejected.

Training a model or calling a provider would make monitoring non-deterministic, tie the system to a provider, and prevent deterministic testing.

Health evaluation and alerting instead remain deterministic and rule-based.

---

### Mutable or Externally Persisted Monitoring State

Rejected.

The monitoring record is the reproducible basis for the health report and its alerts.

Allowing mutation, or delegating persistence to an external store inside the framework, would compromise reproducibility and determinism and violate the framework's immutable, registry-owned design.

---

## Consequences

### Positive

- Clear separation of monitoring from optimization and execution
- Exchange-independent and provider-independent monitoring
- Deterministic, reproducible health reports and alerts
- Observe-only safety: nothing is acted upon automatically
- Full reuse of the existing frameworks
- Immutable, append-only report history
- Thread-safe, atomic per-input processing
- Event-driven architecture
- High testability
- Easy extension for richer monitoring

### Negative

- Additional architectural layer
- Alerts require a separate opt-in step to ever be sent

These trade-offs are acceptable because they preserve scalability, maintainability, modularity, and safety.

---

## Related Components

- monitoring/
- strategies/
- agents/
- learning/
- optimization/
- events/
- core/

---

## Implementation

Implemented during:

**Sprint 8 – Task 28**

Key components include:

- DefaultMonitoringEngine
- DefaultMonitoringManager
- DefaultHealth
- DefaultDiagnostics
- DefaultAlerts
- DefaultMonitoringMetrics
- InMemoryMonitoringRegistry

Supporting capabilities include:

- Health collection
- Health diagnostics
- Alert generation
- Monitoring metrics
- Registry-owned monitoring records
- Snapshot creation
- Structured logging
- Event publication

The framework integrates with:

- Strategy Framework
- AI Decision Engine
- Learning Framework
- Optimization Framework
- Performance Analytics Framework
- Dependency Injection Container
- Event Bus
- LoggerFactory

No modifications to existing frameworks were required.

---

## Future Considerations

Future monitoring capabilities may include:

- An opt-in notification dispatcher
- Additional health indicators
- Alternative diagnostics and severity policies
- Anomaly detection
- Constraint-aware thresholds
- Record persistence and replay
- Advanced reporting
- A closed, human-supervised alerting loop

These features should extend the existing framework without requiring architectural changes.

---

## Decision Summary

The Monitoring Framework introduces a dedicated, exchange-independent and provider-independent layer that turns system signals into deterministic health reports and alerts, strictly observing health without ever acting on it.

By separating health collection, diagnostics, alert generation, metrics, and registration into independent components while reusing the real frameworks through dependency injection and event-driven communication, the AI Trading Operating System remains modular, scalable, thread-safe, deterministic, and safe, and ready for richer monitoring without modifying existing frameworks.
