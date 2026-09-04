# Task 38.11 Phase B — Assurance Report

**DI Registration Provider-Set Resolution — authorization evidence**

| Field | Value |
|---|---|
| Phase | B (evidence) |
| Evidence schema | `38.11.1` |
| Harness report schema | `38.8.0` (unchanged by this task) |
| Implementation commit | `86820007cba4160f15f04bf3a4f297c705c5afd7` |
| Authorization commit | `b17f4be8002a25372ffcb44c405c6b7d991ea379` |
| Interpreter of record | CPython 3.12.13 (`pyproject` `requires-python == "3.12.*"`) |
| Accepting reviewer | Aniket Bhalerao — project owner/reviewer |
| Verdict | **PASS** — scoped, see §1 |

---

## 1. What this proves, and what it does not

**What it proves.** The Task 38.11 Phase A implementation, as pushed at `86820007`, conforms to the ten conditions of the DI Registration Provider-Set Resolution mechanism authorized prospectively in ADR-032 Phase 0.3, and the evidence requirements of that authorization are satisfied. The mechanism emits exactly one aggregate `CallRecord` per site visit, resolves all 191 of them, deduplicates solely by object identity, reconstructs nothing, and moves `calls_unresolved` from 1092 to 901 with zero residue.

**The PASS verdict applies ONLY to conformance with the authorized Task 38.11 mechanism and its evidence requirements. It is not a gate verdict.**

**What it does not prove.** Nothing here clears, weakens, or re-scopes the structural audit gate:

- **ADR-032 remains INDETERMINATE / HOLD.**
- **Task 39 remains BLOCKED.**
- **M-7 remains `Open, narrowed`.**
- **M-8 remains `Open` and unchanged** — taxonomy incomplete; narrowed only within the original 11-family taxonomy.
- **M-9 remains `Open` and unchanged** — the registrar-discovery scan gap is explicitly **not** remediated by Task 38.11; `audit_harness/discovery.py` was not modified.

All three Layer-1 blockers are independently nonzero, and **each one alone is sufficient to hold the gate**: `nodes_unresolved = 16`, `calls_unresolved = 901`, `implicit_dispatch.unresolved_dispatches = 6888`. The audit's own `exit_code` is `1`.

## 2. Baseline

Measurement was taken against the published Phase A commit with `HEAD`, `origin/main`, and the remote `main` all equal to `86820007cba4160f15f04bf3a4f297c705c5afd7`, on branch `main` with no divergence. The only worktree entry throughout was the untracked `uv.lock`, whose SHA-256 — `07982ccb31c51dd96c4a4936509c2c22ac25d753f9c20e831dcd500587ae05fb` — was recorded before the battery and re-verified unchanged after it.

**Two-Phase Provenance.** The human authorization (`b17f4be8`, ADR-032 section *Task 38.11 Phase 0.3*) was recorded and pushed **before** any implementing code was written. `b17f4be8` is the parent of `86820007`, which git itself attests. The four implementation paths are `audit_harness/trace.py`, `audit_harness/self_test.py`, `tests/audit_harness/test_negative_controls.py`, and `tests/audit_harness/test_task_38_11_phase_a.py`.

## 3. The mechanism, and what the 191 records actually are

The aggregate records carry `resolution_mechanism = "di-registration-provider-set"`. Measured read-only at `86820007` by invoking `audit_harness.trace.run_trace()` directly and filtering `CallRecord`s on that field:

| Quantity | Measured |
|---|---|
| Aggregate records emitted | **191** |
| Aggregate records unresolved | **0** |
| Identity categories | `{project_source_available: 191}` |
| Distinct rationale strings | **1**, repeated 191× |
| Distinct site labels | 74 |
| Semantic targets | 214 |
| Walked objects | 214 |
| Symbol identities | 76 |
| Code objects | 101 |

The single rationale, computed live at emit time and never written as a literal:

```
semantic_targets=214; walked_objects=214; symbol_identities=76; code_objects=101; dedup=object-identity; all_targets_resolved=true
```

### 3.1 Site visits, not source locations — stated precisely

**The 191 records represent walker site visits of ONE source AST location under the existing specialization semantics. They are NOT 191 unique source locations.** This was verified mechanically rather than asserted: an `ast` walk of `ServiceContainer.resolve` (defined at `core/container.py:87`) contains **exactly one** `Call` node whose callee text is `registration.provider` — namely `registration.provider(cast(Resolver, self))` at **`core/container.py:116`**. The 191 records are spread across 74 distinct site labels, all carrying that same callee text, because the walker re-visits that one site once per enclosing specialization. Condition 7 of the authorization — *exactly ONE aggregate `CallRecord` per site visit* — is therefore satisfied: one record per visit, never one per target.

### 3.2 Deduplication, and the two diagnostic axes

**Deduplication is solely `id(_underlying(provider))`.** No symbol-based or code-object-based deduplication is used anywhere in the mechanism.

**The 76 symbol identities and 101 code objects are diagnostic UNSOUND axes, not authorization predicates.** They are published in the rationale precisely because they are the two deduplication axes the authorization forbids: recording them alongside `semantic_targets` makes any future regression to symbol- or code-based deduplication visible in the report itself. Neither value participates in the resolution verdict, and neither licenses any classification. This matters because, as ADR-032 records, the prospective metrics do **not** discriminate between the authorized 214-object set and the unsound 76-identity or 101-code-object sets — all three measure `calls_unresolved = 901`. Soundness here rests on the explicit assertion in the implementation, never on these numbers.

**No provider objects were reconstructed.** The target set is captured by reference from the existing `discovery_container` sweep already present in `providers_seen`. The reconstruction hazard recorded in ADR-032 — reconstructed objects defeat `id`-based deduplication and regress `implicit_dispatch.unresolved_dispatches` from 6888 to 7374 while `calls_unresolved` still displays the desired 901 — is confirmed avoided by the measured `unresolved_dispatches = 6888`, which is unchanged.

## 4. Policy delta — zero

`EXACT_IDENTITY_POLICY` was not touched. `audit_harness/identity.py` is not among the four changed paths.

| Field | Before | After |
|---|---|---|
| Version | `2026-09-02.1` | `2026-09-02.1` |
| Entry count | 86 | 86 |
| Keys added | — | 0 |
| Keys removed | — | 0 |

## 5. Verification battery

Every command below was run fresh against the pristine, published `86820007`.

| Check | Command | Result |
|---|---|---|
| Targeted tests | `uv run pytest tests/audit_harness/test_task_38_11_phase_a.py tests/audit_harness/test_negative_controls.py -q` | **15 passed** |
| Harness suite | `uv run pytest tests/audit_harness -q` | **211 passed** |
| Full suite | `uv run pytest -q` | **964 passed** |
| Ruff (four Phase A paths) | `uv run ruff check <four paths>` | **All checks passed** |
| Ruff (harness scope) | `uv run ruff check audit_harness tests/audit_harness` | **All checks passed** |
| Mypy (four Phase A paths) | `uv run mypy <four paths>` | **Success: no issues found in 4 source files** |
| Whitespace | `git diff --check` | clean |

### 5.1 Pre-existing repo-wide ruff findings — disclosed, not a regression

`uv run ruff check .` reports **75 errors**. **Zero of them fall in any of the four Phase A paths**, which the two scoped ruff runs above confirm independently. Breakdown by rule: `UP042` ×68, `UP046` ×4, `B027` ×2, `E501` ×1, across 55 files (largest: `config/constants.py` ×5, `models/order.py` ×4, `adapters/interfaces.py` ×4, `adapters/binance/models.py` ×4). Representative: `adapters/binance/models.py:24` — `UP042 Class BinanceSide inherits from both str and enum.Enum`. Phase A neither introduces nor fixes any of these.

## 6. Fresh audit — three byte-identical runs

**Canonical command:** `uv run python -m audit_harness.run_audit`

This command writes its report to stdout and persists nothing to the repository. For evidence capture only, each run's stdout was redirected to `/tmp/phaseb_run1.json`, `/tmp/phaseb_run2.json`, and `/tmp/phaseb_run3.json` — outside the repository, none committed. **The redirection is an evidence-capture mechanism, not part of the canonical command.**

All three captures are 180,006 bytes and byte-for-byte identical.

| Hash | Value |
|---|---|
| Raw capture SHA-256 (all three runs) | `30cb0df927406afec109f0bc7d844c2acdd83b2728fb9beac68d365c5d1ac1d8` |
| Canonical SHA-256 | `afee9fff17de44c96fcc981f818e6e117b6626bf39d42c3c2f6cb81a38146841` |

The canonical hash was computed for this task from its own captures under the convention documented by the Task 38.10 artifact — `audit_harness.report.AuditReport.canonical_json()`, i.e. `json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True) + "\n"`. It was **not** copied from the previous task. Each raw capture is exactly the canonical JSON (180,005 bytes) plus the single extra trailing newline `print()` emits; that one-byte relationship was verified directly. **These hashes are of the audit run's output, not of this evidence file.**

### 6.1 Operator error during evidence capture — disclosed, and distinct from the three valid runs

A **fourth, earlier** capture attempt produced a **0-byte file** (SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, the hash of empty input) with exit code 1. The cause was an earlier `cd /tmp` that left the shell's working directory outside the repository, so `python -m audit_harness.run_audit` raised `ModuleNotFoundError: No module named 'audit_harness'` under an unrelated interpreter from the uv cache.

**This was operator error in the evidence-capture procedure — not a harness defect, and not a nondeterministic result. The harness never ran.** It is disclosed here for completeness and is **explicitly not one of the three valid runs**. Each of the three counted runs was invoked with an explicit repository-root working directory, matching the documented usage in `audit_harness/run_audit.py` ("from the repository root"). `runs = 3` counts successful canonical runs only.

### 6.2 Measured metrics

| Metric | Value |
|---|---|
| `calls_total` | 7105 |
| `calls_unresolved` | **901** |
| `nodes_total` / `nodes_unresolved` | 268 / **16** |
| `implicit_dispatch` candidates / unresolved / resolved | 7012 / **6888** / 124 |
| `implicit_dispatch.syntax_sites_total` | 10474 |
| `implicit_dispatch.resolved_non_descriptor_exclusion` | 3777 |
| `implicit_dispatch.explicit_path_duplicates` | 0 |
| Identity bucket — `project_source_available` | 3554 |
| Identity bucket — `exact_identity_policy` | 2645 |
| Identity bucket — `forbidden` | 5 |
| Identity bucket — `unresolved` | 901 |
| Bucket sum | 7105 (= `calls_total`) |
| `roots_traced` / `roots_with_error` | 25 / `[]` |
| Module-state candidates / unexplained / parse errors | 523 / 0 / 0 |
| Runtime denial preflight passed / failed / total | 25 / 0 / 25 |
| `forbidden_call_observed` | `null` |
| Negative controls | **10 / 10** |
| `self_test_failed` | `false` |
| `EXACT_IDENTITY_POLICY` version / entries | `2026-09-02.1` / 86 |
| `exit_code` | **1** (expected: gate holds) |

## 7. `calls_unresolved` reconciliation — zero residue

| | |
|---|---|
| Counter of record before Phase B (at `b17f4be8`) | 1092 |
| Measured at `86820007` | **901** |
| Delta | **−191** |
| Provider-set records resolved | 191 |
| Arithmetic | `1092 − 191 == 901` |
| **Residue** | **0** |

**The 191-record reconciliation has zero residue.** The delta maps one-to-one onto the 191 aggregate records tagged `di-registration-provider-set`, every one of which resolved to `project_source_available`. No call site outside that mechanism changed category in either direction.

## 8. Prediction reconciliation

| Metric | Predicted (ADR-032 Phase 0.3) | Measured | Result |
|---|---|---|---|
| `calls_total` | 7105 | 7105 | confirmed |
| `calls_unresolved` | 1092 → 901 | 1092 → 901 | confirmed |
| `nodes_total` / `nodes_unresolved` | 268 / 16 | 268 / 16 | confirmed |
| `implicit_dispatch` cand./unres./res. | 7012 / 6888 / 124 | 7012 / 6888 / 124 | confirmed |
| Probe records emitted / unresolved | 191 / 0 | 191 / 0 | confirmed |
| Negative controls | 7/7 → 10/10 | 10 / 10 | confirmed — see §8.2 |
| `visited_funcs` | 1625 → 1625 | **not measured** | **not evaluable** — see §8.1 |
| `resolve_events` | 383 → 383 | 383 (non-canonical) | **not canonically confirmed** — see §8.1 |

### 8.1 `visited_funcs` and `resolve_events` — not canonically confirmed

**Neither `visited_funcs` nor `resolve_events` is a field of the canonical schema-`38.8.0` report.** Their ADR predictions must therefore **not** be described as canonically confirmed.

- **`visited_funcs`** is an attribute of `audit_harness.trace.StaticWalker`, not of `TraceResult`, and it was **not measured** in Phase B. The prospective 1625 → 1625 figure is neither confirmed nor refuted by this evidence.
- **`resolve_events`** was observed to be **383** by direct, read-only `run_trace()` introspection outside the canonical report path, matching the prospective figure. This is a **non-canonical observation only** and is recorded as such.

### 8.2 Negative controls — intentional, and excluded from the neutrality claim

The move from **7/7 to 10/10** is intentional and was authorized in advance by ADR-032 Phase 0.3, which **explicitly excludes it from the metrics-neutrality claim**. That neutrality claim covers `calls_total`, `visited_funcs`, `nodes_total`, `nodes_unresolved`, `resolve_events`, and every `implicit_dispatch.*` field only. The three added controls are harness self-tests for this mechanism: an incomplete provider set fails closed; one unresolved member makes the whole aggregate unresolved, with no partial credit; and an empty or provenance-unavailable set fails closed rather than passing vacuously. All ten controls were detected.

## 9. Scope confirmation

| Assertion | Status |
|---|---|
| Implementation behaved as authorized | ✅ yes |
| Provider objects reconstructed | ❌ no (forbidden — avoided) |
| Symbol- or code-based deduplication used | ❌ no |
| Key specialization added | ❌ no |
| `EXACT_IDENTITY_POLICY` modified | ❌ no |
| `audit_harness/discovery.py` modified | ❌ no |
| Implicit descriptor `__get__` behavior changed | ❌ no |
| M-8 or M-9 changed | ❌ no |
| ADR-032 status changed | ❌ no |
| Risk register modified | ❌ no |
| Paper-trading boundary touched | ❌ no |
| Live-trading boundary touched | ❌ no |
| `uv.lock` modified | ❌ no |

## 10. Governance state — unchanged

**ADR-032 remains INDETERMINATE / HOLD. Task 39 remains BLOCKED.** H-1 remains `Closed` (Task 38.9B) and H-2 remains `Closed` (Task 38.9A); zero High findings remain open. **M-7 remains `Open, narrowed`. M-8 and M-9 remain `Open` and unchanged.** The `builtins.str.join` Phase 0 review remains **paused and unrecorded** — neither authorized nor rejected here.

## 11. Worktree and artifact provenance

This phase modified no production source, no test, and no governance document. It created exactly two files, both new and untracked at the time of writing:

- `docs/audits/task-38.11-result.json`
- `docs/audits/task-38.11-assurance-report.md`

The three audit captures were written to `/tmp`, outside the repository, and are not committed. `uv.lock` remains untracked and byte-identical before and after. Amending ADR-032 and the risk register is **Phase C's exclusive responsibility and has not been started**.

## 12. Artifact hash

**`docs/audits/task-38.11-result.json` — SHA-256:**

```
9322137e0d9d919ec0fb2f5ba995a23605c464f56f4d54f134309f551663c8c1
```

Following the convention of the preceding evidence artifacts, **this report deliberately does not embed its own hash** — a file cannot contain its own digest. This report's SHA-256 is reported separately at hand-off and is recorded in ADR-032's `Related` bullet by Phase C.

## 13. Conclusion

**PASS — scoped to conformance with the authorized Task 38.11 mechanism and its evidence requirements.**

The implementation at `86820007` does what ADR-032 Phase 0.3 authorized, and nothing else. `calls_unresolved` fell 1092 → 901, reconciling with **zero residue** to 191 aggregate provider-set records — **191 walker site visits of one source AST location at `core/container.py:116`, not 191 unique source locations**. Deduplication is solely `id(_underlying(provider))`; the 76 symbol identities and 101 code objects are diagnostic unsound axes only. Every other measured counter is neutral, with the intentional and pre-authorized exception of the negative-control count.

**The gate does not move. ADR-032 remains INDETERMINATE / HOLD, and Task 39 remains BLOCKED**, on three independently sufficient Layer-1 blockers — `nodes_unresolved = 16`, `calls_unresolved = 901`, `implicit_dispatch.unresolved_dispatches = 6888` — and an audit `exit_code` of `1`.
