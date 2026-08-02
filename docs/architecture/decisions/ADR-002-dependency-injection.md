# ADR-002: Dependency Injection

## Status

Accepted

## Date

2026-08-02

## Context

The AI Trading Operating System consists of many independent infrastructure and business components, including:

- Event Bus
- LoggerFactory
- Trading Engine
- Market Data Framework
- Strategy Framework
- Repository Layer
- Persistence Service
- Exchange Adapters

These components depend on one another but should remain loosely coupled.

Allowing classes to instantiate their own dependencies would result in:

- Tight coupling
- Difficult unit testing
- Hidden dependencies
- Poor extensibility
- Duplicate singleton instances
- Complex object construction

The system requires a centralized mechanism for constructing and managing object dependencies while keeping components independent of implementation details.

---

## Decision

The system will adopt Constructor-Based Dependency Injection using a centralized Dependency Injection Container.

All application services receive their required dependencies through constructor injection.

The Dependency Injection Container is responsible for:

- Registering services
- Resolving dependencies
- Managing object lifetimes
- Constructing dependency graphs
- Detecting circular dependencies

Components never instantiate their collaborators directly.

Object creation is centralized within the composition root.

---

## Rationale

Dependency Injection provides several architectural benefits.

### Loose Coupling

Components depend on abstractions instead of concrete implementations.

For example:

The Trading Engine depends on the EventBus interface rather than creating an EventBus instance.

The Strategy Framework depends on the Market Data Service abstraction rather than a specific provider.

---

### Testability

Dependencies can easily be replaced with test doubles.

Examples include:

- Fake Event Bus
- Fake Repository
- Fake Logger
- Fake Provider

This enables deterministic unit testing without modifying production code.

---

### Centralized Configuration

All dependency registration occurs in one location.

Changing implementations requires only updating registrations.

Application code remains unchanged.

---

### Lifetime Management

The Dependency Injection Container manages object lifetimes.

Supported lifetimes include:

- Singleton
- Transient

Examples:

Singleton:

- EventBus
- LoggerFactory
- TradingEngine
- MarketDataService

Transient:

- Future request-specific services
- Temporary processing objects

---

### Extensibility

New services integrate by:

1. Implementing an interface.
2. Registering with the container.

Existing components require no modification.

This satisfies the Open/Closed Principle.

---

## Alternatives Considered

### Manual Dependency Creation

Advantages:

- Simple for very small applications.

Disadvantages:

- Tight coupling.
- Difficult testing.
- Duplicate infrastructure instances.
- Complex constructors.

Rejected.

---

### Service Locator Pattern

Advantages:

- Simple lookup mechanism.

Disadvantages:

- Hidden dependencies.
- Harder to understand and test.
- Reduced compile-time safety.

Rejected.

---

### External Dependency Injection Framework

Advantages:

- Mature feature set.

Disadvantages:

- Additional dependency.
- Reduced control.
- Unnecessary complexity for the current project.

Deferred.

---

## Consequences

### Positive

- Loose coupling.
- Better modularity.
- Simplified testing.
- Centralized dependency management.
- Consistent singleton lifecycle.
- Easier feature expansion.
- Cleaner architecture.

### Negative

- Additional infrastructure code.
- Initial learning curve.
- More registrations to maintain.
- Constructor signatures may grow as dependencies increase.

---

## Related Components

- core/container.py
- core/interfaces.py
- core/lifetime.py
- events/
- trading/
- market_data/
- database/
- strategies/
- tests/

---

## Implementation

Implemented during:

Sprint 1 – Task 7

Key components include:

- ServiceContainer
- ServiceRegistry
- Lifetime
- Constructor Injection
- Singleton Management
- Circular Dependency Detection

The Dependency Injection Container serves as the composition root for the AI Trading Operating System.

---

## Future Considerations

Future enhancements may include:

- Scoped lifetimes
- Automatic module discovery
- Plugin registration
- Lazy dependency resolution
- Conditional registrations
- Named service registrations
- Configuration-based registrations

These enhancements should preserve constructor injection and maintain compatibility with the existing Dependency Injection architecture.