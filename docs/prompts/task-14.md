# Project Context

Project: AI Trading Operating System

Version: Sprint 2

Task: 14

---

# Background

Sprint 1 established the infrastructure layer:

- Domain Models
- Event Bus
- Dependency Injection
- Logging
- Repository Pattern
- Persistence Service
- Testing Framework

Sprint 2 established:

- Trading Engine
- Market Data Framework
- Strategy Framework

The next layer is the Risk Management Framework.

---

# Purpose

The Risk Engine evaluates every TradingSignal before it reaches the Order Manager.

It is responsible for deciding whether a signal is allowed to proceed.

The Risk Engine never generates signals.

The Risk Engine never executes trades.

The Risk Engine evaluates trading risk only.

---

# Responsibilities

The Risk Engine is responsible for:

- Receiving TradingSignals
- Applying risk rules
- Validating trading constraints
- Producing risk decisions
- Publishing risk events

The Risk Engine must remain independent of:

- Exchanges
- Strategies
- Order execution
- Portfolio persistence

---

# Design Philosophy

Risk evaluation must be completely independent of trading strategy.

Strategies decide:

"What should we do?"

The Risk Engine decides:

"Are we allowed to do it?"

The Order Manager decides:

"How do we execute it?"

---

# Mandatory Architecture Review

Before implementing any code:

Review the existing project.

Search for:

- risk
- validator
- rules
- limits
- position sizing
- exposure
- stop loss

Determine:

- What already exists
- What should be reused
- What should be extended
- Whether implementation would duplicate functionality

Present the architecture review before writing code.

Reuse:

- Event Bus
- Dependency Injection
- LoggerFactory
- Trading Engine
- Market Data Framework
- Strategy Framework
- Repository Pattern

Do not duplicate existing infrastructure.

---

# Current Task

Populate only the existing files inside:

risk/

Do not create additional packages.

Do not implement trading strategies.

Do not implement order execution.

Stop immediately after Task 14 is complete.
# Files to Populate

Populate only the existing files inside:

risk/

├── __init__.py
├── context.py
├── engine.py
├── events.py
├── exceptions.py
├── interfaces.py
├── manager.py
├── models.py
├── rules.py
└── validator.py

Do not create additional modules.

---

# File Responsibilities

## __init__.py

Purpose:

Expose the public Risk Framework API.

Re-export only the primary public classes.

No implementation logic.

---

## context.py

Purpose:

Provide the complete RiskContext required for evaluation.

The context should contain everything required for risk validation.

Examples:

- TradingSignal
- Market Snapshot
- Current Position
- Current Exposure
- Available Capital
- Account Balance
- Open Orders
- Exchange
- Symbol
- Timeframe
- Timestamp
- Optional Metadata

The RiskContext should be immutable.

Risk components must never access infrastructure directly.

---

## models.py

Purpose:

Define all Risk Framework domain models.

Examples:

RiskDecision

RiskDecisionType

RiskViolation

RiskResult

PositionSizing

RiskMetadata

These models should remain immutable.

No exchange-specific fields.

---

## interfaces.py

Purpose:

Define Risk Framework interfaces.

Examples:

RiskEngine

RiskManager

RiskRule

RiskValidator

RiskPolicy

No implementations.

Only Protocols or Abstract Base Classes.

---

## rules.py

Purpose:

Provide the abstract base class for every future risk rule.

Examples of future rules:

- Maximum Position Size
- Daily Loss Limit
- Maximum Exposure
- Maximum Drawdown
- Maximum Concurrent Positions
- Leverage Limits
- Symbol Restrictions

Do not implement these rules.

Only implement the reusable framework.

---

## validator.py

Purpose:

Coordinate execution of risk rules.

Responsibilities:

- Execute enabled rules
- Collect violations
- Produce RiskResult

The validator never executes trades.

The validator never modifies positions.

---

## manager.py

Purpose:

Coordinate Risk Framework execution.

Responsibilities:

Receive RiskContext

Invoke RiskValidator

Produce RiskDecision

Publish Risk events

Return RiskResult

The manager never contains rule logic.

---

## engine.py

Purpose:

Provide the public RiskEngine.

Responsibilities:

Coordinate the complete risk evaluation process.

Integrate with:

- Trading Engine
- Strategy Framework
- Event Bus
- Dependency Injection

The RiskEngine must never execute trades.

---

## events.py

Purpose:

Define Risk Framework events.

Examples:

RiskEvaluationStarted

RiskEvaluationCompleted

RiskRulePassed

RiskRuleFailed

RiskDecisionApproved

RiskDecisionRejected

RiskEngineStarted

RiskEngineStopped

Every event must inherit from the existing Event base class.

---

## exceptions.py

Purpose:

Contain Risk Framework exceptions.

Examples:

RiskError

RiskValidationError

RiskRuleError

RiskEngineError

InvalidRiskContext

DuplicateRiskRule

No handling logic.

Only exception definitions.

---

# Design Constraints

The Risk Framework must NOT:

Implement trading strategies

Execute trades

Manage portfolios

Persist data

Access exchanges

Read Market Data Cache directly

Calculate technical indicators

Contain exchange-specific logic

Everything must remain framework-only.
# Dependency Injection

The Risk Framework must reuse the existing Dependency Injection container.

Do not instantiate dependencies manually.

All components must receive dependencies through constructor injection.

The Risk Engine should depend only on abstractions.

Dependencies should include:

- EventBus
- LoggerFactory
- TradingEngine
- StrategyManager
- RiskValidator
- RiskPolicy

Future dependencies should also be injectable:

- PortfolioManager
- OrderManager
- PositionService
- NotificationService
- MetricsCollector

Everything must be resolved through the existing Dependency Injection container.

---

# Event Driven Architecture

Reuse the existing Event Bus.

Do not modify the Event Bus.

The Risk Framework publishes only risk-related events.

Examples:

RiskEvaluationStarted

RiskEvaluationCompleted

RiskRulePassed

RiskRuleFailed

RiskDecisionApproved

RiskDecisionRejected

RiskEngineStarted

RiskEngineStopped

RiskErrorOccurred

Do not publish:

Orders

Trades

Portfolio updates

Strategy events

Execution events

Every event must inherit from the existing Event base class.

---

# Risk Evaluation Flow

The Risk Framework should process signals in the following order.

Trading Signal

↓

Risk Context

↓

Risk Validator

↓

Enabled Risk Rules

↓

Risk Result

↓

Risk Decision

↓

Risk Event

↓

Event Bus

↓

Order Manager (future)

Each stage has one responsibility.

No stage should bypass another.

---

# Risk Validator

The validator coordinates rule execution.

Responsibilities:

Receive RiskContext

Retrieve enabled rules

Execute each rule

Collect violations

Produce RiskResult

Return RiskDecision

The validator never:

Executes trades

Modifies positions

Publishes orders

Calculates indicators

Contains strategy logic

---

# Risk Rules

Each rule represents one independent validation.

Future examples include:

Maximum Position Size

Maximum Exposure

Daily Loss Limit

Maximum Drawdown

Maximum Concurrent Positions

Symbol Restrictions

Trading Hours

Leverage Limits

Margin Limits

Only the reusable framework should be implemented.

No actual trading rules should be implemented in this task.

---

# Risk Decision

Risk decisions represent approval status only.

Examples:

APPROVED

REJECTED

WARNING

Every decision should include:

Decision ID

Decision Type

Timestamp

Triggered Rules

Violations

Metadata

Decisions must be immutable.

They never execute trades.

---

# Logging

Reuse the existing LoggerFactory.

Log only framework events.

Examples:

Risk evaluation started

Risk evaluation completed

Risk rule passed

Risk rule failed

Decision approved

Decision rejected

Framework errors

Use structured logging.

Correlation IDs must continue functioning.

Risk rules themselves should avoid excessive logging.

---

# Error Handling

Failures inside one risk rule must not stop the framework.

If one rule fails:

Log the error.

Publish RiskErrorOccurred.

Continue evaluating remaining rules.

The Risk Framework must always produce a RiskResult.

---

# Thread Safety

Risk evaluation should support concurrent execution.

Risk rules must remain stateless.

The framework should support future parallel rule evaluation.

Do not manually create unmanaged threads.

---

# Testing Requirements

Reuse the existing testing framework.

Required unit tests:

RiskEngine

RiskManager

RiskValidator

RiskContext

RiskDecision

RiskRule

Risk Events

Exceptions

Dependency Injection registration

Required integration tests:

Strategy Framework → Risk Engine

Risk Validator → Rules

Risk Manager → EventBus

Risk Decision Flow

Use fake risk rules.

Do not implement actual trading rules.

Avoid timing-based assertions.

Do not use sleep().

All tests must be deterministic.

---

# Constraints

The Risk Framework must NOT:

Implement trading strategies

Implement technical indicators

Execute trades

Manage portfolios

Persist data

Access exchanges

Read Market Data Cache directly

Modify Trading Signals

Calculate indicators

Contain exchange-specific logic

Instantiate dependencies manually

Everything must remain framework-only.

---

# Future Extension Points

The framework should support future implementation of:

Maximum Position Size Rule

Maximum Exposure Rule

Daily Loss Rule

Drawdown Rule

Margin Rule

Leverage Rule

Sector Exposure Rule

Time-Based Rule

Portfolio Correlation Rule

AI Risk Rule

Machine Learning Risk Rule

Composite Risk Policies

without modifying the Risk Framework.
# Expected Output

After completing Task 14, provide a comprehensive architectural explanation.

Do not simply list files.

Explain the architecture and design decisions.

The explanation must include the following sections.

---

# 1. Architecture Overview

Explain:

- Why the Risk Framework exists.
- Why it is independent of strategies.
- Why it is separate from the Order Manager.
- Why it contains no exchange-specific logic.

Describe how it integrates with the AI Trading Operating System.

---

# 2. Risk Framework

Explain:

Why the framework exists.

Describe the responsibilities of:

- Risk Engine
- Risk Manager
- Risk Validator
- Risk Rules
- Risk Context

Explain how they collaborate.

---

# 3. Risk Context

Explain:

Why every evaluation receives a RiskContext.

Describe:

- Trading Signal
- Market Snapshot
- Current Position
- Exposure
- Account Balance
- Available Capital
- Open Orders
- Exchange
- Symbol
- Timeframe
- Timestamp
- Metadata

Explain why risk rules must never access infrastructure directly.

---

# 4. Risk Decisions

Explain:

Why the Risk Framework produces RiskDecision objects instead of executing trades.

Describe:

- Decision ID
- Decision Type
- Triggered Rules
- Violations
- Timestamp
- Metadata

Explain why decisions remain immutable.

Explain why decisions represent approval rather than execution.

---

# 5. Risk Validator

Explain:

How the validator coordinates rule execution.

Describe:

RiskContext

↓

Enabled Rules

↓

Violations

↓

RiskResult

↓

RiskDecision

Explain why the validator never contains rule logic.

---

# 6. Risk Rules

Explain:

Why every rule is independent.

Describe how future rules can be added without modifying the Risk Framework.

Examples:

- Maximum Position Size
- Daily Loss
- Maximum Exposure
- Maximum Drawdown
- Margin Limits
- Leverage Limits

Explain why rules remain stateless.

---

# 7. Dependency Injection

Explain:

How the Risk Framework reuses the existing Dependency Injection container.

Describe:

- Constructor Injection
- Validator Injection
- Event Bus Injection
- Logger Injection
- Trading Engine Injection

Explain why future rules can integrate without modifying the framework.

---

# 8. Event Driven Architecture

Explain:

How the Risk Framework integrates with the Event Bus.

Describe:

- RiskEvaluationStarted
- RiskEvaluationCompleted
- RiskRulePassed
- RiskRuleFailed
- RiskDecisionApproved
- RiskDecisionRejected
- RiskErrorOccurred

Explain why the Risk Framework never communicates directly with the Order Manager.

---

# 9. Logging

Explain:

How LoggerFactory is reused.

Describe:

- Risk evaluation logging
- Rule execution logging
- Decision logging
- Framework errors
- Structured logging
- Correlation IDs

Explain why rules should avoid excessive logging.

---

# 10. Error Handling

Explain:

How failures are isolated.

Describe:

- Rule failure
- Framework recovery
- Remaining rule execution
- RiskErrorOccurred event

Explain why one failed rule should never stop the Risk Framework.

---

# 11. Future Extension

Explain how future risk rules can integrate without modifying the Risk Framework.

Examples:

- Maximum Position Size
- Daily Loss
- Drawdown
- Portfolio Correlation
- AI Risk Rules
- Machine Learning Risk Rules
- Composite Policies

without modifying the Risk Framework.

---

# Implementation Summary

Provide a concise summary including:

Files populated

Classes added

Interfaces added

Events added

Risk models implemented

Dependency Injection registrations

Framework components

Tests created

No unrelated modules modified

---

# Acceptance Criteria

Task 14 is complete only if all of the following are satisfied.

✓ Existing infrastructure reused

✓ No duplicate implementations

✓ Risk-independent architecture

✓ Dependency Injection used

✓ Event Bus integrated

✓ LoggerFactory reused

✓ Trading Engine integration completed

✓ Strategy Framework integration completed

✓ Risk Engine implemented

✓ Risk Manager implemented

✓ Risk Validator implemented

✓ Risk Context implemented

✓ Risk Decisions implemented

✓ Thread-safe rule execution

✓ Framework supports future rules

✓ Unit tests implemented

✓ Integration tests implemented

✓ Existing tests continue to pass

✓ No unrelated modules modified

---

# Files That Must Not Be Modified

Unless absolutely required for integration, do not modify:

core/

events/

database/

market_data/

strategies/

trading/

adapters/

models/

Reuse existing infrastructure exactly as implemented.

If an existing module must be modified for integration, explain why before making the change.

---

# Stop Condition

Stop immediately after Task 14 is complete.

Do not begin Task 15.

Do not implement:

- Order Manager
- Portfolio Manager
- Exchange Connectivity
- Paper Trading
- Backtesting
- AI Risk Rules
- Notification System

Only implement the Risk Framework.

End the response with:

"Task 14 complete. Standing by for review."