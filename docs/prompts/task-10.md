# Project Context

Project: AI Trading Operating System

Sprint 1 – Core Infrastructure

Completed:

- Exchange Interface
- Domain Models
- Event Bus
- Dependency Injection
- Logging Infrastructure
- Repository Pattern

---

# Current Task

Task 10 – Testing Framework

## Objective

Review the existing project structure before implementing anything.

The project should gain a professional testing framework that supports:

- Unit Tests
- Integration Tests
- Fake implementations
- Dependency Injection
- Event-Driven Architecture

Do not create duplicate testing utilities.

---

# Architecture Review

Before writing code:

Review the existing project.

Identify:

- existing tests
- testing utilities
- fixtures
- helper modules
- fake implementations
- pytest configuration
- unittest configuration

Explain:

1. What already exists.
2. What should be reused.
3. What should be extended.
4. What should remain unchanged.

Present an implementation plan before making changes.

---

# Implementation Requirements

Python 3.12

Use only the Python standard library.

Prefer unittest and unittest.mock.

Do not introduce third-party testing libraries.

Create or extend:

- unit test structure
- integration test structure
- reusable fake implementations
- shared test utilities
- sample model factories

Repository tests should use fake repositories.

Logging tests should use fake loggers.

Event Bus tests should use fake subscribers.

Dependency Injection tests should verify constructor injection.

Integration tests should verify collaboration between:

- Persistence Service
- Repository
- Logger

Keep all tests deterministic.

Avoid sleep() or timing-based assertions.

---

# Constraints

Do not:

- call real exchanges
- call external APIs
- access production databases
- modify unrelated modules
- duplicate existing utilities

---

# Expected Output

Explain:

1. Test architecture.
2. Unit vs Integration testing.
3. Why fake implementations are used.
4. How Dependency Injection improves testing.
5. How Event Bus testing works.
6. How Logging is verified.
7. How Repository behavior is verified.

---

# Stop Condition

Stop immediately after completing Task 10.