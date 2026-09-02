# Task 38.5 — Risk Register

Every finding from `docs/audits/task-38.5-structural-audit.md`, areas 1–7 (plus new Area 3b). "Cleared" checks (no violation found) are not rows here — they are evidence recorded in the structural audit narrative. Severity rubric is reproduced from `docs/prompts/task-38.5.md` area 8.

**Summary (Task 38.6 harness, updated by Task 38.7's post-evidence correction): 0 Critical discovered · 2 High · 8 Medium · 10 Low.** (v3 was 0/2/5/9; v4 added **M-6**; v5 refined M-6; the honest closeout added **M-7**; Task 38.6 built and ran the harness M-7 called for, narrowing M-7's disposition and adding **L-10** — a real, previously-unrecorded, low-severity typing gap the harness itself found, category F in `docs/audits/task-38.6-assurance-report.md`. Task 38.7 closed **L-10** and, separately, added **M-8** — the static walker's own implicit-protocol-dispatch discovery gap, confirmed by reproducible, non-executed fixture evidence (see M-8 below). "0 Critical discovered" — not "0 Critical" — because the harness's own real, categorized residual (`nodes_unresolved=19`, `calls_unresolved=1032` as of the Task 38.7 Phase B re-run, all accounted for — see M-7/M-8 and the Task 38.7 assurance report) means absence of a Critical finding repo-wide is still not conclusively established, on a narrower basis than before. H-1/H-2 remained open at that point (Task 38.6); nothing here was implemented beyond the harness itself, which is infrastructure, not a fix to any framework. Task 38.8 (Phase C, 2026-08-31) narrowed **M-8** further to **Open, narrowed** — 2 of its 11 named protocol families now have a real, tested, per-site discovery mechanism (see M-8 below); the finding count above is unchanged, since narrowing a disposition does not close it. Task 38.9A (Phase C, 2026-08-31) closed **H-2** — `exchange_adapters` is now wired into `COMPONENT_REGISTRARS` (see H-2 below); of the 2 High findings originally recorded, only **H-1** remained open at that point. Task 38.9B (Phase C, 2026-08-31) closed **H-1** — the false blanket "no framework imports another framework directly" claim is corrected to the narrower, evidenced invariant the repository actually satisfies, backed by a committed regression guard (see H-1 below); **of the 2 High findings originally recorded, 0 remain open.** The "2 High" figure above is unchanged, since it is a total-recorded count, the same convention already established for **10 Low** (unchanged by L-10's own earlier closure). Task 38.10 Phase 0.3 (2026-09-02, documentation and governance only) records **ADR-032**'s human-reviewer authorization of nine exact `EXACT_IDENTITY_POLICY` callable-slot identities — implemented by nothing yet, Phase A pending — and separately corrects the *scope* of **M-8**, whose disposition becomes `Open — taxonomy incomplete; narrowed only within the original 11-family taxonomy` (see M-8 below — Task 38.8's narrowing remains true of the original 11 families it measured, while the mechanisms Task 38.10 Phase 0.2 found outside that taxonomy were never measured by those figures, so the present overall gap is not narrower than first recorded); the finding counts above are unchanged, since correcting a finding's scope neither closes it nor adds a new one, and no harness counter, gate predicate, or `EXACT_IDENTITY_POLICY` entry is changed by that phase.)

---

### H-1 — "No framework imports another framework directly" is false for 14/24 wired frameworks, plus `exchange_adapters`

| Field | Value |
|---|---|
| Severity | **High** |
| Evidence | `app/wiring.py:3`; `docs/prompts/task-38.md:21`. A repo-wide AST scan (production source only, every `.py` file under each framework package) found direct imports of another framework package in **14 of the 24 `COMPONENT_REGISTRARS`-wired frameworks**: `agents, backtesting, execution, learning, market_data, optimization, order_management, paper_trading, performance, portfolio, positions, risk, strategies, trades` (full file list in the structural audit, Area 1). `exchange_adapters` — which is not one of the 24 wired frameworks at all, see H-2 — separately also imports other frameworks directly (`execution`, `trading`); it is additional to, not part of, the 14/24 count. |
| Impact | Anyone relying on the documented "isolation" invariant to reason about blast radius, swap a framework via DI substitution alone, or trust `app/`'s AST boundary test as proof of repo-wide isolation is working from a false premise for 14 of the 24 wired frameworks, plus `exchange_adapters`. |
| Exploit/failure scenario | A future refactor of `risk/` or `order_management/` types, done under the belief that only DI-registered abstractions are depended on externally, silently breaks `execution/`, `backtesting/`, `paper_trading/`, or `strategies/`, which import those modules' concrete types directly — with no test category currently designed to catch it (the AST boundary test only checks `app/`'s own modules). |
| Existing protection | None for the older frameworks. `app/`'s own AST boundary test (`tests/test_app_flow.py::ImportBoundaryTests`) correctly proves isolation for `app/` itself; it makes no claim about, and cannot detect, coupling among the 14 older wired frameworks or `exchange_adapters`. |
| Recommendation (original; superseded, see Disposition) | Correct the claim in `app/wiring.py:3` and `docs/prompts/task-38.md:21` to scope it accurately ("every framework since the DI-only convention was adopted (Tasks 28–38)"), or — as a larger follow-up task — decide whether the older, tightly-coupled trading-domain frameworks should be migrated to the DI-only pattern. Do not implement either here. **Superseded by Task 38.9B's Phase 0 investigation (2026-08-31):** a task-to-framework build-order mapping cross-checked against an empirical backward-only-import scan (56 of 56 cross-framework import pairs point from a later-built framework to an earlier one) found no defensible "DI-only convention adopted at Tasks 28–38" boundary anywhere in the repository — this recommendation's own suggested rescoping was itself unverifiable and is not carried forward as written. The actual corrective action taken is recorded in Disposition below: the claim was corrected to the narrower invariant the repository actually evidences, not scoped by a Tasks-28–38 boundary, and no framework migration was undertaken or found necessary. |
| Disposition | **Closed** — Task 38.9B. Phase A implementation, commit `78b5332197e03777b689794bdd9cbbd4b60e6e77`, corrected the false blanket claim at `app/wiring.py:3` and `docs/prompts/task-38.md:21` and installed a source-controlled regression guard (`tests/test_h1_cross_framework_boundary.py`, 7 tests) proving the corrected, narrower invariant the repository actually satisfies: frameworks are **not** globally import-isolated — legitimate framework-to-framework imports of public domain/value types and `Protocol`/ABC interfaces exist and are not a violation; no framework directly constructs another framework's concrete class, under any reviewed import spelling; the sole reviewed concrete cross-framework runtime type is `trading.engine.TradingEngine`; its runtime importer set is exactly nine frameworks (`exchange_adapters, execution, market_data, order_management, portfolio, positions, risk, strategies, trades`); its runtime references are limited to `resolver.has(TradingEngine)`/`resolver.resolve(TradingEngine)`; and those nine tracked consumers do not directly invoke `TradingEngine.start()`/`.stop()`/`.pause()`/`.resume()`. Phase B evidence, commit `c628a9d5473da3377d7679de1a7fcd5ef687648b` (`docs/audits/task-38.9b-result.json`, schema `38.9b.1`, hash `633ab16e1c85a61c85ca232e53af68c03f1db3aceb087bac53066db5af964b6c`; narrative `docs/audits/task-38.9b-assurance-report.md`, hash `31cafda06e43e9c85507554de5c6eee4d0f000f5bacf2d11133b9f926ac25eaa`), independently regenerated the cross-framework import inventory against the committed Phase A SHA and confirmed: **25** wired frameworks, **26** packages scanned, **203** raw cross-framework import records across **15** importing frameworks (`agents, backtesting, exchange_adapters, execution, learning, market_data, optimization, order_management, paper_trading, performance, portfolio, positions, risk, strategies, trades`); import classification **125** domain/value + **31** Protocol/interface + **9** concrete + **38** TYPE_CHECKING-only = **203**; runtime concrete type set = `{trading.engine.TradingEngine}`; **9** `TradingEngine` runtime import records, **9** `resolver.has` + **9** `resolver.resolve` references, **0** other runtime references, **0** direct concrete construction, **0** direct lifecycle calls; the targeted regression suite (**7 passed**) and full project suite (**944 passed**) both pass; `python -m app.main` exits `0`. H-1 closes because the defect this finding actually named was a **false blanket architectural claim**, not evidence of an unsafe live-execution path requiring a broader migration of the 14 (now 15, including `exchange_adapters`) older frameworks to a DI-only pattern — Phase A replaced the false claim with the narrower, precisely-scoped invariant the repository actually satisfies, and Phase B independently proves that invariant holds, backed by a committed regression guard against future drift. This closes H-1's specific finding only — it does not by itself move the overall `ADR-032` gate off HOLD (see `ADR-032`'s Task 38.9B disposition paragraph): `nodes_unresolved=22`, `calls_unresolved=1092`, and `implicit_dispatch.unresolved_dispatches=6888` remain independently nonzero (unchanged since Task 38.9A's evidence — Task 38.9B performed no audit-harness re-run), and M-8 remains separately `Open, narrowed`. |

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
| Disposition | **Closed** — Task 38.9A, implementation commit `b8ebb23531350d30924e777dfdcbd295311f4f10`. `app/wiring.py` now imports `DefaultExchangeManager`/`register_exchange_adapters` and adds `"exchange_adapters": register_exchange_adapters` to `COMPONENT_REGISTRARS` (with a corresponding `"exchange_adapters.manager"` entry in `_COMPONENT_SERVICE`/`SAFE_SERVICE_KEYS`), making `exchange_adapters` the 25th registered framework — exactly the remediation this finding's own Recommendation named. Confirmed closed by Phase B re-run evidence, commit `384b5486e74a463b78be648590069e569becd95d` (`docs/audits/task-38.9a-result.json`, hash `a1a44b3b793c873a087db21a1e9e4af4e3be0995ba5350f8923a8b3008c6ebc6`; narrative `docs/audits/task-38.9a-assurance-report.md`, hash `0b8a8e83b051fabdde9d43e231c66a50547cbc119e9e8ebe616fcb1162c91424`): `discovery.missing_from_component_registrars=[]` (`exchange_adapters` no longer missing); real dry-run composition `25/25`; `runtime_denial_checks`: `bootstrap_status=SUCCESS`, `preflight_total/passed/failed=25/25/0`, `forbidden_call_observed=None`, `success=True`; the newly discovered `exchange_adapters.engine.DefaultExchangeEngine.start` lifecycle target is under the same defensive, rule-based runtime-denial coverage as every other framework's engine, without being invoked during the real dry-run; full project suite `937 passed`. This closes H-2's specific finding only — it does not by itself move the overall `ADR-032` gate off HOLD (see `ADR-032`'s Task 38.9A disposition paragraph): `nodes_unresolved=22`, `calls_unresolved=1092`, and `implicit_dispatch.unresolved_dispatches=6888` remain independently nonzero, and H-1/M-8 remain separately open. |

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
| Recommendation (Task 38.6, implemented) | Per this closeout: **Task 38.6** built a source-controlled, reusable audit harness (`audit_harness/`, tests and fixtures under `tests/audit_harness/`) covering all four gaps: systematic `__post_init__` call-graph inclusion (implemented — every discovered node's `__post_init__` is walked the same way `__init__`/`__new__` are); `os.open`/`fdopen`/`read`/`write` and DB/Redis/exchange-adapter runtime-denial coverage (implemented — `audit_harness/runtime_denial.py`; DB/Redis genuinely absent from this project's dependencies, reported explicitly rather than omitted; `exchange_adapters` correctly reported present-but-unreachable, H-2); plain-function module-global mutation detection (implemented — `audit_harness/module_state.py`); and an exact-identity policy replacing the text/name allowlist (implemented — `audit_harness/identity.py`, versioned `2026-08-20.1`, three buckets only, no name-pattern fallback). See `docs/audits/task-38.6-assurance-report.md` for the full run. |
| Harness result | `nodes_unresolved=2`, `calls_unresolved=68` (both fully categorized in the assurance report — including third-party `pydantic-settings`/`python-dotenv` internals that fall outside the exact-identity policy's stdlib-only scope, not described as safe; plus a deep stdlib `logging`-internals chain, local project computation, a `cls: type[T]` generic-construction site, an `inspect.getsource` lambda-truncation quirk, and one real narrow typing gap in `strategies/__init__.py`'s `register_strategies(container: object)` annotation). `module_state_unexplained=0`. Runtime denial: `SUCCESS`, `24/24`, paper-only, no forbidden call observed. All 5 negative controls detected on this run (`self_test_failed=false`) — the result is trustworthy per the harness's own contract. |
| Disposition | **Open, narrowed.** The audit-assurance gap this finding names is substantially closed: the process that produced five successive corrections is replaced by a single, source-controlled, tested, re-runnable harness, and the four specifically-named methodological gaps are each closed as detection capabilities. What remains open is the harness's own real, categorized residual (`nodes_unresolved=2`, `calls_unresolved=68`) — not the earlier open-ended "the method might still be missing an unknown class of gap" uncertainty. Per the Gate Rule, a nonzero unresolved count still keeps `ADR-032` at HOLD; this disposition should move to Closed only once a future pass drives both counts to zero (or the residual categories are individually accepted with recorded justification) — not by weakening the identity policy to manufacture a zero. |

---

### M-8 — `StaticWalker` does not discover interpreter-dispatched implicit protocol methods

| Field | Value |
|---|---|
| Severity | Medium |
| Evidence | `audit_harness.trace.StaticWalker`'s own discovery mechanism inventories literal `ast.Call` nodes present in a walked callable's own source (via `_shallow_descendants`) and resolves each one's target through the identity-first, three-bucket scheme. It has no corresponding mechanism for execution the CPython interpreter dispatches implicitly, with no `ast.Call` node anywhere in source, in response to an operator or statement: iteration (`__iter__`/`__next__`, including `for`-loops, comprehensions, and starred unpacking), context managers (`__enter__`/`__exit__`), comparisons (`__eq__`/`__lt__`/etc.), truth testing (`__bool__`, falling back to `__len__`), subscription (`__getitem__`), membership (`__contains__`), hashing (`__hash__`, e.g. on set/dict-key insertion), string formatting (`__format__`), and arithmetic operators (`__add__`/etc.). Property/descriptor access (`obj.attr` invoking a `@property` getter) is the sharpest instance: it is not even an `ast.Call` node at all, only a bare `ast.Attribute` read, so the walker's per-Call-node loop never considers it a candidate call site in the first place. Reproduced directly and repeatedly, without ever executing the reproduction: a small set of non-executed, git-untracked scratch fixtures, each defining a class whose relevant dunder method (`__iter__`/`__next__`, a `@property` getter, `__enter__`/`__exit__`, `__eq__`/`__lt__`, `__bool__`, `__len__`-fallback, `__getitem__`, `__contains__`, `__format__`, `__hash__`, `__add__`) contains a call to `builtins.open` — a member of `FORBIDDEN_IDENTITIES` — was passed through the ordinary syntax that triggers that protocol (a `for`-loop, `with`-statement, comparison operator, `in`/`not in`, an f-string, a set/dict literal, an arithmetic operator, or a bare attribute read) inside a function given to `StaticWalker.walk()`. In every case, across every family tested, the resulting `call_records` contained no entry at all for the embedded `open` call — not `unresolved`, not `forbidden`, simply absent, with no corresponding increment to any reported counter. |
| Impact | This is a gap in the audit method's own discovery reach, not a discovered unsafe path: no currently reachable production call site has been shown to route a forbidden operation through an undiscovered implicit-protocol dispatch. The gap means the harness's `nodes_unresolved=0`/`calls_unresolved=0` condition, if and when a future pass reaches it, would still not by itself prove no forbidden operation is reachable through this class of dispatch — that specific class of execution is outside what the coded predicate's counters can ever reflect, by construction, not merely by current residual size. |
| Exploit/failure scenario | A future (or currently unreviewed) project-owned or third-party class implements one of the protocol methods named above with a body that performs a forbidden operation (file/network/process I/O, a live trade, a live inference call), and that class is passed through the corresponding implicit-dispatch syntax somewhere reachable from `app.main.main`/`app.bootstrap.run_dry_run_bootstrap`. The static walker would report `nodes_unresolved=0`/`calls_unresolved=0` (or any other clean count) with no indication this call site was ever considered, because it was never discovered as a call site to begin with. |
| Existing protection | Partial and complementary, not a substitute: `audit_harness.runtime_denial`'s patching of `builtins.open` and the other named forbidden entry points is a separate, independent mechanism that operates at actual execution time, not at static-analysis time — if a call reachable only through an undiscovered implicit-protocol path were genuinely *executed* during the harness's own paper-only `run_dry_run_bootstrap()` run, the runtime patch would still raise and `forbidden_call_observed` would be non-`None`. This only covers paths actually exercised by that one run's execution, not paths that exist in source but are never triggered during it — it does not make the static gap itself any smaller, only bounds its consequence for whatever code path the runtime check happens to execute. |
| Task 38.8 result (Phase A.1 mechanism + Phase B evidence, 2026-08-31) | Per `docs/prompts/task-38.8.md`'s Option D (ADR-032 Phase 0, 2026-08-24), Phase A.1 (`audit_harness/trace.py`, committed `b338484f8e6e5cd1af1f69260cdb2b044b0db0c5`) mechanizes exactly 2 of the 11 families named above — **context managers** (`__enter__`/`__exit__`/`__aenter__`/`__aexit__`) and **property/descriptor access** (`__get__`/`__set__`/`__delete__`) — via the same identity-first `_resolve_target`/`classify_callable` discipline explicit calls already use, never a name/protocol allowlist. Phase B's real re-run (`docs/audits/task-38.8-result.json`, schema `38.8.0`, hash `7f5ffdf883339fa3e363db8d4a394ba49bb8b0e2416a4e47d7b9790395a7ae53`; narrative `docs/audits/task-38.8-assurance-report.md`; committed `fa66cea8282ac56dc742289cd03272b18b69318a`) found `dispatch_candidates_total=6724` (`syntax_sites_total=10064`), of which **119 resolved** and **6605 unresolved** (`119 + 6605 == 6724`, a genuine partition), plus `resolved_non_descriptor_exclusion=3642` sites soundly proven to dispatch nothing at all and `explicit_path_duplicates=0`. Per method: `__enter__` 0/301 resolved, `__exit__` 0/301, `__get__` 119/6104, `__set__` 0/18, `__aenter__`/`__aexit__`/`__delete__` 0 candidates on this run. The remaining **9 families** — iteration/comprehensions, unpacking, await/async iteration, equality/ordering/arithmetic incl. reflected, truth testing, membership, subscription/assignment/deletion, hashing, formatting incl. `__str__`/`__repr__` fallback — remain entirely unmechanized, reported verbatim in `unsupported_protocol_families`, each requiring its own separately authorized future Phase 0 analysis before any implementation. |
| Task 38.10 Phase 0.2 scope correction (2026-09-02) | While characterizing C-callable constructor boundaries for Task 38.10's `EXACT_IDENTITY_POLICY` authorization question, Phase 0.2 established that **this finding's original 11-family enumeration is incomplete**. At least five further implicit-dispatch mechanisms fall outside that taxonomy entirely — neither mechanized by Task 38.8's Option D nor counted among the 9 known-open families: **(i)** numeric coercion (`__int__`/`__index__`/`__trunc__`); **(ii)** bytes conversion (`__bytes__`); **(iii)** the Python-overridable buffer protocol on CPython 3.12 (`__buffer__`, made overridable from Python by PEP 688 — a mechanism postdating this finding's family list and not Python-reachable on the versions it was written against); **(iv)** C-level duck-typed mapping calls (e.g. the `keys()`/`__getitem__` paths a C constructor invokes internally, producing no `ast.Call` node and not reached by the explicit-call machinery either); **(v)** class-creation hooks (`__set_name__`/`__init_subclass__`/metaclass `__new__`/metaclass `__init__` — note `__set_name__` is **not** `__get__`/`__set__`/`__delete__` and is therefore *not* covered by the mechanized descriptor family); and **(vi)** weakref callbacks (deferred, GC-timed invocation of an arbitrary callable, with no lexical call site any static site enumeration could reach). Evidence: per-slot characterization of the 22 unresolved nodes' `__new__`/`__init__` slots against a harmless marker/counter probe on CPython 3.12.13 (the interpreter of record, `pyproject.toml:6` `requires-python = "==3.12.*"`), run in an isolated process with no repository change. Stated precisely: these mechanisms **were discovered while characterizing C-callable constructor boundaries**, not by a systematic taxonomy review; they **demonstrate that the existing 11-family taxonomy is incomplete**, which corrects the *scope* of this known finding rather than adding a new one; they **do not imply that a reachable forbidden production path has been found** — no such path is claimed, discovered, or implied; they **change no current harness counter**, Task 38.10 Phase 0.3 being documentation-and-governance-only; they **must not be silently folded into an allowlist**, in `EXACT_IDENTITY_POLICY` or anywhere else, and no such folding is authorized; and **future work must decide how to govern and measure them explicitly**, through the same separately-authorized Phase 0 discipline the 9 unmechanized families already require, before any implementation touching them begins. |
| Recommendation | Task 38.8 (Phase 0/A.0/A.1/B, 2026-08-24 through 2026-08-31) was the future task this recommendation anticipated, for the 2 families ADR-032's Option D scoped — implemented via the same identity-first resolution discipline explicit calls already use, never a name/protocol allowlist (see the Task 38.8 result row above). The remaining 9 families still require their own separately authorized future Phase 0 analysis before any implementation, exactly as ADR-032's Task 38.8 Phase 0 paragraph records; no blanket allowlist is recommended or authorized for them. Within the 2 now-mechanized families, driving `unresolved_dispatches` (6605 of 6724 candidates on the Phase B run) toward zero — or individually accepting specific irreducible categories with recorded justification, the same discipline `EXACT_IDENTITY_POLICY` already uses for explicit calls — remains a further, separately scoped future task; Task 38.8 explicitly does not attempt to reduce this residual as part of its own Phase A.1/B/C work. Source-controlled regression coverage proving both the 2-family mechanism (`tests/audit_harness/test_task_38_8_phase_a1_mechanism.py`) and the still-open 9-family boundary (`tests/audit_harness/test_task_38_8_characterization.py`) is committed. |
| Disposition | **Open — taxonomy incomplete; narrowed only within the original 11-family taxonomy.** Task 38.8 replaces the earlier undifferentiated 11-family gap with a real, evidence-backed mechanism for 2 of the 11 families (context managers, descriptors), proven by committed per-site regression tests and a real Phase B re-run — not merely asserted. What remains open is: (a) the 9 families this decision does not mechanize at all, each still exactly the same kind of undiscovered-implicit-dispatch gap this finding originally named, and (b) within the 2 now-mechanized families, a substantial real residual — 6605 of 6724 enumerated dispatch candidates remain unresolved on the same Phase B run, none defaulted safe. Per `ADR-032`'s own rule (Task 38.8 Phase 0, criterion 10 and the gate/policy constraints), a hybrid architecture's per-site evidence may support Closed only for a family it fully covers with zero unresolved sites on the same run — no family reaches zero here (`__enter__`/`__exit__` are 0-of-301 resolved each; `__get__` is 119-of-6104; `__set__` is 0-of-18) — so this disposition cannot move to Closed on this evidence. It should move to Closed, per family, only once a future pass drives that family's own unresolved count to zero (or each remaining category is individually accepted with recorded justification) — the same discipline M-7's own disposition already established for explicit calls — never by weakening `EXACT_IDENTITY_POLICY`, `_resolve_target`, or any per-family resolution logic to manufacture a zero. The 9 unmechanized families remain **Open** outright until each receives its own separately authorized Phase 0 decision and, if adopted, its own Phase A/B evidence. **Task 38.10 Phase 0.3 (2026-09-02) restates this disposition as `Open — taxonomy incomplete; narrowed only within the original 11-family taxonomy`**, on the evidence in the scope-correction row above, because the previous shorthand was ambiguous about *what* had been narrowed. The distinction, explicitly: **(a)** Task 38.8 genuinely narrowed the known gap from 11 completely unmechanized families to 2 mechanized + 9 unmechanized **within the original taxonomy**, and that narrowing is real, evidence-backed, and not retracted; **(b)** Task 38.10 Phase 0.2 subsequently found additional implicit/callback mechanisms **outside** that taxonomy, which the 11-family figures never measured and therefore never narrowed; **(c)** therefore the current overall finding remains **Open**, and "narrowed" is now only a *historical, sub-scope* characterization — true of the original 11 families as of Task 38.8 — never a claim that the full present assurance gap is narrower than when M-8 was first recorded. No per-family disposition changes: the 2 mechanized families keep their per-site evidence, the 9 unmechanized families remain Open outright, and the out-of-taxonomy mechanisms are newly recorded as ungoverned and unmeasured. This correction moves M-8 **further from closure, not nearer**; M-8 is **not closed**, and Task 38.10 Phase 0.3 changes no harness counter, implements no mechanism, and authorizes no allowlist. |

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

### L-10 — `strategies/__init__.py:89`'s `register_strategies(container: object)` is annotated more loosely than the other 23 registrars

| Field | Value |
|---|---|
| Severity | Low |
| Evidence | New finding, Task 38.6 harness (`docs/audits/task-38.6-assurance-report.md` §4.2, category F). `strategies/__init__.py:89` declares `def register_strategies(container: object) -> None:`, where every other one of the 24 `COMPONENT_REGISTRARS` registrars declares `container: Container`. This is why the harness's identity resolution — which resolves `container.register_class(...)`/`.register_singleton(...)`/`.has(...)` everywhere else via the real `Container`/`Resolver` annotation — cannot resolve the 6 equivalent calls inside `register_strategies` the same way; they are correctly reported `unresolved` rather than assumed safe. |
| Impact | Cosmetic/typing-strictness only — `object` is a valid (if loose) supertype annotation, and `container`'s actual runtime value is still the real `ServiceContainer` in every call path; nothing behaves differently. The looseness is purely what makes this one registrar's DI calls unresolvable by the harness's structural, annotation-based mechanism. |
| Exploit/failure scenario | N/A — no behavioral difference; a future contributor relying on the looser `object` annotation for a genuinely different argument type would silently break `register_strategies`, but nothing currently does. |
| Existing protection | None; not needed today given the annotation still accepts what is actually passed. |
| Recommendation | A future task should tighten `strategies/__init__.py:89`'s annotation to `container: Container`, matching the other 23 registrars — closes this specific harness gap and brings the file in line with the rest of the codebase's own convention. Do not implement here. |
| Disposition | **Closed** — Task 38.7, Phase A commit `dcb1ebc6b7fd34e89979fd9adf8ed0d57bc8ac58`. `strategies/__init__.py:89` now reads `def register_strategies(container: Container) -> None:`, importing `core.interfaces.Container` under `TYPE_CHECKING`, matching the other 23 registrars exactly — a pure typing change, no behavior change (the runtime `assert isinstance(container, ServiceContainer)` already enforced the real contract). Confirmed closed by Phase B re-run evidence: `docs/audits/task-38.7-result.json` (hash `bdbe9cffd1b770140af150e2d66a6524e078f17a817f99bb5d1ec771a7731c0b`) shows all three previously-unresolved `registrar:strategies` calls (`container.has`, `.register_class`, `.register_singleton`) now resolve; `docs/audits/task-38.7-assurance-report.md` §8 records the citation. |

---

## Task 39 Gate

**Gate status: INDETERMINATE / HOLD — not the same as a discovered Critical finding.** Per `docs/prompts/task-38.5.md` area 9, the gate is written to block on an open Critical-severity finding. This audit discovered **zero** Critical findings within its verified scope — that fact is unchanged and is restated below with its full evidence. But five successive passes (v1–v5) each found a real gap the previous pass's method could not see, and this closeout pass concludes that pattern has not converged: the trace is a high-confidence bounded trace, not a completeness proof, and it therefore **cannot conclusively establish that no Critical-severity path exists anywhere in the repository** — only that none was found within what it actually walked. **M-7** records this as its own finding rather than leaving it as an implicit caveat. Per this pass's explicit instruction, the correct gate disposition given that fact is **HOLD**, not ALLOWED: Task 39 should not begin until the assurance gap itself is closed (or a deliberate, recorded decision is made to accept it), because "no Critical finding was discovered" and "no Critical finding exists" are different claims, and the gate's own policy is written against the latter.

**The verified coverage evidence, preserved in full (labeled as evidence, not as a completeness proof):** Area 3 (dry-run/live-runtime separation) — 24 independent fresh-container traces, **183** distinct real classes (143 via `resolve()` + 40 found only by AST/entrypoint/mechanism discovery — including 15 `Engine` classes v3 could not see and 8 classes reached only once `core.container`/`core.registry`/`app.planner`/`app.preflight` and `super().__init__()`'s real MRO base were walked as actual targets instead of allowlisted by text), every one classified (78 clean-by-source-scan, 87 inherited-`object.__init__`, 13 dataclass-generated, 5 extension/builtin, **0 unresolved** — but see M-7 gap 1, `__post_init__` coverage). Every one of the **155** unique calls made from registrar bodies, provider closures, `__init__`/`__new__`, dataclass default factories, the documented entrypoint prefix, and the container/registry/planner/preflight machinery itself is classified into one of item 3's **six** buckets — 26 container/registration operation, 121 safe in-process construction, 1 safe in-process domain-state mutation, 5 permitted boundary read, 1 trusted injectable boundary, 1 forbidden-but-unreached-within-verified-scope (**M-6**, `logger.get_logger`), **0 unresolved** (but see M-7 gap 4, the residual allowlist). The module-state inventory (Area 3b) classified all 516 candidates with 0 unexplained *within its scan's own scope* (see M-7 gap 3). A runtime defence check built settings/context normally, then patched every named forbidden-operation surface plus all 33 lifecycle-shaped methods found across the 183 nodes to raise, and `run_dry_run_bootstrap` still returned `SUCCESS` at `24/24` (see M-7 gap 2 — `os.open`/DB/Redis primitives were never patched). 741/741 tests pass; `uv.lock` was not touched by any pass.

**Update — Task 38.6 (harness built, committed at `8fd66ca`, and run):** the source-controlled harness `M-7` called for now exists (`audit_harness/`, tests under `tests/audit_harness/`, committed) and was run against commit `8fd66ca`. Its own machine-readable result (`docs/audits/task-38.6-result.json`, hash `3a48d00cc626c1980b41496ea5c4e3e41e996b2327f6fa044f457f23ac019b82`) and narrative (`docs/audits/task-38.6-assurance-report.md`) supersede the "labeled as evidence, not completeness proof" v5 figures above for Area 3/3b specifically: **205** nodes (**2 unresolved** — `config.settings.Settings`/`pydantic_settings.main.BaseSettings`, a third-party-dependency boundary the exact-identity policy is deliberately scoped not to cover), **1956** calls (**68 unresolved**, fully categorized into six named categories in the assurance report — no forbidden identity established among them, but unresolved is not a claim of safety, it is a claim that identity resolution stopped), module-state candidates **523** (**0 unexplained**), and a real paper-only runtime-denial run (`SUCCESS`, `24/24`, no forbidden call observed). All 5 of the harness's own negative controls were detected (`self_test_failed=false`) before this result was trusted.

**0 Critical findings discovered within verified scope; absence of Critical findings repo-wide is still not conclusively established, on a narrower, harness-backed basis than before.** See `docs/architecture/decisions/ADR-032-structural-audit-gate.md` for the re-evaluated gate decision (still HOLD, with the exact blocker being the harness's own nonzero unresolved counts, not a discovered vulnerability) and `docs/audits/task-38.6-assurance-report.md` for the full run.
