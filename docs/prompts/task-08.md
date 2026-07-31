# PROJECT CONTEXT

Project: AI Trading Operating System

Completed

- Exchange Interface
- Domain Models
- Event System
- Dependency Injection

Architecture

Logging must be infrastructure, not business logic.

Components should not be responsible for formatting or routing logs.

The logging system must integrate cleanly with the existing Event Bus and Dependency Injection container.

---

# CURRENT TASK

Task 8 – Logging Infrastructure

## Objective

Build a structured logging system.

Reuse the existing `core/logging.py` if present.

Do not create duplicate logging implementations.

Requirements

- Python 3.12
- Standard library only
- Structured logging
- Log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Console handler
- File handler
- Logger registration through the DI container
- Design for future Correlation ID support
- Compatible with Event-Driven Architecture

Do not add trading-specific logging.

Do not modify unrelated modules.

Stop after Task 8.

---

# OUTPUT

Explain:

1. Why structured logging is better than print().
2. How the logger integrates with the Event Bus.
3. How Dependency Injection manages the logger.
4. How Correlation IDs will improve debugging in future.