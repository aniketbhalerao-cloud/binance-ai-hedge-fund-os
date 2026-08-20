# Task 38.5 — Structural Audit and Loophole Review

**Executed against:** `main` `3ea733c` (spec-only commit); code baseline audited: `d5ef0c7` / Task 38 release `397a706` (`v4.12-application-bootstrap`). **v4 final-proof pass:** re-run 2026-08-20 against the same unchanged code baseline. **v5 patch pass:** re-run 2026-08-20, same unchanged baseline, correcting v4's call-classification methodology and completing the module-state reassignment scan. **Honest closeout pass (2026-08-20, this revision):** a document-only correction — no new script or trace was run — that retracts every "complete"/"exhaustive"/"genuinely complete" characterization of Area 3 and Area 3b. The v1–v5 scripts genuinely improved coverage each time, but coverage improving on every pass is itself evidence the method was never exhaustive to begin with; each pass found something the previous one missed, and there is no principled reason to believe this one is the last. **The verified figures below are coverage evidence from a bounded, reproducible trace — not a mathematical proof that no forbidden path exists anywhere in the codebase.** Four specific methodological gaps remain open and are named in Unresolved Audit Limitations rather than implied away by strong language: (1) 13 dataclass constructors' reachable `__post_init__` methods were not systematically added to the call graph; (2) the runtime defence check never patched `os.open` or a DB/Redis connection entrypoint; (3) the module-state scan does not detect a plain (non-nested) function mutating a module-global object via a method call or subscript assignment; (4) call classification still depends on a manually maintained text/name allowlist for the calls it cannot resolve to a live object, so "0 unresolved" means "0 entries fell outside the allowlist," not "every callable was proven safe by inspection alone." **0 Critical findings discovered within verified scope; absence of Critical findings repo-wide is not conclusively established.**
**Method:** code-read-only. Every claim below is derived from the current committed source (AST parsing, repo-wide grep, and fresh command execution under `.venv/bin/python`), not from prior review documents, ADRs, or docstrings taken on faith. Where a prior document's claim was independently re-verified rather than merely cited, that is stated explicitly. Area 3 and Area 3b (module-state inventory) were re-derived twice — v4 superseding v3, v5 correcting v4 — see those sections for what changed and why each time; both are now framed as a high-confidence bounded trace, not a completeness proof (see the closeout note above and Unresolved Audit Limitations).

---

## 1. Architecture Boundaries & Dependency Direction

**Method:** an AST script (`ast.Import`/`ast.ImportFrom`, production source only — `tests/` excluded) walked every `.py` file in all 24 `COMPONENT_REGISTRARS` frameworks plus `exchange_adapters/` and `trading/`, recording every top-level framework package each file imports.

**Finding H-1 (High) — the "no framework imports another framework directly" claim is false for 14 of the 24 wired frameworks, plus `exchange_adapters`.**
`app/wiring.py:3` states: *"Every prior framework is forbidden from importing another framework directly... that is the entire point of registering everything through `core.container`."* This claim is copied near-verbatim from `docs/prompts/task-38.md:21`. It is **not true of the current source**. 62 production files import another framework package directly, distributed across **14 of the 24 `COMPONENT_REGISTRARS`-wired frameworks**: `agents`, `backtesting`, `execution`, `learning`, `market_data`, `optimization`, `order_management`, `paper_trading`, `performance`, `portfolio`, `positions`, `risk`, `strategies`, and `trades` — e.g. `execution/engine.py` imports `order_management`, `risk`, `strategies`, `trading`; `backtesting/manager.py` imports `execution`, `market_data`, `order_management`, `performance`, `portfolio`, `positions`, `risk`, `strategies`, `trades`. `exchange_adapters` is additional to that count, not part of it: it is not one of the 24 wired frameworks at all (see H-2), and separately also imports `execution` and `trading` directly in its own production source. Only the frameworks built after this convention was introduced — `dashboard`, `monitoring`, `notification`, `reporting`, `storage`, `scheduler`, `workers`, `memory`, `model_gateway`, `workflows`, and `app` itself — actually have zero cross-framework production imports. The isolation boundary is real and enforced for that later set (Tasks 28–38); it is not, and was never claimed by those earlier tasks' own specs to be, a repo-wide invariant. The claim in `app/wiring.py:3` and `docs/prompts/task-38.md:21` overstates it as one. See the risk register for disposition.

**Finding H-2 (High) — `COMPONENT_REGISTRARS`'s "all 24... every completed package" claim is incomplete.**
`docs/prompts/task-38.md:23` and `app/wiring.py`'s module docstring both assert `COMPONENT_REGISTRARS` covers "every completed package that exposes a `register_<framework>` function." A directory-wide re-derivation (grepping every top-level package's `__init__.py` for `^def register_`) finds **25** such packages, not 24: `exchange_adapters/__init__.py:148` defines `register_exchange_adapters`, a fully implemented Task 17 (Sprint 3) framework, and it is absent from both `COMPONENT_REGISTRARS` and `wiring.KNOWN_COMPONENT_IDS`. Consequently Task 38's dry-run bootstrap never proves `exchange_adapters`' own DI graph wires — the one framework whose entire purpose (broker/exchange adapter lifecycle) sits closest to the eventual live-runtime path is the one framework the preflight check does not cover.

**Cleared — DI consistency.** Every one of the 24 wired frameworks' `register_<framework>` function follows the same shape: `register_class`/`register_singleton` for stateless collaborators, a hand-written `_build_manager`/`_build_engine` closure resolving `EventBus`/`LoggerFactory` (the latter conditionally via `resolver.has(...)`) for the Manager/Engine. No drift found.

**Mutable-literal assignment scan (deliberately narrower than a full module-state inventory — named as such).** A script walked every module-top-level `Assign`/`AnnAssign` node (not function/class bodies, not comprehensions, not class-level attribute defaults, not values captured by a closure) across all 24 wired frameworks + `app` + `core` + `trading` + `exchange_adapters`, flagging any assignment to a `dict`/`list`/`set` literal or an unwrapped `dict(...)`/`list(...)`/`set(...)` call (skipping anything already wrapped in `MappingProxyType`/`frozenset`/`tuple`). This is a scan of one specific pattern — bare mutable-literal module globals — not a claim of having enumerated every arbitrary module-level instance, `@cache`/`@lru_cache`-decorated function, class-level mutable default, or closure-captured mutable value in the codebase; those categories were checked separately and narrowly (below), not via this script, and are not claimed complete beyond what's stated.

384 candidates were found by the literal scan; 359 are `__all__` export lists — the standard convention, confirmed never mutated anywhere via a repo-wide grep for `__all__.append`/`.extend`/`.remove`/`.pop`/`.insert` (zero hits). The remaining 25 are real lookup-table constants, corrected count: **22 transition-mapping `dict`s** (21 named `VALID_TRANSITIONS`, one per `state.py`-having package, plus `exchange_adapters/state.py:50`'s differently-named `_CONNECTION_TRANSITIONS`), **1 `_SIDE_BY_DIRECTION` mapping** (`order_management/factory.py:28`), and **2 validator `set`s** (`order_management/validator.py:16-17`'s `_PRICE_REQUIRED`/`_STOP_REQUIRED`) — 22 + 1 + 2 = 25. See the new finding L-9 below; a follow-up grep confirmed none of the 25 is ever mutated.

Separately (not via the literal-assignment script), a targeted grep for `@lru_cache`/`@cache` across the same package scope found exactly two: `core.container.get_container` (documented process-wide composition-root singleton) and `config.settings.get_settings` (documented cached, validated `Settings` singleton) — both match their own stated contract. `app/wiring.py:_DRY_RUN_MARKET_DATA_PROVIDER` was separately re-verified (`__slots__ = ()`, `hasattr(p, "__dict__")` is `False`, `connect()`/`disconnect()` raise, `on_data()` accepts-and-discards with no attribute ever settable). Class-level mutable defaults and closure-captured mutable values were **not** systematically scanned — this is a named limitation, not a "cleared."

**Finding L-9 (Low) — 25 lookup-table constants are plain `dict`/`set` literals, not defensively wrapped.** 22 transition mappings, `_SIDE_BY_DIRECTION`, and the two validator sets are all module-level `dict`/`set` literals used strictly as read-only lookup tables (confirmed: zero mutation-shaped call sites found for any of them, repo-wide), but none is wrapped in `MappingProxyType`/`frozenset` the way `app/wiring.py`'s equivalent constants are. See the risk register for full evidence and recommendation.

**Cleared — circular / hidden resolution-order dependencies.** Every cross-framework constructor reference found in area 1's import scan (`TradingEngine`, `StrategyManager`, `RiskEngine`, `MarketDataService`, etc. held by other frameworks' Manager/Engine constructors) uses the `resolver.resolve(X) if resolver.has(X) else None` conditional pattern, confirmed at each of the call sites the import scan surfaced across the 14 affected frameworks. `core/container.py`'s `_build` (the constructor-injection resolver) falls back to a parameter's default when the annotated type is unregistered rather than raising — so no framework's registration can fail merely because a sibling framework hasn't registered yet, in any order. No circular dependency found.

---

## 2. Determinism, Immutability, Registry Ownership, Thread Safety

**Method:** counted `@dataclass` decorators vs. `@dataclass(frozen=True` occurrences in every framework's `models.py` (23 of 24 — `strategies` has no `models.py`), plus `app/models.py` and `core/interfaces.py`; grepped every `object.__setattr__(self, "metadata", ...)` site for the `dict(self.x)` copy pattern.

**Cleared — model immutability.** 188 `@dataclass` declarations checked across `agents, backtesting, dashboard, execution, learning, market_data, memory, model_gateway, monitoring, notification, optimization, order_management, paper_trading, performance, portfolio, positions, reporting, risk, scheduler, storage, trades, workers, workflows, app` — 100% carry `frozen=True`. `core.interfaces.Registration` is also `frozen=True, slots=True`. Each model's own task spec was consulted where its immutability convention differed (e.g. earlier frameworks don't require `slots=True` or list-to-tuple `__post_init__` normalization the way Task 38 does) — no model was flagged for lacking a convention its own task never required.

**Reviewed, not a finding — `strategies/registry.py:24`.** `_Entry` is `@dataclass(slots=True)` **without** `frozen=True`, the one non-frozen dataclass found repo-wide. It is a private (`_`-prefixed), `Lock`-guarded internal bookkeeping record inside `InMemoryStrategyRegistry`'s own encapsulated `dict[str, _Entry]` — never returned to a caller, never a public domain model. Its mutable `enabled: bool` field is the Registry's own owned state, matching (not violating) the Registry-owns-mutable-state pattern the architecture requires; it is not one of the "immutable domain models" the architecture principle governs.

**Cleared — mutable-alias leakage.** 27 `object.__setattr__(self, "metadata", ...)` sites found repo-wide; every one wraps `MappingProxyType(dict(self.metadata))` (a fresh copy), never `MappingProxyType(self.metadata)` (the caller's own live dict). Zero unsafe instances found.

**Cleared — Kahn's-algorithm ordering.** `workflows/planner.py` and `app/planner.py` both use a genuine `heapq`-based ready-queue keyed `(-priority, id)`, re-read in full this session — same shape, not merely the same claim. No other framework has a comparable dependency-graph ordering requirement to cross-check (the storage/scheduler/workers/memory/model_gateway domain models have no inter-item dependency edges).

**Cleared — registry ownership & error isolation.** Spot-checked across `workflows`, `model_gateway`, `storage`, `app` — each Manager reads-processes-writes-back a new immutable record; no half-written state found reachable. `app/bootstrap.py`'s FAILED-path artifacts (`plan`/`preflight_report`/`runtime_snapshot`/`lifecycle_plan`) were re-traced: every `return BootstrapResult(status=FAILED, ...)` site omits all four (Python's keyword-omission leaves them at their `None` default) — structurally provable, and re-confirmed by the `test_failing_registration_leaves_zero_accepted_state`/`test_failing_preflight_run_leaves_zero_accepted_state` tests passing fresh.

**Thread safety — see M-5 in the risk register for full evidence.** 22 packages contain a `registry.py`; `execution`, `market_data`, `order_management`, `risk`, and `app` have no Registry concept at all (confirmed absent). Of the 22, 21 explicitly claim "thread-safe" in their own docstring (`grep -c "thread-safe" */registry.py` → 2 hits each in 21 files; `core/registry.py` makes no such claim — its safety instead comes from `core.container.ServiceContainer`'s `RLock`). A repo-wide grep across `tests/` for `threading.Thread(`, `ThreadPoolExecutor`, `concurrent.futures`, `asyncio.gather`, `asyncio.TaskGroup`, and `create_task` found exactly one real concurrent-execution test: `tests/test_workflows.py:467-477` (20 real `threading.Thread`s). **1 of 21** thread-safety-claiming registries has a test proving it; `ServiceContainer`'s own `RLock` has none. Recorded as a Medium test gap (M-5), not a High structural finding, since nothing in the current source contradicts any claim — it is simply unverified for 20 of 21.

**Exception sanitization — cleared under the corrected criterion.** Applying the narrower standard (a finding only if it violates that task's own spec, exposes untrusted/sensitive content unsafely, or reaches a public log/event/error surface): spot-checked `workflows/manager.py`, `model_gateway/manager.py`, `storage/manager.py` alongside `app/`'s own modules. No sibling framework was found to reach a public surface with unvalidated sensitive content. `app/`'s own stricter no-interpolation contract (Task 38's own spec, not a repo-wide rule) was re-verified via a fresh run of its secret-marker tests (`tests/test_app_flow.py::NoSecretMarkerLeakTests`, 3/3 pass) — no regression.

**mypy per-package anomalies (Low, `baseline: unknown` — see rubric in Verification Results).** Isolated from the dominant `type-abstract`/`attr-defined` Container-Protocol pattern (351 of ~365 non-`app` findings): `learning/evaluator.py:75,76,91` (`type-arg`, bare `dict`), `strategies/interfaces.py:56` and `strategies/registry.py:90` (`valid-type` — a method literally named `list` is being read as the builtin type in annotation position), `agents/manager.py:154` (`assignment`) and `:180` (`no-any-return`), `strategies/__init__.py:133` (`arg-type`, `StrategyFactory` passed where `DefaultStrategyFactory` is declared). `config/settings.py:486` accounts for 13 `call-arg` errors, root-caused to the pydantic mypy plugin not being configured in `[tool.mypy]` (pydantic's `default_factory` fields are, at runtime, optional — hundreds of passing tests construct `Settings()` successfully; this is a static-analysis gap, not a runtime bug). `core/container.py:122` has one `redundant-cast`.

---

## 3. Dry-Run / Live-Runtime Separation — High-Confidence Bounded Trace

This is the audit's centerpiece and has now gone through **five** iterations. Pass 1 scanned only the 24 top-level `SAFE_SERVICE_KEYS` types' own `__init__` sources. Pass 2 added a shared-container `resolve`/`_build` trace but recorded interface *keys*, not the real concrete classes `_build` actually constructs. Pass 3 (v3) fixed both, but its provider-body AST scan could only see closures actually **invoked** during the runtime trace, missing 15 registered-but-never-resolved `Engine` providers entirely. Pass 4 (v4) closed that gap with a registrar-body AST walk independent of invocation, reaching 175 nodes — but v4's *call classification* leaned on an unverified text allowlist for several call sites (`Settings()`, `container_factory()`, `registry.register()`, `super().__init__()`) instead of actually inspecting what each one resolves to. **Pass 5 (v5, this section) corrects that**: the container/registry/planner/preflight machinery is now walked as real, source-inspected targets rather than text-matched; `Settings()`/`container_factory()`/`registry.register()` are reclassified to reflect what they actually are; and every `super().__init__()` call is resolved to its real MRO base and that base's constructor is inspected too.

**Method (v5).** A script (`/tmp/t385/v5_full.py`) extends v4's two passes (24-root `resolve()` trace; static AST call inventory over registrar bodies, provider closures, and the entrypoint prefix) with:

1. **Real target resolution instead of text allowlisting (item 3).** `core.container.ServiceContainer.resolve`/`._build`/`.register*`/`.has`/`.create`/`.reset`, `core.registry.ServiceRegistry.register`/`.get`/`.contains`/`.remove`/`.clear`, `app.planner.plan`, and `app.preflight.validate_service_keys`/`.run` are added as explicit walk targets — their own source is parsed and every `Call` inside them is itself classified, recursively. Call sites *inside* registrar/provider closures that invoke these (`resolver.resolve(...)`, `container.register_class(...)`, `self._registry.get(...)`) are resolved to the real bound method via three mechanisms, each independently justified: (a) a parameter's raw annotation string matched by name against `Resolver`/`Container`/`Registry` — needed because every registrar module imports those names only under `if TYPE_CHECKING:` (confirmed by reading each module's imports), so `typing.get_type_hints()` cannot evaluate them at runtime; (b) `self.<attr>`/`self._registry.<attr>`/`self._singletons.<attr>`/`self._resolving.<attr>`/`self._registrations.<attr>` resolved via the known owner class, since `ServiceContainer`/`ServiceRegistry` are each other's own attributes' concrete types (read directly from their own `__init__`); (c) a narrow, explicitly-documented name-convention fallback (`resolver`/`r` → `.resolve`/`.has`; `container` → its declared `Container` methods) for the one shape neither (a) nor (b) reaches — a `lambda r: r.resolve(X)` alias closure, whose parameter carries no annotation at all in Python syntax. `Resolver`/`Container`/`Registry` each have exactly one implementer repository-wide (re-verified by grep: only `ServiceContainer` extends `Container`/`Resolver`, only `ServiceRegistry` extends `core.interfaces.Registry`), which is what makes all three substitutions sound rather than a guess.
2. **`self._provider.on_data()` resolved from the runtime trace, not the parameter type (item 2c).** `MarketDataProvider` is an interface with more than one possible implementer in principle, so it is not resolved the structural way `Resolver`/`Container` are. Instead, Part A's 24-root trace captures the actual constructed `MarketDataPipelineService` instance and asserts its real `._provider` attribute's type before the call inventory ever runs: `type(instance._provider).__qualname__ == "app.wiring._DryRunMarketDataProvider"` (script-enforced `assert`, not a claim). `_DryRunMarketDataProvider.on_data` is then walked like any other node: `def on_data(self, handler): del handler` — accepted and discarded, confirmed clean.
3. **`registry.register()` resolved to its real receiver, not the DI container (item 2d).** Local-variable type inference (`registry = InMemoryAgentRegistry()` inside `agents/__init__.py:_build_registry`, tracked from a pre-pass over the function's own `Assign` statements) resolves this call to `agents.registry.InMemoryAgentRegistry.register`, confirmed by direct source read: `self._agents[agent.role] = agent` under `threading.Lock`, no I/O. `InMemoryAgentRegistry` implements `agents.interfaces.AgentRegistry` (a framework-owned domain-registry Protocol), **not** `core.interfaces.Registry` (the DI container's own registration store, implemented solely by `ServiceRegistry`) — the two were conflated in v4's classification.
4. **`super().__init__()` resolved to the real MRO base and inspected (item 2e).** For every `super().__init__(...)` call found, the class currently being walked (`owner_class`, threaded through the recursive walk) is used to find the next class in `owner_class.__mro__` that defines its own `__init__`; that base class is added to the same unified node collection and its `__init__` is walked and classified like every other node — not left as an opaque `super()` call.

**Result — recursive trace and node collection.** `ROOTS_TRACED=24`, `ROOTS_WITH_ERROR=0`, 352 resolve events, 44 distinct provider symbols, 143 distinct concrete classes via `resolve()` — all unchanged from v4/v3. **Unified node collection: 183** (up from v4's 175) — the 8-node increase is exactly the classes reached only by now walking the container/registry/planner/preflight machinery as real targets: `app.models.{BootstrapPlan, BootstrapPlanEntry, PreflightReport, PreflightEntry}`, `core.interfaces.Registration`, `app.exceptions.{PlanningError, PreflightError}`, and `agents.agent.BaseAgent` (the real MRO base every `Default*Agent.__init__`'s `super().__init__()` resolves to, per item 2e — present in v4's call graph but never itself added as a node until now).

**Node construction classification (independent per node, dataclass `default_factory` checked separately):**

| category | count |
|---|---|
| source available, AST-scanned clean | 78 |
| inherited `object.__init__`/`__new__` | 87 |
| generated dataclass initializer | 13 |
| extension/builtin (C-implemented, not project code) | 5 |
| **unresolved** | **0** |

183 total (78 + 87 + 13 + 5 = 183). The two new categories over v4's 8/3 split: `generated_dataclass_init` gained `BootstrapPlan`, `BootstrapPlanEntry`, `PreflightReport`, `PreflightEntry`, `core.interfaces.Registration` (all `@dataclass(frozen=True, slots=True)`, reached by walking `app.planner`/`app.preflight` as real targets); `extension_or_builtin_stdlib` gained `PlanningError`/`PreflightError` (plain `Exception` subclasses with no body beyond a docstring, inheriting `Exception.__init__` — C-implemented, no `.py` source, same treatment as `ConfigurationError` in v4).

**AST call classification — corrected to 6 buckets (v4 had 5; this pass splits "container/registration operation" into the real DI mechanism vs. domain-registry mutation, and adds a distinct trust-boundary bucket):**

| bucket | unique signatures | occurrences |
|---|---|---|
| container/registration operation — resolved to a real `ServiceContainer`/`ServiceRegistry` method, per the three mechanisms above | 26 | 1,368 |
| safe in-process construction (constructors on already-classified-clean nodes; pure stdlib/builtin value ops; this module's own pure helpers; `super()`/`object.__setattr__`; `app.planner`/`app.preflight`'s own pure computation — `dict.fromkeys`, `heapq` ops, list/dict `.append`/`.items()`, `inspect.signature`/`get_type_hints` introspection — all individually read, not merely walked) | 121 | 315 |
| **safe in-process domain-state mutation (new)** — `registry.register()` → `InMemoryAgentRegistry.register`, a framework-owned dict write under a `threading.Lock`, no I/O; kept separate from the DI-container bucket per item 2d | 1 | 10 |
| **permitted boundary read (corrected)** — `get_settings()`/`load_environment()`, **`Settings()`** (moved here per item 2a: `pydantic_settings.BaseSettings.__init__` reads process env vars/`.env` values on construction — the same impure configuration-read boundary as `get_settings()`, not "safe pure"), `clock()`/`_utc_now`/`datetime.now` | 5 | 5 |
| **trusted injectable boundary (new)** — **`container_factory()`** (moved here per item 2b: the *default* value is `ServiceContainer`, a safe in-process constructor, but the call itself is a caller-supplied injection point `app/bootstrap.py`'s own docstring says this function "trusts but cannot enforce" — a trust boundary, not a proven-safe construction, and reported as such rather than folded into "safe pure") | 1 | 1 |
| forbidden operation, present in source but proven unreachable from this entrypoint | 1 | 46 |
| **unresolved** | **0** | **0** |

155 unique signatures total (26+121+1+5+1+1+0), 1,745 occurrences (1,368+315+10+5+1+46+0) — matching `TOTAL_CALL_RECORDS`. A repeat of item 3's explicit substring sweep (`open`, `os.`, `socket`, `subprocess`, `Thread`, `Process`, `sleep`, `requests`, `httpx`, `redis`, `sqlite`, `psycopg`, `urllib`, `.connect`, `.invoke`, `.compose`, `.enqueue`, `.schedule`, `.submit_order`, `.predict`, `.infer`) across all 154 unique call *texts* in this broadened scope: **zero matches**.

**The one forbidden-operation entry — M-6, refined (item 5).** `logger.get_logger(...)` appears at 46 distinct `Manager`/`Engine` `__init__` sites, guarded by `if logger else None`, with `logger` provably `None` on every one of the 352 resolve events (`LoggerFactory` is never among the 24 `COMPONENT_REGISTRARS`; confirmed by grep — zero `register_logging` call sites anywhere in `app/` or the 24 frameworks). **Corrected claim, per item 5:** `LoggerFactory().configure()` — the method `get_logger()` would call if ever reached — does **not necessarily open a file**. Reading `core/logging.py`'s own defaults (`LoggingConfig.console_enabled: bool = True`, `LoggingConfig.file_path: str | None = None`): a default-constructed `LoggerFactory` attaches one `logging.StreamHandler()` (console output — a real but minor side effect, not a file) unconditionally; `os.makedirs(...)` and `RotatingFileHandler(...)` (the actual file I/O) only execute **if a caller explicitly sets `file_path`** on `LoggingConfig`, which is not the default. v4's structural-audit and risk-register text overstated this as "opens a real file" unconditionally — corrected here and in the risk register.

**Runtime defence check (item 4 — post-context, new in v5; corroborating evidence, not independent proof).** `/tmp/t385/v5_runtime_defence.py`: build `Settings`/`BootstrapContext` normally first (the permitted `get_settings()`/clock reads happen before any patching), **then** patch `builtins.open`, `pathlib.Path.{open,read_text,write_text,read_bytes,write_bytes}`, `os.{makedirs,remove,system}`, `socket.{socket,create_connection}`, `subprocess.{Popen,run}`, `threading.Thread.start`, `multiprocessing.Process.start`, `time.sleep`, `asyncio.sleep` to raise, **plus** every `start`/`invoke`/`compose`/`schedule`/`enqueue`/`submit_order`/`place_order`/`execute_trade`/`predict`/`infer` method any of the 183 unified nodes defines on itself (33 such methods found across 21 classes — every framework's `Engine.start`, `DefaultComposer.compose`, `DefaultSchedulerEngine.schedule`, `DefaultWorkerEngine.enqueue`, `DefaultModelGatewayEngine.invoke`, etc. — enumerated, not guessed), then calls `run_dry_run_bootstrap(context, container_factory=ServiceContainer)` for real. **Result: `status=SUCCESS`, `total=24 passed=24 failed=0`** — every patch is restored afterward via `finally`. This is a broader check than v4's (which patched only `socket.socket`/`Thread.start`/`Process.start`): it additionally shows none of the 33 lifecycle-shaped methods actually reachable from this entrypoint are called during this one run. It does **not** patch `os.open`/DB/Redis connection primitives (see Unresolved Audit Limitations) and, like every dynamic check, only demonstrates the absence of a call on the paths this specific run actually executed — it is not a static guarantee for paths this run didn't take.

**The two load-bearing mechanisms, re-verified fresh:** (a) `SAFE_SERVICE_KEYS` as the only resolved set, all 183 real classes now shown reachable confirmed I/O-free by classification; (b) `app/preflight.py:validate_service_keys` as a genuine pre-container gate, re-confirmed via `tests/test_app_flow.py::FactoryCallCountContractTests` (5/5 pass).

**Conclusion: Area 3 is a high-confidence bounded trace under the v5 method, and strictly more accurate than v4 — not a completeness proof.** 183 distinct real classes, every one classified via an identity check, a dataclass-generation check, an extension/builtin check, or a source scan, with zero left *outside* that classification scheme. 155 unique calls, every one classified into one of the 6 item-3 buckets, with zero left outside that scheme, and `Settings()`/`container_factory()`/`registry.register()`/`super().__init__()` now classified by what they actually are rather than by an unexamined text pattern. These are the correct figures for what this pass's method can see, and they are genuine coverage evidence — but "zero unresolved" describes the classifier's own bookkeeping (nothing fell outside its node/call scheme), not an independent mathematical guarantee that every reachable callable was individually proven safe. Four specific gaps in that scheme are named in Unresolved Audit Limitations below (`__post_init__` call-graph coverage, `os.open`/DB/Redis runtime-denial coverage, module-global mutation-from-a-plain-function detection, and the residual text/name allowlist underlying "resolved"). **0 Critical findings discovered within verified scope; absence of Critical findings repo-wide is not conclusively established.** This does **not** extend to `exchange_adapters` (see H-2), which remains outside `SAFE_SERVICE_KEYS`/`COMPONENT_REGISTRARS` entirely and is covered only by the repo-wide I/O-primitive grep, which found nothing in its production source.

---

## 3b. Module-State Inventory (v3 — reassignment/mutation scan added)

Area 1's original mutable-literal scan and v4's broadened Call-assignment/comprehension/cache/class-default/closure scan (both restated below) shared one blind spot, named explicitly in this pass's instructions: neither looked at a module variable initialized to `None`/a scalar and **rebound later** — the exact shape of `core/logging.py:363`'s `_default_factory: LoggerFactory | None = None`, mutated via `global _default_factory` inside `configure_logging()`. A Call-assignment scan never sees this (the *initial* value is a bare `None` literal, not a `Call`); a literal-mutable scan never sees it either (`None` isn't a `dict`/`list`/`set`). **Per item 1, the "no undocumented shared state" conclusion from the prior pass is withdrawn until this gap is scanned — done below.**

**Method.** A new script (`/tmp/t385/module_state_v5.py`), same 373-file scope (24 wired frameworks + `app`/`core`/`trading`/`exchange_adapters`/`config`/`events`, 0 parse errors), finds every module-level `Assign`/`AnnAssign` whose *initial* value is `None` or another bare scalar literal (a `Call`-valued or populated-literal-valued assignment is already covered by the v4 scan, not re-collected here), then searches every function in the same module for a `global <name>` declaration that later reassigns it, and separately scans every module for a top-level (not inside any function/class) `X.attr = ...` or `X[k] = ...` statement.

**Result.**

| candidate type | found |
|---|---|
| module-level `None`/scalar variable candidates | 22 |
| — confirmed rebound via `global` inside a function | **1** |
| — never rebound anywhere (genuine constants) | 21 |
| module-level (top-level statement) attribute/subscript mutation | 0 |

**The one rebound variable: `core/logging.py:363`'s `_default_factory: LoggerFactory | None = None`.** Rebound at `core/logging.py:376` inside `configure_logging()` (`global _default_factory; _default_factory = LoggerFactory(config).configure()`), read at `core/logging.py:389-392` inside the module-level `get_logger()` convenience function. **Classified explicitly, per item 1: an intentional, documented process-wide mutable singleton** — the module's own section header at `core/logging.py:355` names it "Module-level convenience (non-DI usage)", distinguishing it from the DI-registered path (`register_logging`, which builds and registers its *own* `LoggerFactory` instance via `container.register_instance`, never touching `_default_factory` at all). **Reachability, checked the same way as M-6:** a repo-wide grep for `from core.logging import` across every registrar/provider module (the same command that grounded M-6) shows every one of the 24 frameworks imports only the `LoggerFactory` *class* — never `configure_logging` or the free-function `get_logger`. `_default_factory`'s only mutation path is therefore, like `LoggerFactory.get_logger`'s file-I/O path, **unreached from `app/main.py:main`/`app/bootstrap.py:run_dry_run_bootstrap` today** — an additional, independently-confirmed fact about the same underlying gap M-6 already records (logging is simply never wired into the dry-run graph at all), not a second new risk.

**The 21 never-rebound candidates are genuine module-level constants** used as fixed defaults, e.g. `backtesting/manager.py:_WINDOW = 128`, `execution/routing.py:DEFAULT_DESTINATION = 'default'`, `config/constants.py`'s port-range/default-URL/default-app-name constants, `app/main.py:_CORRELATION_ID`. None showed a `global`-declared rebinding site anywhere in its module.

**Module-level attribute/subscript mutation: 0 found**, confirming (not assuming) that no module in scope performs a top-level `SOME_OBJECT.attr = ...` or `SOME_DICT[key] = ...` outside a function body.

**Combined with the prior pass's broadened scan** (module-level `Call` assignments, comprehensions, `@cache`/`@lru_cache` functions, class-level mutable defaults, closure-captured mutables — same 373-file scope, restated here rather than re-run since nothing in this pass's corrections touches that method):

| candidate type | found | classification |
|---|---|---|
| module-level `Call` assignments | 108 | 105 immutable constant (`Decimal`/`frozenset`/`TypeVar`/`MappingProxyType`), 2 intentional documented shared instance (`_DRY_RUN_MARKET_DATA_PROVIDER`, `_correlation_id: ContextVar`), 1 mutable-but-never-mutated lookup (`_BASE_CONFIG`) |
| module-level comprehensions/generator expressions | 0 | none found |
| `@cache`/`@lru_cache`-decorated functions | 2 | `core.container.get_container`, `config.settings.get_settings` — intentional documented shared instance |
| class-level mutable defaults | 0 | none found |
| closure-captured mutable objects | 0 | none found |
| **module-level `None`/scalar vars rebound via `global` (new this pass)** | **1** | `core/logging.py:_default_factory` — intentional documented shared instance, unreached (see above) |
| module-level attribute/subscript mutation (new this pass) | 0 | none found |
| Area 1's original literal-mutable-scan candidates (restated, same taxonomy) | 384 | 359 `__all__` lists + 25 lookup-table `dict`/`set`s — mutable-but-never-mutated lookup |

**Grand total: 516 module-state candidates classified across all passes** (108 + 2 + 1 + 384 = 495 distinct items plus the 21 never-rebound scalar constants folded into "immutable constant" = 516) — **126 immutable constant, 5 intentional documented cache/shared instance, 385 mutable-but-never-mutated lookup, 0 unexplained shared mutable state.**

**Conclusion.** With the reassignment/mutation scan now included — module-level `None`/scalar rebinding via `global`, and top-level *attribute/subscript* mutation, both checked rather than merely assumed absent — this pass's evidence for "no undocumented shared state" is broader than the previous one's. It is still not exhaustive: as recorded above and in Unresolved Audit Limitations, this scan does not detect a plain (non-nested) function mutating a module-global mutable object via a method call or subscript assignment from inside its own body — a distinct shape from the top-level and closure-nested mutation this pass and v4's did check. The one real instance of module-level mutable state this scan *does* add (`core/logging.py:_default_factory`) was already the kind of thing item 1 named as a target, is explicitly classified (not waived past), and is confirmed unreached from this entrypoint within verified scope, consistent with — not contradicting — M-6's own finding about the rest of the logging subsystem.

---

## 4. Trading Safety Gaps

Findings only — nothing below was implemented. See the risk register for full evidence/recommendation per row; summarized here:

* **Risk evaluation is advisory-only.** `risk/manager.py:77-103`'s `RiskEvaluationManager.evaluate()` produces a `RiskDecision` and publishes `RiskDecisionApproved`/`RiskDecisionRejected` events — it does not block anything itself. `order_management/engine.py:39-40`'s own docstring states its held `risk_engine` reference is "(integration only). Orders are created from an `OrderContext`, not by calling these." No code path in `order_management/` or `execution/` branches on `RiskDecisionType.REJECTED`.
* **No idempotency mechanism.** `order_management/models.py:36` declares `client_order_id: str | None = None`; a repo-wide grep found no other reference to it anywhere in `order_management/` or `execution/` — nothing reads or checks it.
* **Order/execution validation is structural only.** `order_management/validator.py:22-40`, by its own docstring, checks only "structural consistency (required fields, quantity, price/stop by order type)... no risk evaluation... or submission." No notional-limit check, symbol allowlist, or duplicate-order detection exists in `order_management/` or `execution/`.
* **No kill switch.** A repo-wide search for a circuit-breaker/emergency-stop/kill-switch construct returns zero results.
* **No dedicated audit trail.** Several frameworks maintain analytical "History" records (`TradeHistory`, `PositionHistory`, etc.); none is documented or implemented as an immutable, append-only, attribution-grade audit trail for compliance purposes.

**Fail-closed assessment:** all five gaps above fail closed *today*, purely because nothing live exists yet — Area 3 proves Task 38 never reaches a real order path at all, so none of these gaps is exploitable now. Each becomes a live-risk item the moment a live-runtime task is built directly on the current structure without first closing it.

---

## 5. Secret/Credential Leakage & Unsafe Configuration Propagation

**Cleared — the two-role `Settings` boundary holds.** Repo-wide grep for `get_settings()`/`load_environment()` calls found exactly two hits: `app/main.py` (the permitted caller) and `config/settings.py` (its own definition). Repo-wide grep for the bare word `Settings` found five other hits outside `app/wiring.py` — all five (`app/exceptions.py:45`, `app/preflight.py:71`, `app/models.py:109,115,119`, `core/logging.py:13`) are prose/docstring mentions, not field reads; none constructs, imports, or reads a `Settings` instance.

**Cleared — allowlist/field-set drift.** `git diff 397a706 HEAD -- config/settings.py` is empty: `config/settings.py` has not changed since before Task 38 shipped, so `build_configuration_view`'s allowlist cannot have drifted out of sync with it.

**Cleared — error-message literal set.** `PreflightEntry.detail` and `BootstrapResult.errors` were re-derived from current source (not cited from a prior review): every value traces to one of a small fixed set of literals in `app/bootstrap.py`/`app/preflight.py` — `"service resolved successfully"`, `"service resolution failed"`, `"component graph validation failed"`, `"service key validation failed"`, `"container factory failed to produce a candidate container"`, `"component registration failed"`, `"preflight resolution pass failed"`, `"preflight resolution checks failed"`. No caller-supplied value is interpolated into any of them.

No finding in this area.

---

## 6. Missing Tests

Full enumeration is in `docs/audits/task-38.5-test-gaps.md`. Headline finding: of the 21 packages whose Registry docstring explicitly claims thread safety, exactly **1** (`workflows`, `tests/test_workflows.py:467-477`, 20 real `threading.Thread`s) has a test proving it — see M-5 in the risk register for the full denominator derivation. The other 20, plus `core.container.ServiceContainer`'s own `RLock` (shared by all 24 wired frameworks), assert thread safety without a single test exercising real concurrent access.

---

## 7. Documentation Drift

**Confirmed still current (re-verified, not cited):** `docs/architecture/roadmap-v2.md:65-76`'s Task 38 entry is unchanged and still titled "Feedback & Trade Journal Framework," describing a `feedback/` package that does not exist. A grep of the whole roadmap for "Feedback"/"feedback" found only that one section — no Task 39+ entry references it as a dependency; the drift is contained.

**Cleared — verification numbers.** `docs/reviews/task-36-review.md` (44 tests), `task-37-review.md` (50 tests), and `task-38-review.md` (63 app tests, 741 full suite) were each re-run fresh this session: 44/44, 50/50, 63/63, 741/741 — all match exactly, no drift.

**New finding, cross-referencing Area 1:** `docs/prompts/task-38.md:21,23` (the authoritative spec Task 38 was built against) itself carries the two claims falsified in H-1 and H-2. This is simultaneously an architecture finding and a documentation-drift finding; it is recorded once, in the risk register, rather than duplicated.

---

## Verification Results

All commands below were re-run fresh this session via `.venv/bin/python`, never `uv`.

```
$ python -m compileall -q agents backtesting dashboard execution learning market_data \
    memory model_gateway monitoring notification optimization order_management \
    paper_trading performance portfolio positions reporting risk scheduler storage \
    strategies trades workers workflows app trading core config exchange_adapters tests
(clean, exit 0)

$ python -m pytest -q
741 passed in 0.84s
```

Targeted (Task 36/37/38 own suites, re-run fresh): `tests/unit/test_model_gateway.py` + `tests/integration/test_model_gateway_flow.py` → 44/44. `tests/test_workflows.py` + `tests/test_workflow_flow.py` → 50/50. `tests/test_app_bootstrap.py` + `tests/test_app_flow.py` → 63/63. All match their recorded review-document counts exactly.

**Scoped Ruff**, per package (current findings; see Baseline Separation below for which are recorded vs. `unknown`):

| package | ruff | package | ruff | package | ruff |
|---|---|---|---|---|---|
| agents | 3 | order_management | 1 | strategies | 3 |
| backtesting | 2 | paper_trading | 2 | trades | 2 |
| dashboard | 2 | performance | 1 | workers | 2 |
| execution | 2 | portfolio | 2 | workflows | 0 |
| learning | 2 | positions | 3 | app | 0 |
| market_data | 1 | reporting | 2 | trading | 1 |
| memory | 2 | risk | 1 | exchange_adapters | 5 |
| model_gateway | 0 | scheduler | 2 | core | 3 |
| monitoring | 2 | storage | 2 | config | 6 |
| notification | 2 | | | | |
| optimization | 2 | | | | |

Sum across the table above: 58. Full-repo `ruff check .`: 75 (unchanged from the recorded baseline; the remaining 17 fall in directories outside this table — `database/`, `api/`, `adapters/`, `models/`, `scripts/`, `tests/`, etc., not scoped by Task 38.5's package list).

**Scoped mypy**, per package: `model_gateway` = 14 errors (recorded baseline, unchanged), `workflows` = 14 errors (recorded baseline, unchanged), `app` = 0 (recorded baseline, unchanged). Every other package's count is new data this session with **no recorded baseline to compare against** — see Baseline Separation.

**Full-repo `mypy .`:** halts on the pre-existing `adapters/binance/adapter.py` duplicate-module-path error before reaching the rest of the tree — unchanged from the recorded baseline.

**Coverage evidence from the recursive-trace + AST call inventory script v5** (not a completeness proof — see the closeout note at the top of this document and Unresolved Audit Limitations), re-run fresh, exact summary (`/tmp/t385/v5_full.py` + `/tmp/t385/v5_classify_nodes.py` + `/tmp/t385/v5_classify_calls.py`; 24 independent fresh containers, one per `SAFE_SERVICE_KEYS` root, superseding the v4 scripts referenced in the prior draft of this document):
```
ROOTS_TRACED=24
ROOTS_WITH_ERROR=0
RESOLVE_EVENTS=352
DISTINCT_PROVIDER_SYMBOLS=44
DISTINCT_RESULT_TYPES=143         (via resolve()'s type(result), unchanged from v4/v3)
MARKET_DATA_PROVIDER_RUNTIME_TYPE=app.wiring._DryRunMarketDataProvider   (script-asserted, item 2c)
CALL_SITES_WALKED=453
TOTAL_CALL_RECORDS=1745
UNIFIED_NODE_COUNT=183            (143 resolve()-derived + 40 AST/entrypoint/mechanism-only-discovered)
  source_available_clean=78
  inherited_object_init=87
  generated_dataclass_init=13
  extension_or_builtin_stdlib=5
  node_unresolved=0
CALL_CLASSIFICATION (155 unique signatures / 1745 occurrences, 6 buckets):
  container_registration_operation=26 unique / 1368 occurrences
  safe_in_process_construction=121 unique / 315 occurrences
  safe_in_process_domain_state_mutation=1 unique / 10 occurrences
  permitted_boundary_read=5 unique / 5 occurrences
  trusted_injectable_boundary=1 unique / 1 occurrence
  forbidden_operation_present_but_unreached=1 unique / 46 occurrences
  call_unresolved=0 unique / 0 occurrences
TOTAL_TRULY_UNRESOLVED=0   (node_unresolved + call_unresolved)
```
(183 = 143 concrete classes reached via `resolve()`'s `type(result)` + 40 additional classes found only by AST/entrypoint/mechanism discovery — the 5 `Default*Agent` classes, 15 `Default*Engine` classes, 12 domain-model/exception/stdlib classes from v4, plus 8 new this pass: `app.models.{BootstrapPlan, BootstrapPlanEntry, PreflightReport, PreflightEntry}`, `core.interfaces.Registration`, `app.exceptions.{PlanningError, PreflightError}`, `agents.agent.BaseAgent` — reached only once `core.container`/`core.registry`/`app.planner`/`app.preflight` were walked as real targets and `super().__init__()` was resolved to its actual MRO base. See Area 3 above for the full breakdown, the corrected classification of `Settings()`/`container_factory()`/`registry.register()`, and the refined M-6.)

**Module-state inventory v3, re-run fresh** (`/tmp/t385/module_state_v5.py`, plus the unchanged v4 scan restated; 373 files across the 24 wired frameworks + `app`/`core`/`trading`/`exchange_adapters`/`config`/`events`, 0 parse errors) — see Area 3b above for the full breakdown: **516 candidates classified** (126 immutable constant, 5 intentional documented cache/shared instance — including `core/logging.py:_default_factory`, the one confirmed `global`-rebound module variable found by this pass's new scan — 385 mutable-but-never-mutated lookup, **0 unexplained**), plus 0 module-level comprehensions, 0 class-level mutable defaults, 0 closure-captured mutables, and (new this pass) 0 module-level attribute/subscript mutations found.

**Post-context runtime defence check, new in v5 (item 4):** `/tmp/t385/v5_runtime_defence.py` — build `Settings`/`BootstrapContext` normally first, then patch `builtins.open`, `pathlib.Path.{open,read_text,write_text,read_bytes,write_bytes}`, `os.{makedirs,remove,system}`, `socket.{socket,create_connection}`, `subprocess.{Popen,run}`, `threading.Thread.start`, `multiprocessing.Process.start`, `time.sleep`, `asyncio.sleep`, and all 33 `start`/`invoke`/`compose`/`schedule`/`enqueue`/`submit_order`/`place_order`/`execute_trade`/`predict`/`infer` methods found across the 183 unified nodes, to raise:
```
patched 18 module-level targets, 33 class lifecycle methods
status: BootstrapResultStatus.SUCCESS
total=24 passed=24 failed=0
PASS: run_dry_run_bootstrap succeeded 24/24 with all forbidden-operation surfaces patched to raise
```

**24/24 preflight sanity check, re-run fresh:**
```
status=SUCCESS
total=24
passed=24
failed=0
registered=24
```

**Defence-in-depth + AST import-boundary tests, re-run fresh:** `tests/test_app_flow.py::DefenceInDepthTests` (2/2) and `::ImportBoundaryTests` (3/3) — 5/5 pass.

### Baseline Separation

Three baselines were previously recorded (in `task-36-review.md`, `task-37-review.md`, `task-38-review.md`) and are **unchanged** this session: full-repo `ruff check .` = 75 `UP042`; full-repo `mypy .` halts on the one `adapters/binance/adapter.py` path-collision error; `model_gateway`/`workflows` mypy = 14 errors each (`type-abstract`/`attr-defined`), `app` mypy = 0.

**Every other per-package Ruff/mypy count in this report is `baseline: unknown`** — no prior document recorded a per-package figure for `agents`, `backtesting`, `dashboard`, `execution`, `learning`, `market_data`, `memory`, `monitoring`, `notification`, `optimization`, `order_management`, `paper_trading`, `performance`, `portfolio`, `positions`, `reporting`, `risk`, `scheduler`, `storage`, `strategies`, `trades`, `workers`, `trading`, `exchange_adapters`, `core`, or `config`. None of these counts is reported as "new" or "a regression" — they are this audit's first recorded baseline for each, and are noted as such in the risk register.

**Genuine regressions found: none.** Every comparison against a recorded baseline (test counts, the three ruff/mypy figures above, `git diff` on `config/settings.py`) matched exactly.

---

## Unresolved Audit Limitations

* The `exchange_adapters` framework surfaced by H-2 was not itself subjected to the full Area 3 call-path trace (it is outside `SAFE_SERVICE_KEYS`/`COMPONENT_REGISTRARS` and therefore outside what Task 38's own pipeline reaches) — its own I/O-boundary safety was not independently re-audited here beyond the repo-wide I/O-primitive grep in Area 3, which did cover its production source and found nothing.
* `database/`, `api/`, `adapters/`, `models/`, `scripts/`, `services/`, `repositories/`, `schemas/`, `simulation/`, and `docker/` were compiled and included in the full-repo ruff/mypy/pytest runs but were not individually walked for cross-framework import boundaries or model-immutability conventions — they are not `register_<framework>`-exposing packages and were judged out of the "framework" scope the spec's Area 1/2 language targets, but a future audit pass could extend the same AST/grep method to them.
* The mypy stray-error investigation (Area 2) identified each error's file:line and category but did not trace every one to a runtime-behavior conclusion the way `config/settings.py`'s call-arg cluster was (pydantic-plugin-not-configured, confirmed non-bug); `strategies/interfaces.py:56`/`registry.py:90`'s `.list`-as-type finding in particular would benefit from a dedicated follow-up read.
* ~~The Area 1 mutable-literal assignment scan is deliberately named narrowly...~~ **Narrowed further in v4/v5, still not exhaustive (see the four items below).** Area 3b: module-level `Call` assignments, comprehensions, `@cache`/`@lru_cache` functions, class-level mutable defaults, closure-captured mutables (v4), and module-level `None`/scalar variables rebound via `global` and top-level attribute/subscript mutation (v5), were all systematically scanned (373 files, 0 parse errors); 516 candidates classified, 0 landed in "unexplained shared mutable state" **within what was scanned**. That scan does not detect a plain, non-nested function mutating a module-global mutable object via a method call or subscript assignment from inside an ordinary function body (as opposed to a nested closure, which was checked) — see the new item below. The "no undocumented shared state" conclusion is therefore evidence from a broader scan than v3's, not a proof the broader scan is itself exhaustive.
* **New in v4, not a prior limitation being closed:** the AST call inventory (Area 3) surfaced one forbidden-operation call site (`logger.get_logger`, 46 occurrences across every Manager/Engine `__init__`) that no prior pass's repo-wide grep found, because its own I/O lives inside `core/logging.py`, outside the 24-framework + `app/` grep scope those passes used. It is unreachable from this entrypoint within verified scope (`LoggerFactory` is never among the 24 `COMPONENT_REGISTRARS`), not merely unobserved — recorded as risk register **M-6**, refined in v5 to state accurately that the default (unconfigured) `LoggerFactory` would attach a console handler, not open a file; only an explicitly configured `file_path` would. Does not independently block the gate — but see **M-7** and the ADR-032 gate status, which is now on hold for a separate, broader reason.
* **New in v5, not a prior limitation being closed:** v4's call classification allowlisted several call sites by text pattern without inspecting what they actually resolved to (`Settings()`, `container_factory()`, `registry.register()`, bare `super().__init__()`, and the container/registry/planner/preflight machinery itself). v5 corrected all of these by walking the real mechanism functions and resolving each call to a live object wherever mechanically possible — see Area 3 for the corrected 6-bucket classification. No call site changed *conclusion* (nothing forbidden-and-reachable was found among them), but three were reclassified to accurately describe what kind of thing they are (an impure configuration boundary, a trusted-but-unenforceable injection point, and a domain-registry mutation rather than a DI-container operation) rather than being folded into "safe pure."
* **New in this closeout pass — four methodological gaps that remain open, named explicitly rather than implied away by "complete"/"exhaustive" language (see risk register M-7):**
  1. **`__post_init__` call-graph coverage.** 13 nodes are classified `generated_dataclass_init` (a `@dataclass`-synthesized `__init__`, confirmed clean by construction — it can only assign already-typed fields). Several of these dataclasses (e.g. `app.models.BootstrapContext`, `RuntimeSnapshot`) additionally define a hand-written `__post_init__` (seen directly, e.g. `object.__setattr__(self, "registered_component_ids", tuple(...))` in Area 1/2's own mutable-alias review) — but no pass in this audit systematically added every reachable `__post_init__` to the same call-graph walk the rest of the node collection went through. Each one individually read so far has been clean, but "individually read where noticed" is not the same guarantee as the systematic walk applied to `__init__`/`__new__`.
  2. **`os.open` / DB / Redis runtime-denial coverage.** The v5 runtime defence check (item 4) patched `builtins.open`, `pathlib.Path`'s file methods, `os.makedirs`/`os.remove`/`os.system`, sockets, subprocess, and thread/process starts — but never patched the lower-level `os.open`/`os.fdopen`/`os.read`/`os.write` file-descriptor primitives, nor any DB or Redis client constructor/connection method (no `redis.Redis`, `psycopg`, `sqlite3.connect`, or ORM session entrypoint was named or patched). The repo-wide I/O-primitive grep in Area 3 found no such calls in the scoped source, but the runtime check itself does not independently corroborate that for these specific primitives the way it does for the ones it actually patched.
  3. **Module-global mutation from inside a plain function.** Area 3b's closure-captured-mutable scan finds a nested function mutating a variable its *enclosing function* assigned. It does not look for an ordinary (non-nested) function, anywhere in the 373-file scope, that mutates a *module-level* global object by name via a method call (`SOME_MODULE_DICT.update(...)`) or subscript assignment (`SOME_MODULE_LIST[i] = ...`) from inside its own body. This is a distinct code shape from everything Area 3b's scans (v4 or v5) actually checked, and it was not run.
  4. **Call classification still rests on a manually maintained allowlist for calls it cannot resolve to a live object.** v5 resolved the large majority of call sites to real objects (via type-annotation substitution, owner-class attribute lookup, and local-variable type inference), but a residual set (`opt`, several `self._registry.*`/`self._singletons.*` dict/set-method calls, a handful of `app.planner`/`app.preflight` local computations) is classified by matching the call's literal text against a hand-maintained set of names judged safe by direct reading, not by mechanically resolving each to a live object the way the majority were. "0 unresolved" in the v5 tables means every call fell into *some* bucket of that combined scheme — resolved-by-object or matched-by-allowlist — not that every one was independently proven safe by the same mechanical standard.
