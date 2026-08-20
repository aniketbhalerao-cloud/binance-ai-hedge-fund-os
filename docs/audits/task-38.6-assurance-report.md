# Task 38.6 — Audit-Assurance Harness: Assurance Report

**Executed against:** `main` `8fd66ca` (commit `8fd66cadacc52cc83902d4bd7ed004ee9ae3552b`, "Implement Task 38.6 audit assurance harness" — the first commit to actually contain `audit_harness/` and `tests/audit_harness/`). Harness source: `audit_harness/` (production package, never registered in `app/wiring.py:COMPONENT_REGISTRARS`, never imported by any production framework). Tests and negative-control fixtures: `tests/audit_harness/`. Machine-readable result: `docs/audits/task-38.6-result.json` (schema `38.6.0`, result hash `3a48d00cc626c1980b41496ea5c4e3e41e996b2327f6fa044f457f23ac019b82`).

**Gate outcome: HOLD.** Unchanged from `ADR-032`'s prior state — but now backed by a real, source-controlled, committed, tested harness run instead of another one-off pass. `nodes_unresolved=2`, `calls_unresolved=68`. Per the Gate Rule in `docs/prompts/task-38.6.md`, any nonzero unresolved count keeps the gate at HOLD; this report names the exact blockers below rather than a general statement that "issues remain."

---

## 1. What was built

Per `docs/prompts/task-38.6.md`'s nine Harness Requirements:

* **`audit_harness/discovery.py`** — Requirement 2. Independently re-derives every `register_*` package via a directory scan and diffs it against `app.wiring.COMPONENT_REGISTRARS`.
* **`audit_harness/identity.py`** — Requirement 4. The exact-identity policy (`EXACT_IDENTITY_POLICY_VERSION = "2026-08-20.1"`) and the three-bucket classification (`project_source_available` / `exact_identity_policy` / `unresolved`, plus `forbidden`).
* **`audit_harness/trace.py`** — Requirements 1 and 3. `StaticWalker`, the reusable AST call-graph engine; `run_trace()`, the real 24-root fresh-container trace plus static walk. Also reads every *registered* provider (resolved or not) from one extra discovery container, fixing an earlier gap where never-resolved provider closures (every framework's `Engine`) were silently excluded from lifecycle discovery.
* **`audit_harness/module_state.py`** — Requirement 5. Specified-pattern module-state detection, including the `global`/`nonlocal` rebind and plain-function-mutates-module-global scans M-7 gap 3 named as missing.
* **`audit_harness/runtime_denial.py`** — Requirement 6. Paper-only runtime denial checks, including the `os.open` family and DB/Redis/exchange-adapter discovery M-7 gap 2 named as missing. At runtime, the harness asserts that every target `discover_lifecycle_targets()` returns was patched (`AssertionError` on any mismatch) — a self-consistency check between two production code paths, not merely patched and trusted, but also not by itself an independent validation of that discovery helper. See Section 6 for the separate, fixed, non-circular test baselines that do independently verify the expected targets.
* **`audit_harness/self_test.py`** — the five negative controls (Requirement 7), run first, before any other part of the audit is trusted (implementation item 5). Case 5 exercises three independently named fake clients (DB, Redis, exchange-adapter) and passes only if all three are intercepted.
* **`audit_harness/report.py`** — Requirement 8. The deterministic JSON schema and gate computation.
* **`audit_harness/run_audit.py`** — orchestration entrypoint (`python -m audit_harness.run_audit`). Import failures during the runtime-denial node-loading step are sanitized to a fixed, generic `"<qualname>: import failed"` string — never a raw exception, traceback, or filesystem path.
* **`tests/audit_harness/`** — Requirement 9: 16 tests, all passing — determinism, fresh-container isolation (strong-reffed, cross-root singleton-leak check), lifecycle denial completeness (regression-baselined, non-circular), discovery completeness, false-negative-fixture self-test, three distinct safe-failure-sanitization modes, plus the five negative-control tests.

## 2. Self-test result (run before the real audit, per item 5)

All five negative controls were detected on this run — the audit's own result is trustworthy per Requirement 8's `self_test_failed` contract:

| # | Control | Detected |
|---|---|---|
| 1 | `__post_init__` performing a forbidden operation (`open(...)`) | ✅ |
| 2 | An unresolvable call reported `unresolved`, not dropped | ✅ |
| 3 | A module-global mutated from inside a plain (non-nested) function | ✅ |
| 4 | A direct `os.open(...)` call | ✅ |
| 5 | Three named fake clients (DB, Redis, exchange-adapter) — `connect()` intercepted on all three before any real connection | ✅ |

`negative_controls_total=5`, `negative_controls_detected=5`, `self_test_failed=false`.

## 3. Discovery (Requirement 2 — re-confirms H-2, does not fix it)

25 `register_*` functions found across the repository; 24 are present in `COMPONENT_REGISTRARS`. `missing_from_component_registrars = ["exchange_adapters"]` — the same H-2 finding Task 38.5 recorded by hand, now independently re-derived by committed, re-runnable code. Per Non-Goals, this harness does not add `exchange_adapters` to `COMPONENT_REGISTRARS`; H-2 remains open.

## 4. Trace and identity resolution (Requirements 1, 3, 4)

* `roots_traced=24`, `roots_with_error=0`.
* `nodes_total=205`, `nodes_unresolved=2`.
* `calls_total=1956`, `calls_unresolved=68`.
* Identity buckets across all 1956 calls: `project_source_available=1740`, `exact_identity_policy=145`, `forbidden=3`, `unresolved=68`.

**The 3 forbidden calls** are the same chain M-6 already records: `logger.get_logger()` → `LoggerFactory.configure()` → `self._build_handlers()` → `logging.StreamHandler(...)` / `logging.handlers.RotatingFileHandler(...)` / `os.makedirs(...)`. Found in `__init__:agents.manager.DefaultDecisionManager` (and, by the same shape, every other Manager/Engine `__init__`). Unreached from `app.main.main`/`app.bootstrap.run_dry_run_bootstrap` for the same reason M-6 already gives: `LoggerFactory` is never among the 24 `COMPONENT_REGISTRARS`.

### 4.1 The 2 unresolved nodes

| Node | `.init` | `.new` |
|---|---|---|
| `config.settings.Settings` | unresolved | project_source_available |
| `pydantic_settings.main.BaseSettings` | unresolved | project_source_available |

`Settings.__init__` is inherited from `pydantic_settings.main.BaseSettings.__init__` — a third-party dependency, not a stdlib builtin/C-extension and not project-owned source. Per Harness Requirement 4, the exact-identity policy is scoped to exactly three categories (dataclass-synthesized methods, Python stdlib builtins, C-extension types backed by a recognized stdlib/extension type) and explicitly excludes arbitrary third-party libraries — `pydantic-settings` does not qualify under any of the three, so this is correctly reported unresolved rather than silently trusted. This is not a claim of safety: `get_settings()`/`Settings()` construction is the documented, permitted external-configuration-read boundary (`app/main.py`'s own module docstring: "the only external read anywhere in this run") — but the harness's own identity policy, as specified, does not extend coverage into what that boundary's third-party implementation does internally, so what it does internally is reported unresolved, not assumed benign.

### 4.2 The 68 unresolved calls, categorized (none folded into a "safe" bucket by assumption)

Recalculated directly from the fresh trace's 68 raw unresolved `CallRecord`s (not from the 56 deduplicated display strings `calls_unresolved_detail` shows — several call sites, e.g. `self._registry.register` inside `register_instance`'s lambda, or `container.register_class` in the `strategies` registrar, are reached and recorded more than once by the walker's fixed-point traversal, so the raw and deduplicated counts differ by design; the raw count is what backs `calls_unresolved` and the table below).

| Category | Count | What it is |
|---|---|---|
| A | 7 | `pydantic_settings`/`python-dotenv` internals reached directly from `Settings()`/`load_environment()` — `__pydantic_self__.__class__._settings_build_values`/`_settings_init_sources`, `super().__init__()`, `find_dotenv`, `load_dotenv`. Same root cause as the 2 unresolved nodes above; third-party, out of the exact-identity policy's stdlib-only scope. |
| B | 25 | `core/logging.py` internals reached via `LoggerFactory.configure()` and `core.logging.JsonFormatter`/`logging.StreamHandler`/`logging.handlers.RotatingFileHandler`'s own `__init__` chains — `_STYLES` lookups, `Handler.__init__`, `BaseRotatingHandler.__init__`, `io.text_encoding`, and similar CPython `logging` module internals two-plus attribute hops deep, beyond what the harness's single-hop local-variable-type-inference currently follows. Same unreached-from-production root cause as the 3 forbidden findings above (M-6). |
| C | 19 | Local computation inside `app.bootstrap.run_dry_run_bootstrap`, `app.planner._plan`, `app.preflight.run`, `app.models.BootstrapContext.__post_init__`, and `config.settings.active_environment`/`Environment.from_str` — `dict`-of-`list` `.append()` chains, `os.getenv`, `value.strip().lower()`, and similar already-source-inspected project code. |
| D | 6 | `core.container.ServiceContainer._build`'s own `cls(**kwargs)` and its `resolver.resolve()` helper calls — `cls: type[T]` is a generic type-parameter, not a single concrete identity; constructing "whichever class the caller names" is not reducible to one exact-identity-policy entry. |
| E | 5 | `ServiceContainer.register_instance`'s internal lambda: `inspect.getsource` on this specific lambda returns a source fragment that omits the enclosing `self._registry.register(...)` statement entirely (a real, observed quirk of `inspect.getsource` on some lambda argument positions), so the local instance-attribute context is unavailable when walking it directly. |
| F | 6 | `strategies/__init__.py`'s `register_strategies(container: object)` — annotated `object`, not `Container`, unlike the other 23 registrars. A real, minor typing looseness in production source (not a harness bug) that happens to be exactly what the identity-first mechanism needs to resolve `container.register_class(...)`/`.register_singleton(...)`/`.has(...)` the way it does everywhere else. |

7 + 25 + 19 + 6 + 5 + 6 = 68.

**No forbidden identity was established for these 68; unresolved behavior remains safety-unknown and keeps HOLD.** Every one is either a third-party dependency's own internals (A), a deep stdlib-internals chain triggered only by the unreached logging path (B, same root cause as the 3 forbidden findings above), pure local computation in already-source-inspected project code (C), a structurally-irreducible generic construction (D), a documented `inspect.getsource` quirk (E), or a real but narrow typing gap in one registrar (F). None of these categories amounts to proof of safety — they explain *why identity resolution stopped*, not that what lies past it is benign — so all 68 are reported as `unresolved` rather than assumed safe, which is exactly what keeps the gate at HOLD.

## 5. Module-state (Requirement 5)

`candidates_total=523`, `unexplained_total=0`. Buckets: `mutable_never_mutated_lookup=394`, `immutable_constant=126`, `intentional_documented_shared_instance=3`. The `global`/`nonlocal`-rebind scan and the plain-function-mutates-module-global scan (M-7 gap 3) ran across the full 30-package scope and found zero unexplained shared mutable state.

## 6. Runtime denial (Requirement 6) — paper-only

Settings/context built normally first; then `file_io`, `os_low_level` (including the `os.open`/`fdopen`/`read`/`write` family M-7 gap 2 named as missing), `network`, `subprocess`, `threads_processes`, `sleeps`, `logging_handlers`, and **33** discovered `lifecycle_methods` targets were patched.

Two distinct claims back that 33, and they should not be conflated: at runtime, `runtime_denial.py` asserts that every target `discover_lifecycle_targets()` returns — every discovered node's own `start`/`invoke`/`compose`/`schedule`/`enqueue`/`submit_order`/`place_order`/`execute_trade`/`predict`/`infer` method — was actually patched (`AssertionError` on any mismatch). That is a self-consistency check between two production code paths (discovery and patching), not by itself an independent validation of the discovery helper. Separately, `tests/audit_harness/test_lifecycle_denial_completeness.py`'s fixed, non-circular test baselines (`EXPECTED_LIFECYCLE_TARGETS`, `EXPECTED_ENGINE_NODES` — hand-curated, not derived from `discover_lifecycle_targets()` or `run_trace()`'s own output) independently verify the expected 33 lifecycle targets across 22 `Engine`/`Manager`/`Composer`/`Service` classes.

`app.bootstrap.run_dry_run_bootstrap` was then run for real, with the result: **SUCCESS** — `status=SUCCESS`, `total=24`, `passed=24`, `failed=0`, no forbidden call observed. `db_clients_found=[]`, `redis_clients_found=[]` (explicitly reported empty, not omitted — no DB/Redis client library is a dependency of this project: only `pydantic`, `pydantic-settings`, and `python-dotenv` are declared in `pyproject.toml`). `exchange_adapter_connections_found` names `exchange_adapters` as present but not reachable from the traced graph (H-2). One discovered node, `builtins.mappingproxy`, is unimportable through the same class-loading path the other nodes use; the harness reports this sanitized as `"builtins.mappingproxy: import failed"` — the fixed, generic, path-free message format Requirement 6's safe-failure handling specifies, not a raw exception or traceback. **This run performed no real trade, no real inference call, and no real network/database/Redis/exchange connection at any point.**

## 7. Re-run requirements

* **Targeted Ruff**: `ruff check audit_harness tests/audit_harness` → 0 findings.
* **Targeted mypy**: `mypy audit_harness` (strict, matching `pyproject.toml`) → **0 errors**. Reached via precise per-line casts, protocol-consistent typing, and narrow, individually-commented `# type: ignore[...]` codes only (e.g. the two intentionally-unsound `cls.__init__`/`cls.__new__` introspection comparisons in node classification) — no module-wide ignore, no broad `Any` conversion, no interface weakening.
* **Harness's own test suite**: `pytest tests/audit_harness/` → **16 passed**.
* **Full project test suite**: `pytest -q` → **757 passed** (741 previously recorded + 16 harness tests; delta fully explained, no regression).
* **Paper-only 24/24 bootstrap defence**: see Section 6 — `SUCCESS`, `24/24`, confirmed paper-only, no live connection at any point.
* **Deterministic repeated-run comparison**: two `run_full_audit()` calls against commit `8fd66ca` produce byte-identical `canonical_json()` and an identical `result_hash()` (`3a48d00cc626c1980b41496ea5c4e3e41e996b2327f6fa044f457f23ac019b82`). Confirmed both in the harness's own test suite (`test_deterministic_repeated_runs_produce_identical_report`) and manually for this report's cited hash.

## 8. Conclusion

The harness satisfies all nine Harness Requirements and its own five negative controls. It found the same 3 real findings the v1–v5 passes already knew about (the `logger.get_logger()` chain, M-6) and re-confirmed H-2 independently. It found **no new Critical, High, or reachable-forbidden finding**. It also found a **real, previously-unrecorded, narrow typing gap** (`strategies/__init__.py`'s `container: object` annotation, category F above) — worth a low-severity follow-up note, not a safety finding.

Per the Gate Rule, because `nodes_unresolved=2` and `calls_unresolved=68` are both nonzero, `ADR-032` **stays HOLD** — this is not a discovered Critical vulnerability, and is a substantially narrower, precisely-categorized residual than the open-ended uncertainty the v1–v5 passes left behind. See `docs/architecture/decisions/ADR-032-structural-audit-gate.md` for the re-evaluated gate record and `docs/audits/task-38.5-risk-register.md`'s **M-7** for the updated disposition.
