# PROJECT CONTEXT

Project: AI Trading Operating System

Completed

- Exchange Interface
- Domain Models
- Event System

Architecture

Use Dependency Injection.

Shared services must be managed by a DI Container.

---

# CURRENT TASK

Task 7 – Dependency Injection Container

## Objective

Build a lightweight Dependency Injection Container.

Create only:

core/
    __init__.py
    container.py
    registry.py
    interfaces.py
    lifetime.py

Requirements

Python 3.12

Type hints everywhere

No external libraries

Support:

- Service registration
- Service resolution
- Singleton lifetime
- Constructor injection
- Generic typing

Do not modify existing files.

Do not create trading logic.

Do not create Binance code.

Stop after Task 7.

---

# OUTPUT

Explain:

1. Why Dependency Injection improves architecture.
2. Why Singleton is appropriate for EventBus, Logger and Config.
3. How future services will resolve dependencies through the container.