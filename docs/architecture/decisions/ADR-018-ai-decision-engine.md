# ADR-018: AI Decision Engine

## Status

Accepted

## Date

2026-08-04

## Context

The AI Trading Operating System now includes dedicated frameworks for market data, trading, strategies, risk management, order management, execution, exchange adapters, broker integration, portfolio management, position management, trade lifecycle management, performance analytics, historical backtesting, and live paper trading.

While these frameworks decide *what happens* mechanically, none of them provides autonomous, multi-perspective reasoning over the current state of the system to arrive at a single considered decision.

Coordinating specialised agents — each reasoning from a different perspective (market, strategy, risk, portfolio) and arbitrated by a coordinating CEO agent — is a distinct concern that must not be mixed into any trading framework, must never touch an exchange, and must never be tied to a specific AI provider.

The system therefore requires a dedicated AI Decision Engine responsible for orchestrating agents to produce standardized decisions across the existing architecture, deterministically and completely independent of any exchange and of any AI provider.

---

## Decision

Introduce a standalone AI Decision Engine that coordinates autonomous agents to reason over the standardized results the existing frameworks produce and aggregates their opinions into a single immutable decision.

The framework consists of:

- Decision Engine
- Decision Manager
- Agents
- Consensus
- Metrics
- History
- Registry
- Decision Models
- Decision Events

The framework consumes standardized domain models (market snapshot, strategy signals, risk decision, portfolio, position, and performance results) assembled into a decision context. It never places an order and never calls a model, provider, or network client.

No existing framework requires modification.

---

## Rationale

### Separation of Responsibilities

Each framework within the AI Trading Operating System owns a single responsibility.

The existing frameworks answer:

**"What happened, and what should happen mechanically?"**

The AI Decision Engine answers:

**"Given every perspective, what is the single considered decision?"**

Separating reasoning from the frameworks being reasoned over prevents the decision engine from becoming tightly coupled with strategy, risk, portfolio, position, or performance logic.

---

### AI Provider Independence

The AI Decision Engine never communicates directly with:

- Binance or any exchange
- REST APIs
- WebSockets
- LLM or model providers
- External AI services

Instead, agents are injected abstractions that reason over standardized domain models such as:

- MarketSnapshot
- TradingSignal
- RiskDecision
- PortfolioResult
- PositionResult
- PerformanceResult

The framework core is deterministic and makes no model, provider, or network call. Model-backed agents are supplied through the registry as injected implementations, so the engine behaves identically regardless of which AI provider — if any — backs an agent.

---

### Agent Design

Agents reason over the decision context and produce opinions.

Responsibilities include:

- Market analysis
- Strategy analysis
- Risk analysis
- Portfolio analysis

Each agent is stateless and produces a single immutable opinion. Agents are abstractions behind a protocol; the deterministic default agents are rule-based over the standardized inputs, and future model-backed agents plug in without changing the framework. No agent contacts an exchange or a provider, and every agent remains deterministic under test.

---

### CEO Arbitration

The CEO agent arbitrates over the analyst opinions.

The manager gathers the analyst opinions, assembles an enriched context carrying those opinions, and invokes the CEO agent to arbitrate. This keeps the agent abstraction uniform — every agent reasons only from a context — while letting the CEO weigh the collected perspectives. Agents therefore never call one another, and arbitration policy can evolve without changing the analyst agents.

---

### Consensus Design

Consensus aggregates the opinions into a single result.

Responsibilities include:

- Confidence and role weighting
- Directional resolution
- Risk veto
- Agreement measurement

The consensus resolver is stateless and holds no agent logic. A risk veto blocks approval, and a rejection is a first-class, non-failure outcome distinct from an error. Consensus policy can evolve without touching the agents.

---

### Metrics Design

Decision Metrics derives aggregate figures over the decisions.

Responsibilities include:

- Decision counts and directional breakdown
- Approval, rejection, and agreement rates
- Average confidence and average agent participation

Metrics are derived from the decision history and the collected opinions rather than stored independently, reusing the historical record and avoiding duplication.

---

### Atomic Decision Processing

Each decision is processed atomically.

The Decision Manager coordinates:

Decision Context

↓

Market → Strategy → Risk → Portfolio Agents

↓

CEO Agent

↓

Consensus

↓

Decision

↓

Decision History

↓

Decision Metrics

If the decision fails, the decision history is not overwritten.

Partial decisions are never persisted.

---

### Immutability

All decision models are immutable frozen dataclasses.

Immutability applies to:

- Decision Context
- Agent opinions
- Consensus results
- Decisions and summaries
- Snapshots and results

Confidences, weights, and monetary figures use Decimal, and metadata is exposed as a read-only mapping. Each decision produces a new immutable decision; existing decisions and snapshots are never mutated, which guarantees that a reported decision is safe to share, log, and reproduce.

---

### Error Handling

Decision failures are isolated inside the framework.

Stage failures are translated into framework exceptions:

- AgentError
- ConsensusError
- MetricsError
- HistoryError
- RegistryError

Any failure is published as a DecisionErrorOccurred event — and, for an agent failure, a role-tagged AgentErrorOccurred event — and returned as a failed DecisionResult. Internal implementation details never escape the framework, and no partial decision is written on failure.

---

### Dependency Injection

All framework components are resolved through the existing Dependency Injection container.

Dependencies include:

- Decision Engine
- Decision Manager
- Agents
- Consensus
- Metrics
- History
- Registry
- Event Bus
- LoggerFactory

The default agents are injected through the registry, and every implementation is bound to its abstraction. No infrastructure is instantiated manually, and the framework never instantiates a model, provider, or network client.

---

### Event-Driven Architecture

The framework publishes decision events through the existing Event Bus.

Examples include:

- DecisionRequested
- AgentEvaluated
- ConsensusReached
- DecisionMade
- DecisionRejected
- DecisionSnapshotCreated
- DecisionMetricsUpdated
- DecisionCancelled
- AgentErrorOccurred
- DecisionErrorOccurred

Events are published only after a consistent state, and consumers subscribe without requiring direct coupling to the framework.

---

### Thread Safety

The framework supports concurrent decisions.

Thread safety is achieved through:

- Stateless agents
- Stateless consensus resolver
- Stateless metrics calculator
- Thread-safe agent registry
- Atomic decision processing
- Immutable context, models, and events

Shared mutable state is minimized, and one decision is processed atomically before the next begins.

---

### Testability

The framework is fully testable without external services.

Tests use:

- Deterministic standardized inputs
- A controllable fake agent
- The deterministic default agents

No exchange connectivity is required, and no AI provider is involved.

All tests remain deterministic, with no sleeps and no randomness, and no real model or network calls.

---

## Alternatives Considered

### Decision Logic Inside the Strategy Framework

Rejected.

The Strategy Framework is responsible for generating signals.

Embedding multi-agent reasoning and arbitration would violate the Single Responsibility Principle and couple signal generation with decision-making.

---

### Direct Provider Calls Inside the Framework Core

Rejected.

Calling an LLM or model provider directly from the framework core would make decisions non-deterministic, tie the system to a specific provider, and prevent deterministic testing.

Agents instead remain injected abstractions, and the core stays deterministic.

---

### Agents Calling One Another

Rejected.

Allowing agents to invoke one another would couple agents and obscure responsibility.

The manager instead gathers opinions and enriches the context for CEO arbitration, so agents reason only from a context and never call one another.

---

### Mutable or Provider-Persisted Decision State

Rejected.

The decision history is the reproducible record of the engine's reasoning.

Allowing mutation, or delegating persistence to a provider inside the framework, would compromise reproducibility and determinism and violate the framework's immutable, registry-owned design.

---

## Consequences

### Positive

- Clear separation of reasoning from mechanical trading
- Exchange-independent and AI-provider-independent decisions
- Deterministic, reproducible decision-making
- Full reuse of the existing frameworks
- Immutable, append-only decision history
- Thread-safe, atomic decision processing
- Event-driven architecture
- High testability
- Easy extension for model-backed agents and additional roles

### Negative

- Additional architectural layer
- Additional coordination across the agents the manager drives per decision

These trade-offs are acceptable because they preserve scalability, maintainability, and modularity.

---

## Related Components

- agents/
- market_data/
- strategies/
- risk/
- portfolio/
- positions/
- performance/
- events/
- core/

---

## Implementation

Implemented during:

**Sprint 5 – Task 25**

Key components include:

- DefaultDecisionEngine
- DefaultDecisionManager
- DefaultMarketAgent
- DefaultStrategyAgent
- DefaultRiskAgent
- DefaultPortfolioAgent
- DefaultCEOAgent
- DefaultConsensus
- DefaultDecisionMetrics
- DefaultDecisionHistory
- InMemoryAgentRegistry

Supporting capabilities include:

- Agent orchestration
- CEO arbitration
- Consensus resolution
- Decision metrics
- Append-only history
- Agent registration
- Structured logging
- Event publication

The framework integrates with:

- Market Data Framework
- Strategy Framework
- Risk Framework
- Portfolio Management Framework
- Position Management Framework
- Performance Analytics Framework
- Dependency Injection Container
- Event Bus
- LoggerFactory

No modifications to existing frameworks were required.

---

## Future Considerations

Future decision capabilities may include:

- Model-backed agents
- Additional agent roles (Research, News, Learning, Optimisation)
- Ensemble reasoning
- A learning and feedback loop
- Decision persistence and replay
- Confidence calibration
- Advanced reporting
- Autonomous end-to-end orchestration

These features should extend the existing framework without requiring architectural changes.

---

## Decision Summary

The AI Decision Engine introduces a dedicated, exchange-independent and AI-provider-independent layer that coordinates autonomous agents to reason over the existing standardized results and produce a single considered decision.

By separating agent reasoning, CEO arbitration, consensus resolution, metrics, history, and registration into independent components while reusing the real frameworks through dependency injection and event-driven communication, the AI Trading Operating System remains modular, scalable, thread-safe, deterministic, and ready for model-backed agents and advanced reasoning without modifying existing frameworks.
