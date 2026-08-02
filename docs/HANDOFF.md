# Binance AI Hedge Fund OS — Project Handoff

> Handoff doc for continuing this build in a fresh session. Read this top-to-bottom, then open the relevant `docs/prompts/task-NN.md` for the next task.

---

## 1. Project Overview

**Name:** `binance-ai-hedge-fund-os`
**Goal:** An institutional-grade, modular, event-driven **AI trading operating system** for Binance (Spot). Built as a layered set of independent **frameworks**, each added in its own numbered task, all wired together through a single Dependency-Injection container and a shared async Event Bus.

**Status:** Sprint 3 in progress. Tasks **1–20 complete**. **215 tests passing.** No known bugs.

**Guiding principles:** SOLID, Clean Architecture, Dependency Inversion, exchange-independence, Open/Closed (new capabilities plug in without modifying existing frameworks), immutable domain models, thread-safe stateless components, framework-only (no business/trading logic leaks between layers).

**The processing spine (data flow):**
```
Market Data → Strategy (signals) → Risk (approve/reject) → Order Management (order request)
→ Execution (coordinate) → Exchange Adapters (route) → adapters/binance (submit)
→ Portfolio (account: holdings/cash/valuation) → Positions (per-position lifecycle)
```
Everything communicates through the **Event Bus**; every layer is resolved through the **DI container**. The **Trading Engine** owns application start/stop lifecycle.

---

## 2. Tech Stack & Dependencies

- **Python 3.12** (project target; `requires-python == 3.12.*`). NOTE: host machine default `python3` is 3.14 — tests currently run fine under it, but use `uv` (3.12) for parity.
- **Package manager:** `uv`.
- **Runtime dependencies** (only these — keep it minimal):
  - `pydantic>=2.7`, `pydantic-settings>=2.3`, `python-dotenv>=1.0` (used by `config/` only).
- **Dev dependencies:** `pytest>=8.0`, `ruff>=0.6`, `mypy>=1.11`.
- **Tests use the stdlib `unittest` only** — NOT pytest. No third-party test libs. No network. No `sleep()`.
- The Binance adapter (Task 18) uses **stdlib only**: `hmac`/`hashlib` (HMAC-SHA256 signing), `urllib` (default HTTP transport). REST/WebSocket transports are **injectable abstractions** — tests inject fakes; no live network anywhere.

**Run the whole suite:**
```bash
cd ~/binance-ai-hedge-fund-os
PYTHONPATH=. python3 -m unittest discover -s tests -t .
```
(Or via `uv`/Makefile: `make test`.)

---

## 3. Folder Structure (packages with code shown; `count` = .py files)

```
binance-ai-hedge-fund-os/
├── core/            (8)  DI container, registry, interfaces, lifetime, logging, exceptions, constants
├── config/          (5)  pydantic-settings config system (settings/environment/validators/constants)
├── events/          (6)  async Event Bus: base Event, bus, publisher, subscriber, system events
├── models/          (8)  shared domain models: Order/Trade/Position/Portfolio/Account/Signal + enums
├── database/        (5)  Repository pattern + PersistenceService (in-memory) + DI registration
├── adapters/        (19) adapters/interfaces.py (generic ExchangeInterface, Task 4)
│   └── binance/     (18) Binance Spot Adapter (Task 18): auth/signer/rest/websocket/connection/
│                         translator/parser/validator/config/models/events/errors/adapter/registry
├── trading/         (7)  Trading Engine (Task 11): engine/coordinator/lifecycle/state/interfaces/exceptions
├── market_data/     (9)  Market Data Framework (Task 12): provider/normalizer/cache/service/events/…
├── strategies/      (10) Strategy Framework (Task 13): base/manager/registry/factory/context/signals/…
├── risk/            (10) Risk Framework (Task 14): engine/manager/validator/rules/models/context/…
├── order_management/(13) Order Management (Task 15): factory/validator/routing/manager/engine/orders/…
├── execution/       (13) Execution Framework (Task 16): executor/validator/routing/lifecycle/manager/…
├── exchange_adapters/(15) Exchange Adapter Framework (Task 17): adapter/auth/connection/registry/…
├── portfolio/       (15) Portfolio Management (Task 19): holdings(accounting)/cash/valuation/allocation/…
├── positions/       (15) Position Management (Task 20): tracker/lifecycle/calculator/history/metrics/…
├── tests/           (42) unit/ + integration/ + support/ (fakes & factories)
├── docs/
│   ├── prompts/          task-01.md … task-20.md (the source-of-truth specs)
│   ├── reviews/          task-10-review.md
│   ├── architecture/     roadmap.md (+ empty agents/workflows/database/coding-standards/decisions.md)
│   └── HANDOFF.md         ← this file
├── pyproject.toml, Makefile, docker-compose.yml, docker/Dockerfile, .env.example, README, LICENSE
└── EMPTY SCAFFOLD DIRS (placeholders, not yet implemented):
    agents/ api/ app/ dashboard/ backtesting/ simulation/ monitoring/ memory/
    repositories/ services/ schemas/ scripts/ workflows/ utils/ data/
```

---

## 4. Completed Tasks (1–20)

| Task | Deliverable | Package |
|------|-------------|---------|
| 1 | Project scaffolding (dirs, pyproject, Docker, Makefile, LICENSE) | root |
| 2 | Configuration system (pydantic-settings, per-section Settings, `get_settings()` cached) | `config/` |
| 3 | Documentation structure | `docs/` |
| 4 | Exchange **interface** abstraction (generic `ExchangeInterface`) | `adapters/interfaces.py` |
| 5 | Domain models (Order/Trade/Position/Portfolio/Account/Signal, `Decimal`, frozen) | `models/` |
| 6 | Event System (async `EventBus`, pub/sub, type-hierarchy routing) | `events/` |
| 7 | Dependency Injection container (singleton/transient lifetimes, **constructor injection**) | `core/` |
| 8 | Structured Logging (`LoggerFactory`, JSON/text, correlation IDs via ContextVar) | `core/logging.py` |
| 9 | Repository pattern + `PersistenceService` (in-memory repos, DI wiring) | `database/` |
| 10 | Testing framework (unittest, support fakes/factories, unit+integration) | `tests/` |
| 11 | **Trading Engine** (lifecycle FSM, coordinator, DI, publishes ServiceStarted/Stopped) | `trading/` |
| 12 | **Market Data Framework** (provider→normalizer→cache→events, replay-ready) | `market_data/` |
| 13 | **Strategy Framework** (BaseStrategy, registry, factory, manager, signals) | `strategies/` |
| 14 | **Risk Framework** (rules base, validator, policy, manager, engine) | `risk/` |
| 15 | **Order Management Framework** (factory/validator/router/manager/engine) | `order_management/` |
| 16 | **Execution Framework** (executor/validator/router/lifecycle/manager/engine) | `execution/` |
| 17 | **Exchange Adapter Framework** (auth/connection/validator/router/registry/adapter base) | `exchange_adapters/` |
| 18 | **Binance Spot Adapter** (HMAC signing, REST/WS clients over injectable transports) | `adapters/binance/` |
| 19 | **Portfolio Management Framework** (holdings/cash/valuation/allocation/performance) | `portfolio/` |
| 20 | **Position Management Framework** (tracker/lifecycle/calculator/history/metrics) | `positions/` |

---

## 5. Remaining / Next Tasks

Per the "Stop Condition" sections of the latest prompts, the roadmap continues with (specs not yet written — will arrive as `docs/prompts/task-21.md`, etc.):

- **Trade Lifecycle Framework**
- **Performance Analytics Framework** / Portfolio Analytics Dashboard
- **AI Decision Engine** (the CEO/Market/Strategy/Risk agents in `agents/` — currently an empty stub)
- Later roadmap (see `docs/architecture/roadmap.md`): Dashboard, Monitoring, Docker/K8s, CI/CD, Backtesting, Paper Trading, Learning/feedback loop.

Empty scaffold packages awaiting future tasks: `agents/ api/ app/ dashboard/ backtesting/ simulation/ monitoring/ memory/ repositories/ services/ schemas/ scripts/ workflows/ utils/ data/`.

**Next step:** wait for the user to say `Read docs/prompts/task-21.md`, then follow the standard workflow (§9).

---

## 6. Current Bugs / Known Issues

- **None known.** Full suite green: **215/215**.
- Minor cleanliness (non-blocking): `tests/unit/test_positions.py` has a small module-level `manager_update_safe` helper that could be inlined; a couple of intentionally-defensive `except Exception` blocks exist in transports/adapter. No functional impact.
- Host `python3` is 3.14 while project targets 3.12 — fine today, but run via `uv` for guaranteed parity.
- `ruff`/`mypy strict` are configured but **not run in CI** yet; code was written to their intent but a full lint/type pass hasn't been enforced.

---

## 7. Architecture Decisions & ADRs

Every framework (Tasks 11–20) follows the **same package blueprint** — this is the single most important thing to internalize:

```
<framework>/
  state.py        # Enum of lifecycle states + VALID_TRANSITIONS + can_transition()
  models.py       # immutable @dataclass(frozen, slots) value objects; Decimal for money
  exceptions.py   # <Framework>Error base + specific subclasses (definitions only)
  events.py       # events inheriting events.base.Event; @dataclass(frozen, slots, kw_only)
  context.py      # immutable input object for one pipeline run
  interfaces.py   # @runtime_checkable Protocols (the abstractions)
  <components>.py # stateless services (validator/router/calculator/…)
  registry.py     # thread-safe store (threading.Lock), never creates instances
  manager.py      # coordinator: atomic update under Lock, always returns a *Result,
                  #   isolates per-stage errors, publishes events AFTER a consistent update
  engine.py       # public entry point; start/stop; delegates to manager; holds optional
                  #   upstream-engine refs for integration (never drives them)
  __init__.py     # public exports + register_<framework>(container) DI helper
```

**ADR-001 — Event-driven, layered frameworks.** Each capability is an independent framework communicating only through the Event Bus and shared domain models. *Why:* loose coupling, independent testability, replaceability.

**ADR-002 — Dependency Injection everywhere; no manual instantiation.** `core.container.ServiceContainer` (singleton/transient + constructor injection). Each framework ships a `register_<x>(container)` helper. Concretes are bound to Protocol keys (Dependency Inversion). *Why:* swap implementations and inject fakes without touching consumers.

**ADR-003 — Immutable domain models with `Decimal`.** All models are `@dataclass(frozen=True, slots=True)`; money/quantities are `Decimal`; timestamps are timezone-aware UTC. State changes produce **new** objects. *Why:* no floating-point money drift, safe to log/publish/share, no accidental mutation.

**ADR-004 — Interfaces are Protocols; concretes are prefixed.** `interfaces.py` defines `@runtime_checkable` Protocols (e.g. `OrderValidator`); implementations are `Default*` / `InMemory*` to avoid name clashes. DI registers the concrete and aliases the Protocol to it.

**ADR-005 — Manager owns the workflow; components are single-responsibility.** The manager sequences stateless components (validator → … → result), computes the whole new state atomically under a `threading.Lock`, then publishes events. Components never call each other.

**ADR-006 — Always return a Result; never leak internal exceptions.** Every manager returns a `*Result` (SUCCESS/FAILED). Any internal failure is caught, translated to a framework exception, published as a `*ErrorOccurred` event, and returned as a FAILED result — partial updates never persist (integrity).

**ADR-007 — Exchange independence + adapter boundary.** Only `adapters/binance/` knows Binance. It translates standardized `ExchangeRequest` → Binance request and parses Binance responses → standardized `ExchangeResponse`. No broker-specific field, payload, or secret escapes the adapter.

**ADR-008 — Injectable transports; no forced network.** REST/WebSocket are `HttpTransport`/`StreamTransport` Protocols. Default stdlib HTTP transport for prod; fakes for tests. No live network in tests, no third-party HTTP/WS deps.

**ADR-009 — Security.** HMAC-SHA256 request signing (stdlib). API secret is `repr=False`, never logged/evented/exception'd; only masked forms are shown.

**ADR-010 — Tests: stdlib unittest, deterministic.** `IsolatedAsyncioTestCase` for async; shared fakes in `tests/support/`; no `sleep()`, no timing assertions, no network. One `*_fakes.py` support module per framework.

**ADR-011 — Reuse over duplication.** Downstream frameworks reuse upstream models (e.g. Positions reads `PortfolioResult.portfolio.ledger[-1]`; Order Mgmt reuses `models.OrderSide/OrderType/TimeInForce`). Prior frameworks are never modified.

---

## 8. Coding Standards & Conventions

- **Python 3.12**, `from __future__ import annotations` at top of every module, full type hints, PEP 8, comprehensive docstrings.
- **Frozen dataclasses** (`frozen=True, slots=True`; add `kw_only=True` for `Event` subclasses so subclasses can add required fields).
- **Money = `Decimal`**; **time = timezone-aware UTC** (`datetime.now(UTC)`).
- **Read-only mappings** for metadata (`types.MappingProxyType` in `__post_init__`).
- **Thread safety:** registries and managers guard mutable state with `threading.Lock`; stateless services (validators/routers/calculators/parsers/translators/normalizers) hold no mutable state.
- **DI helper pattern:** `register_<x>(container: Container)`: register `EventBus` on demand; `register_class(Protocol, Concrete)` for stateless singletons; `register_singleton(Concrete, builder)` + alias `register_singleton(Protocol, lambda r: r.resolve(Concrete))`; resolve `LoggerFactory`/upstream engines only `if resolver.has(...)`.
- **Events** publish only after a consistent state; names end in past-tense/`*Occurred`.
- **Logging:** `LoggerFactory.get_logger("<framework>.<component>")`, structured `extra={}`, correlation IDs preserved; never log secrets/sensitive financial detail.
- **Do NOT modify** `core/ events/ database/ models/ trading/ market_data/ strategies/ risk/ order_management/ execution/ exchange_adapters/ adapters/binance/ portfolio/` when doing a new task unless the prompt explicitly requires it — and if so, explain why first.

---

## 9. Standard Workflow for the Next Task (IMPORTANT — how each task is executed)

The user drives tasks by saying: **"Read docs/prompts/task-NN.md ... populate only the existing empty files ... stop after Task NN."** Reproduce this exact flow:

1. **Read** `docs/prompts/task-NN.md` fully (it is the source of truth: file list, components, DI deps, events, constraints, expected-output sections, acceptance criteria, stop condition).
2. **Architecture review first (no code):** inspect the target package (files already exist, empty) and confirm reuse targets; state what exists / reuse / extend / whether it would duplicate.
3. The target package **already exists with empty files** — **populate only those files**; do not create, rename, or move files; no new modules unless the prompt allows.
4. **You must `Read` each empty file before `Write`** (the tool requires it).
5. Follow the package blueprint (§7). Reuse `core/events/database/models` + all prior frameworks via DI. Keep it exchange-independent unless it's an adapter task.
6. Add tests: `tests/support/<framework>_fakes.py` (new), `tests/unit/test_<framework>.py`, `tests/integration/test_<framework>_flow.py`. Deterministic, stdlib unittest, `IsolatedAsyncioTestCase` for async, reuse `tests/support/fakes.py` (`FakeSubscriber`, `FakeLoggerFactory`).
7. **Run the full suite** and confirm all prior tests still pass:
   `PYTHONPATH=. python3 -m unittest discover -s tests -t .`
8. Provide the **Expected Output** sections the prompt asks for (architecture explanation, implementation summary, acceptance criteria), then end with the exact required sentence (e.g. `"Task NN complete. Standing by for review."`).
9. **Stop** — do not begin the next task.

Note on a past quirk: `docs/prompts/task-11.md` initially arrived empty and the user insisted "do not infer." If a prompt is empty, **stop and ask** for the spec.

---

## 10. Key DI Registration Entry Points (wire-up cheat sheet)

To assemble the whole system in one container (as the integration tests do):

```python
from core.container import ServiceContainer
from core.logging import register_logging          # or register_instance(LoggerFactory, ...)
from database.registration import register_persistence
from trading import register_trading_engine
from market_data import register_market_data        # needs a MarketDataProvider instance
from strategies import register_strategies
from risk import register_risk
from order_management import register_order_management
from execution import register_execution
from exchange_adapters import register_exchange_adapters
from adapters.binance import register_binance_adapter   # takes a BinanceConfig (+ optional transports)
from portfolio import register_portfolio
from positions import register_positions

c = ServiceContainer()
register_logging(c)                    # or a FakeLoggerFactory in tests
register_trading_engine(c)
register_market_data(c, provider=...)
register_strategies(c)
register_risk(c)
register_order_management(c)
register_execution(c)
register_exchange_adapters(c)
register_binance_adapter(c, BinanceConfig(api_key=..., secret_key=...), transport=...)
register_portfolio(c)
register_positions(c)
```
Every `register_*` registers `EventBus` on demand and injects `LoggerFactory` + upstream engines only if already present, so **order is forgiving** but the above (infra → engines) is the canonical order.

---

## 11. Reusable Public Types (most-used across layers)

- **Events:** `events.base.Event`, `events.bus.EventBus`, `events.EventPublisher`, `Subscriber`, `Subscription`.
- **DI:** `core.container.ServiceContainer`, `core.interfaces.{Container,Resolver,Lifetime}`.
- **Logging:** `core.logging.{LoggerFactory, register_logging, correlation_id_scope}`.
- **Domain:** `models.{Order,Trade,Position,Portfolio,Account,Signal,OrderSide,OrderType,TimeInForce}`.
- **Persistence:** `database.{PersistenceService, register_persistence, OrderRepository, ...}`.
- **Cross-framework results (the pipeline handoffs):**
  `strategies.TradingSignal` → `risk.RiskDecision` → `order_management.OrderResult`
  → `execution.ExecutionResult` → `exchange_adapters.ExchangeResult`
  → `portfolio.PortfolioResult` → `positions.PositionResult`.

---

## 12. Important Prompts / Where the Specs Live

- **All task specs:** `docs/prompts/task-01.md … task-20.md` — each is authoritative and self-contained (context, files, components, DI, events, constraints, expected output, acceptance criteria, stop condition).
- **Roadmap (7 phases):** `docs/architecture/roadmap.md`.
- **A completed review example:** `docs/reviews/task-10-review.md`.
- The user typically pastes a wrapper of 10–12 numbered rules ("populate only existing files, reuse infra, DI throughout, don't modify prior frameworks, stop after Task NN") plus `Read docs/prompts/task-NN.md`. Follow both the wrapper and the prompt.

---

## 13. Quick-Start for the Next Chat

1. `cd ~/binance-ai-hedge-fund-os`
2. Confirm green baseline: `PYTHONPATH=. python3 -m unittest discover -s tests -t .` → expect `Ran 215 tests ... OK`.
3. Wait for the user's `Read docs/prompts/task-21.md` (or next). If the prompt file is empty, ask for the spec — do not infer.
4. Execute using the **Standard Workflow (§9)** and the **package blueprint (§7)**.
5. Keep money `Decimal`, models frozen, everything DI-wired, tests deterministic, and **do not modify existing frameworks**.
```
```
```

*Last updated: after Task 20. 215 tests passing. No known bugs.*
