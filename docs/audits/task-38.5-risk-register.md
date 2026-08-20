# Task 38.5 — Risk Register

Every finding from `docs/audits/task-38.5-structural-audit.md`, areas 1–7 (plus new Area 3b). "Cleared" checks (no violation found) are not rows here — they are evidence recorded in the structural audit narrative. Severity rubric is reproduced from `docs/prompts/task-38.5.md` area 8.

**Summary (honest closeout): 0 Critical discovered · 2 High · 7 Medium · 9 Low.** (v3 was 0/2/5/9; v4 added **M-6**; v5 refined M-6's evidence and corrected three other call classifications, no count change; this closeout pass adds **M-7**, recording that the audit-assurance gap itself is a finding, not merely a caveat. "0 Critical discovered" — not "0 Critical" — because the trace's own methodological limits mean the absence of a Critical finding repo-wide is not conclusively established; see M-7. H-1/H-2 and all prior Medium/Low findings are unchanged and still open; nothing here was implemented.)

---

### H-1 — "No framework imports another framework directly" is false for 14/24 wired frameworks, plus `exchange_adapters`

| Field | Value |
|---|---|
| Severity | **High** |
| Evidence | `app/wiring.py:3`; `docs/prompts/task-38.md:21`. A repo-wide AST scan (production source only, every `.py` file under each framework package) found direct imports of another framework package in **14 of the 24 `COMPONENT_REGISTRARS`-wired frameworks**: `agents, backtesting, execution, learning, market_data, optimization, order_management, paper_trading, performance, portfolio, positions, risk, strategies, trades` (full file list in the structural audit, Area 1). `exchange_adapters` — which is not one of the 24 wired frameworks at all, see H-2 — separately also imports other frameworks directly (`execution`, `trading`); it is additional to, not part of, the 14/24 count. |
| Impact | Anyone relying on the documented "isolation" invariant to reason about blast radius, swap a framework via DI substitution alone, or trust `app/`'s AST boundary test as proof of repo-wide isolation is working from a false premise for 14 of the 24 wired frameworks, plus `exchange_adapters`. |
| Exploit/failure scenario | A future refactor of `risk/` or `order_management/` types, done under the belief that only DI-registered abstractions are depended on externally, silently breaks `execution/`, `backtesting/`, `paper_trading/`, or `strategies/`, which import those modules' concrete types directly — with no test category currently designed to catch it (the AST boundary test only checks `app/`'s own modules). |
| Existing protection | None for the older frameworks. `app/`'s own AST boundary test (`tests/test_app_flow.py::ImportBoundaryTests`) correctly proves isolation for `app/` itself; it makes no claim about, and cannot detect, coupling among the 14 older wired frameworks or `exchange_adapters`. |
| Recommendation | Correct the claim in `app/wiring.py:3` and `docs/prompts/task-38.md:21` to scope it accurately ("every framework since the DI-only convention was adopted (Tasks 28–38)"), or — as a larger follow-up task — decide whether the older, tightly-coupled trading-domain frameworks should be migrated to the DI-only pattern. Do not implement either here. |
| Disposition | **Open** |

---

### H-2 — `COMPONENT_REGISTRARS` omits `exchange_adapters`, contradicting its own "all 24, every completed package" claim

| Field | Value |
|---|---|
| Severity | **High** |
| Evidence | `docs/prompts/task-38.md:23`; `app/wiring.py:COMPONENT_REGISTRARS`/`KNOWN_COMPONENT_IDS`. `exchange_adapters/__init__.py:148` defines `def register_exchange_adapters(container: Container) -> None`, a complete Task 17 (Sprint 3) framework, absent from both. |
| Impact | Task 38's dry-run bootstrap does not prove `exchange_adapters`' own DI graph wires, contradicting the "prove the whole system wires" purpose of the framework — the one already-built framework closest to the eventual live broker-adapter path is the one not covered. |
| Exploit/failure scenario | A future change to `exchange_adapters/__init__.py`'s registration logic (e.g. a typo in a constructor-injection type) would go undetected by `python -m app.main`'s 24/24 preflight check, even though that check's entire premise is "if this passes, the whole system's DI graph is sound." |
| Existing protection | `exchange_adapters` has its own unit/integration tests (outside this audit's re-run scope) that would likely catch a registration bug in isolation — but not as part of the composed, whole-system dry run Task 38 promises. |
| Recommendation | A follow-up task should add `"exchange_adapters": register_exchange_adapters` (and a corresponding `SAFE_SERVICE_KEYS` entry) to `app/wiring.py`, updating `KNOWN_COMPONENT_IDS` to 25, and re-verify the 24/24 sanity check becomes 25/25. Do not implement here. |
| Disposition | **Open** |

---

### M-1 — Risk evaluation is advisory-only; nothing enforces a `RiskDecisionRejected`

| Field | Value |
|---|---|
| Severity | Medium |
| Evidence | `risk/manager.py:77-103` (`RiskEvaluationManager.evaluate()` publishes `RiskDecisionApproved`/`RiskDecisionRejected`, returns the decision, enforces nothing); `order_management/engine.py:39-40` docstring: `risk_engine: Optional Risk Engine reference (integration only). Orders are created from an OrderContext, not by calling these.` |
| Impact | If a live-runtime task is built on the current structure without adding enforcement, a rejected `RiskDecision` would have no effect on whether an order is created or submitted. |
| Exploit/failure scenario | A future live order path calls `order_management`'s engine directly from an `OrderContext` without first consulting `risk/`'s decision, because nothing in the current wiring makes that consultation structurally required. |
| Existing protection | None today; currently moot because Area 3 confirms no live order path exists yet (fails closed by absence, not by design). |
| Recommendation | A future live-runtime task must make risk-decision consultation a structural precondition of order submission (e.g. `execution`/`order_management` refusing to proceed without an `APPROVED` `RiskDecision`), not an optional integration reference. Do not implement here. |
| Disposition | Open |

---

### M-2 — No idempotency mechanism for order submission

| Field | Value |
|---|---|
| Severity | Medium |
| Evidence | `order_management/models.py:36` (`client_order_id: str \| None = None`); repo-wide grep for `client_order_id` outside that one line, across `order_management/` and `execution/`, returns zero results. |
| Impact | A retried order intent (e.g. after a timeout) has no mechanism anywhere in committed code to be recognized as a duplicate of a prior submission. |
| Exploit/failure scenario | Once a live-runtime task exists: a network timeout on an order-submission call is retried by a caller, and the same intent is submitted twice with no dedup check in the way. |
| Existing protection | None. |
| Recommendation | A future live-runtime/execution task should use `client_order_id` (or an equivalent correlation key) to detect and reject a duplicate submission before it reaches a real exchange. Do not implement here. |
| Disposition | Open |

---

### M-3 — Order/execution validation is structural only; no notional limit, symbol allowlist, or duplicate-order check

| Field | Value |
|---|---|
| Severity | Medium |
| Evidence | `order_management/validator.py:1-6` (docstring: "checks... for structural consistency (required fields, quantity, price/stop by order type)... performs no risk evaluation... or submission") and `:22-40` (the actual `validate()` body: non-empty symbol, positive quantity, price/stop-price presence by order type — nothing else). |
| Impact | Nothing in the current committed code would reject an order for exceeding a notional limit, targeting a disallowed symbol, or duplicating an already-in-flight order. |
| Exploit/failure scenario | A future live-runtime task wires `execution`'s validator as its only gate, assuming "validated" implies "safe to send," and an oversized or duplicate order reaches a real exchange. |
| Existing protection | None beyond the structural checks named above; `risk/` produces an advisory decision (see M-1) that nothing consults here either. |
| Recommendation | A future task should add notional-limit, symbol-allowlist, and duplicate-detection checks — either inside `order_management`/`execution` or as a mandatory pre-submission gate a live-runtime task cannot bypass. Do not implement here. |
| Disposition | Open |

---

### M-4 — No kill switch / circuit breaker exists anywhere

| Field | Value |
|---|---|
| Severity | Medium |
| Evidence | Repo-wide grep for `kill.switch\|circuit.breaker\|emergency.stop\|halt_trading\|KillSwitch` across all production `.py` files: zero matches. |
| Impact | No mechanism exists today that a future live-runtime task could flip to halt order flow in an emergency. |
| Exploit/failure scenario | Once live, an anomalous condition (a runaway strategy, a bad market-data feed) has no committed halt mechanism to fall back on. |
| Existing protection | None. |
| Recommendation | A future live-runtime task should design and build an explicit kill-switch/circuit-breaker mechanism before any order can reach a real exchange. Do not implement here. |
| Disposition | Open |

---

### M-5 — 1 of 21 registries claiming thread safety has an actual concurrency test

| Field | Value |
|---|---|
| Severity | Medium |
| Evidence | **Denominator**, precisely enumerated: 22 packages contain a `registry.py` (`agents, backtesting, dashboard, learning, memory, model_gateway, monitoring, notification, optimization, paper_trading, performance, portfolio, positions, reporting, scheduler, storage, strategies, trades, workers, workflows, exchange_adapters, core`); `execution, market_data, order_management, risk, app` have no Registry concept at all (confirmed absent, not merely unfound). Of those 22, **21** explicitly state "thread-safe" in their module docstring (`grep -c "thread-safe" */registry.py` → 2 hits each in 21 files; `core/registry.py` is the one exception — it makes no such claim, and its own concurrency safety is instead provided by `core.container.ServiceContainer`'s `RLock`, which wraps all registry access). **Numerator**: a repo-wide grep across `tests/` for `threading.Thread\(\|ThreadPoolExecutor\|concurrent\.futures\|asyncio\.gather\|asyncio\.TaskGroup\|create_task` found exactly **one** match: `tests/test_workflows.py:467-477` (`test_concurrent_registration_is_thread_safe`, 20 real `threading.Thread`s against `workflows`' registry). **Result: 1 of 21** thread-safety-claiming registries has a test proving it. `core.container.ServiceContainer`'s own `RLock` — relied on by all 24 wired frameworks' resolution/registration path — additionally has zero concurrent-access test coverage of its own. |
| Impact | 20 of the 21 registries' documented thread-safety claims are asserted, not verified, by the current test suite; so is `ServiceContainer`'s `RLock` itself. |
| Exploit/failure scenario | A future refactor of any of those 20 frameworks' Registry, or of `ServiceContainer` itself, introduces a real race condition; nothing in the current suite would catch it except `workflows`' own test. |
| Existing protection | The `Lock`/`RLock` usage itself is real and, on inspection, correctly placed in the frameworks spot-checked — this is a test-coverage gap, not a known-broken lock. |
| Recommendation | A future task should add a `workflows`-style concurrent-registration test to each of the other 20 registries, and one for `core.container.ServiceContainer` itself. Full enumeration in `docs/audits/task-38.5-test-gaps.md`. Do not implement here. |
| Disposition | Open |

---

### M-6 — `LoggerFactory.get_logger()` would attach a console handler (and, only if configured, open a file) if ever reached; reachability is an application-level fact, not a structural guarantee

| Field | Value |
|---|---|
| Severity | Medium |
| Evidence | v4's AST call inventory (structural audit Area 3) found `logger.get_logger(...)` at **46 distinct sites** — every one of the 23 `Manager.__init__`s and 23 `Engine.__init__`s across the 24 wired frameworks, e.g. `agents/manager.py:96`: `self._log = logger.get_logger("agents.manager") if logger else None`. `logger` is supplied by every registrar's `_build_manager`/`_build_engine` closure as `resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None`. `core/logging.py`'s `LoggerFactory.get_logger()` calls `self.configure()` on first use. **Corrected in v5 (item 5): this does not necessarily open a file.** Reading `core/logging.py`'s own defaults — `LoggingConfig.console_enabled: bool = True`, `LoggingConfig.file_path: str \| None = None` — a *default*-constructed `LoggerFactory` (`LoggerFactory()`, no `config` argument, which is what a bare `resolver.resolve(LoggerFactory)` would produce if `LoggerFactory` were ever registered via plain `container.register_class`) attaches exactly one `logging.StreamHandler()` (console output) unconditionally; `os.makedirs(...)` and `RotatingFileHandler(...)` (the actual file I/O) execute **only if a caller explicitly sets `LoggingConfig.file_path`**, which is not the default. The v4 version of this finding stated the file-I/O outcome as if it were unconditional — that was inaccurate and is corrected here. A repo-wide grep for `register_logging` across `app/` and all 24 frameworks' production source returns zero call sites, and `LoggerFactory` does not appear among the 143 concrete types resolved across any of the 352 resolve events in the v5 recursive trace — so `resolver.has(LoggerFactory)` is provably `False`, and `logger` is provably `None`, at every one of the 46 call sites, today. A related, independently-confirmed fact (structural audit Area 3b, v5): `core/logging.py`'s own module-level convenience path (`configure_logging()`/free-function `get_logger()`, distinct from the `LoggerFactory.get_logger()` *method* this finding is about) mutates a module-global `_default_factory` via `global` — also confirmed unreached from this entrypoint, for the same reason (only the `LoggerFactory` class, never `configure_logging`/`get_logger`, is imported by any of the 24 registrars). |
| Impact | None today — the guard (`if logger else None`) is structurally never satisfied because nothing wires `LoggerFactory` into the dry-run graph. Even if it were reached with a default configuration, the concrete impact would be a console `StreamHandler` attaching (minor, not silent-file-writing) — actual file I/O requires an additional, separate configuration choice (`file_path`) nothing in the current wiring makes. The gap is that unreachability is true only because no registrar happens to call `register_logging`, not because any type, test, or structural boundary would prevent it — the same "fails closed by absence, not by design" shape already recorded for M-1 through M-4. |
| Exploit/failure scenario | A future task adds `"logging": functools.partial(register_logging, config=...)` (or similar) to `COMPONENT_REGISTRARS`, intending only to make structured logging available — and, as an unplanned side effect, every one of the 46 `__init__` sites now attaches a console handler the moment its `Manager`/`Engine` is constructed during what is still nominally a "dry run" (and, if that future task's `config` sets `file_path`, opens a real file too), with no test in the current suite that would catch a dry-run bootstrap suddenly producing log output or writing to disk. |
| Existing protection | The guard clause itself (`if logger else None`) is real and correctly placed at all 46 sites; `LoggerFactory`'s continued absence from `COMPONENT_REGISTRARS` is the only reason this is Medium, not Critical — same class of protection as M-1 through M-4's "fails closed by absence." |
| Recommendation | If a future task wires `LoggerFactory` into the dry-run composition root, it should decide explicitly whether a console handler attaching during a "dry run" is acceptable, and should not set `file_path` on any `LoggingConfig` used in that path without also auditing for a "no I/O" dry-run guarantee. Do not implement here. |
| Disposition | Open |

---

### M-7 — Audit-assurance gap: Task 38.5's trace cannot conclusively establish absence of a Critical path

| Field | Value |
|---|---|
| Severity | Medium |
| Evidence | Five passes (v1–v5) of the Area 3/3b trace each found something the previous pass's method could not see (pass 2 fixed pass 1's key-vs-concrete-type conflation; v3 fixed pass 2's shared-container singleton hiding; v4 found 15 `Engine` classes v3's invocation-gated provider scan missed; v5 found 8 more nodes and corrected 4 mischaracterized call classifications once the container/registry/planner/preflight machinery was walked instead of allowlisted). That pattern — each stricter pass surfacing something real the last one missed — is itself evidence the method has not converged on exhaustive, and four specific, currently-open methodological gaps remain, independent of any one of them individually rising to Critical: (1) 13 `generated_dataclass_init` nodes' reachable `__post_init__` methods were never systematically added to the call-graph walk the way `__init__`/`__new__` were; (2) the v5 runtime defence check never patched `os.open`/`os.fdopen`/`os.read`/`os.write` or any DB/Redis client constructor or connection method — only the higher-level primitives (`builtins.open`, `pathlib.Path` methods, `os.makedirs`/`remove`/`system`, sockets, subprocess, thread/process starts) were patched; (3) the module-state scan (Area 3b) detects a nested closure mutating its enclosing function's local, and top-level module mutation, but not a plain, non-nested function anywhere in the 373-file scope mutating a module-global object via a method call or subscript assignment from inside its own body; (4) call classification still resolves the majority of calls to a live object, but the residual set that cannot be so resolved (`opt`, several `self._registry.*`/`self._singletons.*` dict/set-method calls, a handful of `app.planner`/`app.preflight` local computations) is classified by matching against a manually maintained, human-judged allowlist of names — "0 unresolved" in every pass's summary table means "0 entries fell outside this combined resolved-or-allowlisted scheme," not "every callable was mechanically proven safe." |
| Impact | The audit's own headline claims of Area 3 completeness (retracted in this closeout pass — see the structural audit's revised Area 3 language) were never fully load-bearing: they described what a bounded, repeatedly-corrected trace found, not a mathematical guarantee that nothing else exists. Task 39 (or any task) proceeding on the strength of "Area 3 proves no forbidden path exists" would be relying on a stronger claim than the evidence supports. |
| Exploit/failure scenario | A Critical-severity path exists in one of the four gap categories above (an `__post_init__` that performs I/O, a DB/Redis client construction the runtime check never exercised, a module-global mutated from a plain function in a way that creates cross-run state leakage, or a call site the allowlist mis-judged safe) and is never surfaced by this audit, because no pass — v1 through v5 — was designed to look there. |
| Existing protection | None structural. The five-pass iteration history itself is evidence each individual gap found so far was Medium-or-below and closed once identified, not evidence the *process* of finding gaps has terminated. |
| Recommendation | Per this closeout: **Task 38.6** should build a source-controlled, reusable audit harness (not another one-off `/tmp` script per pass) covering the four gaps above — systematic `__post_init__` call-graph inclusion, `os.open`/DB/Redis runtime-denial coverage, plain-function module-global mutation detection, and replacing the residual text/name allowlist with resolved callable identities wherever mechanically possible — and rerun the Task 39 gate against it. Do not implement the harness here. |
| Disposition | Open |

---

### L-1 — No dedicated, immutable, append-only audit trail

| Field | Value |
|---|---|
| Severity | Low |
| Evidence | Repo-wide grep for `AuditLog\|audit_log\|audit.trail` finds only unrelated "History" record types (`TradeHistory`, `PositionHistory`, `BacktestHistory`, etc.) — analytical records, not documented or implemented as compliance-grade audit trails. |
| Impact | No attribution/compliance-grade record exists for a future live-runtime task to build on. |
| Exploit/failure scenario | N/A today — no live trading exists to audit. |
| Existing protection | The existing "History" records provide some analytical trail, just not one designed or documented for audit/compliance purposes. |
| Recommendation | A future live-runtime task should design a dedicated audit-log concept if compliance/attribution requirements demand one. Do not implement here. |
| Disposition | Accepted-risk (no live trading exists yet; revisit when a live-runtime task is scoped) |

---

### L-2 — `learning/evaluator.py:75,76,91` — bare `dict` missing type arguments

| Field | Value |
|---|---|
| Severity | Low |
| Evidence | `mypy learning` → 3× `[type-arg]` at those lines. |
| Impact | Cosmetic strict-typing gap; no runtime behavior implication found. |
| Exploit/failure scenario | N/A |
| Existing protection | N/A |
| Recommendation | Add explicit type parameters to the `dict` annotations. |
| Disposition | Open, `baseline: unknown` (no prior record for `learning`'s mypy count) |

---

### L-3 — `strategies/interfaces.py:56`, `strategies/registry.py:90` — a method named `list` read as the builtin type

| Field | Value |
|---|---|
| Severity | Low |
| Evidence | `mypy strategies` → `Function "...list" is not valid as a type [valid-type]` at both lines. |
| Impact | A real annotation ambiguity mypy is warning about; worth a dedicated read to confirm it isn't masking a genuine typing bug. |
| Exploit/failure scenario | N/A confirmed yet — flagged for follow-up per the structural audit's "Unresolved Audit Limitations." |
| Existing protection | N/A |
| Recommendation | Dedicated follow-up read of `strategies/interfaces.py:56` and `strategies/registry.py:90` to confirm intent and, if needed, rename or re-annotate. |
| Disposition | Open, `baseline: unknown` |

---

### L-4 — `agents/manager.py:154,180` — `assignment`/`no-any-return` typing gaps

| Field | Value |
|---|---|
| Severity | Low |
| Evidence | `mypy agents` → `:154` incompatible assignment (`object` vs `DecisionHistory`), `:180` returning `Any` from a function declared to return `AgentOpinion`. |
| Impact | Typed-boundary erosion around a DI-resolved value; no runtime failure evidence found. |
| Exploit/failure scenario | N/A |
| Existing protection | N/A |
| Recommendation | Add an explicit cast or narrower resolution helper at both sites. |
| Disposition | Open, `baseline: unknown` |

---

### L-5 — `strategies/__init__.py:133` — `StrategyFactory` passed where `DefaultStrategyFactory` is declared

| Field | Value |
|---|---|
| Severity | Low |
| Evidence | `mypy strategies` → `Argument 3 to "StrategyExecutionManager" has incompatible type "StrategyFactory"; expected "DefaultStrategyFactory" [arg-type]`. |
| Impact | A real type mismatch in DI wiring code, distinct from the repo-wide `type-abstract`/`attr-defined` pattern. |
| Exploit/failure scenario | N/A — the container's runtime constructor injection tolerates this; it is a static-typing gap, not an observed runtime failure. |
| Existing protection | N/A |
| Recommendation | Widen the constructor parameter's annotation to the abstract `StrategyFactory`, or resolve the concrete type explicitly. |
| Disposition | Open, `baseline: unknown` |

---

### L-6 — `config/settings.py:486` — 13 `call-arg` errors from the missing pydantic mypy plugin

| Field | Value |
|---|---|
| Severity | Low |
| Evidence | `mypy config` → 13× `Missing named argument "..." for "Settings" [call-arg]` at line 486 (`return Settings()` inside `get_settings()`). Root cause confirmed: `[tool.mypy]` in `pyproject.toml` does not configure the pydantic mypy plugin, so mypy cannot see that every field uses `Field(default_factory=...)`. Hundreds of tests construct `Settings()`/call `get_settings()` successfully at runtime. |
| Impact | False-positive-shaped static findings; no runtime bug. |
| Exploit/failure scenario | N/A — confirmed non-bug. |
| Existing protection | Extensive passing test coverage confirms runtime correctness. |
| Recommendation | Configure the pydantic mypy plugin in `[tool.mypy]` (out of scope for this audit — a dependency/config change). |
| Disposition | Accepted-risk (confirmed non-bug; a config change, not a code fix) |

---

### L-7 — `core/container.py:122` — one `redundant-cast` finding

| Field | Value |
|---|---|
| Severity | Low |
| Evidence | `mypy core` → `core/container.py:122: error: Redundant cast to "T" [redundant-cast]`. |
| Impact | Cosmetic; no behavioral implication. |
| Exploit/failure scenario | N/A |
| Existing protection | N/A |
| Recommendation | Remove the redundant `cast(...)` call at that line. |
| Disposition | Open, `baseline: unknown` |

---

### L-8 — No test for a `container_factory` that violates its documented freshness precondition, and no cross-framework same-container isolation test

| Field | Value |
|---|---|
| Severity | Low |
| Evidence | `tests/test_app_flow.py` has no test constructing a `container_factory` that returns a shared/reused container to observe the consequence (Task 38's spec documents this precondition as trusted-but-unenforced, but nothing demonstrates what actually happens if it's violated); no test resolves two different frameworks' managers from the same candidate container to check for accidental cross-framework singleton leakage beyond registration presence. |
| Impact | Two documented-as-out-of-scope edge cases have no observability even at the level of "here's what happens." |
| Exploit/failure scenario | N/A — these are coverage gaps, not known defects. |
| Existing protection | N/A |
| Recommendation | Add both as demonstrative (not defensive) tests in a future task — full detail in `docs/audits/task-38.5-test-gaps.md`. |
| Disposition | Open |

---

### L-9 — 25 lookup-table constants are plain mutable `dict`/`set` literals, not defensively wrapped

| Field | Value |
|---|---|
| Severity | Low |
| Evidence | A **mutable-literal assignment scan** (a targeted AST pass for one specific pattern — bare module-top-level `dict`/`list`/`set` literals — not a claim of a complete module-state inventory; see the structural audit's Area 1 for the scan's stated scope and limitations) across all 24 wired frameworks + `app` + `core` + `trading` + `exchange_adapters` found 384 candidates; 359 are `__all__` export lists (standard convention, confirmed never mutated anywhere via a repo-wide grep for `__all__.append\|extend\|remove\|pop\|insert` — zero hits). The remaining 25, precisely: **22 transition-mapping `dict`s** (21 named `VALID_TRANSITIONS`, one per `state.py`-having package — `agents, backtesting, dashboard, execution, learning, memory, model_gateway, monitoring, notification, optimization, order_management, paper_trading, portfolio, positions, reporting, scheduler, storage, trades, workers, workflows, trading` — plus `exchange_adapters/state.py:50`'s differently-named `_CONNECTION_TRANSITIONS`), **1 `_SIDE_BY_DIRECTION` mapping** (`order_management/factory.py:28`), and **2 validator `set`s** (`order_management/validator.py:16-17`'s `_PRICE_REQUIRED`/`_STOP_REQUIRED`). None is wrapped in `MappingProxyType`/`frozenset`. A follow-up repo-wide grep for mutation-shaped calls on any of these exact names (`.update(`, `.pop(`, `.setdefault(`, `[key] =`, `.add(`) found zero — every one is used strictly as a read-only lookup table in practice. |
| Impact | None observed — nothing mutates these constants anywhere in the current source. The gap is purely defense-in-depth: unlike `app/wiring.py`'s equivalent constants (which are `MappingProxyType`/`frozenset`-wrapped), these ~25 would not raise if some future code accidentally tried to mutate them. |
| Exploit/failure scenario | A future contributor, unaware `VALID_TRANSITIONS` is meant to be a fixed lookup table, adds a line that mutates it at runtime (e.g. inside a bugfix that "patches in" an extra transition) — nothing today would stop that from silently corrupting shared state read by every subsequent call. |
| Existing protection | None structural; the current absence of any mutation site is the only reason this is Low, not Medium. |
| Recommendation | A future task should wrap these ~25 constants in `MappingProxyType`/`frozenset`, matching `app/wiring.py`'s own convention. Do not implement here. |
| Disposition | Open |

---

## Task 39 Gate

**Gate status: INDETERMINATE / HOLD — not the same as a discovered Critical finding.** Per `docs/prompts/task-38.5.md` area 9, the gate is written to block on an open Critical-severity finding. This audit discovered **zero** Critical findings within its verified scope — that fact is unchanged and is restated below with its full evidence. But five successive passes (v1–v5) each found a real gap the previous pass's method could not see, and this closeout pass concludes that pattern has not converged: the trace is a high-confidence bounded trace, not a completeness proof, and it therefore **cannot conclusively establish that no Critical-severity path exists anywhere in the repository** — only that none was found within what it actually walked. **M-7** records this as its own finding rather than leaving it as an implicit caveat. Per this pass's explicit instruction, the correct gate disposition given that fact is **HOLD**, not ALLOWED: Task 39 should not begin until the assurance gap itself is closed (or a deliberate, recorded decision is made to accept it), because "no Critical finding was discovered" and "no Critical finding exists" are different claims, and the gate's own policy is written against the latter.

**The verified coverage evidence, preserved in full (labeled as evidence, not as a completeness proof):** Area 3 (dry-run/live-runtime separation) — 24 independent fresh-container traces, **183** distinct real classes (143 via `resolve()` + 40 found only by AST/entrypoint/mechanism discovery — including 15 `Engine` classes v3 could not see and 8 classes reached only once `core.container`/`core.registry`/`app.planner`/`app.preflight` and `super().__init__()`'s real MRO base were walked as actual targets instead of allowlisted by text), every one classified (78 clean-by-source-scan, 87 inherited-`object.__init__`, 13 dataclass-generated, 5 extension/builtin, **0 unresolved** — but see M-7 gap 1, `__post_init__` coverage). Every one of the **155** unique calls made from registrar bodies, provider closures, `__init__`/`__new__`, dataclass default factories, the documented entrypoint prefix, and the container/registry/planner/preflight machinery itself is classified into one of item 3's **six** buckets — 26 container/registration operation, 121 safe in-process construction, 1 safe in-process domain-state mutation, 5 permitted boundary read, 1 trusted injectable boundary, 1 forbidden-but-unreached-within-verified-scope (**M-6**, `logger.get_logger`), **0 unresolved** (but see M-7 gap 4, the residual allowlist). The module-state inventory (Area 3b) classified all 516 candidates with 0 unexplained *within its scan's own scope* (see M-7 gap 3). A runtime defence check built settings/context normally, then patched every named forbidden-operation surface plus all 33 lifecycle-shaped methods found across the 183 nodes to raise, and `run_dry_run_bootstrap` still returned `SUCCESS` at `24/24` (see M-7 gap 2 — `os.open`/DB/Redis primitives were never patched). 741/741 tests pass; `uv.lock` was not touched by any pass.

**0 Critical findings discovered within verified scope; absence of Critical findings repo-wide is not conclusively established.** See `docs/architecture/decisions/ADR-032-structural-audit-gate.md` for the recorded gate decision (now HOLD) and its rationale, including the two open High findings, the refined M-6, and the new M-7 naming **Task 38.6** — a source-controlled, reusable audit harness closing the four gaps above — as the required follow-up before the gate can be re-evaluated.
