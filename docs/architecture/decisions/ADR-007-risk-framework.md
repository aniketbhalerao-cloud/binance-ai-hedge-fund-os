# ADR-007: Risk Framework

## Status

Accepted

## Date

2026-08-02

## Context

Trading strategies determine trading opportunities, but they should not decide whether those opportunities are safe to execute.

Without a dedicated Risk Framework, strategy implementations would become responsible for evaluating exposure, drawdown, leverage, position sizing, and account constraints.

This would tightly couple trading decisions with risk management and make the system difficult to extend, test, and maintain.

The architecture therefore requires a dedicated Risk Framework positioned between the Strategy Framework and the future Order Manager.

---

## Decision

The system will implement a reusable Risk Framework responsible solely for evaluating TradingSignals before execution.

The framework consists of:

- Risk Engine
- Risk Manager
- Risk Validator
- Risk Rules
- Risk Context
- Risk Decisions
- Risk Events

The framework evaluates trading intent but never executes trades.

Future risk rules will plug into the framework without requiring changes to the Risk Engine.

---

## Rationale

Separating risk evaluation from strategy execution provides several architectural benefits.

### Separation of Concerns

Strategies decide:

**"What should we do?"**

Risk Framework decides:

**"Are we allowed to do it?"**

Order Manager decides:

**"How should it be executed?"**

Each layer has one responsibility.

---

### Open/Closed Principle

New risk rules can be introduced without modifying the framework.

Examples include:

- Maximum Position Size
- Maximum Exposure
- Daily Loss
- Drawdown
- Margin Limits
- Leverage Limits
- Portfolio Correlation

---

### Testability

Every rule is deterministic.

Rules receive a RiskContext and return a RiskResult.

No external services are required.

---

### Replay Compatibility

The Risk Framework consumes normalized domain models rather than exchange-specific payloads.

Replay, paper trading, and live trading therefore share the same evaluation pipeline.

---

### Event-Driven Architecture

Risk evaluation publishes framework events through the existing Event Bus.

Future Order Managers subscribe to Risk Decisions rather than being called directly.

---

## Alternatives Considered

### Strategies Performing Risk Checks

Rejected.

This tightly couples trading logic with risk management.

---

### Order Manager Performing Risk Checks

Rejected.

Execution should not contain business decision logic.

---

### Exchange-Specific Risk Validation

Rejected.

Risk policies should remain independent of broker or exchange APIs.

---

## Consequences

### Positive

- Clear separation of responsibilities
- Extensible risk policies
- Replay compatibility
- Improved testing
- Event-driven integration
- Framework independence
- Exchange-independent design

### Negative

- Additional abstraction layer
- More framework components
- Additional events

These trade-offs are acceptable for long-term maintainability.

---

## Related Components

- risk/
- strategies/
- trading/
- market_data/
- events/
- core/

---

## Implementation

Implemented during:

Sprint 2 – Task 14

Key components include:

- RiskEvaluationEngine
- RiskEvaluationManager
- RuleRiskValidator
- BaseRiskRule
- RiskContext
- RiskDecision
- Risk Events

---

## Future Considerations

Future enhancements include:

- Composite Risk Policies
- Rule Priorities
- AI Risk Rules
- Machine Learning Risk Models
- Portfolio Correlation
- Dynamic Rule Configuration
- Distributed Risk Evaluation

These enhancements should preserve the framework's role as the centralized risk evaluation layer while keeping strategies and execution independent.