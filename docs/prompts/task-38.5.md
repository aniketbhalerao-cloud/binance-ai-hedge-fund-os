# Task 38.5 — Structural Audit and Loophole Review

---

# Sprint 18.5

## Type

Audit. Inserted between Sprint 18 (Task 38 — Application Bootstrap & Dry-Run Runtime Composition) and Sprint 19 (Task 39). **Code-read-only: no production code, test, or documentation file is modified by this task.** Its only output is the four documents listed under "Deliverables".

## Scope

Every committed framework, Tasks 1–38, as they stand at `main` `d5ef0c7` (Task 38 itself released at `397a706` / `v4.12-application-bootstrap`). The audit's center of gravity is `app/` — the one package permitted to import across every other framework, and therefore the one place a structural mistake in any of the other 37 tasks would first become externally observable. But the audit is not scoped to `app/` alone: a boundary violation, a shared-mutable-state leak, or a missing safety control in `market_data/`, `execution/`, `order_management/`, `risk/`, or any other framework is equally in scope, whether or not `app/` currently exercises it.

---

# Objective

Tasks 1–38 were each implemented and reviewed individually. No task to date has re-examined the *system as a whole* for structural cracks that only appear once every framework exists and is wired together: hidden coupling that individual per-framework tests can't see, a determinism guarantee that holds framework-by-framework but not under composition, a safety boundary asserted in one task's docstring but never actually checked against a sibling task's real behavior, or a trading-safety control the roadmap assumes exists somewhere but that no task ever actually built.

Task 38.5 is a **deep, code-read-only audit** that inspects the real committed source — not specs, not prior review documents, not docstrings taken on faith — and produces a ranked, evidence-backed record of what it finds. It changes no code. It exists so that Task 39 (and every task after it) builds on a verified foundation instead of an assumed one.

---

# Architecture Requirements

* Read-only, with a precisely defined final state at each stage — never merely "no changes":
  - This spec-writing pass ends with `git status --short` showing exactly `?? docs/prompts/task-38.5.md` and `?? uv.lock` (the latter pre-existing and untouched) — nothing else.
  - The future audit run ends with `git status --short` showing exactly its four new deliverables (`docs/audits/task-38.5-structural-audit.md`, `docs/audits/task-38.5-risk-register.md`, `docs/audits/task-38.5-test-gaps.md`, `docs/architecture/decisions/ADR-032-structural-audit-gate.md`) plus `?? uv.lock` — nothing else.
  - Both passes leave **no existing documentation modified** — every file either pass's final `git status` shows is a new file it was explicitly asked to create, never a change to a file that already existed.
* Evidence-based: every finding in every output document cites a concrete `path:line` (or `path:function`/`path:class` where a line number would drift) and, wherever the finding concerns behavior rather than static structure, the exact command whose output demonstrates it.
* No implementation, no fix, no refactor, no new test file, no dependency change — a finding that a control is missing is recorded as a finding, not built.
* No shortcuts: a section of this spec that says "trace every call path" means every call path, not a representative sample.

---

# Audit Areas

The audit report (`docs/audits/task-38.5-structural-audit.md`) must cover all nine areas below. Each area names the concrete things to check — this is the minimum, not a ceiling.

## 1. Architecture Boundaries & Dependency Direction

* Scope: **production source only** (every `.py` file under each framework package, excluding `tests/`). A test module importing another framework's public API (e.g. `register_workflows`, `DefaultWorkflowEngine`) to build a fixture is expected and is never a boundary violation — tests are supposed to import public APIs. A package importing its own types is not cross-framework coupling. Importing `core/`, `config/`, or `events/` is not a violation either — those are foundational, not "another framework."
* For each of the 24 packages exposing a `register_<framework>` function (the set in `app/wiring.py:COMPONENT_REGISTRARS`) plus `trading/`, re-derive — from real `ast.Import`/`ast.ImportFrom` nodes in production source, not source substrings or trust in a prior review — which *other* top-level framework packages it imports, and confirm none does. The one documented composition exception: `app/wiring.py` alone may import another framework's `register_<framework>` function or a framework's concrete `Manager`/`Engine`/service type — and only for DI registration/resolution wiring, never to call a business method.
* Confirm `app/wiring.py` is in fact the *only* production module, anywhere in the tree (not just within `app/`; test modules are out of scope for this check per the exception above), that imports a `register_<framework>` function or a framework's concrete `Manager`/`Engine`/service type as executable code — and confirm every such import inside `app/wiring.py` exists solely for composition, never to call a business method (`.start()`, `.invoke()`, `.schedule()`, `.enqueue()`, `.compose()`, or equivalent).
* Re-derive `app/wiring.py:COMPONENT_REGISTRARS`'s coverage independently (do not just read the dict literal — cross-check it against a directory listing of top-level packages exposing `register_*`) and confirm: all 24 are present, none is duplicated, `trading/` is correctly absent, and no 25th framework has been added to the codebase since Task 38 that `COMPONENT_REGISTRARS` has silently fallen out of sync with.
* Check DI consistency: does every `register_<framework>` function register its singletons/factories the same way (`register_class` vs. a hand-written `_build_*` provider) for equivalent roles across frameworks, or has drift crept in that would make one framework behave differently under `ServiceContainer.reset()` or re-registration than its siblings?
* Hidden coupling — module-level state inventory: enumerate **every** module-level object across all 24 frameworks plus `app/`, `core/`, and `trading/` that is constructed once at import time and shared across calls (a `dict`/`list`/`set` literal, a class instance, an `lru_cache`d function, a class-level mutable default). Do not start from the assumption that `app/wiring.py:_DRY_RUN_MARKET_DATA_PROVIDER` is the only one — it is one known example to include in the inventory, not the expected conclusion. Evaluate each entry against its own contract rather than flagging it by presence alone:
  - an immutable constant (a `frozenset`, a `MappingProxyType`-wrapped literal, a genuinely stateless `__slots__ = ()` instance) is not a finding;
  - an intentional process-wide cache with a documented contract (`core.container.get_container`'s `@lru_cache(maxsize=1)` singleton, explicitly documented as the process-wide composition root) is not a finding *if* its documented contract is what the code actually does;
  - a mutable object shared across calls **without** a documented single-owner/thread-safety contract, or one whose actual behavior diverges from its documented contract, is a finding — cite the divergence, not merely the sharing.
* Circular dependencies: trace whether any two frameworks' `register_*` functions, in combination with `core.container.ServiceContainer._build`'s constructor-injection resolution, can produce a resolution-order dependency between two frameworks that neither declares — i.e., a framework whose manager only resolves cleanly if *another* framework happened to register first, even though `app/wiring.py:build_default_manifest` declares zero dependencies between them.

## 2. Determinism, Immutability, Registry Ownership, Thread Safety

* Scope: every in-scope model module — all 24 frameworks' `models.py`, `app/models.py`, `trading/models.py` (or equivalent, if present), and any `core/` model type a framework's public API exposes to callers (e.g. `core.interfaces.Registration`) — not `app/`'s models alone.
* For each model, verify **effective immutability against that model's own task specification** (`docs/prompts/task-<N>.md`), not a blanket rule imported from Task 38's conventions. Confirm the model matches what its own spec actually requires — frozen dataclass, `Decimal` for the numeric domain fields its spec names, immutable-collection fields where its spec calls for them. **Do not retroactively flag a model for lacking `slots=True` or list-to-tuple `__post_init__` normalization unless that model's own task specification required it** — Task 38's stricter conventions are Task 38's, not a universal retroactive standard applied to earlier tasks that never adopted them.
* Detect mutable-alias leakage specifically: for any field a `__post_init__` wraps or copies (a `tuple(...)` conversion, a `MappingProxyType(...)` wrap), confirm the wrap is applied to a **copy** of the caller-supplied value, not the caller's original mutable object by reference — e.g. `MappingProxyType(dict(x))` is safe (a fresh dict is wrapped), `MappingProxyType(x)` where `x` is the caller's own dict is not (the caller retains a live, mutable reference to state the model claims is immutable). Flag every instance of the unsafe form found.
* Confirm no field is generated by `datetime.now()`/`uuid.uuid4()`/`random`/hash order inside a pure model or pipeline function — list every framework's designated impure boundary (its `main`, its context-builder, or equivalent) that is the *only* place such a call is permitted, the way `app/main.py:_utc_now` is for Task 38.
* For each framework's Planner (or equivalent ordering component), confirm ordering is a genuine dependency-aware sort (Kahn's algorithm or equivalent), not `sorted()` over a flat priority key, wherever a dependency graph is involved — Task 37 (`workflows/planner.py`) and Task 38 (`app/planner.py`) both claim this; verify it is actually the same shape, not merely the same claim, and check whether any *other* framework with graph-like ordering (if any) makes the same claim without the same mechanism.
* Registry ownership: for each framework with a `Registry`, confirm the Registry — not the Manager, not the Engine, not the caller — is the sole owner of running record state, and that the Manager always reads-processes-writes back a *new* immutable record rather than mutating one in place.
* Thread safety: for each framework's Registry/Manager, identify the lock (or documented lock-free invariant) protecting concurrent access, and check whether `core.container.ServiceContainer`'s own `RLock`-guarded `resolve`/`register` path is sufficient to make concurrent bootstrap or concurrent framework use actually safe, or whether it only looks safe because nothing in the current test suite exercises concurrency.
* Error isolation and partial-state leakage: for each framework's Manager/Engine, confirm a failure partway through processing one input never leaves the Registry holding a half-written record, and confirm `app/bootstrap.py`'s "zero accepted runtime state on any failure" guarantee is actually structurally true — re-trace every `return BootstrapResult(status=FAILED, ...)` path and confirm none of them can be reached with a non-`None` `plan`/`preflight_report`/`runtime_snapshot`/`lifecycle_plan`.
* Exception sanitization: grep every `raise` and every `except Exception` across `app/` and, spot-checked, every other framework's Manager/Engine, for any place a value is interpolated into an exception message. Interpolating an identifier into a message is **not, by itself, a finding** — most of the codebase's validation/planning-error messages do this safely inside an internal, caught-and-translated flow. It is a finding only when at least one of the following holds:
  - it violates that specific task's own written specification (Task 38's is unusually strict — every message must be fixed and generic, verified by its own secret-marker tests; confirm that specific, stricter contract hasn't regressed);
  - the interpolated value is genuinely sensitive or untrusted (a credential-shaped value, or caller-controlled content whose safety was never validated) and the message reaches a surface that value shouldn't reach; or
  - the message actually reaches a public log, a published event payload, or a caller-facing error/result field — trace the reach, don't assume it from the `raise` site alone.

## 3. Dry-Run / Live-Runtime Separation — Complete Call-Path Analysis

This is the highest-stakes area and must be treated as a full proof, not a sample check. Starting from `app/main.py:main` and `app/bootstrap.py:run_dry_run_bootstrap` — the documented end-to-end dry-run entrypoints for this task, not the only callable APIs in `app/` (`planner.plan`, `preflight.validate_service_keys`, `preflight.run`, and `wiring`'s builders are all independently public and importable, and are in scope wherever they're reachable from either entrypoint) — trace **every reachable call path** — through `app/wiring.py:COMPONENT_REGISTRARS`, through every framework's `register_<framework>` function, through every provider/singleton closure those functions define, through `core.container.ServiceContainer._build`'s constructor-injection resolution, and through `app/preflight.py:run`'s resolution of `app/wiring.py:SAFE_SERVICE_KEYS` — and, for each framework's `Manager`/`Engine`/service type reachable from `SAFE_SERVICE_KEYS`, prove from its actual `__init__` source (not its docstring) that construction alone can never:

* execute a trade or touch `execution/`, `order_management/`, or `trading/`'s live-order path
* invoke a model / call `ModelGatewayManager.invoke()` or any AI provider
* execute, schedule, or dispatch a workflow step, a scheduled job, or a queued work item
* call `.start()` on any framework's `Engine`
* open a real network socket, database connection, or Redis connection
* read or write a file
* spawn a thread or process, or sleep

Explicitly re-verify the two mechanisms Task 38 relies on for this guarantee and confirm neither has a gap: (a) `app/wiring.py:SAFE_SERVICE_KEYS` as the *only* set of types ever resolved, and every type in it as genuinely I/O-free in its constructor (not just asserted to be, in a comment) — including `app/wiring.py:_DryRunMarketDataProvider`, whose `__slots__ = ()` claim and fail-closed `connect`/`disconnect` must be re-derived from the current source, not assumed unchanged since its last review; (b) `app/preflight.py:validate_service_keys` as a genuine pre-container gate that makes an unlisted key unreachable before any resolution is attempted. Report the full reachable call graph, or a precise statement of why a full trace was infeasible for a named subset (with that subset then treated as an open finding, not silently excluded).

## 4. Trading Safety Gaps

Nothing built through Task 38 is a live trading path — but the roadmap and several frameworks' docstrings imply real trading-safety controls exist or will be needed. This area is an inventory of what actually exists today versus what a real live-runtime task would need, **recorded as findings only — do not implement anything here**:

* Order validation: does `order_management/` or `execution/` enforce any check beyond structural/type validation (notional limits, symbol allowlist, duplicate-order detection) today, and is that check reachable from a live path or only from tests?
* Idempotency: is there any mechanism, anywhere in the committed code, that would prevent the same order intent from being submitted twice (e.g., on a retry after a timeout)? If none exists, say so explicitly rather than inferring one from an unrelated correlation-id field.
* Position/risk limits: `risk/` declares `RiskEvaluationManager`/`RiskPolicy` — confirm whether evaluated risk limits actually gate anything today, or whether they only produce an advisory `RiskDecision` object that nothing downstream is wired to enforce.
* Kill switches: search for any mechanism — configuration flag, circuit breaker, emergency-stop path — that could halt order flow once a live-runtime task exists, and confirm whether one exists today or is entirely absent.
* Audit logging: confirm whether a trade/order audit trail (immutable, append-only, attributable) exists anywhere in the current code, or whether current logging is best-effort/observability-only.
* Fail-closed behavior: for each of the above, state explicitly whether the *absence* of the control today fails open (an unguarded path would proceed) or fail closed (nothing live exists yet, so there is nothing to proceed) — Task 38's dry-run-only design should make everything fail closed today by construction; confirm that is actually true and flag anywhere it might not be once a live-runtime task lands on top of the current structure without additional guardrails.

## 5. Secret/Credential Leakage & Unsafe Configuration Propagation

* The permitted `Settings` boundary has two distinct, non-interchangeable roles — audit each separately. `app/main.py` is the one permitted **caller** of `config.settings.get_settings()` (the sole external-configuration read anywhere in the dry-run pipeline). `app/wiring.py:build_configuration_view` is the one permitted **consumer/copier** of the resulting `Settings` object, turning it into a redacted `ConfigurationView` before anything else ever sees it. Confirm neither role has a second, unaudited implementation anywhere in the tree: no framework outside `app/main.py` calls `get_settings()`/`load_environment()`, and no module outside `app/wiring.py` reads a `Settings` instance's fields directly.
* Re-verify `app/wiring.py:build_configuration_view`'s positive allowlist and its independent mechanical name-fragment filter (`key`/`secret`/`token`/`credential`/`password`/`url`/`dsn`) against the *current* `config/settings.py:Settings` field set. Audit both directions: enumerate every field the allowlist actually copies today and confirm each is genuinely non-sensitive; and confirm no field added to `Settings` since Task 38 shipped would be missed by both layers — an unlisted field is excluded by construction (positive selection, not exclusion-by-exception), so the audit's job is to verify what *is* copied, not merely to confirm the mechanical filter exists.
* Audit for bypass paths: a `Settings` field reachable through something other than `build_configuration_view` — a nested settings model's `__repr__`/`__str__`, a logging integration that serializes an object graph, a test fixture accidentally exercised from production code — and grep every framework's logging call sites, event payloads, and exception messages for a plausible path by which a credential-shaped value could reach output, not just within `app/` but across all 24 frameworks, since any one of them resolving through `app/preflight.py` could in principle have its exception text surfaced.
* Confirm `PreflightEntry.detail` and every `BootstrapResult.errors` entry are, on the current source, always drawn from a fixed literal set — re-derive the literal set from source and list it in the audit report, rather than trusting the prior review's list.

## 6. Missing Negative, Adversarial, Concurrency, Boundary, and Integration Tests

Enumerate concretely, per framework and for `app/` in particular:

* Negative cases with no covering test today (malformed input shapes the type system doesn't prevent, e.g. an empty string id, a manifest with only self-referential components, a `Settings` object at the edge of its validators).
* Adversarial cases: a `container_factory` that returns a container the caller keeps a live reference to (Task 38 documents this as a trusted-but-unenforced precondition — is there a test that at least demonstrates what happens when the precondition is violated, even if Task 38 isn't expected to defend against it?); a `register_<framework>` function replaced with one that behaves correctly on the surface but retains a reference to the container past its call.
* Concurrency: is there a single test anywhere that runs two bootstrap attempts, or two framework Manager operations, concurrently against shared infrastructure (the `ServiceContainer`'s lock, a shared `EventBus`)? If not, say so as a gap rather than inferring thread safety from the presence of `RLock`s.
* Boundary: exact-limit tests (a manifest at exactly `wiring.KNOWN_COMPONENT_IDS`'s size, a `Decimal` priority at its type's practical extremes, a `requested_at` at exactly `utcoffset() == timedelta(0)` versus the smallest valid non-zero UTC offset supported by Python's datetime/timezone implementation).
* Integration: cross-framework paths that Task 38 makes newly possible (all 24 in one container) but that no test exercises beyond registration/resolution — e.g., is there any test that resolves two different frameworks' managers from the *same* candidate container and checks they don't observe each other's state through a shared singleton they weren't supposed to share?

## 7. Documentation Drift

* `docs/architecture/roadmap-v2.md`'s Task 38 entry ("Feedback & Trade Journal Framework", a `feedback/` package) is already known-obsolete — confirm its exact current text, confirm no other roadmap entry (Task 39 onward) implicitly assumes the old Task 38 concept exists (e.g., a "Dependencies: ... Feedback" line), and record precisely what would need to change without changing it.
* Cross-check every Task 32–38 ADR and review document's factual claims (verification numbers, package file lists, acceptance-criteria checklists) against the *current* committed source — flag any claim that has drifted (e.g., a test count that no longer matches a fresh run, a file list that omits a file actually present).
* Confirm `docs/prompts/task-38.md` and the shipped `app/` implementation still agree on every acceptance criterion — this task's own audit is the first opportunity for an independent check of that, rather than trusting the implementer's own completion report.

## 8. Risk Ranking

Every finding across areas 1–7 is recorded in `docs/audits/task-38.5-risk-register.md` as one row with, at minimum:

* **Severity** — Critical / High / Medium / Low (see the rubric below)
* **Evidence** — exact `path:line` or `path:symbol`, plus the command/output that demonstrates it for behavioral findings
* **Impact** — what actually goes wrong, concretely, if this is left as-is
* **Exploit/failure scenario** — the specific sequence of events (a caller, an input, a timing window) that triggers the impact
* **Existing protection** — what, if anything, already mitigates this today (a test, a structural guarantee, a fail-closed default) — "none" is a valid, expected answer
* **Recommendation** — what a future task should do; never "fixed here"
* **Disposition** — open / accepted-risk (with a named reason) / not-applicable

Severity rubric:

* **Critical** — a path exists, in the current committed code, by which *any documented production or core entrypoint across Tasks 1–38* (not only `app/main.py:main`/`app/bootstrap.py:run_dry_run_bootstrap`) — run exactly as its own task's specification describes it being run — could perform real trading, real model inference, or real unspecified I/O, or leak a real credential, in violation of that entrypoint's own declared no-trade/no-I/O/no-inference/no-secret boundary. A Critical finding must cite the exact call path and the specification line the behavior violates. **This explicitly excludes intentionally impure adapters and boundaries whose own specification requires real I/O**: `adapters/binance/adapter.py`, a real `MarketDataProvider` implementation, `config.settings.get_settings()`'s environment/`.env` read, and `app/main.py:_utc_now`'s wall-clock read are not Critical findings merely for performing the I/O their own spec assigns them. A Critical finding here is *forbidden* core/domain behavior — a component specified as pure, deterministic, or I/O-free that in fact is not.
* **High** — a structural guarantee this task's own spec or a prior task's spec claims (determinism, immutability, isolation, no-cross-framework-import) is falsifiable from the current source, even if no live-trading path is involved yet.
* **Medium** — a real gap (missing test, missing trading-safety control, documentation drift) that does not falsify an existing claim but would need to be closed before the next dependent task can safely build on top of it.
* **Low** — a real but low-impact inconsistency (style drift, a stale comment, a non-exploitable inefficiency) worth recording but not blocking.

## 9. Gate

**Any Critical finding blocks Task 39.** If `docs/audits/task-38.5-risk-register.md` contains one or more Critical-severity, open-disposition rows when the audit concludes, Task 39 must not begin until each is either resolved by a dedicated follow-up task or explicitly re-classified with a recorded justification. `docs/architecture/decisions/ADR-032-structural-audit-gate.md` records this gate as an accepted architectural decision, independent of whatever the audit itself finds.

---

# Verification Requirements

The audit run itself (not this spec) must execute and report, verbatim, at least:

* `python -m compileall` over every package touched by the audit's call-path tracing (at minimum: all 24 frameworks + `app/` + `trading/` + `core/` + `config/` + their test files) — using the project's `.venv`, never `uv`.
* The full test suite: `python -m pytest -q` from repo root, with the resulting pass count compared against the last known-good count recorded in the most recent review/ADR, and any delta explained.
* Scoped `ruff check` and `mypy` per framework package (not just `app/`), each run individually so a package-specific new finding cannot hide inside a full-repo run.
* The deterministic/safety checks already established as Task 38's own verification pattern: the exact 24/24 preflight sanity check (`status=SUCCESS, total=24, passed=24, failed=0, registered=24`), the `socket.socket`/`threading.Thread.start`/`multiprocessing.Process.start` defence-in-depth monkeypatch check, and the AST-based cross-framework import-boundary check — re-run fresh, not cited from a prior report.

**Baseline separation is mandatory.** These baselines are already recorded (in prior review/ADR documents) and must not be reported as new findings unless their shape has changed:

* Full-repo `ruff check .`: 75 pre-existing `UP042` (`(str, Enum)` vs. `enum.StrEnum`) findings across earlier frameworks.
* Full-repo `mypy .`: halts on one pre-existing `adapters/binance/adapter.py` duplicate-module-path error before reaching the rest of the tree.
* Per-package `mypy` on `model_gateway/` and `workflows/`: each report 14 `Container` DI-typing errors (`attr-defined`/`type-abstract`) from the shared `register_class`-with-a-Protocol-type pattern; `mypy app/` reports zero.

For every other package the audit runs scoped Ruff/mypy against, **no historical baseline is recorded anywhere in this repository's docs**. Do not label a package's current findings "new" or "a regression" without a prior recorded count to compare against — where no such record exists, report the package's current finding count under an explicit **`baseline: unknown`** label, state that plainly in the audit report, and let a future task establish the first recorded baseline rather than the audit inventing one retroactively.

Any finding that *can* be compared against a recorded baseline and differs from it — a test that now fails, a new finding in a package whose baseline was previously zero, a changed error count in an already-recorded package — is reported as a finding in its own right, separately from the recorded baselines above. A finding in a package with no recorded baseline is still reported; it is simply labeled `baseline: unknown` rather than implied to be new.

---

# Deliverables

This task (the spec) produces exactly one file: `docs/prompts/task-38.5.md`.

The **future** audit task this spec defines produces exactly these four files and modifies nothing else:

* `docs/audits/task-38.5-structural-audit.md` — the narrative audit report covering areas 1–7.
* `docs/audits/task-38.5-risk-register.md` — the ranked findings table described in area 8.
* `docs/audits/task-38.5-test-gaps.md` — the concrete enumeration from area 6, structured so each row is directly actionable as a future test to write.
* `docs/architecture/decisions/ADR-032-structural-audit-gate.md` — records the Task 39 gate from area 9 as an accepted decision.

---

# Constraints

* Do NOT modify any production code, test file, or existing documentation file (including `docs/architecture/roadmap-v2.md`, every prior `docs/reviews/*.md`, every prior `docs/architecture/decisions/ADR-*.md`, `docs/CHANGELOG.md`, `docs/HANDOFF.md`).
* Do NOT add, remove, or upgrade a dependency. Do NOT run `uv` in any form. `uv.lock` stays untracked and untouched.
* Do NOT commit, push, or tag.
* Every check the audit runs is read-only against the working tree: no fix, no refactor, no new test, no config change — a gap is a finding, never a patch.

---

# Acceptance Criteria

✓ `docs/prompts/task-38.5.md` exists and defines a code-read-only audit — no implementation performed by this task

✓ All nine audit areas specified with concrete, source-grounded check instructions, not generic prompts

✓ Call-path analysis requirement (area 3) demands a complete trace with an explicit fallback for any subset left untraced, not a sample

✓ Trading-safety inventory (area 4) explicitly forbids implementing anything it finds missing

✓ Risk-ranking rubric (area 8) is objective and evidence-anchored, with Critical explicitly tied to a real I/O/trading/inference/credential-leak path

✓ Gate (area 9) is unambiguous: any open Critical finding blocks Task 39

✓ Verification requirements name exact commands, separate the recorded baselines from any new finding, and require an explicit `baseline: unknown` label for any package with no recorded historical count

✓ Four future deliverables named exactly, with no fifth file implied

✓ Constraints explicitly forbid modifying code, tests, existing docs, dependencies, and `uv.lock`, and forbid commit/push/tag

---

# Completion Checklist

After writing this spec, stop. Do not begin the audit. Report:

1. The one file created
2. A summary of the nine audit areas and the four future deliverables
3. Exact output of `git diff --check`, `wc -l docs/prompts/task-38.5.md`, and `git status --short`

Stop after reporting completion.
