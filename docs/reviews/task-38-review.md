# Sprint 18 – Task 38 Review

## Task
Application Bootstrap & Dry-Run Runtime Composition

## Objective
Implement the application's composition root: the one package permitted to import across every completed framework, build a disposable candidate `ServiceContainer`, register every known framework into it, and validate — without ever starting anything or retaining what it built — that the resulting object graph is sound. Task 38 is dry-run integration only: every bootstrap run creates its own fresh, throwaway container, registers into that container alone, performs required-service resolution checks against it alone, and discards it — success or failure. Nothing this task builds is ever returned, cached, or handed to a caller as a live, usable container.

## Deliverables
- `app/` package (8 files: `__init__.py`, `main.py`, `models.py`, `exceptions.py`, `wiring.py`, `planner.py`, `preflight.py`, `bootstrap.py`) — deliberately lean, not the 14-module domain-framework blueprint, since there is exactly one implementation of a composition root
- `wiring.py`: `COMPONENT_REGISTRARS` (all 24 completed packages), `KNOWN_COMPONENT_IDS`, `SAFE_SERVICE_KEYS`, `build_configuration_view`, `build_default_manifest` — the sole sanctioned cross-framework import site
- `planner.py`: dependency validation + deterministic topological component-registration ordering (Kahn's algorithm)
- `preflight.py`: static service-key allowlist check (`validate_service_keys`) and the real resolution pass (`run`), the latter accepting a narrow `ServiceResolver` callable rather than a container
- `bootstrap.py`: `run_dry_run_bootstrap` — the single orchestrating function tying planner → disposable container → wiring registration → preflight → artifacts together
- `main.py`: safe, preflight-only CLI entrypoint (`main()` / `_utc_now()`)
- Unit tests: `tests/test_app_bootstrap.py`
- Integration tests: `tests/test_app_flow.py`
- Fixtures: `tests/app_fakes.py`

## Verification
- App tests (unit + integration): 63/63 passed
- Full suite: 741/741 passed
- Targeted Ruff (`app/`): clean
- Targeted mypy (`app/`): clean — 0 errors (the only one of the three Sprint 16–18 frameworks with no DI-typing baseline errors, since `app/` never itself calls `register_class`/`register_singleton` with a Protocol type)
- Deterministic sanity check: `status=SUCCESS, total=24, passed=24, failed=0, registered=24`

## Acceptance Criteria
- Lean composition root confined to the 8 listed `app/` files
- Safe, preflight-only `main()`; no live mode, engine startup, trading, network, DB, Redis, workflow execution, or background work
- `COMPONENT_REGISTRARS` covers all 24 completed packages; `trading` correctly excluded (no `register_trading` function)
- No function in this task accepts a container instance as a parameter — a candidate is only ever obtained by calling `container_factory` (structurally provable); `preflight.run` takes a `ServiceResolver` callable, not `Container`
- `container_factory` called zero times when planning or static service-key validation fails, exactly one time thereafter — even for a run that later fails during registration or resolution
- Whatever candidate a compliant factory returns is never returned, cached, or retained by `BootstrapResult` or any artifact
- A preflight report with any failed check, a registration exception, or a factory exception is itself a failed bootstrap: `FAILED` status, zero artifacts, one fixed generic error — never a raw exception, credential, or caller-supplied manifest value
- Deterministic topological component-registration ordering; priority ordering with lexical tie-breaking
- Unknown component id / duplicate id / missing dependency / self-dependency / cyclic dependency rejection, and unknown service-key rejection, all before any resolution attempt
- Immutable `BootstrapPlan`, `PreflightReport`, `RuntimeSnapshot`, `LifecyclePlan` — `LifecyclePlan.stop_order` is enforced (not merely produced) as the exact reverse of `start_order`
- `ConfigurationView` excludes every credential/secret/token/URL field by both a positive allowlist and a mechanical name-pattern filter
- Canonical-UTC `requested_at`; no non-deterministic identifier/timestamp generation inside any pure pipeline function
- Cross-framework imports confined to `app/wiring.py`
- No unrelated modules modified

## Architecture Summary

`app/` is the composition root — the one package allowed to import across every completed framework.

```
main.py  (impure boundary: reads wall clock, calls get_settings())
   │
   ▼
BootstrapContext
   │
   ▼
bootstrap.run_dry_run_bootstrap
   │
   ├─▶ planner.plan               (validate + order the component graph)
   ├─▶ preflight.validate_service_keys   (static allowlist check, no container yet)
   ├─▶ container_factory()        (exactly one disposable candidate)
   ├─▶ wiring.COMPONENT_REGISTRARS[id](container)   (per plan entry)
   ├─▶ preflight.run(plan, resolve)      (real resolution pass, narrow resolver)
   └─▶ RuntimeSnapshot / LifecyclePlan   (built from plan + report data only)
```

The candidate container is never referenced again after the pipeline completes — its last reference simply goes out of scope at the end of `run_dry_run_bootstrap`.

## Determinism and Safety Boundaries

**Disposable container ownership.** `run_dry_run_bootstrap` accepts only `container_factory: Callable[[], Container]` — no function in this task accepts a container instance as a parameter. The factory is called exactly once, only after both planning and static service-key validation succeed; a factory exception is itself caught and reported as a safe `FAILED` result rather than propagating. The candidate obtained is passed to `preflight.run` only through a local `_resolve` closure (`Callable[[type], object]`), never as the container itself — `preflight.run`'s own signature structurally cannot accept registration capability.

**24/24 preflight resolution.** `wiring.build_default_manifest()` declares all 24 known components, each requiring its own framework's manager/service key. `strategies`, `backtesting`, and `paper_trading` optionally resolve `MarketDataService`, which in turn needs a `MarketDataProvider`; `market_data` itself needs one directly. `wiring.COMPONENT_REGISTRARS["market_data"]` is bound via `functools.partial(register_market_data, provider=_DRY_RUN_MARKET_DATA_PROVIDER)` so all four resolve cleanly without a real, credentialed provider. A preflight report with any `failed_checks > 0` is itself treated as a failed bootstrap (`FAILED` status, no artifacts) — so a default run succeeding at all is proof the object graph fully wires, not a partial credit.

**Stateless dry-run market-data provider.** `_DryRunMarketDataProvider` declares `__slots__ = ()`, so no attribute — including a callback handler — can ever be stored on an instance, by this class or any caller. `MarketDataPipelineService.__init__` unconditionally calls `provider.on_data(handler)`; `on_data` accepts that handler and immediately discards it (`del handler`) rather than storing or invoking it. `connect`/`disconnect` fail closed, raising `RuntimeError` immediately rather than doing anything, so the type can never be mistaken for, or misused as, a usable provider. The single shared module-level instance therefore retains nothing across bootstrap runs and is safe under concurrent use.

**No runtime execution or I/O.** Neither `bootstrap.py`, `planner.py`, nor `preflight.py` ever calls `.start()` on an Engine, `.compose()`, `.invoke()`, `.schedule()`, or `.enqueue()` on any manager, triggers an Agent, executes a trade, or performs inference. `config.settings.get_settings()` is the only external read anywhere in the pipeline. Verified under `socket.socket`/`threading.Thread.start`/`multiprocessing.Process.start` monkeypatches configured to raise — a full default dry run completes successfully without tripping any of them.

**No caller-controlled values in errors.** Every `PlanningError`/`PreflightError`/`BootstrapResult.errors` message is a fixed, generic string — no component id, dependency id, service key, or other manifest-derived value is ever interpolated into an error, verified with dedicated secret-marker tests.

## Verification Results

App package import:

PASS

App tests (`tests/test_app_bootstrap.py` + `tests/test_app_flow.py`):

63 / 63 Passed

Entire repository:

741 / 741 Passed

Targeted Ruff (`app/`):

All checks passed — the framework's one `(str, Enum)` class (`BootstrapResultStatus`) already carries the same `# noqa: UP042` the sibling frameworks use.

Targeted mypy (`app/`):

0 errors — `app/` never itself calls `register_class`/`register_singleton` with a Protocol type, so it introduces none of the `Container` DI-typing baseline errors present in every sibling framework's `__init__.py`.

Deterministic sanity check (`wiring.build_default_manifest()` through a fresh `ServiceContainer`):

```
status=SUCCESS
total=24
passed=24
failed=0
registered=24
```

Full-repo baseline (pre-existing, unrelated to Task 38):

- `ruff check .`: 75 pre-existing `UP042` findings across other frameworks.
- `mypy .`: 1 pre-existing `adapters/binance/adapter.py` duplicate-module-path error that halts whole-repo mypy before it reaches package-scoped checks.

## Audit Conclusion

The Task 38 implementation was audited against `docs/prompts/task-38.md` and its own subsequent patch rounds. The composition root is confirmed to hold no live, retained container anywhere: `run_dry_run_bootstrap` obtains a candidate only via `container_factory()`, passes only a narrow resolver callable into `preflight.run`, and every returned artifact is built from plan/report data rather than from the candidate itself — proven both structurally (signature inspection) and behaviorally (distinct-object-per-call, non-retention tests). The default manifest resolves all 24 known components with zero failed preflight checks, closing the gap that an earlier round of this task left open (a `20/24` partial pass). `_DryRunMarketDataProvider` is confirmed genuinely stateless — `__slots__ = ()` makes retaining a callback structurally impossible, not merely a coding convention — closing a second gap where a module-global instance had been claimed stateless while actually storing a bound handler. No runtime execution, business-method call, or real I/O occurs anywhere in the dry-run path, and no caller-supplied manifest value ever reaches an error message.

## Commit and Release Tag

- Commit: `397a706` — "Implement Task 38 Application Bootstrap and Dry-Run Composition"
- Tag: `v4.12-application-bootstrap`

## Conclusion

Task 38 completed successfully with no regressions and follows the architectural pattern established by Tasks 27–37, adapted for its role as the project's sole composition root.
