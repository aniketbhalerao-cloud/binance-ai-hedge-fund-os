# Task 38.6 — Audit-Assurance Harness and HOLD Resolution

---

# Sprint 18.6

## Type

Harness build + audit re-run. Inserted between Sprint 18.5 (Task 38.5 — Structural Audit and Loophole Review, whose gate this task resolves) and Sprint 19 (Task 39, which remains blocked until this task closes). **This is a specification-writing pass only: it authors this one file and performs no implementation.** The future implementation task this spec defines builds a source-controlled audit harness, re-runs the Task 38.5 gate against it, and re-evaluates `docs/architecture/decisions/ADR-032-structural-audit-gate.md`.

## Scope

`docs/architecture/decisions/ADR-032-structural-audit-gate.md` currently records the Task 39 gate as **INDETERMINATE / HOLD**: Task 38.5's five iterative passes (v1–v5) each closed a real gap the previous pass's method could not see, and `docs/audits/task-38.5-risk-register.md`'s **M-7** records that this pattern is itself evidence the trace never reached exhaustive — naming four specific, still-open methodological gaps. This task's scope is exactly those four gaps, plus the structural precondition every one of them shares: every prior pass's tooling lived in `/tmp`, was never committed, and could not be re-run, diffed, reviewed, or regression-tested. The future implementation task must build a **source-controlled, deterministic, reusable audit harness** that closes all four M-7 gaps and re-runs the Task 38.5 gate against the current committed source (`main` at `5c36401` or whatever commit is HEAD when that task runs), producing a re-evaluated `ADR-032` outcome — ALLOWED or HOLD, on the harness's own evidence, never assumed.

This task does **not** re-open Task 38.5's Areas 1, 2, 4, 5, 6, or 7, and does **not** re-litigate H-1 or H-2 (both remain open, tracked, unimplemented — see Non-Goals). Its scope is the harness itself and the specific re-run of Area 3 / Area 3b it makes possible.

---

# Objective

Task 38.5's own risk register records, in **M-7**, that the audit-assurance gap is itself the finding: "0 unresolved" in every one of the v1–v5 passes' summary tables meant "0 entries fell outside that pass's classification scheme," not "every callable was mechanically proven safe" — and the scheme itself grew across five passes because each one found something the last one's method could not see. `ADR-032` records the resulting gate as HOLD, not ALLOWED and not BLOCKED: no Critical finding exists in the record, but the absence of one repo-wide is not conclusively established either.

Task 38.6 is a **harness-build-and-re-run** task. It exists to replace the pattern that produced five successive corrections — a new one-off `/tmp` script per pass, each fixing the previous one's blind spot — with a single, source-controlled, deterministic, tested piece of infrastructure that can be re-run on every future commit, not just this one. Building that harness and running it once is what actually lets `ADR-032`'s gate move off HOLD, in either direction, on the strength of evidence rather than another round of the same throwaway-script method.

---

# Architecture Requirements

* Read-only against production source, with a precisely defined final state at each stage — never merely "no changes":
  - This spec-writing pass ends with `git status --short --untracked-files=all` showing exactly `?? docs/prompts/task-38.6.md` plus `?? uv.lock` (the latter pre-existing and untouched) — nothing else.
  - The future harness-build-and-re-run task's own final `git status` is defined by its own Deliverables section below — new, source-controlled files only, no modification to any file this spec does not name as a Deliverable.
* The harness itself is **infrastructure, not a framework**: it must never be one of the 24 packages exposing a `register_<framework>` function, must never be added to `app/wiring.py:COMPONENT_REGISTRARS`, and must never be imported by any production framework or by `app/`. It analyzes the codebase from outside the composition root's own import graph, the same way a linter or a test suite does — it is not a 25th thing for the dry-run bootstrap to wire.
* The harness performs **static analysis and a disposable, paper-only runtime check** — never a live trade, live inference call, or live broker/exchange connection, under any configuration, at any point in its own test suite or its own run against the real codebase. This mirrors the same invariant Task 38's own `run_dry_run_bootstrap` already holds itself to.
* Evidence-based: every harness-produced finding cites a concrete `path:line`/`path:symbol` and the exact resolution mechanism that established it (live-object identity, MRO walk, runtime-instance assertion, or — explicitly labeled as such — a human-reviewed annotation that could not be resolved by identity). No finding is asserted from a script run once and discarded; every harness run is reproducible from committed source.

---

# Harness Requirements

The harness (built by the future implementation task, not by this spec) must satisfy every numbered requirement below. Each is a hard requirement, not a suggestion — an implementation that does not satisfy one is not a complete Task 38.6.

## 1. Source-controlled, deterministic, reusable

The harness is a versioned Python package committed to the repository, not a script written to `/tmp` or any other path `git status` does not track. Running it twice against the same commit, with no other input, produces byte-identical machine-readable output (see requirement 8) — no wall-clock timestamp, random seed, dict/set iteration order, or filesystem-traversal order may influence its result. A future commit changing production source must be checkable by re-running the same committed harness, with no script rewritten from scratch — closing exactly the gap named in the Objective.

## 2. `register_*` discovery vs. `COMPONENT_REGISTRARS`

The harness independently re-derives, from a directory-wide grep/AST scan for `^def register_` in every top-level package's `__init__.py`, the complete set of packages exposing a `register_<framework>` function — the same check Task 38.5 Area 1 and finding **H-2** performed by hand — and diffs it against `app/wiring.py:COMPONENT_REGISTRARS`. `exchange_adapters` (or any other package the check surfaces) must appear in the harness's own discovered set and in its diff output explicitly, whether or not it is present in `COMPONENT_REGISTRARS`. This discovery step is diagnostic evidence the harness reports, not a fix — the harness must never itself add an entry to `COMPONENT_REGISTRARS` (see Non-Goals).

## 3. Fresh-container recursive tracing plus specified-pattern static analysis coverage

For each of the 24 `SAFE_SERVICE_KEYS` roots, the harness builds a fresh, independently, fully-registered `ServiceContainer` (no container or its singleton cache reused across roots — the same invariant every prior pass held) and traces `resolve()`, recording the requested key, the provider's own symbol, and `type(result)`. Independently, and not gated on a given provider having been invoked during that trace, the harness statically walks:

* every registrar function body;
* every provider closure, whether or not it was invoked;
* every class discovered by direct construction inside a registrar or provider;
* `core.container.ServiceContainer`'s and `core.registry.ServiceRegistry`'s own methods, `app.planner.plan`, and `app.preflight.validate_service_keys`/`.run` — as real, source-inspected targets, never assumed safe by name;
* every discovered node's `__init__` and `__new__`;
* **every reachable `__post_init__`** on every discovered node — closing M-7 gap 1: a `@dataclass`-generated `__init__` being classified clean does not exempt a hand-written `__post_init__` on the same class from the same call-graph walk `__init__`/`__new__` already receive;
* every dataclass `default_factory` callable;
* the real MRO base of every `super().__init__()` call, added to the same unified node collection and walked the same way — not left as an opaque `super()` call.

Every node this walk discovers is added to **one unified node collection** — no separate manual list for any subset of it, the same invariant Task 38.5 v4/v5 established and this harness must preserve.

## 4. Identity-first callable resolution

Every call site the static walk encounters is resolved to a live callable object wherever mechanically possible: via direct name/global lookup, owner-class attribute resolution, local-variable type inference, parameter-annotation substitution (including the raw-string-annotation fallback Task 38.5 v5 required for `TYPE_CHECKING`-only imports), or a runtime-instance assertion (the way `self._provider.on_data()` was resolved to `app.wiring._DryRunMarketDataProvider.on_data` in v5). Identity resolution alone is not sufficient to close a node or call — what happens once an object is identified is governed by the following source-availability policy, which replaces any text/name allowlist as the mechanism for deciding what counts as resolved:

* **Project-owned Python callables require inspectable source.** If the resolved object's own defining module is one of the audited project packages, the harness must retrieve and statically walk its real source (`inspect.getsource` succeeding, or equivalent). A project-owned callable whose source cannot be retrieved is **unresolved**, regardless of how safe its name looks — there is no project-code exception to this.
* **A narrow, versioned exact-identity policy covers three specific, source-unavailable-by-construction categories**: a `@dataclass`-synthesized method (an `__init__`/`__repr__`/etc. that is exec-generated, not read from a `.py` file, and is provably synthesized by the dataclass machinery rather than hand-written); a Python stdlib builtin (`len`, `isinstance`, `str.join`, and equivalents, resolved to the real `builtins`/stdlib object); and a C-extension callable whose defining type is a recognized, versioned stdlib/extension type (`decimal.Decimal`, `collections.defaultdict`, and equivalents). Each such acceptance is keyed to an **exact module+qualname identity**, pinned to the harness's own versioned policy table — never a name pattern, a substring match, or a "looks like a known-safe shape" heuristic. **This identity policy is not a text/name fallback**: it accepts a specific, individually-listed, source-unavailable-by-construction object identity, not a class of names judged safe by a human reader.
* **An identity that does not match the exact-identity policy table, and whose source cannot be retrieved, remains unresolved.** There is no third bucket — an object is either project-owned-with-inspectable-source, an exact-identity-policy match, or unresolved. A call the harness cannot place in the first two categories is reported as **unresolved**, full stop, and a nonzero unresolved count keeps the gate at HOLD regardless of how small the count is or how safe the call looks by name.
* **Every accepted exact-identity-policy entry carries its own safety rationale in the machine-readable output** (requirement 8) — a per-entry field naming why that specific module+qualname is accepted (e.g. "dataclass-synthesized, fields already enumerated via `dataclasses.fields()`, no arbitrary code" or "CPython stdlib builtin, no I/O by definition") — not a blanket policy-level note. A future reviewer must be able to see, for any one accepted identity, exactly why it was accepted without re-deriving the policy from scratch.
* **A known-forbidden identity is never eligible for the exact-identity policy and stays forbidden.** `builtins.open`, and every other identity Harness Requirement 6 patches to raise, remain classified as forbidden operations regardless of whether they would otherwise match the shape of a policy-eligible entry (a well-known, versioned, stdlib identity) — the exact-identity policy is an allowance for provably inert, source-unavailable objects, never a route to reclassifying an operation this specification names as forbidden.

This is the harness's core correction of M-7 gap 4: identity resolution establishes *what* a call is; the source-availability and exact-identity policy above — not a text/name allowlist — establishes whether that identification is sufficient to call it resolved.

## 5. Module-state detection — specified-pattern coverage

The harness's static scan covers each of the following specified patterns, across the full audited package scope (the 24 wired frameworks + `app`/`core`/`trading`/`exchange_adapters`/`config`/`events`, the scope Task 38.5 v5 established). This list is the harness's contract, not a claim that every conceivable way a module global could be mutated in Python has been enumerated — a mutation pattern outside this list is out of scope for this task and must be documented as such in the assurance report (Deliverables), not silently implied covered:

* a module-level variable rebound via `global` inside a function (the `core/logging.py:_default_factory` pattern v5 first found);
* a module-level variable rebound via `nonlocal` from a nested scope;
* a module-global object mutated from inside an **ordinary (non-nested) function** via a method call (`.update(`, `.append(`, `.add(`, `.pop(`, etc.) or an augmented assignment (`+=`, `|=`, etc.) — the exact shape M-7 gap 3 names as undetected by every prior pass's closure-only scan;
* a module-global object mutated via attribute assignment (`SOME_OBJECT.attr = ...`) or subscript assignment (`SOME_DICT[key] = ...`), from any scope, top-level or nested;
* the existing v4/v5 categories (module-level `Call` assignments, comprehensions, `@cache`/`@lru_cache` functions, class-level mutable defaults, closure-captured mutables) — carried forward, not dropped.

Every candidate found is classified into one of: immutable constant; intentional documented cache/shared instance; mutable-but-never-mutated lookup; or unexplained shared mutable state. Any candidate landing in the last bucket is a nonzero "unexplained" count and keeps the gate at HOLD.

## 6. Runtime denial checks

The harness builds `Settings`/`BootstrapContext` normally first (the permitted configuration/clock reads happen before any patching — the same ordering v5 established), then patches the following to raise, and confirms `run_dry_run_bootstrap` still succeeds 24/24 with every patch active:

* `builtins.open`; every `pathlib.Path` file method (`open`, `read_text`, `write_text`, `read_bytes`, `write_bytes`);
* `os.makedirs`/`os.remove`/`os.system`, **and, closing M-7 gap 2, the lower-level file-descriptor primitives `os.open`, `os.fdopen`, `os.read`, `os.write`**;
* `socket.socket`, `socket.create_connection`, and any other network-connection entrypoint the static walk's discovery step (requirement 2/3) surfaces;
* `subprocess.Popen`, `subprocess.run`;
* `threading.Thread.start`, `multiprocessing.Process.start`;
* `time.sleep`, `asyncio.sleep`;
* every logging handler/file-opening path reachable from `core.logging.LoggerFactory.configure()` (`logging.StreamHandler`, `logging.handlers.RotatingFileHandler`, and the `os.makedirs` call `configure()` makes when `file_path` is set) — closing the file-vs-console-handler ambiguity **M-6** named;
* **every DB client constructor/connection method and every Redis client constructor/connection method** discoverable in the dependency set or the static walk — closing the other half of M-7 gap 2. If no such client is constructible from any reachable path, the harness must say so explicitly (a stated "none found, none patched" result) rather than silently omitting the category;
* **every exchange-adapter connection method** (`exchange_adapters/`'s own `connect`/equivalent, and any CCXT-backed adapter's connection entrypoint) reachable from the traced graph — this check must never establish a real connection, under any configuration, to satisfy the Architecture Requirements' paper-only invariant;
* every `start`/`invoke`/`compose`/`schedule`/`enqueue`/`submit_order`/`place_order`/`execute_trade`/`predict`/`infer` method any discovered node defines on itself, enumerated from the unified node collection (requirement 3), not hand-listed.

**No real connection or live-trading action is permitted at any point** — every patched target must raise before the traced call would otherwise reach it; the harness's own test suite (requirement 9) proves the patches themselves are effective before the harness ever trusts a "24/24, no forbidden call observed" result from them.

## 7. Negative-control fixtures

The harness ships fixture code, under its own version-controlled test tree, that deliberately reproduces each of the following unsafe shapes, and the harness's test suite asserts the harness **detects** every one of them (a fixture that goes undetected is a harness bug, not a passing test):

* a `__post_init__` that performs a forbidden operation (e.g. calls `open(...)`) on a fixture dataclass reachable from a fixture registrar;
* a call site the harness's resolution mechanism (requirement 4) cannot resolve to a live object — proving the harness reports it as `unresolved`, not silently drops it or defaults it to safe;
* a module-global mutated from inside a plain (non-nested) fixture function via a method call or subscript assignment — proving requirement 5's new detection actually fires;
* a fixture provider that calls `os.open(...)` directly;
* a fixture provider that constructs a DB client, a Redis client, or an exchange-adapter connection and calls its connect method — proving requirement 6's runtime-denial patches actually intercept it, without the fixture ever completing a real connection.

Each negative control has an expected detection outcome documented alongside it; the harness's own pytest suite (requirement 9) fails if any expected detection does not occur.

## 8. Stable machine-readable output

The harness emits one machine-readable result (JSON, schema versioned and documented in the assurance report — see Deliverables) per run, containing at minimum: `schema_version`, `commit_sha`, `roots_traced`, `roots_with_error`, `nodes_total`, `nodes_unresolved`, `calls_total`, `calls_unresolved`, `module_state_candidates_total`, `module_state_unexplained`, `runtime_denial_checks` (per-category pass/fail, including the DB/Redis/exchange-adapter and `os.open`-family categories requirement 6 adds), `negative_controls_total`, `negative_controls_detected`, and `exit_code`. **"Zero unresolved" is a valid, gate-relevant claim only when every negative control in requirement 7 was correctly detected on the same run** — a run whose negative controls did not all fire must report its own primary result as untrustworthy (a distinct `self_test_failed` field, not a silent pass) rather than let a broken detector report a clean bill of health. Exit code `0` requires every unresolved/unexplained count to be zero, every runtime-denial check to have passed, and every negative control to have been detected; any other combination exits nonzero.

## 9. Harness test suite

Beyond the negative-control tests (requirement 7), the harness's own committed test suite covers:

* **Deterministic repeated runs** — running the harness twice against the same commit produces identical machine-readable output (byte-for-byte, or hash-equal after canonicalizing the JSON), asserted directly.
* **Fresh-container isolation** — no state (a resolved instance, a cache, a mutated collection) observably leaks from one of the 24 root traces into another; asserted by construction (a fresh container per root, verified by identity) rather than inferred from the absence of a symptom.
* **Discovery completeness** — a fixture package exposing `register_fixture_framework` is added to a temporary/fixture directory tree, and the harness's discovery step (requirement 2) is asserted to find it and correctly report it as absent from a fixture `COMPONENT_REGISTRARS`-equivalent, proving the discovery mechanism generalizes past the one real `exchange_adapters` case.
* **False-negative fixtures** — an explicit test asserting that if any negative control (requirement 7) were *not* detected, the harness's own `self_test_failed` flag would be set and its exit code would be nonzero — proving the harness fails closed on its own detector breaking, not just on the codebase having a real problem.
* **Safe failure sanitization** — the harness's own error paths (a file it cannot read, a module it cannot import, an unparseable source file) never leak a raw exception, a stack trace, a credential, or filesystem-absolute-path detail into the machine-readable result or the assurance report; each failure mode is asserted to produce a fixed, generic, safe message — the same contract `app/bootstrap.py:run_dry_run_bootstrap` already holds itself to.

---

# Re-run Requirements

Once the harness exists and its own test suite (requirement 9) passes, the future implementation task must run and report, verbatim:

* Targeted `ruff check` and a type check (`mypy` or equivalent, matching this repo's existing per-package pattern) scoped to the harness's own new source — a new package's static-analysis baseline is established here, the same `baseline: unknown` labeling discipline Task 38.5's own Verification Requirements used for every package with no recorded prior count.
* The harness's own test suite, in full.
* The full existing project test suite (`python -m pytest -q` from repo root, under `.venv/bin/python`, never `uv`) — the resulting pass count compared against the last recorded count (741, per Task 38.5's final documents) with any delta explained.
* A **paper-only** 24/24 bootstrap defence run: the harness's own runtime-denial check (requirement 6) executed against the real, current `app.bootstrap.run_dry_run_bootstrap`, confirming `status=SUCCESS, total=24, passed=24, failed=0` with every patch from requirement 6 active — "paper-only" stated explicitly in the report, restating (never relaxing) the invariant that no live trade or live connection occurs at any point in this run.

---

# Gate Rule

`docs/architecture/decisions/ADR-032-structural-audit-gate.md` **remains HOLD unless every required check above passes with zero unresolved, zero unexplained, and every negative control detected on the same run.** If every condition holds, the future implementation task re-evaluates `ADR-032` to reflect the new, harness-backed evidence — a move to ALLOWED requires the harness's own machine-readable result to justify it, cited explicitly, not merely a task-completion claim. If any condition does not hold, `ADR-032` **stays HOLD**, and the future implementation task's report must name **the exact blocker** — which check, which node, which call, which module-global, which runtime-denial category, or which negative control — rather than a general statement that "some issues remain." **Uncertainty is never downgraded**: a harness run that cannot conclusively resolve something must report that fact plainly, the same way this spec's own predecessor documents do, rather than rounding an unresolved or ambiguous result up to a clean pass.

---

# Deliverables

This task (the spec) produces exactly one file: `docs/prompts/task-38.6.md`.

The **future** implementation task this spec defines produces:

* A source-controlled harness package (e.g. `audit_harness/`, or an equivalent top-level location the implementation task chooses and documents) implementing every requirement in Harness Requirements 1–8 — never registered in `app/wiring.py:COMPONENT_REGISTRARS`, never imported by a production framework.
* The harness's own committed test suite and negative-control fixtures (Harness Requirements 7 and 9), living alongside or under the harness package, or under this repository's existing `tests/` tree — the implementation task's choice, documented in its own completion report.
* A machine-readable audit result (the JSON described in Harness Requirement 8), committed at a documented path.
* `docs/audits/task-38.6-assurance-report.md` — the narrative report: what the harness found, the exact re-run outputs from Re-run Requirements, and the schema for the machine-readable result.
* Updated `docs/audits/task-38.5-risk-register.md` — **M-7**'s disposition changed from Open to either Closed (with the harness's evidence cited) or left Open with the exact remaining blocker named, per the Gate Rule; no other finding in that document is to be altered except as directly required by closing M-7.
* Updated `docs/audits/task-38.5-test-gaps.md` — rows 17–20 (the Audit-Assurance Gap Coverage section) marked addressed or left open per the same evidence, one-for-one.
* `docs/architecture/decisions/ADR-032-structural-audit-gate.md` re-evaluated: gate outcome updated (ALLOWED or HOLD-with-named-blocker) with the harness run that justifies it cited by commit and result hash.

---

# Non-Goals

Explicitly out of scope for both this spec-writing pass and the future implementation task it defines:

* **No remediation of H-1 or H-2.** Both remain open, tracked findings. The harness's discovery step (Harness Requirement 2) may re-confirm H-2's evidence; it must never add `exchange_adapters` to `COMPONENT_REGISTRARS` or otherwise fix either finding.
* **No framework refactor.** No production framework's import structure, DI wiring, or module boundaries are changed to make the harness's job easier or to close H-1.
* **No dependency change.** No package is added, removed, or upgraded; `uv` is never invoked in any form; `uv.lock` stays untracked and untouched by this spec-writing pass, and unmodified in content by any future implementation task unless that task explicitly adds a harness-only dev dependency and documents it — which this spec does not authorize.
* **No credential use.** The harness never reads, requires, or is tested against a real API key, database credential, or exchange credential.
* **No broker/exchange connection, staging deployment, or live trading**, under any configuration, at any point — including inside the harness's own negative-control fixtures, which must simulate the *attempt* without completing a real connection.
* **No commit, push, or tag** by this spec-writing pass. The future implementation task's own commit/push/tag policy is out of this spec's scope to authorize; it follows the repository's standing workflow, not a grant made here.

---

# Constraints

* This spec-writing pass modifies no production code, test file, or existing documentation file — it creates exactly one new file, `docs/prompts/task-38.6.md`.
* Do NOT add, remove, or upgrade a dependency. Do NOT run `uv` in any form. `uv.lock` stays untracked and untouched.
* Do NOT commit, push, or tag.
* Every requirement above binds the **future** implementation task, not this spec-writing pass — this pass performs no implementation, runs no harness, and modifies no code.

---

# Acceptance Criteria

✓ `docs/prompts/task-38.6.md` exists and defines a harness-build-and-re-run task — no implementation performed by this spec-writing pass

✓ All nine Harness Requirements specified with concrete, fail-closed acceptance conditions, each traceable to one of M-7's four named gaps or to the source-controlled/reusable precondition the Objective names

✓ Identity-first resolution requirement (Harness Requirement 4) requires inspectable source for every project-owned callable, confines the exact-identity policy to versioned, individually-listed, source-unavailable-by-construction identities (never a name pattern), requires a per-entry safety rationale in machine output, keeps forbidden identities such as `builtins.open` forbidden regardless of that policy, and explicitly forbids a text/name allowlist from converting an unresolved call into a resolved one — with any unresolved node/call/receiver tied to a nonzero result that keeps the gate at HOLD

✓ Module-state requirement (Harness Requirement 5) explicitly names module-global mutation from inside an ordinary function via method call, subscript, augmented assignment, `global`, and `nonlocal` — the exact gap M-7 named as undetected

✓ Runtime-denial requirement (Harness Requirement 6) explicitly names `os.open`/`fdopen`/`read`/`write`, DB clients, Redis clients, and exchange-adapter connections — the exact gap M-7 named as unpatched — while requiring the check remain paper-only with no real connection ever attempted

✓ Negative-control requirement (Harness Requirement 7) requires fixtures proving detection of all five named unsafe shapes, and ties an undetected fixture to a harness bug, not a passing test

✓ Machine-readable output requirement (Harness Requirement 8) names a documented schema, an explicit exit-code contract, and makes "zero unresolved" conditional on negative controls having passed on the same run

✓ Gate Rule is unambiguous: HOLD unless every check passes with zero unresolved/unexplained and every negative control detected; any shortfall is reported as an exact named blocker, never a downgraded or rounded-up uncertainty

✓ Deliverables name the harness, its tests/fixtures, its machine-readable output, the assurance report, and the exact three documents (risk register, test gaps, ADR-032) the re-run updates — with no fifth undocumented file implied

✓ Non-Goals explicitly forbid H-1/H-2 remediation, framework refactor, dependency changes, credential use, broker/exchange connection, live trading, staging, commit, and push

✓ Constraints explicitly forbid this spec-writing pass from implementing anything, modifying `uv.lock`, or committing/pushing/tagging

---

# Completion Checklist

After writing this spec, stop. Do not begin building the harness. Report:

1. The one file created
2. A summary of the nine Harness Requirements, the Re-run Requirements, the Gate Rule, and the Deliverables/Non-Goals
3. Exact output of `git diff --check --no-index /dev/null docs/prompts/task-38.6.md`, `wc -l docs/prompts/task-38.6.md`, and `git status --short --untracked-files=all`

Stop after reporting completion.
