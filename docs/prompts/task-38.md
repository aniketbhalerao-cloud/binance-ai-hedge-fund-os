# Task 38 — Application Bootstrap & Dry-Run Runtime Composition

---

# Sprint 18

## Framework

Application Bootstrap & Dry-Run Runtime Composition (Composition Root)

---

# Objective

Design and implement the application's **composition root**: the one place in the codebase permitted to import across every completed framework, build a disposable candidate `ServiceContainer`, register every known framework into it, and validate — without ever starting anything or retaining what it built — that the resulting object graph is sound.

Task 38 is **dry-run integration only**. Every bootstrap run creates its own fresh, throwaway container, registers into that container alone, performs required-service resolution checks against it alone, and then discards it — success or failure. Nothing this task builds is ever returned, cached, or handed to a caller as a live, usable container. A future task builds and retains the real runtime container; Task 38 only proves the graph *would* wire correctly.

The framework consumes an explicit, immutable `ComponentManifest` describing the declared components (one entry per framework) and their dependency edges, deterministically validates and orders that graph, executes registration and resolution checks against a disposable candidate container in that order, and produces four immutable artifacts: `BootstrapPlan`, `PreflightReport`, `RuntimeSnapshot`, and `LifecyclePlan`.

**Why `app/` is the one exception to import isolation:** every prior framework is forbidden from importing another framework directly — that is the entire point of registering everything through `core.container`. `app/` is the composition root that *performs* that wiring, so it is the only package permitted to import each framework's `register_<framework>` function. That permission is confined to `app/wiring.py`; no other module, in `app/` or elsewhere, gains it.

`COMPONENT_REGISTRARS` must cover **every** completed package that exposes a `register_<framework>` function — all 24 of them: `market_data`, `strategies`, `risk`, `order_management`, `execution`, `portfolio`, `positions`, `trades`, `performance`, `backtesting`, `paper_trading`, `agents`, `learning`, `optimization`, `monitoring`, `dashboard`, `notification`, `reporting`, `storage`, `scheduler`, `workers`, `memory`, `model_gateway`, `workflows`. `trading/` has no `register_trading` function and is excluded — there is nothing to wire.

**`app/main.py` is a safe, preflight-only entrypoint.** It runs the dry-run pipeline against a fresh disposable container and returns a success/failure status (exit code `0`/`1`). It never starts live mode, never starts a framework's engine, never trades, never performs inference, never makes a real network/database/Redis connection, never executes a workflow step, and never does background work.

The framework must never:

* retain, return, or leak the disposable candidate container it built — every run discards it, whether it succeeds or fails
* mutate a container it did not create for that run — there is no "caller-supplied shared container" input anywhere in this task
* call `.start()` on any framework's `Engine`, or call `WorkflowManager.compose()`, `ModelGatewayManager.invoke()`, `SchedulerManager.schedule()`, `WorkerManager.enqueue()`, or any other framework's manager/engine business method
* trigger an Agent, execute a trade, or perform inference
* resolve a constructor capable of I/O — only service keys on an explicit, safe allowlist (proven free of I/O in their constructors) are ever resolved; an unlisted key is rejected before any candidate container even exists, never resolved as a real client/adapter
* make a real network, database, or Redis connection, write a file, spawn a thread or process, or sleep
* let a credential, secret, API key, or URL userinfo/query value reach a model, event, error message, or log line — see "Configuration View"

---

# Architecture Requirements

* Clean Architecture
* Domain Driven Design
* SOLID Principles
* Immutable Models
* Dependency Injection (via plain, explicit constructor/parameter injection — no Protocol layer is introduced where exactly one implementation will ever exist)
* Thread Safety (nothing in this task is concurrent, but nothing it does is unsafe if called concurrently — every function is a pure or disposable-resource-scoped call, never shared mutable state)
* Deterministic Processing
* No Speculative Abstraction — this is a lean composition root, not a domain framework; see "Package Structure"

No shortcuts.

---

# Package Structure

Task 38 does **not** follow the 14-module domain-framework blueprint used by `storage/`, `scheduler/`, … `workflows/` — there is exactly one implementation of a composition root, so a `state.py`/`interfaces.py`/`events.py`/`registry.py`/`manager.py`/`engine.py`/`collector.py`/`dispatcher.py`/`metrics.py` split would be unrequested abstraction over nothing. Use exactly:

```text
app/
    __init__.py
    main.py
    models.py
    exceptions.py
    wiring.py
    planner.py
    preflight.py
    bootstrap.py

tests/
    app_fakes.py
    test_app_bootstrap.py
    test_app_flow.py
```

No additional files. Do not add `state.py`, `context.py`, `interfaces.py`, `events.py`, `collector.py`, `dispatcher.py`, `metrics.py`, `registry.py`, `manager.py`, or `engine.py` unless a specific requirement below cannot be met without one — none currently requires it.

* **`models.py`** — every immutable domain object (see "Models").
* **`exceptions.py`** — `BootstrapError`, `PlanningError`, `PreflightError`, `ConfigurationError`.
* **`wiring.py`** — the sanctioned cross-framework import site: the component registrar map, the safe service-key allowlist, and the configuration-view builder. See "Wiring & Safe Allowlists".
* **`planner.py`** — dependency validation and deterministic topological ordering. See "Deterministic Component Registration Ordering".
* **`preflight.py`** — the static service-key allowlist check (before any container exists) and the required-service resolution checks against the disposable candidate container. See "Preflight Resolution Checks".
* **`bootstrap.py`** — the single orchestrating function that ties planner → disposable container → wiring → preflight → artifacts together. See "Disposable Candidate Container".
* **`main.py`** — the safe CLI entrypoint. See "main.py".

---

# Models

All models are frozen dataclasses, `Decimal`-only for numeric domain values, `MappingProxyType` for metadata, and fully immutable.

No identifier or timestamp is ever generated *inside* a model or inside `planner.py`/`preflight.py`/`bootstrap.py` via `datetime.now()`, `datetime.utcnow()`, `uuid.uuid4()`, or any other non-deterministic source. Every identifier/timestamp that appears in an artifact is either supplied by the caller on `BootstrapContext`, or produced by an explicitly injected, swappable factory parameter (e.g. a `clock: Callable[[], datetime]`) — never called directly by name inside the deterministic pipeline.

Required models:

* `ComponentSpec` — one declared component: stable `component_id`, `priority: Decimal`, `required_service_keys: tuple[str, ...]`, `detail: str`, immutable `metadata`.
* `ComponentDependency` — `component_id` and the `depends_on` identifier, both scoped to the same manifest.
* `ComponentManifest` — the full declared graph: `components: tuple[ComponentSpec, ...]`, `dependencies: tuple[ComponentDependency, ...]`.
* `ConfigurationView` — the redacted, allowlisted subset of `Settings` (see "Configuration View"). Contains only scalar/collection values already proven non-sensitive; never a raw `Settings` reference.
* `BootstrapContext` — the deterministic input to a bootstrap run: `manifest: ComponentManifest`, `configuration: ConfigurationView`, `correlation_id: str`, `requested_at: datetime` (must be canonical UTC — timezone-aware with `utcoffset() == timedelta(0)`; `__post_init__` rejects a naive value, a `tzinfo` whose `utcoffset()` returns `None`, and any non-zero-offset value, all with `ConfigurationError`), `metadata`. Does **not** contain `Settings`, a container reference, or any callable.
* `BootstrapPlan` — the deterministic, resolved registration order: `entries: tuple[BootstrapPlanEntry, ...]`, each carrying `position`, `component_id`, `priority`, and canonicalized (lexical-ascending) `dependencies`.
* `PreflightEntry` — one component's resolution-check outcome: `component_id`, `service_key`, `resolved: bool`, `detail: str` (already redacted/safe — never a raw exception).
* `PreflightReport` — `entries: tuple[PreflightEntry, ...]`, `total_checks: int`, `passed_checks: int`, `failed_checks: int` (derived once at construction time, never recomputed elsewhere as a second source of truth).
* `RuntimeSnapshot` — an immutable, redacted view of what the disposable candidate container looked like for this run: which component ids registered, the `PreflightReport`, and the `ConfigurationView` used. Never a live container reference, never a resolved instance.
* `LifecyclePlan` — `start_order: tuple[str, ...]` (identical to `BootstrapPlan`'s resolved component-id order) and `stop_order: tuple[str, ...]` (its exact reverse). Declarative only — consumed by a future live-runtime task, never acted on here.
* `BootstrapResultStatus` — `SUCCESS`, `FAILED`.
* `BootstrapResult` — `status`, `plan: BootstrapPlan | None`, `preflight_report: PreflightReport | None`, `runtime_snapshot: RuntimeSnapshot | None`, `lifecycle_plan: LifecyclePlan | None`, `errors: tuple[str, ...]` (safe messages only).

---

# `ComponentSpec` & `ComponentDependency`

Represent the manifest's graph structure only.

`ComponentSpec` may contain a stable component identifier, priority, the component's `required_service_keys` (strings — see "Preflight Resolution Checks"), descriptive detail, and immutable metadata.

`ComponentDependency` may contain the dependent component identifier and the identifier it depends on; both must resolve to components within the same manifest.

Neither may ever contain a callable reference to a registrar/manager/engine, a network client, a database client, or credentials/API keys/secrets — the identifier-to-callable mapping lives only in `app/wiring.py`, never in model data.

---

# Wiring & Safe Allowlists (`app/wiring.py`)

This module is the one sanctioned place in the codebase permitted to import across frameworks. It holds three things and nothing else:

**1. `COMPONENT_REGISTRARS: Mapping[str, Callable[[Container], None]]`** — maps every one of the 24 known `component_id` strings listed in the Objective to that package's real `register_<framework>` function. `KNOWN_COMPONENT_IDS = frozenset(COMPONENT_REGISTRARS)` is exported for the planner to validate against. A `component_id` on a `ComponentManifest` that is not a key of `COMPONENT_REGISTRARS` is rejected by the planner as invalid — deterministically, before any container is created or any registration call is made.

**2. `SAFE_SERVICE_KEYS: Mapping[str, type]`** — maps a `required_service_keys` string (e.g. `"scheduler.manager"`, `"workflows.engine"`) to the actual interface/manager/engine type to resolve. Only types already proven to have I/O-free constructors — every completed framework's `Manager`/`Engine`/`Registry` abstraction, all of which only ever accept already-constructed collaborators (`EventBus`, `LoggerFactory`, other in-process objects) — are listed. **No real network client, database client, Redis client, or exchange adapter type is ever added to this allowlist, under any name.** If a component has no I/O-free service worth resolving, it simply contributes no entry to `SAFE_SERVICE_KEYS` and its `ComponentSpec.required_service_keys` must be empty — declaring a key that has no safe entry is a hard error, not a silent skip (see "Preflight Resolution Checks"). Where a dry-run check of an otherwise I/O-capable component is genuinely wanted, `wiring.py` may register an explicitly documented, deterministic no-I/O fake/wrapper type for it (e.g. a construction-only stand-in that performs no network/DB/Redis call) and list *that* type in `SAFE_SERVICE_KEYS` under its own key — never the real client/adapter type.

**3. `build_configuration_view(settings: Settings) -> ConfigurationView`** — the only function in the codebase that reads a real `Settings` object for this task's purposes; see "Configuration View".

**4. `build_default_manifest() -> ComponentManifest`** — one `ComponentSpec` per key in `COMPONENT_REGISTRARS` (all 24), zero declared dependencies (no completed framework's `register_<framework>` function requires another to already be registered), used by `main.py`'s default run.

---

# Configuration View

`build_configuration_view(settings)` copies only an explicit allowlist of fields already known to be free of secrets — application name/version/debug/timezone, environment, trading mode/base currency/symbols, dashboard enabled/host/port, monitoring enabled/metrics port, logging level/format, every risk fraction and `max_leverage`/`max_open_positions`, backtesting/simulation cost and sizing knobs, and `binance.testnet`. Unknown or unlisted fields are excluded by construction, not merely omitted from a hand-maintained list — the builder filters `Settings`' fields by name and rejects (never partially includes) any field whose name contains `key`, `secret`, `token`, `credential`, `password`, `url`, or `dsn`, as a second, mechanical layer of defence independent of the positive allowlist above. This blanket exclusion is why `binance.api_key`/`api_secret`, `ai.anthropic_api_key`/`openai_api_key`, `security.secret_key`/`api_token`, and every `*.url` field (`database.url`, `redis.url`, `binance.base_url`, `binance.ws_url`) are never copied, whether or not they happen to embed userinfo or query-string credentials — no URL is ever partially sanitized and included; it is excluded outright.

A credential, secret, API key, or URL userinfo/query value must never reach `BootstrapContext`, any model, any exception message, or any log line, at any point in this task.

`config.settings.get_settings()` (which itself calls `config.environment.load_environment()`) is the **sole** permitted read of external configuration state anywhere in this task — it reads environment variables and an optional `.env` file, both already validated/owned by `config/`, which this task does not modify. No other external I/O of any kind — no other file read, no file write, no network call, no database or Redis connection — happens anywhere in `app/`.

---

# Disposable Candidate Container

`bootstrap.py`'s orchestrating function takes `container_factory: Callable[[], Container]` as its only container-related parameter (defaulting to `ServiceContainer` where a caller does not supply one). **No function in this task accepts a container instance as a parameter anywhere** — a candidate is only ever obtained by calling the factory, never passed in directly. That absence of a container-accepting parameter is a structural fact this task's code and tests can prove.

`container_factory` additionally carries a **documented precondition**, not an enforced guarantee: each call must return a newly allocated container exclusive to that one bootstrap run — never one reused across calls, never one shared with or still reachable by the caller. `Callable[[], Container]` is just a function type; nothing in Python's type system, and nothing this task can do at runtime, verifies that precondition against a factory that is buggy or actively noncompliant (e.g. one that returns the same object on every call, or hands back a container the caller kept its own reference to). Task 38 trusts the precondition and is not responsible for enforcing it — a caller-supplied factory that violates it is a contract violation on the caller's side, not a defect in Task 38, and this spec does not claim otherwise.

What Task 38 itself does structurally guarantee, independent of the factory's compliance: whatever candidate a call to the factory returns is never returned to the caller, cached, pooled, or otherwise retained by anything in this task. It is registered into and resolved against, and then its last reference simply goes out of scope. `BootstrapResult` and every artifact it contains are built entirely from already-known plan/report data — never by inspecting or holding onto the container — so they are provably free of any container reference regardless of what the factory did.

Each run:

1. Plans the manifest (`planner.plan`) — validates the component graph (unknown component ids, uniqueness, dependency references, self-dependencies, cycles). If planning fails, `container_factory` is **never called**; return `BootstrapResult(status=FAILED, ...)` immediately.
2. Statically validates every declared `required_service_keys` entry across the plan against `wiring.SAFE_SERVICE_KEYS` (`preflight.validate_service_keys(plan)`) — this is the last check performed before any container exists. If it fails, `container_factory` is **never called**; return `BootstrapResult(status=FAILED, ...)` immediately.
3. Only once both of the above succeed does the run call `container_factory()` — **exactly once**, for the rest of that run, regardless of what happens next. A run that goes on to fail during registration or resolution still made exactly that one factory call; it never makes a second one, and it never retroactively counts as zero.
4. Registers each planned component into that candidate, in plan order, via `wiring.COMPONENT_REGISTRARS[component_id]`. Any exception during registration discards the candidate immediately (it is simply never referenced again) and returns `BootstrapResult(status=FAILED, ...)`.
5. Runs the actual preflight resolution pass (`preflight.run`) against that same candidate — every key it touches has already passed step 2's static check. Any exception discards the candidate and returns `BootstrapResult(status=FAILED, ...)`.
6. Builds the immutable `RuntimeSnapshot` and `LifecyclePlan` from the plan and preflight report — never from the candidate itself.
7. The candidate is discarded — its last reference goes out of scope at the end of the function. Nothing is cached, pooled, or returned.

On any failure at any step, the run leaves **zero accepted runtime state**: no candidate survives the call, no partial `RuntimeSnapshot` is ever constructed or returned, and `BootstrapResult.errors` carries only safe (already-redacted-input-derived) messages.

A future live-runtime task is responsible for building and retaining the real, long-lived container — that is explicitly out of scope here.

---

# Deterministic Component Registration Ordering

A bootstrap run has exactly one `ComponentManifest`, owning one dependency graph. `planner.plan(manifest)` resolves it using the following exact sequence:

1. Validate every `component_id` is a member of `wiring.KNOWN_COMPONENT_IDS` — an unknown component id is rejected deterministically, before any other validation or any container is created.
2. Validate all component identifiers are unique within the manifest.
3. Validate every dependency references an existing component within the same manifest.
4. Reject self-dependencies.
5. Reject cyclic dependency graphs.
6. Resolve components using deterministic topological ordering — a genuine dependency-aware Kahn's algorithm with a deterministic ready queue, never `sorted(components)`.
7. Among simultaneously-ready components, order by:
   a. component priority — higher first
   b. stable component identifier — lexical ascending
8. Identical immutable input must always produce identical `BootstrapPlan` ordering.

`BootstrapPlanEntry.dependencies` is canonicalized to lexical-ascending order, so equivalent graphs with differently ordered dependency declarations always produce identical plan entries.

No timestamps, randomness, dictionary/set iteration order, process state, network state, or external service state may influence ordering.

---

# Dependency Validation Rules

Components are treated as immutable graph nodes; dependencies are treated as immutable directed edges, scoped to the single `ComponentManifest`.

An unknown `component_id` (not present in `wiring.KNOWN_COMPONENT_IDS`) invalidates the manifest.

A component identifier that is not unique invalidates the manifest — it must not be silently deduplicated.

A dependency edge referencing a component identifier that does not exist invalidates the manifest.

A dependency edge whose `depends_on` equals its own `component_id` (a self-dependency) invalidates the manifest.

A dependency graph containing a cycle invalidates the manifest — no partial ordering may be returned.

Every validation failure is reported through `PlanningError`; none ever produces a partially ordered `BootstrapPlan`, and none ever results in a container being created.

---

# Component Registration Tie-Breaking

When two or more ready components could be registered next:

1. Compare component priority (higher preferred).
2. If equal, compare the stable component identifier lexically.

The framework must never use object identity, memory address, hash randomization, insertion order, current time, or random numbers as a tie-breaker.

---

# Preflight Resolution Checks (`app/preflight.py`)

`app/preflight.py` exposes two functions, deliberately run at two different points of the pipeline (see "Disposable Candidate Container") — the first is a static check with no container in scope; only the second ever touches the candidate.

**`validate_service_keys(plan: BootstrapPlan) -> None`** — runs *before* any candidate container exists. Preflight validates **only** the service keys a component actually declares on its `ComponentSpec.required_service_keys` — it never invents checks for keys nobody declared, and it never skips a declared key. For every component in the plan and every key it declares, raises `PreflightError` if that key is not present in `wiring.SAFE_SERVICE_KEYS`. Every declared key must exist in the allowlist; there is no third outcome — a key is either known-safe or a hard rejection, decided entirely from the plan and the allowlist, without needing or creating a container.

**`run(plan: BootstrapPlan, container: Container) -> PreflightReport`** — the actual resolution pass, run *after* registration, against the one candidate this run obtained. By the time this function is called, every key on every component has already passed `validate_service_keys`, so nothing is rejected here for being unknown — only resolution itself can still fail. For each component in plan order and each of its (already-validated) keys: resolve the mapped type from the candidate via its ordinary constructor-injection path (the same mechanism `register_class` already uses everywhere) and record success; a resolution failure (missing registration, construction error) is recorded as a failed `PreflightEntry` with a safe, generic detail message — never a raw exception, stack trace, or any value drawn from `Settings`.

Neither function calls a business method (`.start()`, `.invoke()`, `.schedule()`, `.enqueue()`, `.compose()`) on anything, performs a real network/DB/Redis call, or mutates another framework's state. Together they only prove the object graph *would* wire.

---

# `main.py`

A module-level, named function — not an inline lambda default, which Ruff flags as an ambiguous mutable/call-in-default-expression pattern — supplies the default clock:

```python
def _utc_now() -> datetime:
    return datetime.now(UTC)
```

`main(argv=None, *, container_factory=ServiceContainer, clock=_utc_now) -> int` builds a `BootstrapContext` from `wiring.build_default_manifest()`, a `ConfigurationView` built from `config.settings.get_settings()`, a fixed `correlation_id`, and `requested_at=clock()` (the one place in this task allowed to read a real wall clock — `main.py` is the impure entrypoint boundary; everything it calls afterward is deterministic given that context). The injected `clock` must always return a canonical-UTC `datetime` (timezone-aware, `utcoffset() == timedelta(0)`); `BootstrapContext.__post_init__` rejects a naive `requested_at`, a `tzinfo` whose `utcoffset()` is `None`, and any non-zero-offset timestamp, all with `ConfigurationError` — a bootstrap run can never be constructed with an ambiguous or non-UTC timestamp. `get_settings()` (see "Configuration View") is the only external read `main()` or anything it calls performs. It calls `bootstrap.run_dry_run_bootstrap(context, container_factory=container_factory)` and returns `0` if `status is BootstrapResultStatus.SUCCESS`, else `1`. It never starts live mode, never starts a framework engine, never trades, infers, or performs any network/DB/Redis/file/thread/process work.

```python
if __name__ == "__main__":
    raise SystemExit(main())
```

---

# Error Handling

Create: `BootstrapError` (base), `PlanningError`, `PreflightError`, `ConfigurationError` (raised by `build_configuration_view` if it is ever asked to copy an excluded field — defence-in-depth, should be unreachable given the mechanical filter).

`bootstrap.run_dry_run_bootstrap` isolates every failure into `BootstrapResult(status=FAILED, errors=(...))`. It never leaks a raw exception, a credential, an internal connection detail, or a stack trace to its caller.

---

# Determinism Requirements

For an identical `BootstrapContext` and an equivalent fresh container produced by `container_factory`, `run_dry_run_bootstrap` is a deterministic function: identical validation results, identical topological ordering, identical `BootstrapPlan`, `PreflightReport`, `RuntimeSnapshot`, and `LifecyclePlan` on every call. Because every run uses a brand-new disposable container and no history/registry/cache is kept anywhere in this task, there is no distinct "idempotence" concern beyond ordinary function determinism — calling it twice with the same context is calling a deterministic function twice.

Determinism must not depend on current time, random values, UUID generation, memory addresses, object identity, hash iteration order, dictionary insertion order, process ID, hostname, unvalidated environment variables, or external framework state. The only place a real wall clock is read is `main()`'s injectable `clock` parameter (`_utc_now` by default), and even there the result must be canonical UTC — timezone-aware with `utcoffset() == timedelta(0)`. A naive `datetime`, a `tzinfo` whose `utcoffset()` is `None`, or any non-zero-offset `datetime` is never accepted onto `BootstrapContext.requested_at`.

---

# Testing

Create:

```text
tests/app_fakes.py
tests/test_app_bootstrap.py
tests/test_app_flow.py
```

Requirements: deterministic, no sleeps, no randomness, no real network/DB/Redis connection, no model training.

Unit tests (`test_app_bootstrap.py`) must verify:

* immutable models, `Decimal` numeric fields, immutable metadata
* deterministic topological registration ordering, insertion-order independence for components and dependencies
* component-priority ordering and lexical component-id tie-breaking
* unknown component id rejected before any container is created
* duplicate component identifier, missing dependency, self-dependency, and cyclic dependency rejection
* unknown `required_service_keys` entry rejected by `PreflightError` before any resolution attempt
* successful and failed resolution-check paths recorded correctly in `PreflightReport`
* `ConfigurationView` contains only allowlisted fields; every field whose name contains `key`/`secret`/`token`/`credential`/`password`/`url`/`dsn` is verifiably absent, even when `Settings` is constructed with real-looking credential values
* `LifecyclePlan.stop_order` equals the exact reverse of `start_order`
* `requested_at` acceptance: a canonical-UTC value (`utcoffset() == timedelta(0)`) is accepted; a naive value (`tzinfo is None`), a `tzinfo` whose `utcoffset()` returns `None`, and a non-zero-offset value (e.g. `UTC+05:30`) are each rejected with `ConfigurationError`
* deterministic repeated runs: calling `run_dry_run_bootstrap` twice with the same `BootstrapContext` and two independently-constructed fresh containers produces field-for-field equal `BootstrapPlan`/`PreflightReport`/`RuntimeSnapshot`/`LifecyclePlan`

Integration tests (`test_app_flow.py`) must verify:

* end to end: context → planner → disposable container → wiring registration → preflight → artifacts
* `wiring.build_default_manifest()` declares all 24 known component ids and `bootstrap.run_dry_run_bootstrap` registers every one of them into the candidate container (`container.has(...)` true for each) — `trading` is absent from the manifest entirely
* **factory call-count contract**: wrap `container_factory` in a spy and assert it is called **zero** times when `planner.plan` fails, **zero** times when `preflight.validate_service_keys` fails, and **exactly one** time whenever both succeed — including a run that goes on to fail during registration or resolution. Never assert a second call, and never assert zero calls once pre-container validation has already passed
* **contract-compliant spy factory**: using a spy factory that *is* written to satisfy the documented precondition (returns a newly allocated container on every call), assert across multiple runs that each call produced a distinct object (`is not` every other) and that none of those objects is reachable from `BootstrapResult` or any artifact it contains. This proves how Task 38 itself handles what it receives; it does **not**, and cannot, prove that an arbitrary caller-supplied factory actually returns fresh containers — that is the factory's documented precondition, not something `Callable[[], Container]` or this task's code enforces against a noncompliant or malicious factory. No test may claim otherwise
* no test-owned container object is ever passed into any Task 38 function as a parameter — there is no code path that accepts a container instance directly; this (unlike factory freshness) is provable structurally
* a failing registration or a failing preflight check leaves zero accepted runtime state: no `RuntimeSnapshot` is returned, `BootstrapResult.status is FAILED`, and the container used for that attempt (obtained from the spy) is discarded and never touched again
* `app/main.py`'s `main()` returns `0` on a successful dry run and `1` on a failure, without starting live mode, a framework engine, or any background work
* `main()`'s default `clock` (`_utc_now`) produces a canonical-UTC `datetime` (`utcoffset() == timedelta(0)`), and `get_settings()` is the only external read exercised anywhere in the run
* defence-in-depth: `socket.socket`, `threading.Thread.start`, `multiprocessing.Process.start`, and any DB/Redis client constructor available in this codebase are monkeypatched to raise if called; a full dry-run bootstrap still completes successfully without tripping any of them
* the application-only cross-framework import boundary: only `app/wiring.py` imports another framework's `register_<framework>` function — verified with the AST-based technique introduced in Task 37 (real `Import`/`Name`/`Attribute` nodes only, never source substrings, so a docstring or comment mention is not a false positive)
* `mypy app/` introduces no new errors beyond the existing project baseline (none are expected — `app/` never itself calls `container.register_class`/`register_singleton` with a Protocol type; it only invokes already-defined `register_<framework>` functions and plain-typed helpers)
* the full existing test suite continues to pass unmodified

---

# Constraints

Do NOT modify: `market_data`, `strategies`, `risk`, `order_management`, `execution`, `portfolio`, `positions`, `trades`, `performance`, `backtesting`, `paper_trading`, `agents`, `learning`, `optimization`, `monitoring`, `dashboard`, `notification`, `reporting`, `storage`, `scheduler`, `workers`, `memory`, `model_gateway`, `workflows`, `core/`, `config/`, `events/`, `pyproject.toml`, or any existing test file.

Cross-framework imports are permitted **only** inside `app/wiring.py` — nowhere else in `app/`, and nowhere outside `app/` — and only for registration/resolution, never for calling a business method.

The framework must never: start a framework's engine, call another framework's manager/engine business method, trigger an Agent, execute a trade, perform inference, train a model, make a real network/DB/Redis call, spawn a thread or process, sleep, block on external I/O, write a file, mutate a caller-supplied container, retain or return a disposable container, or let a credential/secret/API key/URL-userinfo-or-query value reach a model, event, error message, or log line.

`uv.lock` is intentionally untracked in this repository state; do not create, modify, stage, or delete it.

The known `Container` Protocol `mypy` baseline (present in every sibling framework's `__init__.py`, from `register_class`/`type-abstract`) remains out of scope — do not modify `core/` to fix it. `app/` is not expected to introduce any of its own, since it never calls `register_class`/`register_singleton` with a Protocol type.

---

# Deliverables

Populate only the files listed in "Package Structure". Implement `models.py`, `exceptions.py`, `wiring.py`, `planner.py`, `preflight.py`, `bootstrap.py`, and the safe `main.py` entrypoint. Implement deterministic dependency validation and topological registration ordering. Implement the four immutable artifacts (`BootstrapPlan`, `PreflightReport`, `RuntimeSnapshot`, `LifecyclePlan`). Add unit and integration tests. Run the complete test suite — all existing tests must continue passing. Verify that no unrelated modules are modified, no framework is started, no manager/engine business method is called, no caller-supplied container is mutated, and no secret value ever appears in output.

---

# Acceptance Criteria

✓ Lean composition root confined to the 8 listed `app/` files — no unrequested domain-framework modules

✓ Safe, preflight-only `main()` returning success/failure status; no live mode, engine startup, trading, network, DB, Redis, workflow execution, or background work

✓ `COMPONENT_REGISTRARS` covers all 24 completed packages exposing a registrar; `trading` correctly excluded

✓ Task 38 accepts no container instance as a parameter anywhere — a candidate is only ever obtained by calling `container_factory` (structurally provable)

✓ `container_factory` carries a documented precondition — return a new, exclusive candidate on every call — that Task 38 trusts but cannot enforce against a noncompliant or malicious factory; this is proven for a compliant factory only, never claimed as a type-level or runtime guarantee

✓ `container_factory` is called zero times when planning or static service-key allowlist validation fails, and exactly one time thereafter, even for a run that later fails during registration or resolution

✓ Whatever candidate a compliant factory returns is never returned, cached, or retained by `BootstrapResult` or any artifact — proven structurally

✓ On any failure, zero accepted runtime state is left behind — no partial `RuntimeSnapshot`

✓ Deterministic topological component registration ordering; component-priority ordering and lexical component-id tie-breaking

✓ Unknown component id rejected before any container is created

✓ Unknown required-service-key rejected before any resolution attempt

✓ No constructor capable of I/O is ever resolved; only the safe service-key allowlist is used

✓ Duplicate component identifier, missing dependency, self-dependency, and cyclic dependency rejection

✓ Immutable `BootstrapPlan`, `PreflightReport`, `RuntimeSnapshot`, `LifecyclePlan`

✓ `LifecyclePlan.stop_order` is the exact reverse of `start_order`

✓ `ConfigurationView` excludes every credential/secret/token/URL field by both a positive allowlist and a mechanical name-pattern filter

✓ No identifier or timestamp is generated by `datetime.now()`/`uuid.uuid4()`/randomness inside any pure artifact or pipeline function; every `requested_at` is canonical UTC (`utcoffset() == timedelta(0)`), and a naive, broken-`tzinfo`, or non-zero-offset timestamp is rejected with `ConfigurationError`

✓ `get_settings()`/`load_environment()` is the sole permitted read of external configuration state; no other file read, file write, network, database, or Redis access occurs anywhere in `app/`

✓ Deterministic repeated runs on independently-constructed fresh candidate containers

✓ Unit Tests, Integration Tests, Existing Tests Passing

✓ Defence-in-depth: patched network/DB/Redis/thread/process APIs never triggered during a dry run

✓ Cross-Framework Imports Confined to `app/wiring.py`

✓ `mypy app/` introduces no new errors beyond the existing baseline

✓ No Unrelated Modules Modified

---

# Completion Checklist

After implementation, stop. Provide:

1. Architecture Overview
2. Component Collaboration (`main.py` → `bootstrap.py` → `planner.py`/`wiring.py`/`preflight.py`)
3. Registrar Coverage (all 24 packages, `trading` excluded)
4. Deterministic Component Registration Ordering
5. Component Registration Tie-Breaking
6. Wiring & Safe Allowlists Design
7. Configuration View / Redaction Design
8. Disposable Candidate Container & Ownership Contract Design
9. Preflight Resolution Checks Design
10. `main.py` Design
11. Error Handling
12. Determinism Requirements (including canonical-UTC timestamps)
13. Testing Strategy
14. Future Extensions (a live-runtime task that builds and retains the real container)

Implementation Summary

Acceptance Criteria Checklist

Stop after reporting completion.
