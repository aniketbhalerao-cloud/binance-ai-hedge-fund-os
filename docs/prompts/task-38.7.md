# Task 38.7 — Audit Residual Resolution and Gate Re-evaluation

---

# Sprint 18.7

## Type

Residual-resolution + gate re-evaluation. Inserted between Sprint 18.6 (Task 38.6 — built, committed at `8fd66ca`, and ran the audit-assurance harness; evidence recorded at `e86cca3`) and Sprint 19 (Task 39, which remains blocked until `ADR-032` reaches ALLOWED). **This is a specification-writing pass only: it authors this one file and performs no implementation.** The future implementation task this spec defines drives the harness's own reported 2-node/68-call residual to zero (or to a properly authorized, implemented, and re-run-proven ADR-level policy entry — never a bare acceptance note) and re-evaluates `docs/architecture/decisions/ADR-032-structural-audit-gate.md`. **This is not a guarantee that `ADR-032` reaches ALLOWED.** Driving the residual to zero clears only the counters this task's own remediation work touches; `ADR-032`'s outcome also depends on H-2 (`missing_from_component_registrars=["exchange_adapters"]`) and every other independent gate condition named in Exact Gate Predicate below, none of which this task is authorized to remediate. If any of those remain open, the re-evaluated `ADR-032` stays HOLD and Task 39 stays blocked, even with a fully zeroed residual.

## Scope

Task 38.6 built and committed a source-controlled audit harness (`audit_harness/`, `tests/audit_harness/`) and ran it against commit `8fd66ca`. That run is the current baseline of record (`docs/audits/task-38.6-result.json`, hash `3a48d00cc626c1980b41496ea5c4e3e41e996b2327f6fa044f457f23ac019b82`; narrative in `docs/audits/task-38.6-assurance-report.md`). The harness itself works correctly — its own 16-test suite passes, mypy/ruff are clean, and it is deterministic — but its real run against this codebase reports a nonzero residual that keeps `ADR-032` at HOLD per the Gate Rule Task 38.6 defined. This task's scope is exactly that residual: the 2 unresolved nodes, the 68 unresolved calls (categorized A–F below), and the one sanitized-but-unexplained `builtins.mappingproxy: import failed` entry. Its scope is **not** a rewrite of the harness's architecture — every mechanism named below extends or corrects an existing `audit_harness/` module in place; none replaces Requirement 4's three-bucket identity scheme or Requirement 8's schema.

This task does **not** re-open H-1 or H-2, does not touch `strategies/__init__.py` beyond the one Category F fix named below, and does not re-litigate any Task 38.5 finding other than the M-7 disposition this task's own gate outcome drives.

---

# Objective

`docs/audits/task-38.6-assurance-report.md` §4.2 categorizes all 68 unresolved calls into six named categories (A–F) and explicitly states none of them is a claim of safety — "unresolved" means identity resolution stopped, not that what lies past it is benign. `ADR-032` stays HOLD on that basis today. But the residual counters are not the *only* thing keeping it there in principle, and this spec does not assume they are: `audit_harness/report.py::build_report`'s actual `exit_code` predicate (quoted in full in Exact Gate Predicate, below) checks eight real conditions, not four, and `ADR-032` itself separately records **H-2** (`missing_from_component_registrars=["exchange_adapters"]`) as an open, unremediated finding that the coded predicate does not test at all today. Task 38.7 must not conflate "the residual counters this task can close" with "everything `ADR-032` needs to reach ALLOWED."

Task 38.7 exists to close the residual it is actually scoped to close, the same way Task 38.6 closed M-7's four gaps: by extending the harness's own resolution mechanisms with real, general, source-grounded techniques — never by trusting a name, a package origin, or a human judgment call in place of an identity. Where a residual item turns out to be a real, narrow production-code looseness (Category F) rather than a harness limitation, this task fixes that one line of production code, the same way Task 38.6 found but did not fix `strategies/__init__.py`'s `register_strategies(container: object)` annotation (**L-10**). Where a residual item cannot be closed by any of these means without weakening Requirement 4's identity policy, this task does not close it — it reports the exact remaining blocker. For that specific, named identity, a human reviewer **must first**, in a step preceding any implementation, record an explicit `ADR-032` decision authorizing exactly one new `EXACT_IDENTITY_POLICY` entry for it — this decision is never made retroactively after the entry is already coded. Only once that prior authorization exists may the entry be implemented, individually justified, regression-tested, and proven on a real re-run to leave the affected counter at zero (see Gate Outcome Requirements below). An ADR acceptance — whether recorded before or after implementation — never by itself overrides a nonzero `nodes_unresolved`/`calls_unresolved`/`module_state_unexplained` counter, or any of the other real predicate conditions. A "zero" produced by loosening what counts as resolved is not an acceptable path to ALLOWED under any circumstance this spec authorizes. And even a fully zeroed residual, with every predicate condition satisfied, does not by itself make `ADR-032` ALLOWED while H-2 remains open — see H-2 Reconciliation, below.

---

# Starting Baseline

Every remediation requirement below is measured against this exact baseline — the future implementation task's own re-run must show its work relative to these numbers, never a different starting point:

* **Source:** `audit_harness/` and `tests/audit_harness/` as committed at `8fd66ca`; evidence as committed at `e86cca3`.
* **`nodes_unresolved = 2`:** `config.settings.Settings`, `pydantic_settings.main.BaseSettings` (both `.__init__` unresolved — third-party, no exact-identity-policy match).
* **`calls_unresolved = 68`** (raw `CallRecord` count backing `calls_unresolved`, not the 56-entry deduplicated `calls_unresolved_detail` — Requirement 5 below governs that distinction), categorized in `docs/audits/task-38.6-assurance-report.md` §4.2:

  | Category | Count | Root cause |
  |---|---|---|
  | A | 7 | `pydantic_settings`/`python-dotenv` third-party internals reached from `Settings()`/`load_environment()` |
  | B | 25 | Multi-hop `logging`-module internals reached via `core.logging.LoggerFactory.configure()`/`JsonFormatter`/`StreamHandler`/`RotatingFileHandler` `__init__` chains |
  | C | 19 | Local project computation in `app.bootstrap`/`app.planner`/`app.preflight`/`app.models.BootstrapContext.__post_init__`/`config.settings.active_environment` not currently reachable by the walker's single-hop inference |
  | D | 6 | `core.container.ServiceContainer._build`'s generic `cls: type[T]` construction and its `resolver.resolve()` helper calls |
  | E | 5 | `ServiceContainer.register_instance`'s internal lambda — an `inspect.getsource` fragment-truncation quirk |
  | F | 6 | `strategies/__init__.py`'s `register_strategies(container: object)` — a narrow, real typing gap (**L-10**) |

  7 + 25 + 19 + 6 + 5 + 6 = 68.
* **`self_test_failed = False`**, all 5 negative controls detected, `lifecycle_methods_patched = 33` (matches the fixed `EXPECTED_LIFECYCLE_TARGETS`/`EXPECTED_ENGINE_NODES` baselines in `tests/audit_harness/test_lifecycle_denial_completeness.py`), runtime denial `SUCCESS` at `24/24`.
* **`unimportable_nodes = ["builtins.mappingproxy: import failed"]`** — one node discovered but not importable through `run_audit._load_classes`'s normal `importlib.import_module` + `getattr` path.
* **Gate outcome: HOLD.** `nodes_unresolved=2`, `calls_unresolved=68` — both nonzero.

A future implementation task that reports different starting numbers must explain the delta (a source change since `8fd66ca`/`e86cca3`, or a harness fix already landed) before proceeding — it must never silently substitute a different baseline.

---

# Exact Gate Predicate

This task binds itself to the **real, as-coded** predicate — not an assumed or simplified version of it. `audit_harness/report.py::build_report`, as committed at `8fd66ca`, computes `exit_code` from exactly this boolean:

```python
all_clear = (
    nodes_unresolved == 0
    and calls_unresolved == 0
    and module_state_unexplained == 0
    and runtime_denial_ok
    and not self_test_failed
    and discovery.get("parse_errors_total", 0) == 0
    and module_state.get("parse_errors_total", 0) == 0
    and trace.get("roots_with_error_total", 0) == 0
)
exit_code = 0 if all_clear else 1
```

where `runtime_denial_ok = bool(runtime_denial.get("success", False))` and `runtime_denial.success` (`audit_harness/runtime_denial.py::RuntimeDenialResult.success`) is itself `bootstrap_status == "SUCCESS" and preflight_total == 24 and preflight_passed == 24 and preflight_failed == 0 and forbidden_call_observed is None`; and `self_test_failed = negative_controls_detected != negative_controls_total` (i.e. anything less than 5/5).

**The eight real ALLOWED prerequisites (`exit_code == 0`) are exactly:**

1. `nodes_unresolved == 0`
2. `calls_unresolved == 0`
3. `module_state_unexplained == 0`
4. `runtime_denial_ok` — `bootstrap_status == "SUCCESS"`, `24/24` preflight, `forbidden_call_observed is None`
5. `not self_test_failed` — all 5 negative controls detected
6. `discovery.get("parse_errors_total", 0) == 0` — always `0` today by construction: `discover_register_functions` (`audit_harness/discovery.py`) is a regex scan over already-read text, not an AST parse, and documents that an unreadable `__init__.py` is silently skipped as "not itself a finding" rather than counted as a parse error. This condition is real but permanently trivially true under the current discovery design — a future implementation task must not treat it as evidence discovery has no failure modes, only that this specific field cannot surface one as currently built.
7. `module_state.get("parse_errors_total", 0) == 0` — a real, non-trivial count from `module_state.scan_scope`'s own AST parsing.
8. `trace.get("roots_with_error_total", 0) == 0` — a real count of the 24 fresh-container root traces (`len(tr.roots_with_error)`) that raised during registration/resolution.

**Explicitly NOT part of this predicate, verified by reading `build_report` line by line:**

* **`unimportable_nodes`** (the `builtins.mappingproxy: import failed` entry) — present in the JSON output (nested under `runtime_denial_checks`) but never read by `all_clear`. A nonzero `unimportable_nodes` count does not, today, prevent `exit_code == 0`. See "`builtins.mappingproxy: import failed` — Explicit Treatment" below for how this task must close that gap.
* **`missing_from_component_registrars`** (H-2 — `discovery["missing_from_component_registrars"]`) — present in the JSON output but never read by `all_clear`. `exchange_adapters` remaining absent from `COMPONENT_REGISTRARS` does not, today, prevent `exit_code == 0`. See H-2 Reconciliation below — this task does not close that gap by extending the coded predicate; it closes it by making `ADR-032`'s human-authored ALLOWED decision require H-2's disposition explicitly, on top of `exit_code`.

**Also verified, and enforced by a different mechanism than `exit_code` entirely:** the fixed, non-circular lifecycle-target baseline (33 targets / 22 engine nodes) is not a soft `all_clear` condition at all — `runtime_denial.run_paper_only_denial_check` raises `AssertionError` outright if the patched lifecycle set does not exactly equal `discover_lifecycle_targets()`'s independently discovered set, which would abort the run before any `Report`/`exit_code` is produced. "Lifecycle fixed baselines intact" is therefore a precondition for a report to exist at all, not a ninth `all_clear` clause — this task's own regression tests (`tests/audit_harness/test_lifecycle_denial_completeness.py`) are what actually guard it, as they already do.

`docs/prompts/task-38.6.md`'s Gate Rule ("HOLD unless every required check above passes with zero unresolved, zero unexplained, and every negative control detected") and `ADR-032`'s own re-evaluation narrative are consistent with, but not a verbatim restatement of, this coded predicate — the Gate Outcome Requirements section below defines exactly how this task's own ALLOWED bar composes the coded predicate above with the two conditions it deliberately excludes.

---

# H-2 Reconciliation

`docs/architecture/decisions/ADR-032-structural-audit-gate.md` records H-2 (`exchange_adapters` missing from `app/wiring.py:COMPONENT_REGISTRARS`, independently re-confirmed by Task 38.6's own discovery step — `missing_from_component_registrars=["exchange_adapters"]`) as an open, unremediated finding — not Critical, but real and unwaived. As Exact Gate Predicate above establishes, the coded `exit_code` predicate does not test `missing_from_component_registrars` today, so a fully zeroed Category A–F residual would, by the code alone, produce `exit_code == 0`. This task does not let that code-level fact stand in for `ADR-032`'s actual, human-authored ALLOWED decision:

* **Task 38.7 can drive its 2-node/68-call residual to zero.** That is this task's real, achievable scope, exactly as specified in Remediation Requirements below.
* **The final `ADR-032` result remains HOLD if H-2 — or any other independent gate condition named in Exact Gate Predicate above — remains open**, regardless of what the coded `exit_code` reports. A zeroed residual is necessary but not sufficient for `ADR-032` to move to ALLOWED; H-2's disposition is evaluated separately, by a human reviewer, as part of that re-evaluation.
* **Task 39 stays blocked** until `ADR-032` actually reaches ALLOWED — not until this task's own residual work finishes. Completing every Remediation Requirement below does not, by itself, unblock Task 39.
* **H-2 requires a separate, explicitly authorized remediation task.** Wiring `exchange_adapters` into `COMPONENT_REGISTRARS` would add a 25th framework to the composition root's dry-run bootstrap and its 24/24 preflight check — a change that could affect the live-network safety boundary this repository's entire dry-run/paper-only discipline depends on, and is exactly the kind of change Task 38.6's and this task's own Non-Goals already forbid deciding unilaterally inside an audit-residual task. It needs its own scoped, reviewed task, not a byproduct of this one.

**This task does not silently add H-2 remediation to its own scope.** No Remediation Requirement below touches `app/wiring.py:COMPONENT_REGISTRARS`, `exchange_adapters/`, or `audit_harness/discovery.py`'s diff logic. `missing_from_component_registrars` is read and reported exactly as Task 38.6 left it — this task changes nothing about how it is computed, and does not extend `build_report`'s coded predicate to test it either, precisely so that "H-2 gets fixed" and "H-2 gets gated on" are never conflated with a routine residual-closure task.

---

# Remediation Requirements

Each category gets its own requirement. Every one is a hard requirement — an implementation that leaves any category's mechanism unaddressed (even if the residual count happens to reach zero by coincidence elsewhere) is not a complete Task 38.7. **None of these requirements may be satisfied by adding a name, a module path, a package name, or a text pattern to any kind of allowlist** — every fix is either (a) a genuine, general resolution-mechanism improvement applicable to any future call shaped the same way, or (b) one specific, named, individually-reviewed production-code fix, or (c) an ADR-authorized, individually-listed `EXACT_IDENTITY_POLICY` entry for one specific residual identity that no mechanism can close — implemented and regression-tested, not merely recorded as accepted (see Gate Outcome Requirements).

## 1. Category A — third-party settings identities (7 calls, 2 nodes)

**Root cause:** Requirement 4's source-availability rule (`docs/prompts/task-38.6.md` §4) currently requires inspectable source only for objects whose defining module is in `audit_harness.identity.PROJECT_TOP_LEVEL_PACKAGES`. `pydantic_settings` and `python-dotenv` are installed, pure-Python packages with real, on-disk `.py` source — but because their top-level package name is not in that frozenset, they fall through to the exact-identity policy (which correctly does not list them — they are not dataclass-synthesized, stdlib builtins, or C-extension types) and are reported unresolved.

**Requirement:** Extend `audit_harness.identity`'s source-availability rule so that **any Python callable with genuinely retrievable source (`inspect.getsource` succeeds on real `.py` text) is walked the same way project-owned code is walked — third-party origin is not, by itself, a reason to stop.** This is not "trust third-party code": every call the walker reaches inside `pydantic_settings`/`python-dotenv` internals must still be resolved and classified by the same three-bucket rule, recursively, with no depth cap tied to package origin. A call inside `pydantic_settings` that itself cannot be resolved (e.g. reaches a C-extension boundary, or `pydantic-core`'s compiled Rust core) is still reported `unresolved` or handled by the exact-identity policy on its own merits — this requirement changes *whose source gets walked*, not *what counts as resolved once reached*. `config.settings.Settings`/`pydantic_settings.main.BaseSettings` must end this task in one of exactly three states, each requiring its own evidence, not an assumption: (a) fully resolved via walked source with zero new unresolved calls introduced by the walk, (b) resolved down to a specific, individually-listed exact-identity-policy entry for a genuine C-extension/compiled boundary (e.g. `pydantic_core`'s Rust validators), with its own rationale, or (c) still unresolved with the exact new blocking call site named.

**Constraint:** Do not add `pydantic_settings`/`python-dotenv`/`pydantic_core` to `PROJECT_TOP_LEVEL_PACKAGES` as a special case — that would be exactly the "blanket third-party trust" this task forbids (it would silently exempt those packages' *unwalked* internals from ever being checked again). The fix is a general "walk any retrievable Python source, regardless of package" rule, applied uniformly, not a per-package grant.

**Termination requirement (binds this category specifically, since it is the one that opens recursion into code the harness does not control):** walking third-party source must be a **deterministic fixed-point traversal**, not an unbounded recursive descent:

* **Visited-state/cycle detection** keyed by `(callable identity, specialization)` — the same key shape Category D's call-site specialization uses — so a third-party call graph that recurses (directly or through a cycle across multiple modules) is walked to a fixed point and then stops, never re-walked, never infinitely expanded.
* **Deterministic ordering** of traversal (e.g. sorted by module+qualname at each expansion step) — required by Harness Requirement 1's existing byte-identical-output guarantee, which this extension must not break.
* **No silent truncation.** If a work/recursion budget (depth, node count, or wall-clock — the implementation task's choice, documented) is exhausted before a third-party subgraph reaches a fixed point, that fact is reported explicitly — as a new, named entry in `roots_with_error` (if the exhaustion occurred during a root trace) or as its own explicit HOLD blocker in the assurance report (if it occurred during the static walk) — never as a quietly-shortened result that reports fewer unresolved calls than actually exist.
* Third-party source walking **must not hang** (an unbounded loop with no termination check) **and must not expand without bound** (a recursion depth or node budget with no ceiling) — both are correctness requirements for this extension, not performance tuning.

A regression test (see Regression Test Requirement, Category A) must include a fixture reproducing a cyclic or self-referential third-party-shaped call graph and assert the walker terminates, reaches a fixed point, and reports deterministic output on repeated runs.

## 2. Category B — multi-hop logging identities (25 calls)

**Root cause:** `audit_harness.trace.StaticWalker`'s local-variable type inference (Requirement 4's "local-variable type inference" mechanism) currently resolves a single hop — e.g. `logger = logging.getLogger(name)` lets `logger.setLevel(...)` resolve because `logging.getLogger`'s return type is known — but does not propagate that inferred type through a second assignment or a chained call (`handler = self._build_handlers()[0]; handler.setFormatter(...)`, or `console.setFormatter(...)` where `console` comes from a list comprehension over `logging.StreamHandler()` results). All 25 sites are inside `core.logging.LoggerFactory.configure()`/`_build_handlers()` or `JsonFormatter`/`logging.StreamHandler`/`logging.handlers.RotatingFileHandler`'s own `__init__` chains — real CPython `logging`-module methods, not project code, unreached from production per M-6 (`LoggerFactory` is never in `COMPONENT_REGISTRARS`) but still required to resolve for the gate.

**Requirement:** Extend local-variable type inference to be **transitive across chained assignment, list/comprehension element type, and multi-hop attribute access** — the type inferred for a local at one statement must propagate to any later local it is assigned into or subscripted from, within the same function body, to at least the same depth as Task 38.5 v5's parameter-annotation substitution already reaches. Combined with Requirement 1 above (or independently, since `logging` is stdlib, already project-adjacent via the existing stdlib-builtin exact-identity-policy path), every one of the 25 sites must resolve to a real `logging`/`io` stdlib identity and be classified via the exact-identity policy (each new entry individually listed with its own rationale — `logging.Handler.addFilter`, `logging.StreamHandler.setFormatter`, `io.text_encoding`, etc. are not one blanket "logging module" grant) or via walked source where the target is pure Python.

**Constraint:** This requirement extends the walker's inference reach — it does not add a "trust anything under `logging.*`" rule. A future call into `logging` internals the extended inference still cannot trace must remain unresolved, exactly as any other unreachable identity would.

## 3. Category C — local/container type inference (19 calls)

**Root cause:** 19 sites are pure local computation already inside source-inspected project code (`app.bootstrap.run_dry_run_bootstrap`, `app.planner._plan`, `app.preflight.run`, `app.models.BootstrapContext.__post_init__`, `config.settings.active_environment`/`Environment.from_str`) — `dict`-of-`list().append()` chains keyed by a subscript expression (`dependents[dependency.depends_on].append`), `os.getenv(...)` calls whose return type the walker does not currently model, and simple string-method chains (`value.strip().lower()`) on an already-typed local.

**Requirement:** Extend the walker's local-variable/parameter type inference to cover: (a) **subscript-target chains** — `container_expr[key_expr].method(...)` resolves `container_expr`'s element type from its own declared/inferred type (e.g. `dict[str, list[X]]`'s value type is `list[X]`) and then resolves `.method` against that; (b) **a small, explicit, versioned table of stdlib-function return types** for the specific functions this residual actually calls (`os.getenv` → `str | None`), added to `audit_harness.identity` the same way `EXACT_IDENTITY_POLICY` is versioned and individually justified per entry — not a general "trust os.*" rule; (c) **flow-sensitive narrowing of a `str | None`-typed local before resolving a chained string method.** `config.environment.Environment.from_str(value: str | None)` is the concrete case this residual contains: `if value is None: return cls.DEVELOPMENT` executes first, and only the code path reaching `normalized = value.strip().lower()` is the one where `value` has already been narrowed from `str | None` to `str` by that early-return guard. The walker must recognize this exact narrowing shape (an `is None` check followed by an unconditional `return`/`raise` on the `None` branch) and track the narrowed type for the remainder of the enclosing block — resolving `.strip()`/`.lower()` to `str.strip`/`str.lower` only because the guard makes that sound, not by assuming the non-`None` member of a union without evidence. A `str | None` local used in a chained-method call **without** such a preceding guard must remain unresolved (or be reported as a new finding if the call would be unsound at runtime) — this mechanism proves narrowing, it does not blanket-assume the "obviously intended" branch of any union type; (d) **chained-method inference on an already-narrowed/already-resolved local** (`value.strip()`'s return type is `str`, so `.lower()` on that result resolves too, once (c) has established `value: str`). Every one of the 19 sites must end in `project_source_available` (already-walked project code, once reachable) or a specific new stdlib exact-identity-policy entry — never a bulk exemption for "the composition/bootstrap layer."

## 4. Category D — generic `cls: type[T]` substitution (6 calls)

**Root cause:** `core.container.ServiceContainer._build(self, cls: type[T], resolver: Resolver) -> T` constructs `cls(**kwargs)` where `cls` is a generic type parameter, not one concrete identity — there is no single "the type `_build` constructs," so identity-first resolution has nothing fixed to resolve to. `resolver.resolve()` inside the same method has the same shape (`Resolver.resolve` is a `Protocol` method, not one concrete implementation).

**Requirement:** Extend the walker with **call-site specialization**: instead of trying to resolve `cls`/`resolver` as a single generic identity inside `_build`'s own body, the walker must, for every actual call into `_build(cls=X, resolver=Y)` it discovers elsewhere in the trace (from `register_class`'s stored provider, from `create()`, from any other reachable call site), re-walk `_build`'s body once per distinct concrete `X`/`Y` pair with `cls`/`resolver` locally substituted to that real, known type for that specialization — the same principle Requirement 4's existing "parameter-annotation substitution" already applies to typed parameters, extended to also substitute from a caller's *known concrete argument*, not only its static annotation. Every specialization must independently resolve `cls(**kwargs)` to a real constructor call on the real class passed at that site, and `resolver.resolve(...)` to `ServiceContainer.resolve` (the only concrete `Resolver` implementation the codebase registers). A `_build` call reached with a `cls`/`resolver` value the walker cannot pin to one concrete type at that call site (e.g. a truly dynamic value) remains unresolved for that specific specialization, named explicitly — not silently merged into an already-resolved specialization's result.

## 5. Category E — lambda/source extraction (5 calls)

**Root cause:** `ServiceContainer.register_instance`'s `lambda _resolver: instance` (core/container.py) — `inspect.getsource` on this specific lambda object returns a source fragment that omits the enclosing `self._registry.register(...)` statement, a documented CPython quirk affecting some lambda argument positions (lambdas passed as a non-final positional/keyword argument inside a multi-argument call on the same line as other code). The walker cannot recover the lambda's real body/closure context from that fragment.

**Requirement:** Do not rely on `inspect.getsource(lambda_obj)` in isolation for any lambda. Instead: locate the lambda's enclosing function via `lambda_obj.__qualname__` (already available), retrieve **that enclosing function's full source** the same way any other project-owned callable's source is retrieved (Requirement 4's existing `project_source_available` path — this is not a new mechanism, just applying the existing one at the right scope), parse it with `ast`, and match the specific lambda `ast.Lambda` node by its `lineno`/`col_offset` against `lambda_obj.__code__.co_firstlineno` (and, if more than one lambda shares a line, by argument-count/body-shape disambiguation). Walk the matched AST node directly rather than re-invoking `inspect.getsource` on the lambda object itself. This closes the specific, named quirk — it must not become a blanket "any lambda is trusted" rule; a lambda whose enclosing function cannot itself be source-located remains unresolved exactly as before.

## 6. Category F — `register_strategies(container: object)` typing (6 calls)

**Root cause:** `strategies/__init__.py:89`'s `register_strategies(container: object) -> None` is the one registrar of the 24 wired frameworks annotated `object` instead of `Container` (compare `agents/__init__.py`'s `register_agents(container: Container) -> None`). This is genuinely a narrow production-code typing gap Task 38.6 found and recorded as **L-10** in `docs/audits/task-38.5-risk-register.md` — not a harness limitation. The function body immediately does `assert isinstance(container, ServiceContainer)` and then calls `container.register_class(...)`/`.register_singleton(...)`/`.has(...)` exactly like every other registrar; only the *declared parameter type* differs, which is exactly what the identity-first mechanism needs to resolve those calls the way it does everywhere else.

**Requirement:** Fix the one-line production annotation: `register_strategies(container: object) -> None` → `register_strategies(container: Container) -> None`, importing `core.interfaces.Container` (or `core.container.ServiceContainer`, matching whichever the other 23 registrars use — confirm via `agents/__init__.py` or equivalent before choosing) at module scope the same way every sibling registrar already does. This is a pure typing change — the runtime `assert isinstance(container, ServiceContainer)` already enforces the real contract; the annotation was simply never tightened to match. No behavior changes. This annotation fix is part of Phase A (the source/tests commit, see Two-Phase Provenance below); `docs/audits/task-38.5-risk-register.md`'s **L-10** disposition is updated separately, in Phase B, once the re-run confirms Category F's calls actually resolve — it is not closed in the same commit as the code change itself.

**Constraint:** This is the one production-code file this task may touch outside `audit_harness/`/`tests/audit_harness/`/`docs/`. No other line of `strategies/__init__.py`, and no other registrar, may be modified.

---

# No Allowlists, No Blanket Trust, No Weakened Gate

Binding across every requirement above, restated because it is the one way this task could fail silently:

* **No name/text allowlist of any kind** — not a package name, not a module prefix, not a function-name pattern, not a "looks safe" heuristic — may be added anywhere in `audit_harness/` to convert an unresolved call into a resolved one. Every closure above is either a general mechanism (source retrieval, type inference, call-site specialization, AST-based lambda location) applicable to any future call of the same shape, or an individually-listed `EXACT_IDENTITY_POLICY` entry with its own rationale, or the one named production-code fix (Category F).
* **No blanket third-party trust.** Category A's fix walks real third-party source under the same rules as project source — it does not exempt `pydantic_settings`/`python-dotenv` from ever being checked, and it does not extend to any other third-party package by association.
* **No call is ever silently dropped or ignored.** A call the extended mechanisms still cannot resolve after this task's work remains in `calls_unresolved`, reported exactly as before — this task does not add a new "ignored" or "assumed safe" bucket alongside the existing four categories in `audit_harness.identity.Category`.
* **No weakening of the Gate Rule.** `docs/prompts/task-38.6.md`'s Gate Rule (HOLD unless zero unresolved/unexplained and every negative control detected) is unchanged by this task. This task's own Gate Outcome section (below) is that same rule, not a relaxed version of it.

---

# Regression Test Requirement

The future implementation task must add, per category, a regression test in `tests/audit_harness/` proving the specific mechanism now resolves that category's shape and does not silently over-resolve something it should not:

1. **Category A** — a fixture (or a direct assertion against the real `config.settings.Settings`) proving a third-party call previously unresolved now resolves via walked source or a newly-added, individually-named exact-identity-policy entry; a negative case proving a genuinely unresolvable third-party call (e.g. a fixture reaching a fabricated C-extension stand-in) still reports `unresolved`; and a cyclic/self-referential third-party-shaped fixture proving the fixed-point traversal terminates, is deterministic across repeated runs, and reports any budget exhaustion explicitly rather than truncating silently.
2. **Category B** — a fixture exercising a two-hop local-variable chain (`x = f(); x.g().h()`) proving the walker's transitive inference now resolves the second hop, plus confirmation that all 25 real `core.logging`-chain sites in the live trace resolve.
3. **Category C** — a fixture exercising a subscript-target chain (`d[key].append(...)`), one covered stdlib-return-type case (`os.getenv`), and a flow-sensitive `str | None`-narrowing case matching `Environment.from_str`'s exact `if value is None: return ...` guard shape (plus a negative case: a `str | None` local used in a chained-method call with **no** such guard, asserting it stays unresolved), each proving resolution; confirmation that all 19 real sites resolve.
4. **Category D** — a fixture registering two different concrete classes through `ServiceContainer.register_class`/`create()` and asserting the walker produces two distinct, correctly-specialized resolutions of `_build`'s `cls(**kwargs)` — not one merged/generic result — plus a case where `cls` truly cannot be pinned at a call site, asserting that specific specialization stays unresolved.
5. **Category E** — a fixture reproducing the exact `inspect.getsource`-truncation lambda shape (a lambda as a non-final argument in a multi-argument, single-line call) and asserting the AST-based enclosing-function lookup resolves it, plus a case proving a lambda whose enclosing function itself has no retrievable source still reports unresolved.
6. **Category F** — a regression test asserting `strategies.register_strategies`'s parameter annotation is `Container` (not `object`), and that the harness's own call-resolution for `registrar:strategies`'s three call sites (`container.has`, `.register_class`, `.register_singleton`) succeeds identically to every other registrar.

All **16** existing harness tests (`tests/audit_harness/`, per Task 38.6's committed suite) must continue to pass unmodified in intent — a test may be extended, but none of the 16 existing behavioral guarantees (determinism, fresh-container isolation, lifecycle-completeness's fixed non-circular baseline, discovery completeness, false-negative self-test, the three safe-failure-sanitization modes, the five negative controls) may be weakened or removed to make room for the new category tests. The full harness suite after this task must be **16 + (this task's new tests)**, not a replacement count.

---

# Machine-Readable Unresolved-Detail Reconciliation

`docs/audits/task-38.6-assurance-report.md` §4.2 already documents that `calls_unresolved` (raw `CallRecord` count, 68) and `calls_unresolved_detail` (deduplicated `f"{site} :: {callee}"` strings, 56) differ by design — several call sites are reached and recorded more than once by the walker's fixed-point traversal. This task's machine-readable output must make that reconciliation itself verifiable, not just narratively asserted:

* `audit_harness/run_audit.py`'s trace dict must add a `calls_unresolved_detail_multiplicity` field: for every distinct deduplicated site string in `calls_unresolved_detail`, its exact raw occurrence count (e.g. `{"...self._registry.register": 5, ...}`), such that `sum(calls_unresolved_detail_multiplicity.values()) == calls_unresolved` is a directly checkable invariant on the JSON output itself, not something a reader has to re-derive from the raw trace.
* A regression test in `tests/audit_harness/` asserts that invariant holds on every real run — not only on a fixture.
* This field is additive to the existing schema (`docs/audits/task-38.6-result.json`'s schema `38.6.0`) — bump `schema_version` to `38.7.0` in `audit_harness/report.py` for this addition, and document the bump (old field set plus the one new field, nothing removed) in the assurance report's schema section.

---

# `builtins.mappingproxy: import failed` — Explicit Treatment

**Root cause, established for this spec:** `type(object.__dict__)` (and any class's own `__dict__`) is CPython's internal `mappingproxy` type, whose own `__module__`/`__qualname__` metadata reads `"builtins"`/`"mappingproxy"` — but `mappingproxy` is **not** actually an attribute of the `builtins` module (`hasattr(builtins, "mappingproxy")` is `False`); the only public, importable path to that exact type object is `types.MappingProxyType`. The harness's own discovery step picked up this type as a "node" (almost certainly via walking a class's `__dict__`-typed value somewhere in module-state or class-attribute-type inference) and produced the qualname `"builtins.mappingproxy"` from its raw `__module__`/`__qualname__`, which `run_audit._load_classes`'s `importlib.import_module(mod_name); getattr(mod, cls_name)` path then correctly, safely fails to import — proving Category-2's safe-failure sanitization (from the prior Phase A patch) works on a real, naturally-occurring case, not only a fixture.

**Requirement:** This task must resolve `builtins.mappingproxy` in exactly one of two ways, each fully specified — it must not remain a silently-accepted "known quirk" with no disposition:

1. **Fix the qualname resolution.** Extend `audit_harness.identity.module_and_qualname` (or the discovery step that produced this node) to special-case types whose real, importable location differs from their raw `__module__`/`__qualname__` metadata — specifically, detect `mappingproxy` and resolve it to `types.MappingProxyType` for both the node's reported qualname and its `_load_classes` import attempt, then classify it via the existing exact-identity-policy path (`types.MappingProxyType` is a recognized, versioned stdlib/extension type per Requirement 4's third category) with its own individually-listed rationale. This is the preferred resolution: it turns a false "unimportable" into a correctly-resolved stdlib identity.
2. **If (1) is not adopted**, this task must instead explain, in the assurance report, *why* `mappingproxy` is discovered as a node at all — trace the exact discovery path that produced it — and either (a) show that path does not actually require this node to be importable/lifecycle-checked (in which case exclude it from `unimportable_nodes`'s gate-relevant meaning, with the harness's own code and a regression test proving the exclusion is principled, not a name-based skip), or (b) leave it in `unimportable_nodes` and treat a nonzero `unimportable_nodes` count as its own named HOLD blocker in the Gate Outcome section below, exactly like a nonzero `nodes_unresolved`/`calls_unresolved`.

Whichever path is taken, a regression test must assert the chosen behavior against the real `mappingproxy` case (not a synthetic stand-in), and the assurance report must state the resolution explicitly — "resolved via `types.MappingProxyType`" or "excluded because X, proven by test Y" or "counted as a HOLD blocker" — never left as an unexplained residual line item.

---

# Gate Outcome Requirements

`ADR-032`'s re-evaluation at the end of this task composes three layers — the coded predicate (Exact Gate Predicate, above), the `unimportable_nodes` gap that predicate does not currently close, and H-2 (H-2 Reconciliation, above). **Every layer must hold for ALLOWED; none of them is optional, and none of them is a "four counters" simplification:**

* **Layer 1 — the coded predicate.** All eight conditions in Exact Gate Predicate must hold on the same run: `nodes_unresolved == 0`; `calls_unresolved == 0`; `module_state_unexplained == 0`; `runtime_denial_ok` (`SUCCESS`, `24/24`, no forbidden call observed); `not self_test_failed` (5/5 negative controls); `discovery.parse_errors_total == 0`; `module_state.parse_errors_total == 0`; `roots_with_error_total == 0`. These are non-negotiable: **no ADR text, reviewer sign-off, or accepted-risk note ever substitutes for a nonzero value in any of the eight.**
* **Layer 2 — `unimportable_nodes`.** Because Exact Gate Predicate establishes that the coded `all_clear` does not test this field today, this task must close the gap by one of the two paths already specified in "`builtins.mappingproxy: import failed` — Explicit Treatment": either (preferred) resolve `mappingproxy` via `types.MappingProxyType` so `unimportable_nodes` is naturally empty and no code change to `build_report` is needed, or, if any entry remains, extend `build_report`'s `all_clear` to add `unimportable_nodes == []` (or an equivalent count) as a real, coded ninth condition — never leave a nonzero `unimportable_nodes` silently outside the predicate while calling the residual "closed."
* **Layer 3 — H-2, and any other independent finding.** Per H-2 Reconciliation, `missing_from_component_registrars` is deliberately **not** added to the coded predicate by this task. Instead, `ADR-032`'s own re-evaluation must state explicitly whether `missing_from_component_registrars == []` — and it must not report ALLOWED while that list is nonempty, regardless of what Layers 1–2 show. The same applies to any other independently-tracked open finding (e.g. H-1) that `ADR-032`'s narrative already carries — this task does not get to declare those irrelevant to its own gate outcome.
* **The ADR-authorized `EXACT_IDENTITY_POLICY` entry path (Layer 1 only) requires a decision *before* implementation, never after.** If, during work on any category, a specific, named identity turns out to be genuinely irreducible by every mechanism this spec provides, work on *that one identity* stops. A human reviewer must first record, in `ADR-032`, an explicit, individually-named authorization — module+qualname, the specific reason no mechanism resolves it, and the accepting reviewer — *before* any code implementing that entry is written. Implementing an `EXACT_IDENTITY_POLICY` entry and then asking for retroactive Phase B sign-off is not a valid sequence under this spec. Once (and only once) that prior authorization exists, the entry may be implemented, individually justified in code, regression-tested, and proven by a real re-run to leave the affected counter (`nodes_unresolved` or `calls_unresolved`) at zero — all four of those, still required, still in Phase A/Phase B order, exactly as Two-Phase Provenance defines. A bulk "the remaining residual is accepted" ADR note, or any authorization recorded after the fact, does not satisfy this path.
* **Otherwise: HOLD**, with the future implementation task's report naming **the exact blocker** at whichever layer is unmet — which node, which call (by `site :: callee`), which category, which unimportable node, or H-2/another named finding — exactly as `docs/prompts/task-38.6.md`'s Gate Rule already requires. A partial success (e.g. Layers 1–2 fully closed but H-2 still open) is reported as HOLD, naming H-2 as the sole remaining blocker, not rounded up to ALLOWED.

---

# Preserved Invariants

Unchanged by this task, and the future implementation task's re-run must prove each still holds, not merely assume it:

* **Paper-only runtime denial.** Every mechanism above operates only on the harness's own static analysis and its existing paper-only bootstrap check (`app.bootstrap.run_dry_run_bootstrap` under full patching). No requirement in this task authorizes a real network, database, Redis, or exchange connection, live trade, or live inference call at any point, in the harness's own test suite or its real run.
* **5/5 negative controls.** All five negative controls (Requirements 7's fixtures, per Task 38.6) must continue to be detected on every run, including this task's re-run. `self_test_failed` must remain `False`.
* **33 lifecycle targets / 22 engine nodes, non-circularly.** `tests/audit_harness/test_lifecycle_denial_completeness.py`'s `EXPECTED_LIFECYCLE_TARGETS`/`EXPECTED_ENGINE_NODES` fixed baselines are not recalculated or replaced by this task's work; if any category fix changes the traced node/lifecycle count, the fixed baselines are updated deliberately, with review, in the same change — never silently regenerated from the harness's own output.

---

# Two-Phase Provenance

The future implementation task follows the same two-phase discipline this repository already used for Task 38.6 (`8fd66ca` then `e86cca3`) — a **code/tests phase**, committed and verified first, then an **evidence phase**, generated only after re-running against that committed code and committed separately. No deliverable of one phase may be committed alongside a deliverable of the other. One category (Categories A–E) may additionally require a phase that precedes Phase A entirely:

* **Phase 0 — reviewer-decision step (only if a category needs it).** If, and only if, a specific named identity is found genuinely irreducible by every mechanism Remediation Requirements 1–5 provide, implementation on that one identity stops and a human reviewer records an explicit `ADR-032` authorization for one new `EXACT_IDENTITY_POLICY` entry — module+qualname, the reason, the accepting reviewer — **before** Phase A's code for that entry is written (see Gate Outcome Requirements). Phase 0 produces one `ADR-032` edit, standing alone, not bundled with any Phase A or Phase B deliverable. Categories with no irreducible identity skip Phase 0 entirely.
* **Phase A — source/tests commit.** Contains, and contains only: the `audit_harness/` mechanism extensions (Remediation Requirements 1–5, including any Phase-0-authorized `EXACT_IDENTITY_POLICY` entry, and the `mappingproxy` resolution), the schema bump, the new regression tests (Regression Test Requirement), and the one-line `strategies/__init__.py` annotation fix (Remediation Requirement 6). No evidence document, JSON result, risk-register disposition change, or `ADR-032` re-evaluation is part of Phase A.
* **Phase B — evidence commit, after rerun.** Produced strictly after Phase A is committed and the harness is re-run against that commit. Contains, and contains only: the new evidence artifacts (named exactly below), `docs/audits/task-38.5-risk-register.md`'s **L-10** disposition update (closed, citing the Phase A fix and the Phase B re-run that confirms Category F's calls actually resolve), and `docs/architecture/decisions/ADR-032-structural-audit-gate.md`'s full re-evaluation (Layers 1–3, per Gate Outcome Requirements). L-10 is **not** closed in the same commit as the `strategies/__init__.py` fix — its disposition update belongs to Phase B because it depends on evidence that does not exist until the harness has actually been re-run against the fix.

---

# Deliverables

This task (the spec) produces exactly one file: `docs/prompts/task-38.7.md`.

The **future** implementation task this spec defines produces, split by phase:

**Phase 0 (reviewer decision, only if a category needs it):**

* An `ADR-032` edit recording one explicit, individually-named `EXACT_IDENTITY_POLICY` authorization — module+qualname, reason, accepting reviewer — for exactly one irreducible identity, if and only if Remediation Requirements 1–5 turn up one. Nothing else changes in this step; it does not touch code, tests, or any other document. Skipped entirely if no category needs it.

**Phase A (source/tests commit):**

* Extended `audit_harness/identity.py`, `audit_harness/trace.py` implementing Remediation Requirements 1–5 (source-availability extension, transitive local-variable inference, subscript/stdlib-return-type/flow-sensitive-narrowing inference, call-site specialization, AST-based lambda location) plus the `mappingproxy` resolution (whichever path is chosen), including the fixed-point traversal termination controls (visited-state/cycle detection, deterministic ordering, no silent truncation), plus any Phase-0-authorized `EXACT_IDENTITY_POLICY` entry (never implemented without a prior Phase 0 record).
* `audit_harness/run_audit.py`, updated to add the `calls_unresolved_detail_multiplicity` field to the trace dict, and to report any recursion/work-budget exhaustion into `roots_with_error` or as an explicit blocker, per the Termination requirement.
* `audit_harness/report.py`'s schema bumped to `38.7.0` with the new `calls_unresolved_detail_multiplicity` field, and, **only if any `unimportable_nodes` entry remains after the `mappingproxy` resolution work** (Layer 2, Gate Outcome Requirements), `all_clear` extended to add `unimportable_nodes == []` (or an equivalent count) as a real, coded ninth condition — not merely narrated as a blocker while the code stays silent on it. `build_report` is **not** otherwise touched, and specifically never extended to test `missing_from_component_registrars` (H-2 stays out of the coded predicate — see H-2 Reconciliation).
* The one-line `strategies/__init__.py` fix (Remediation Requirement 6) — no other line of that file, and no other registrar, touched.
* New regression tests per category (Regression Test Requirement above), including the Category A termination fixture and the Category C flow-sensitive-narrowing fixture, added to `tests/audit_harness/`, with all 16 pre-existing tests still passing unmodified in intent.

**Phase B (evidence commit, after rerun):**

* `docs/audits/task-38.7-result.json` — the fresh, canonical JSON result of re-running the harness against the Phase A commit, schema `38.7.0`. This is a **new file**, named exactly `task-38.7-result.json` — it never overwrites, replaces, or is written to `docs/audits/task-38.6-result.json`, which remains exactly as committed at `e86cca3`, the historical record of the `8fd66ca` run under schema `38.6.0`.
* `docs/audits/task-38.7-assurance-report.md` — the narrative report, named exactly `task-38.7-assurance-report.md` (a new file, not an edit to `task-38.6-assurance-report.md`), documenting: the final resolved/unresolved counts per category, the `mappingproxy`/`unimportable_nodes` disposition, the `calls_unresolved_detail_multiplicity` reconciliation, and the re-evaluated gate outcome across all three layers (Gate Outcome Requirements), citing `docs/audits/task-38.7-result.json`'s commit and result hash.
* `docs/audits/task-38.5-risk-register.md` — **L-10** disposition updated from open to closed, citing the Phase A fix and the Phase B evidence that confirms it.
* `docs/architecture/decisions/ADR-032-structural-audit-gate.md` re-evaluated: **ALLOWED only if Layers 1–3 (Gate Outcome Requirements) all hold — including H-2 closed or otherwise resolved by a separate task, which this task does not perform** — with every condition cited by commit and result hash; otherwise **HOLD**, with the exact named blocker(s), including H-2 by name if it is the sole remaining one. Never a task-completion claim standing in for the cited evidence. Any Phase-0-authorized `EXACT_IDENTITY_POLICY` entry is confirmed here, individually, only once Phase B's re-run proves its effect on the relevant counter.

---

# Non-Goals

Explicitly out of scope for both this spec-writing pass and the future implementation task it defines:

* **Task 39 does not begin as part of this task, and this task makes no promise that it unblocks Task 39.** Reaching ALLOWED requires Layers 1–3 (Gate Outcome Requirements), and Layer 3 (H-2, and any other independent finding) is explicitly not something this task remediates — see H-2 Reconciliation. Completing every Remediation Requirement below can leave `ADR-032` at HOLD.
* **No live operations.** No real trade, live inference call, or live broker/exchange/DB/Redis connection, under any configuration, at any point — including inside any new fixture this task adds.
* **No dependency updates.** No package is added, removed, or upgraded to make any category's resolution easier; `pydantic-settings`/`python-dotenv` are walked as they are currently pinned, not upgraded to a version with cleaner internals.
* **`uv.lock` stays untracked and untouched.** `uv` is never invoked in any form, by this spec-writing pass or (unless a future dependency is explicitly justified and documented, which this spec does not authorize) the implementation task.
* **No opportunistic H-1/H-2 fixes, and no code change made because of H-2.** Neither finding is remediated, re-scoped, or closed by this task or the one it defines; `app/wiring.py:COMPONENT_REGISTRARS`, `exchange_adapters/`, and `audit_harness/discovery.py`'s diff logic are untouched. H-2's disposition is handled purely as an `ADR-032` narrative condition (H-2 Reconciliation) — never as a reason to modify code, and never folded into `build_report`'s coded predicate. H-2 remediation, if it happens, is its own future, separately authorized task per H-2 Reconciliation.
* **No commit, push, or tag** by this spec-writing pass. The future implementation task's own commit/push/tag policy follows the repository's standing three-step (optional Phase 0, then code/tests, then evidence) workflow already used for Task 38.6 — this spec does not grant a new exception.

---

# Constraints

* This spec-writing pass modifies no production code, test file, or existing documentation file — it creates exactly one new file, `docs/prompts/task-38.7.md`.
* Do NOT add, remove, or upgrade a dependency. Do NOT run `uv` in any form. `uv.lock` stays untracked and untouched.
* Do NOT commit, push, or tag.
* Every requirement above binds the **future** implementation task, not this spec-writing pass — this pass performs no implementation, runs no harness, and modifies no code.

---

# Acceptance Criteria

✓ `docs/prompts/task-38.7.md` exists and defines a residual-resolution-and-gate-re-evaluation task — no implementation performed by this spec-writing pass, and no unconditional promise that completing it clears HOLD

✓ Starting Baseline states the exact current numbers (2 unresolved nodes; 68 unresolved calls; A=7, B=25, C=19, D=6, E=5, F=6; HOLD) as the fixed reference point for all remediation work

✓ Exact Gate Predicate quotes `audit_harness/report.py::build_report`'s real `all_clear` boolean verbatim, lists all eight real ALLOWED prerequisites (not four), and states explicitly that `unimportable_nodes` and `missing_from_component_registrars` are not part of it today

✓ Six separate Remediation Requirements (A–F), each naming its real root cause (grounded in the actual current source: `config/settings.py`, `core/logging.py`, `core/container.py`, `strategies/__init__.py`) and a real, general or individually-justified resolution mechanism — never a name/text allowlist

✓ An explicit "No Allowlists, No Blanket Trust, No Weakened Gate" section binds every requirement above and forbids any new/fifth `Category` bucket (there are already four: `project_source_available`, `exact_identity_policy`, `forbidden`, `unresolved`), a package-name exemption, or any relaxation of the existing Gate Rule

✓ Regression Test Requirement names one test per category plus preserves all 16 existing harness tests, with an explicit "16 + new" accounting, not a replacement count

✓ Machine-readable unresolved-detail reconciliation requirement adds a checkable `calls_unresolved_detail_multiplicity` field (schema bumped to `38.7.0`) making the raw-vs-deduplicated count relationship a verifiable invariant, not a narrative claim

✓ `builtins.mappingproxy: import failed` is given an explicit, fully specified disposition (resolve via `types.MappingProxyType`, or a principled documented exclusion, or an explicit HOLD-blocker treatment) — not left as an unexplained residual

✓ H-2 Reconciliation states plainly that Task 38.7 can zero its own residual, that `ADR-032` stays HOLD if H-2 (or any other independent finding) remains open regardless of the coded `exit_code`, that Task 39 stays blocked until `ADR-032` actually reaches ALLOWED, and that H-2 needs a separate, explicitly authorized remediation task because wiring `exchange_adapters` could affect the live-network safety boundary — with no H-2 remediation added to this task's own scope

✓ Gate Outcome Requirements define ALLOWED as three required layers (the eight-condition coded predicate; `unimportable_nodes` closed by resolution or by a real coded ninth condition; H-2/other findings resolved as an `ADR-032` narrative condition, not a coded one), state explicitly that no ADR text overrides a nonzero predicate value, and require any ADR-authorized `EXACT_IDENTITY_POLICY` entry to be authorized *before* implementation (never retroactively), then implemented, individually justified, regression-tested, and re-run-proven — plus HOLD's exact-blocker reporting requirement across all three layers

✓ Preserved Invariants explicitly re-assert paper-only runtime denial, 5/5 negative controls, and the fixed non-circular lifecycle/engine baselines are not silently recalculated by any category fix

✓ Two-Phase Provenance (with an optional Phase 0 reviewer-decision step preceding Phase A when needed) and Deliverables split the reviewer authorization, the harness/test/`strategies` code, and the evidence into three non-overlapping commits, name `audit_harness/run_audit.py` explicitly, name the evidence artifacts exactly (`docs/audits/task-38.7-result.json`, `docs/audits/task-38.7-assurance-report.md`, both new files that never overwrite the `task-38.6` evidence), and place L-10's risk-register closure in Phase B, never in the same commit as the `strategies/__init__.py` fix

✓ Non-Goals explicitly forbid starting Task 39 (and any promise it will be unblocked), live operations, dependency updates, `uv.lock` changes, opportunistic H-1/H-2 fixes or any H-2-motivated code change, and any commit/push/tag by this spec-writing pass

✓ Constraints explicitly forbid this spec-writing pass from implementing anything, modifying `uv.lock`, or committing/pushing/tagging

---

# Completion Checklist

After writing this spec, stop. Do not begin implementing any remediation. Report:

1. The one file created
2. A summary of the Starting Baseline, the Exact Gate Predicate, the H-2 Reconciliation, the six Remediation Requirements, the no-allowlist constraints, the regression-test/reconciliation/`mappingproxy` requirements, the three-layer Gate Outcome Requirements, the Phase 0/Two-Phase Provenance split, and the Deliverables/Non-Goals
3. Exact output of the Markdown/table consistency checks, `git diff --check`, and `git status --short --untracked-files=all`

Stop after reporting completion.
