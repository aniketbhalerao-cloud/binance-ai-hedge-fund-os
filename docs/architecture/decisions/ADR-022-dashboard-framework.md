# ADR-022: Dashboard Framework

## Status

Accepted

## Date

2026-08-06

## Context

The AI Trading Operating System now includes dedicated frameworks for market data, trading, strategies, risk management, order management, execution, exchange adapters, broker integration, portfolio management, position management, trade lifecycle management, performance analytics, historical backtesting, live paper trading, autonomous AI decision-making, learning from completed activity, optimization of learning outputs, and monitoring of system health.

While each framework produces its own results, no framework presents the state of the running system as a whole, arranges those outputs into panels, or exposes them as widgets.

Aggregating system outputs, composing them into panels, resolving their layout, and generating widgets — without ever acting on them — is a distinct concern that must not be mixed into any trading, decision, learning, optimization, or monitoring framework, must never touch an exchange, and must never modify strategies, agents, or portfolios.

The system therefore requires a dedicated Dashboard Framework responsible for producing deterministic dashboard views and widgets from system outputs, completely independent of any exchange and of any display provider, and strictly present-only.

---

## Decision

Introduce a standalone Dashboard Framework that consumes standardized system outputs and turns them into dashboard views, widgets, and metrics.

The framework consists of:

- Dashboard Engine
- Dashboard Manager
- Aggregator
- Composer
- Widgets
- Metrics
- Registry
- Dashboard Models
- Dashboard Events

The framework consumes standardized domain models (strategy sources, performance sources, optimization sources, and monitoring sources) assembled into a dashboard context. It never places an order, never renders to a real display, and never trains a model, calls a provider, or performs network communication.

No existing framework requires modification.

---

## Rationale

### Separation of Responsibilities

Each framework within the AI Trading Operating System owns a single responsibility.

The Monitoring Framework answers:

**"Is the running system healthy, and what needs attention?"**

The Dashboard Framework answers:

**"Given all of that, how is the system presented at a glance?"**

Separating dashboards from the frameworks being presented prevents the dashboard layer from becoming tightly coupled with strategy, decision, optimization, or monitoring logic.

---

### Dashboard Independence

The Dashboard Framework never communicates directly with:

- Binance or any exchange
- REST APIs
- WebSockets
- Display or model providers
- External libraries beyond the standard library

Instead, it consumes standardized domain models such as:

- DashboardSource
- Panel
- DashboardView
- Widget

Aggregation and composition are deterministic and rule-based, derived only from the system outputs. The framework core makes no display, provider, or network call, so the dashboard behaves identically and reproducibly under test.

---

### Aggregator Design

The Aggregator derives and normalizes display series.

Responsibilities include:

- Gathering outputs
- Normalizing panel sources
- Deriving display series
- Building the view

The aggregator is stateless and deterministic. It normalizes readings worst-first with a stable tiebreak and builds one panel per source. It only presents and never modifies a subject.

---

### Composer Design

The Composer component composes the view.

Responsibilities include:

- Composing the view
- Arranging panels and sections
- Resolving the layout

The composer is stateless and deterministic, resolving each panel's visibility against the visible threshold. It never acts on a panel — composition produces a layout, not mutations.

---

### Widgets Design

The Widget generator turns the composed view into widgets.

Responsibilities include:

- Widget generation
- Panel view-model rendering
- Summary suggestions

The widget generator is stateless and deterministic. It presents view models only and never modifies strategies, agents, or portfolios and never renders to a real display.

---

### Metrics Design

Dashboard Metrics derives aggregate figures over the record.

Responsibilities include:

- Panel and widget counts
- Average panel score
- Best and worst panel
- Coverage ratio
- Visible and hidden widget counts

Metrics are derived from the record rather than stored independently. The hidden widget count reflects the panels that produced no widget, since the framework only presents visible panels.

---

### Atomic Dashboard Processing

Each input is processed atomically.

The Dashboard Manager coordinates:

Dashboard Context

↓

Load Record

↓

Aggregator

↓

Composer

↓

Widgets

↓

Dashboard Metrics

↓

New Immutable Record

If the update fails, the record is not overwritten.

Partial dashboard state is never persisted.

---

### Immutability

All dashboard models are immutable frozen dataclasses.

Immutability applies to:

- Dashboard Context
- Sources, panels, and views
- Widgets
- The dashboard record, snapshots, and results

Scores use Decimal, and metadata is exposed as a read-only mapping. Each update produces a new immutable record; existing records and snapshots are never mutated, which guarantees that a reported view is safe to share, log, and reproduce.

---

### Error Handling

Dashboard failures are isolated inside the framework.

Stage failures are translated into framework exceptions:

- AggregationError
- CompositionError
- WidgetError
- MetricsError
- RegistryError

Any failure is published as a DashboardErrorOccurred event and returned as a failed DashboardResult. Internal implementation details never escape the framework, and no partial record is written on failure.

---

### Dependency Injection

All framework components are resolved through the existing Dependency Injection container.

Dependencies include:

- Dashboard Engine
- Dashboard Manager
- Aggregator
- Composer
- Widgets
- Metrics
- Registry
- Event Bus
- LoggerFactory

Every implementation is bound to its abstraction. No infrastructure is instantiated manually, and the framework never instantiates a model, provider, or network client.

---

### Event-Driven Architecture

The framework publishes dashboard events through the existing Event Bus.

Examples include:

- DashboardStarted
- DashboardViewCreated
- DashboardComposed
- WidgetsGenerated
- DashboardSnapshotCreated
- DashboardMetricsUpdated
- DashboardCompleted
- DashboardCancelled
- DashboardErrorOccurred

Events are published only after a consistent state, and consumers subscribe without requiring direct coupling to the framework.

---

### Thread Safety

The framework supports concurrent rendering.

Thread safety is achieved through:

- Stateless aggregator
- Stateless composer
- Stateless widget generator
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
- Deterministic dashboard contexts
- The deterministic default components

No exchange connectivity is required, and no display provider is involved.

All tests remain deterministic, with no sleeps and no randomness, and no model training or network calls.

---

## Alternatives Considered

### Dashboard Logic Inside the Monitoring Framework

Rejected.

The Monitoring Framework is responsible for health collection, diagnostics, and alerting.

Embedding view aggregation, composition, and widget generation would violate the Single Responsibility Principle and couple monitoring with presentation.

---

### Rendering Widgets Automatically

Rejected.

Automatically rendering to a display would couple the dashboard to an external provider, remove human oversight, and make the framework unsafe.

The framework instead only presents view models; a renderer, if ever wanted, is a separate opt-in concern.

---

### Training a Model Inside the Framework Core

Rejected.

Training a model or calling a provider would make composition non-deterministic, tie the system to a provider, and prevent deterministic testing.

Aggregation and composition instead remain deterministic and rule-based.

---

### Mutable or Externally Persisted Dashboard State

Rejected.

The dashboard record is the reproducible basis for the view and its widgets.

Allowing mutation, or delegating persistence to an external store inside the framework, would compromise reproducibility and determinism and violate the framework's immutable, registry-owned design.

---

## Consequences

### Positive

- Clear separation of the dashboard from monitoring and execution
- Exchange-independent and provider-independent presentation
- Deterministic, reproducible views and widgets
- Present-only safety: nothing is acted upon automatically
- Full reuse of the existing frameworks
- Immutable, append-only view history
- Thread-safe, atomic per-input processing
- Event-driven architecture
- High testability
- Easy extension for richer dashboards

### Negative

- Additional architectural layer
- Widgets require a separate opt-in step to ever be rendered

These trade-offs are acceptable because they preserve scalability, maintainability, modularity, and safety.

---

## Related Components

- dashboard/
- strategies/
- agents/
- optimization/
- monitoring/
- events/
- core/

---

## Implementation

Implemented during:

**Sprint 9 – Task 29**

Key components include:

- DefaultDashboardEngine
- DefaultDashboardManager
- DefaultAggregator
- DefaultComposer
- DefaultWidgets
- DefaultDashboardMetrics
- InMemoryDashboardRegistry

Supporting capabilities include:

- View aggregation
- View composition
- Widget generation
- Dashboard metrics
- Registry-owned dashboard records
- Snapshot creation
- Structured logging
- Event publication

The framework integrates with:

- Strategy Framework
- AI Decision Engine
- Optimization Framework
- Monitoring Framework
- Performance Analytics Framework
- Dependency Injection Container
- Event Bus
- LoggerFactory

No modifications to existing frameworks were required.

---

## Future Considerations

Future dashboard capabilities may include:

- An opt-in widget renderer
- Additional panel types
- Alternative composition and layout policies
- Real-time streaming
- Constraint-aware visibility
- Record persistence and replay
- Advanced reporting
- A closed, human-supervised presentation loop

These features should extend the existing framework without requiring architectural changes.

---

## Decision Summary

The Dashboard Framework introduces a dedicated, exchange-independent and provider-independent layer that turns system outputs into deterministic dashboard views and widgets, strictly presenting the system state without ever acting on it.

By separating view aggregation, composition, widget generation, metrics, and registration into independent components while reusing the real frameworks through dependency injection and event-driven communication, the AI Trading Operating System remains modular, scalable, thread-safe, deterministic, and safe, and ready for richer dashboards without modifying existing frameworks.
