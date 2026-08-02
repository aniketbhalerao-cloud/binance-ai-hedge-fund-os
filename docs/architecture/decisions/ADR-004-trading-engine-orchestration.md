# ADR-004: Trading Engine Orchestration

## Status

Accepted

## Date

2026-08-02

## Context

The AI Trading Operating System consists of multiple independent components responsible for different aspects of the trading lifecycle, including:

- Market Data Framework
- Strategy Framework
- Risk Engine
- Order Manager
- Portfolio Manager
- Persistence Layer
- Notification Services
- Exchange Adapters

A central component is required to coordinate the lifecycle and interaction of these services.

A common architectural mistake in trading systems is allowing the Trading Engine to become a "God Object" that contains:

- Strategy logic
- Risk calculations
- Order execution
- Exchange communication
- Portfolio management
- Notification handling

This results in excessive coupling, poor maintainability, and a system that becomes increasingly difficult to test and extend.

The architecture therefore requires a central coordinator that manages infrastructure while remaining independent of business logic.

---

## Decision

The Trading Engine will act exclusively as an orchestration layer.

Its responsibilities are limited to:

- Managing application lifecycle
- Coordinating infrastructure services
- Starting and stopping system components
- Managing engine state
- Publishing lifecycle events
- Coordinating through Dependency Injection
- Logging lifecycle operations

The Trading Engine will **not**:

- Generate trading signals
- Execute strategies
- Calculate technical indicators
- Manage portfolio positions
- Evaluate risk
- Execute orders
- Connect directly to exchanges
- Persist business data

Business decisions remain delegated to dedicated framework components.

---

## Rationale

Separating orchestration from business logic creates a modular architecture where each component has a single responsibility.

### Separation of Concerns

The Trading Engine manages **when** components operate.

Other components decide **what** actions should be taken.

Examples:

- Market Data receives and normalizes market information.
- Strategy Framework evaluates market conditions.
- Risk Engine evaluates trade safety.
- Order Manager prepares executable orders.
- Exchange Adapter communicates with external exchanges.

Each component focuses exclusively on its own domain.

---

### Maintainability

Business rules evolve much faster than orchestration.

Keeping them separate allows strategy changes without modifying the Trading Engine.

Similarly, infrastructure improvements do not require changes to trading algorithms.

---

### Extensibility

Future components can integrate through Dependency Injection and the Event Bus.

Examples include:

- AI Decision Engine
- Machine Learning Models
- Backtesting Engine
- Paper Trading
- Analytics
- Monitoring
- Notification Services

No Trading Engine modifications should be required.

---

### Testability

The Trading Engine can be tested independently from trading algorithms.

Unit tests verify:

- Lifecycle transitions
- Service coordination
- Dependency Injection
- Event publishing
- Logging

Business logic is tested separately within its own framework.

---

### Lifecycle Management

The Trading Engine owns the application lifecycle.

Supported states include:

- CREATED
- INITIALIZING
- STARTING
- RUNNING
- PAUSED
- STOPPING
- STOPPED
- FAILED

Transitions are validated by the Lifecycle Manager to prevent invalid state changes.

---

## Alternatives Considered

### Monolithic Trading Engine

Advantages:

- Simple initial implementation.
- Fewer classes.

Disadvantages:

- Violates Single Responsibility Principle.
- Difficult testing.
- Tight coupling.
- Large maintenance burden.
- Poor scalability.

Rejected.

---

### Service-to-Service Coordination

Advantages:

- No central orchestrator.

Disadvantages:

- Complex dependency graph.
- Circular dependencies.
- Difficult lifecycle management.
- Harder debugging.

Rejected.

---

### Workflow Engine

Advantages:

- Flexible orchestration.
- Dynamic workflows.

Disadvantages:

- Additional complexity.
- External dependency.
- Unnecessary for the current architecture.

Deferred for future consideration.

---

## Consequences

### Positive

- Clear separation of responsibilities.
- Simple orchestration layer.
- Easy testing.
- Loose coupling.
- Supports future expansion.
- Cleaner architecture.
- Predictable lifecycle management.
- Easier debugging.

### Negative

- Additional coordination layer.
- More interfaces to maintain.
- Business logic distributed across multiple components.

These trade-offs are considered acceptable in exchange for long-term maintainability.

---

## Related Components

- trading/
- trading/engine.py
- trading/coordinator.py
- trading/lifecycle.py
- events/
- core/
- market_data/
- strategies/

---

## Implementation

Implemented during:

Sprint 2 – Task 11

Key components include:

- TradingEngine
- TradingCoordinator
- LifecycleManager
- RuntimeState
- Trading Engine Lifecycle Events
- Dependency Injection Registration

The Trading Engine serves as the orchestration layer for the AI Trading Operating System and delegates all business logic to specialized framework components.

---

## Future Considerations

Future enhancements may include:

- Service health monitoring
- Graceful shutdown sequencing
- Dynamic service registration
- Runtime service discovery
- Distributed orchestration
- Cluster-aware lifecycle management
- Metrics collection
- Engine diagnostics

These enhancements should preserve the Trading Engine's role as an orchestrator and must not introduce trading algorithms or business logic into the engine.