# Task 38.7 — Audit Residual Resolution: Assurance Report

**Executed against:** `main` `dcb1ebc` (commit `dcb1ebc6b7fd34e89979fd9adf8ed0d57bc8ac58`, "Implement Task 38.7 structural audit improvements" — the Phase A source/tests commit). Harness source: `audit_harness/` (production package, never registered in `app/wiring.py:COMPONENT_REGISTRARS`, never imported by any production framework). Tests and negative-control fixtures: `tests/audit_harness/`. Machine-readable result: `docs/audits/task-38.7-result.json` (schema `38.7.0`, result hash `bdbe9cffd1b770140af150e2d66a6524e078f17a817f99bb5d1ec771a7731c0b`, produced by `audit_harness.report.Report.canonical_json()` — never hand-edited).

**Gate outcome: HOLD.** `nodes_unresolved=19`, `calls_unresolved=1032` — both nonzero. Per the Gate Rule (`docs/prompts/task-38.6.md`, restated unchanged by `docs/prompts/task-38.7.md`), any nonzero unresolved count keeps the gate at HOLD. This report names the exact blockers below rather than a general statement that "issues remain," and makes **no claim that `ADR-032` is ALLOWED, that Task 38.7 is complete, or that Task 39 is unblocked.**

---

## 1. What Phase A changed

Per `docs/prompts/task-38.7.md`'s six Remediation Requirements plus the `calls_unresolved_detail_multiplicity` and `mappingproxy` requirements:

* **Category A (source-availability/termination)** — `audit_harness/trace.py`: package-neutral fixed-point traversal (`_MAX_TOTAL_WALK_STEPS`, `visited_funcs` keyed by `(callable identity, specialization)`, `depth_exceeded` surfaced into `roots_with_error` on real budget exhaustion). `audit_harness/identity.py`: `classify_callable` no longer gates the source-walk attempt on `PROJECT_TOP_LEVEL_PACKAGES` membership — any callable with genuinely retrievable `.py` source is walked, project-owned or third-party alike.
* **Category B (multi-hop local-variable inference)** and **Category C (subscript-target chains, flow-sensitive narrowing)** — `audit_harness/trace.py`: `_collect_local_var_types`/`_infer_type`/`_resolve_target` extended for chained assignment, subscript-value types, and `is None`-guard narrowing.
* **Category D (call-site specialization)** — `_specialization_key`, `_bind_call_site_locals`'s `local_var_types` parameter-type propagation across call boundaries.
* **Category E (lambda AST location)** — `_owner_class_from_qualname`, locating a lambda via its enclosing function's real source rather than `inspect.getsource` on the lambda object directly.
* **Category F** — `strategies/__init__.py`: `register_strategies(container: object)` → `register_strategies(container: Container)`, the one production-code line this task is authorized to touch (**L-10**, disposition closed below, §8).
* **`builtins.mappingproxy: import failed` disposition** — resolved via path 1 (preferred): `audit_harness.identity.module_and_qualname` corrects the type's raw `builtins`/`mappingproxy` metadata to the real, importable `types.MappingProxyType`; `unimportable_nodes` is naturally empty (confirmed below, §6).
* **NamedTuple-generated `__new__` structural detection** and the **local-callable-alias mechanism** — both general, structural (never name/package-based) resolution mechanisms, extending the harness's existing `is_dataclass_generated` precedent and its global/closure-attribute resolution respectively.
* **Two ADR-032 Phase 0-authorized `EXACT_IDENTITY_POLICY` entries** — `builtins.str.strip` and `builtins.list.append`, each individually rationalized in `audit_harness/identity.py` (`EXACT_IDENTITY_POLICY_VERSION` `2026-08-20.1` → `2026-08-22.1`). Authorization was recorded in `docs/architecture/decisions/ADR-032-structural-audit-gate.md` (accepting reviewer: Aniket Bhalerao — project owner/reviewer) **before** either entry was implemented, per Two-Phase Provenance. `builtins.str.upper` was explicitly considered and **not** authorized (zero real-trace impact measured); it remains absent from the policy table and any call reaching it remains `unresolved`. `builtins.str.lower` is a pre-existing entry, unchanged by this task.
* **Schema** — `SCHEMA_VERSION` `38.6.0` → `38.7.0` (additive only): new `calls_unresolved_detail_multiplicity` field, reconciled below (§6).

## 2. Self-test result (run before the real audit)

All five negative controls were detected on this run:

| # | Control | Detected |
|---|---|---|
| 1 | `__post_init__` performing a forbidden operation (`open(...)`) | ✅ |
| 2 | An unresolvable call reported `unresolved`, not dropped | ✅ |
| 3 | A module-global mutated from inside a plain (non-nested) function | ✅ |
| 4 | A direct `os.open(...)` call | ✅ |
| 5 | Three named fake clients (DB, Redis, exchange-adapter) — `connect()` intercepted on all three before any real connection | ✅ |

`negative_controls_total=5`, `negative_controls_detected=5`, `self_test_failed=false`.

## 3. Discovery (H-2 — re-confirmed, not remediated)

25 `register_*` functions found; 24 present in `COMPONENT_REGISTRARS`. `missing_from_component_registrars=["exchange_adapters"]` — unchanged from Task 38.6. Per Non-Goals, this task does not add `exchange_adapters` to `COMPONENT_REGISTRARS`; H-2 remains open (§9).

## 4. Trace and identity resolution — counters, and why they are not directly comparable to the `8fd66ca` baseline

* `roots_traced=24`, `roots_with_error=[]` (empty — the fixed-point traversal reached completion on every root without exhausting `_MAX_TOTAL_WALK_STEPS`, confirmed by `test_termination_real_trace_reaches_fixed_point_without_exhaustion`).
* `nodes_total=258` (was `205` at `8fd66ca`), `nodes_unresolved=19` (was `2`).
* `calls_total=6783` (was `1956` at `8fd66ca`), `calls_unresolved=1032` (was `68`).
* Identity buckets across all 6783 calls: `project_source_available=3206`, `exact_identity_policy=2541`, `forbidden=4`, `unresolved=1032`.

**These totals are not apples-to-apples with the Task 38.6 baseline, and this report does not present them as such.** Category A's Requirement (broaden source-availability so third-party source is walked the same way project-owned code is) is precisely what grew `calls_total` from 1956 to 6783 and `nodes_total` from 205 to 258: the walker now recurses into `pydantic_settings`/`python-dotenv` internals that were entirely unreached and uncounted at `8fd66ca`. A larger walked universe producing a larger absolute unresolved count is an expected, intended consequence of correctly implementing that requirement — not a regression. Both figures for the same, real underlying question this task is scoped to answer — "of what the harness now correctly reaches, how much is still unresolved" — are the ones that matter, and are reported in full below.

**The two nodes the `8fd66ca` baseline named are confirmed closed:** neither `config.settings.Settings` nor `pydantic_settings.main.BaseSettings` appears in the current `nodes_unresolved_detail` (confirmed directly against the live trace, not merely absent from a stale list). The two Category-A-adjacent NamedTuple nodes diagnosed mid-task, `dotenv.parser.Binding` and `dotenv.parser.Original`, are likewise confirmed closed.

### 4.1 The 19 currently-unresolved nodes

All 19 are C-level stdlib types newly *discovered* only because Category A's broadened walk now recurses into third-party internals that reference them — none is a name the `8fd66ca` baseline ever saw, and none is a forbidden identity:

```
_io.StringIO                    builtins.memoryview           collections.deque
_thread.RLock                   builtins.range                functools.partial
_thread._ExceptHookArgs         builtins.type                 itertools.islice
builtins.AssertionError         collections.OrderedDict       weakref.ReferenceType
builtins.NotImplementedError
builtins.OSError
builtins.OverflowError
builtins.bytearray
builtins.bytes
builtins.int
builtins.map
```

Each is a CPython builtin/stdlib container, exception, or synchronization-primitive type whose `.__init__`/`.__new__` has no exact-identity-policy entry and (for the C-implemented ones) no retrievable source — the same structural reason `builtins.str.strip`/`builtins.list.append` were unresolved before this task's two Phase 0 authorizations, not yet individually reviewed for a policy entry of their own. No Phase 0 authorization was sought for any of these 19 this task — none was found, during Category A/B/C/D/E work, to be a specific, named blocker that mechanism work alone could not address; they simply were not reached and diagnosed to that level of specificity within this task's scope.

### 4.2 The 1032 unresolved calls — dominant families

Recomputed directly from the raw `CallRecord`s (not the 489-entry deduplicated `calls_unresolved_detail`):

| Raw count | Identity / callee shape |
|---|---|
| 191 | `builtins.str.join` |
| 183 | `core.interfaces.Registration.provider` (confirmed genuinely dynamic — `Registration`'s own `provider` attribute, no fixed identity to resolve to) |
| 110 | `builtins.mappingproxy.items` |
| 81 | `emit` (no resolved identity at all — a callee expression the walker could not tie to any live object) |
| 27 | `cls.model_config.get` (pydantic internals) |
| 16 | `builtins.type` |
| 15 | `builtins.int` |
| 14 | `builtins.hasattr` |
| 13 | `dict.get` |
| 12 | `builtins.ValueError` |
| 11 | `self.config.get` |
| 10 | `re.error`, `builtins.ord` (10 each) |
| — | remainder: a long tail of individually small-count identities (`builtins.range`, `builtins.print`, `sys._getframe`, `builtins.chr`, `posixpath.abspath`, `warnings.warn`, `settings_cls.model_config.get`/`.model_fields.items`, and others), each under 10 raw occurrences |

**326 of the 1032** have no resolved identity at all (`verdict.qualname is None`) — the walker could not tie the callee expression to any live object well enough to even name a candidate identity, let alone classify it. These are the genuinely hardest residual: not "known identity, no policy entry" but "identity itself not pinned." No mechanism in Requirements 1–5 closes these without a further, specifically-diagnosed extension this task did not undertake.

**Multiplicity reconciliation:** `sum(calls_unresolved_detail_multiplicity.values()) == calls_unresolved` holds exactly (1032 == 1032, verified against the persisted JSON, not only in-memory), and `set(calls_unresolved_detail_multiplicity) == set(calls_unresolved_detail)` holds exactly (489 == 489 keys).

**No forbidden identity was established among any of the 1032; unresolved behavior remains safety-unknown, not proven benign — exactly why this stays HOLD.**

## 5. This task's own delta (the correct, apples-to-apples comparison)

The comparison that *is* directly meaningful is within this task's own work, against the identical, already-broadened walked universe: immediately before the two Phase 0-authorized entries were implemented, this same commit's mechanism work alone (Categories A–F, NamedTuple detection, local-callable-alias resolution, parameter-type propagation, receiver-prepend binding) had already reduced `calls_unresolved` to `1052` (from an initial post-Category-A figure that is not separately preserved as a named checkpoint in this report, since it was an intermediate diagnostic state, not a deliverable). Implementing the two authorized entries (`builtins.str.strip`, `builtins.list.append`) then closed exactly **20 more raw calls** (`1052 → 1032`): 1 site (`config.settings.get_settings → load_environment() → active_environment() → Environment.from_str() :: value.strip`) and 19 sites across 11 deduplicated call sites (`app.bootstrap.run_dry_run_bootstrap`, `app.planner._plan`'s `dependents[...].append`/`deps_by_component[...].append`/`order.append`, `app.preflight.run`, `config.settings.Settings`'s pydantic-internal alias handling, and `agents.manager.DefaultDecisionManager`'s logging-configure chain). `nodes_unresolved` was unaffected by either entry (0 nodes resolve to a `str`/`list` method).

## 6. Module-state (unchanged mechanism)

`candidates_total=523`, `unexplained_total=0`. Buckets: `mutable_never_mutated_lookup=394`, `immutable_constant=126`, `intentional_documented_shared_instance=3`. `module_state_parse_errors=[]`.

## 7. Runtime denial — paper-only

`bootstrap_status=SUCCESS`, `preflight_total=24`, `preflight_passed=24`, `preflight_failed=0`, `forbidden_call_observed=None`. Categories patched: `file_io`, `lifecycle_methods`, `logging_handlers`, `network`, `os_low_level`, `sleeps`, `subprocess`, `threads_processes`. `db_clients_found=[]`, `redis_clients_found=[]`. `exchange_adapter_connections_found=["exchange_adapters (present, not wired into COMPONENT_REGISTRARS -- see H-2)"]`. **`unimportable_nodes=[]`** — the `builtins.mappingproxy: import failed` entry from the `8fd66ca` baseline is fully closed via the `types.MappingProxyType` qualname correction (Layer 2 of Gate Outcome Requirements, closed).

`lifecycle_methods_patched` — **34** targets (was 33 at `8fd66ca`), independently confirmed against `tests/audit_harness/test_lifecycle_denial_completeness.py`'s reviewed, non-circular 34-entry baseline: `dotenv.parser.Position.start` (a real, third-party `@classmethod`) newly included; `builtins.range.start` (a non-callable `member_descriptor`) correctly excluded under the same rule — both a direct, reviewed consequence of Category A's broadened walking reaching a new third-party class.

**This run performed no real trade, no real inference call, and no real network/database/Redis/exchange connection at any point.**

## 8. L-10 disposition — closed

`docs/audits/task-38.5-risk-register.md`'s **L-10** (`strategies/__init__.py`'s `register_strategies(container: object)` typing gap) is closed by this Phase B evidence: `container.has`, `container.register_class`, `container.register_singleton` at `registrar:strategies` all resolve on this run (confirmed via `test_category_f_registrar_strategies_call_sites_resolve`, and independently by their absence from `calls_unresolved_detail`). See the risk register's own updated entry for the full citation.

## 9. H-1, H-2 — unchanged, explicitly not remediated by this task

`missing_from_component_registrars=["exchange_adapters"]` (§3). Per `docs/prompts/task-38.7.md`'s H-2 Reconciliation, this task does not remediate H-2 — wiring `exchange_adapters` into `COMPONENT_REGISTRARS` would add a 25th framework to the dry-run bootstrap and its 24/24 preflight check, a change to the live-network safety boundary this task is explicitly forbidden from making unilaterally. H-2 requires its own separately authorized task.

**H-1** (`docs/audits/task-38.5-risk-register.md`'s H-1 entry: "every prior framework is forbidden from importing another framework directly" is false for 14 of the 24 wired frameworks, plus `exchange_adapters`) is likewise open and unchanged — Task 38.7's scope, per its own Non-Goals, does not touch H-1 either; the risk register's H-1 disposition remains `Open`, exactly as recorded before this task.

## 10. Re-run requirements

* **Targeted Ruff**: `ruff check audit_harness tests/audit_harness` → **all checks passed**.
* **Targeted mypy**: `mypy audit_harness` → **no issues found in 9 source files**.
* **Harness's own test suite**: `pytest tests/audit_harness -q` → **70 passed**.
* **Full project test suite**: `pytest -q` → **811 passed**.
* **`git diff --check`**: exit 0, no whitespace errors.
* **Paper-only 24/24 bootstrap defence**: see §7 — `SUCCESS`, `24/24`, confirmed paper-only, no live connection at any point.
* **Deterministic repeated-run comparison**: two `run_full_audit()` calls against commit `dcb1ebc6b7fd34e89979fd9adf8ed0d57bc8ac58` produce byte-identical `canonical_json()` and an identical `result_hash()` (`bdbe9cffd1b770140af150e2d66a6524e078f17a817f99bb5d1ec771a7731c0b`). The persisted `docs/audits/task-38.7-result.json` was independently re-parsed and confirmed to equal the in-memory canonical data and reproduce the same hash byte-for-byte.

## 11. Conclusion

Phase A's mechanism work and the two ADR-032 Phase 0-authorized policy entries are implemented, individually regression-tested (positive, negative, and real-trace evidence per mechanism), and proven on a real re-run against the committed Phase A code. `unimportable_nodes` (Layer 2) is closed. **`ADR-032`'s three-layer gate remains HOLD**: Layer 1 fails on two counts (`nodes_unresolved=19`, `calls_unresolved=1032`, both nonzero — see §4 for why these are not directly comparable to the `8fd66ca` baseline, and why they are not a regression), and **Layer 3 (H-1 and H-2) remains open** and is not remediated by this task (§9). This report makes **no claim that `ADR-032` reaches ALLOWED, that Task 38.7 is complete, or that Task 39 is unblocked** — a future task must close the remaining node/call families named in §4.1/§4.2 (or record further individually-authorized Phase 0 entries for genuinely irreducible ones) and separately resolve H-1 and H-2, before the gate can move.

See `docs/architecture/decisions/ADR-032-structural-audit-gate.md` for the re-evaluated gate record, citing this report's commit and result hash.
