# PROJECT CONTEXT

Project: AI Trading Operating System

Completed

- Sprint 0 Foundation
- Exchange Interface
- Domain Models

Architecture Decision

The system uses Event-Driven Architecture.

Components must never communicate directly when an event can be used.

All communication flows through the Event Bus.

---

# CURRENT TASK

Task 6 – Event System

## Objective

Build a generic asynchronous Event Bus.

Create only:

events/
    __init__.py
    base.py
    bus.py
    publisher.py
    subscriber.py
    events.py

Requirements

Python 3.12

Use asyncio

Use dataclasses

Type hints everywhere

No external libraries

Support:

- Event publishing
- Event subscription
- Multiple subscribers
- Asynchronous dispatch
- Event metadata (timestamp, event_id)

The Event Bus must not contain trading logic.

Do not create Binance code.

Do not create AI code.

Do not create Dashboard code.

Do not modify existing files.

Stop after Task 6.

---

# OUTPUT

Explain:

1. Why Event-Driven Architecture scales better.
2. Why the Event Bus should remain generic.
3. How Market Data, Strategy, Risk Manager, and Dashboard will communicate through it.