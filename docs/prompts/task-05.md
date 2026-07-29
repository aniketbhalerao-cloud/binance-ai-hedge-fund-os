# PROJECT CONTEXT

Project: AI Trading Operating System

Completed:
- Task 1: Project Structure
- Task 2: Configuration
- Task 3: Documentation
- Task 4: Exchange Interface

Architecture Decision:
The platform is exchange-agnostic. Business models must never depend on a broker or exchange.

---

# CURRENT TASK

Task 5 – Domain Models

## Objective

Create the core business models for the Trading Operating System.

Create ONLY:

models/
    __init__.py
    order.py
    trade.py
    portfolio.py
    position.py
    account.py
    signal.py

Requirements:

- Python 3.12
- dataclasses
- Decimal for prices and quantities
- Enum where appropriate
- Type hints everywhere
- Comprehensive docstrings
- Immutable (`frozen=True`) where appropriate
- No database code
- No API calls
- No logging
- No exchange-specific fields
- No business logic beyond simple validation

Do NOT modify existing files.

Stop after Task 5.

---

# OUTPUT

Explain:

1. Why domain models are important.
2. Why they are exchange-independent.
3. How the Trading Engine, Risk Manager and Exchange Adapter will all share the same models.