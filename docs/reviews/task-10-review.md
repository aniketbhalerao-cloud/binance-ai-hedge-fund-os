# Task 10 Review — Testing Framework

**Sprint:** 1 – Core Infrastructure
**Scope:** Establish a professional, standard-library testing framework (unit +
integration) with reusable support utilities. Documentation-only review; no
source code was modified.

---

## 1. Architecture Review (performed before implementation)

Before writing any tests, the existing project was inventoried:

- `tests/` contained only `tests/__init__.py` (a docstring stub) — **no** tests,
  fixtures, fakes, factories, helpers, or `conftest`.
- **No** `unittest` configuration existed; the only config was
  `[tool.pytest.ini_options] testpaths = ["tests"]` in `pyproject.toml`.
- Apparent "fake/factory" matches in the source tree were incidental words
  (e.g. `LoggerFactory`, `_make_formatter`) — not test utilities.

**Conclusions:**

1. **What exists:** an empty `tests` package + a pytest `testpaths` setting.
2. **Reuse:** the production modules under test — `ServiceContainer` (DI),
   `models`, `events` (Event Bus + `Subscriber`), `database` (repositories +
   `PersistenceService`), and `core.logging`.
3. **Extend:** the empty `tests/` package into a real framework.
4. **Unchanged:** every production module, `pyproject.toml`, and all unrelated
   code. Work was confined to `tests/`.

Because no test utilities existed, nothing was duplicated — the framework was
built fresh using only the standard library.

---

## 2. Testing Framework Design

A three-layer structure:

```
tests/
  support/            # reusable framework: factories + fakes
    __init__.py
    factories.py
    fakes.py
  unit/               # one component in isolation, using fakes
    __init__.py
    test_models.py
    test_container.py
    test_event_bus.py
    test_repositories.py
    test_logging.py
    test_persistence_service.py
  integration/        # real components wired via the real DI container
    __init__.py
    test_persistence_flow.py
```

Design rules: tests depend on production code (never the reverse); all tests are
deterministic; no real exchange, external API, or database is touched.

---

## 3. Support Layer (factories + fakes)

**Factories (`tests/support/factories.py`)** — deterministic builders
`make_order`, `make_trade`, `make_position` with sensible defaults and per-call
overrides. Identifiers come from a monotonic counter for reproducibility;
timestamps are left to model defaults and are not asserted upon.

**Fakes (`tests/support/fakes.py`)** — standard-library test doubles:

- `FakeOrderRepository`, `FakeTradeRepository`, `FakePositionRepository` — dict
  backed, honour the `Repository` contract, and **record every call** (spy) via
  a shared `_RecordingRepository` base, enabling interaction assertions.
- `FakeSubscriber` — an `events.subscriber.Subscriber` that records received
  events.
- `FakeLoggerFactory` / `FakeLogger` — duck-typed stand-ins for
  `core.logging.LoggerFactory`, capturing log calls as
  `(level, message, extra)` tuples in memory.

None perform I/O, keeping every test hermetic and deterministic.

---

## 4. Unit Test Coverage

- **Models** (`test_models.py`) — validation (non-positive quantity, limit order
  without price, non-positive trade price, negative position quantity),
  `Decimal` money types, and frozen immutability.
- **DI container** (`test_container.py`) — constructor injection, shared
  singletons, `create()` without registration, `KeyError` for unregistered
  dependencies, `register_instance` identity.
- **Event Bus** (`test_event_bus.py`) — single/multiple subscribers, base-type
  (hierarchy) routing, unsubscribe, no-subscriber no-op.
- **Repositories** (`test_repositories.py`) — full contract via fakes.
- **Logging** (`test_logging.py`) — fake logger capture; real `JsonFormatter`
  structured output and correlation ID.
- **Persistence service** (`test_persistence_service.py`) — delegation to fake
  repositories, silent behaviour without a logger, and logging via an injected
  fake logger.

---

## 5. Integration Test Coverage

`test_persistence_flow.py` wires the **real** `ServiceContainer` and the **real**
in-memory repositories, with a `FakeLoggerFactory` registered as the
`LoggerFactory`:

- default wiring persists through the real repositories resolved from the
  container;
- `PersistenceService` + `Repository` + `Logger` collaborate — the entity is
  stored *and* the operation is logged;
- `PersistenceService` resolves as a singleton.

This exercises collaboration across persistence, DI, and logging without any
external dependency.

---

## 6. Deterministic Async Testing

Event Bus tests use `unittest.IsolatedAsyncioTestCase` and `await bus.publish(...)`
directly, asserting on recorded state afterwards. There are **no** `sleep()`
calls and **no** timing-based assertions, so async behaviour is verified
deterministically.

---

## 7. Dependency Injection Testing

Constructor injection is validated directly: registering a leaf dependency and a
dependent class and resolving the dependent proves the container builds the
graph, shares singletons, and fails loudly (`KeyError`) on missing
registrations. DI also makes every other test simpler — collaborators are passed
in as fakes, with no global state to patch.

---

## 8. Event Bus Testing

The real bus is driven with `FakeSubscriber` doubles. Tests confirm delivery to
one and many subscribers, that a base-type subscription receives subclass events
(type-hierarchy routing), that `unsubscribe()` stops delivery, and that
publishing with no subscribers is a safe no-op.

---

## 9. Repository Contract Testing

The fake repositories implement the same `database.interfaces.Repository`
contract as the production in-memory repositories, so the repository tests are
effectively **contract tests**: add/get, missing-key `None`, replace-by-key,
`remove` return semantics, `list_by_symbol` filtering, `clear`, and symbol-keyed
positions. Any future SQLite/PostgreSQL implementation must satisfy the same
assertions.

---

## 10. Logging Verification

Two complementary approaches: the **fake logger** asserts that a component emits
the expected calls and structured `extra` fields without configuring real
handlers; and the **real `JsonFormatter`** is checked with an in-memory
`logging.Handler` to confirm JSON structure and correlation-ID capture.

---

## 11. `unittest`-only Implementation

The framework uses only the Python 3.12 standard library — `unittest`,
`unittest.IsolatedAsyncioTestCase`, and in-memory `logging` handlers. No
third-party testing libraries were introduced. The suite is run with:

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -t .
```

---

## 12. Result

**35 tests passing** (`Ran 35 tests in ~0.01s — OK`), deterministic and
hermetic. No production source code was modified; all additions live under
`tests/`.
