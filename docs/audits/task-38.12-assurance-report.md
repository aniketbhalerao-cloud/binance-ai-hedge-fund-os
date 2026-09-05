# Task 38.12 Phase B — Assurance Report

**Task:** Task 38.12 — `builtins.str.join` exact-identity authorization
**Phase:** B (assurance / evidence only)
**Verdict:** **PASS** — mechanism conformance only, scoped as stated in §1
**Machine-readable companion:** `docs/audits/task-38.12-result.json` (schema `38.12.1`)

| Provenance | SHA |
| --- | --- |
| Phase 0 authorization (ADR-032 "Task 38.12 Phase 0") | `aa220b705e68ec1a9c900da69597d663732b0eb9` |
| Phase A implementation | `afd5f5f833f3a818c05ee66ae1c16f8a469f0560` |
| Measurement baseline (Task 38.11 Phase B) | `86820007cba4160f15f04bf3a4f297c705c5afd7` |

`afd5f5f`'s parent is exactly `aa220b7`: the authorization was committed **before** the
implementation, satisfying Task 38.7's Two-Phase Provenance requirement. `afd5f5f` is
simultaneously `HEAD`, `origin/main`, and the live remote `refs/heads/main`.

**Interpreter of record:** CPython 3.12.13 (repository `.venv`).

---

## 1. What this proves, and what it does not

**Proves.** The single identity ADR-032's Phase 0 section authorized — `builtins.str.join`,
and nothing else — was added to `EXACT_IDENTITY_POLICY`; it resolves **199** explicit-call
records on the live trace through the real classification path; it leaves **zero**
`builtins.str.join` residuals unresolved; and the reduction in `calls_unresolved` is
attributable to it **exactly, with zero residue**.

**Does not prove.** Nothing about the gate. ADR-032 remains **INDETERMINATE / HOLD** and
Task 39 remains **BLOCKED**. All three Layer 1 blockers remain nonzero. Phase B modified no
production source, no test, and no governance document. Phase C has not started.

A separate matter that a reader must not skip: **unauthorized modifications to a Phase A
test file were observed in the working tree twice during this task.** The published commit
was never affected, and this report's measurements were taken so as to be immune to it, but
the live worktree currently does **not** match `afd5f5f`. See §10.

---

## 2. Baseline, and why Task 38.11's measurement is the right one

The immediate code baseline is Task 38.11 Phase B, measured at `8682000`. The three commits
between `8682000` and `afd5f5f`'s parent `aa220b7` touched only `docs/`:

```
docs/architecture/decisions/ADR-032-structural-audit-gate.md
docs/audits/task-38.11-assurance-report.md
docs/audits/task-38.11-result.json
docs/audits/task-38.5-risk-register.md
```

`git diff --name-only 8682000 aa220b7 -- audit_harness tests` is **empty**. No code changed
in that span, so 38.11's counters are the valid immediate predecessor.

---

## 3. Policy delta — exactly one entry

| | Before (`aa220b7`) | After (`afd5f5f`) |
| --- | --- | --- |
| `EXACT_IDENTITY_POLICY_VERSION` | `2026-09-02.1` | **`2026-09-05.1`** |
| Entry count | 86 | **87** |

- **Added (1):** `builtins.str.join`
- **Removed (0):** none

`str.join` is a C-implemented `method_descriptor` carrying no `__module__`; its key
`("builtins", "str.join")` is reconstructed from `__objclass__` by
`audit_harness.identity.module_and_qualname`. The entry's rationale records — rather than
presumes benign — that `str.join` iterates its argument, so the argument's
`__iter__`/`__next__` side effects execute during the call. That is the single most
load-bearing qualification in the authorization, and it is pinned by a regression test.

---

## 4. The mechanism — what the 199 records are

Measured via `audit_harness.trace.run_trace()`, filtering `explicit_calls` on
`verdict.module` / `verdict.qualname`. **No name matching and no text matching.**

| Measurement | Value |
| --- | --- |
| Resolved via `exact_identity_policy` | **199** |
| Residual `unresolved` | **0** |
| Present in any other bucket | **0** |
| Distinct rationales attached | **1** (identical to the policy table text) |

These are **site visits**, not distinct source locations — the walker's fixed-point
traversal reaches several sites more than once, exactly as Task 38.7 documented for
`calls_unresolved` generally. The heaviest contributors are the DI container's
`" -> ".join(...)` circular-dependency message and the `", ".join(...)` messages in
`core/logging.py`, reached through the per-component provider builders.

### 4.1 The excluded identities — the half that proves there is no pattern

The authorization explicitly declined to review the neighbouring `.join` identities. All
remain out of the policy table and none resolves through it:

| Identity | In policy | Trace occurrences | Bucket | Status |
| --- | --- | --- | --- | --- |
| `posixpath.join` | No | 3 | `unresolved` × 3 | Remains unresolved, as authorized |
| `builtins.bytes.join` | No | 1 | `unresolved` × 1 | Remains unresolved, as authorized |
| `builtins.bytearray.join` | No | 0 | — | Unauthorized and unaffected |

`bytearray.join` is **never reached on the live trace**, so its exclusion cannot be
demonstrated by a trace residual. It is proven instead by direct classifier assertion
(`test_unauthorized_join_identities_classify_unresolved`), which drives it through the same
`module_and_qualname` → `classify_callable` path and confirms `unresolved` with no
rationale. Stating this precisely matters: a reader who saw only "0 occurrences" might
mistake absence of evidence for evidence of exclusion.

### 4.2 No broad `.join` matching exists

- Policy keys ending in `.join`: **`["builtins.str.join"]`** — exactly one.
- Every traced identity whose qualname ends in `join`:

| Identity | Category | Count |
| --- | --- | --- |
| `builtins.str.join` | `exact_identity_policy` | 199 |
| `posixpath.join` | `unresolved` | 3 |
| `builtins.bytes.join` | `unresolved` | 1 |

Two sibling `.join` identities sit on the trace and stay unresolved. No wildcard,
name-pattern, or textual `".join"` exemption could produce that split.

---

## 5. Fresh audit — measured, not assumed

**Canonical command:** `uv run python -m audit_harness.run_audit`

Three runs. Runs 1 and 2 executed in-repo; run 3 from a pristine out-of-repo extract of
`afd5f5f`. Runs 1 and 2 are **byte-identical**
(`3ed7ededcdd819bb63b4aa49152b89ea1e143420fef0ec5d678401617e49a0f0`). Run 3 differs in the
single field `commit_sha` (`"unknown"`, since the extract carries no `.git`); **all other
fields are identical**.

### 5.1 Measured metrics

| Counter | Measured | Expected | |
| --- | --- | --- | --- |
| `calls_total` | 7105 | 7105 | MATCH |
| `calls_unresolved` | 702 | 702 | MATCH |
| `nodes_total` | 268 | — | |
| `nodes_unresolved` | 16 | 16 | MATCH |
| `implicit_dispatch.syntax_sites_total` | 10474 | — | |
| `implicit_dispatch.dispatch_candidates_total` | 7012 | — | |
| `implicit_dispatch.resolved_dispatches` | 124 | — | |
| `implicit_dispatch.unresolved_dispatches` | 6888 | 6888 | MATCH |
| `identity_resolution_buckets.exact_identity_policy` | **2844** | 2844 | MATCH |
| `identity_resolution_buckets.project_source_available` | 3554 | — | |
| `identity_resolution_buckets.forbidden` | 5 | — | |
| `identity_resolution_buckets.unresolved` | 702 | — | |
| `module_state_candidates_total` | 523 | — | |
| `module_state_unexplained` | **0** | — | |
| `negative_controls` | 10 / 10 detected | — | |
| `self_test_failed` | `false` | — | |
| `exit_code` | 1 | 1 | MATCH |

All six pinned expectations were treated as claims to verify and **all six were confirmed**.

Supporting: `roots_traced` 25, `roots_with_error` 0, runtime-denial `bootstrap_status`
SUCCESS at preflight 25/25, `forbidden_call_observed` `null`, `unimportable_nodes` empty.

### 5.2 `exit_code = 1` is expected

The harness exits nonzero whenever any Layer 1 blocker is nonzero. Three are. This is not a
Task 38.12 failure and must not be read as one.

---

## 6. Reconciliation — zero unexplained residue

### 6.1 `calls_unresolved`

```
baseline (8682000)  901
measured (afd5f5f)  702
delta               199
str.join resolved   199
residue               0
```

`901 − 199 = 702`. The entire reduction is attributable to the one authorized identity.

### 6.2 Bucket arithmetic

`exact_identity_policy` moved `2645 → 2844`, delta **+199** — the same 199. Every other
bucket is unchanged: `project_source_available` 3554, `forbidden` 5, `calls_total` 7105.

### 6.3 Counters that must not have moved, and did not

`nodes_unresolved` 16, `unresolved_dispatches` 6888, `dispatch_candidates_total` 7012 — all
identical to baseline. A policy entry is expected to affect explicit-call classification and
nothing else; it did exactly that.

### 6.4 Internal invariants of the report itself

| Invariant | Result |
| --- | --- |
| `sum(identity_resolution_buckets) == calls_total` | 7105 = 7105 |
| `buckets.unresolved == calls_unresolved` | 702 = 702 |
| `sum(calls_unresolved_detail_multiplicity) == calls_unresolved` | 702 = 702 |
| `len(calls_unresolved_detail) == len(multiplicity)` | 373 = 373 |
| `resolved_dispatches + unresolved_dispatches == candidates` | 124 + 6888 = 7012 |
| `len(nodes_unresolved_detail) == nodes_unresolved` | 16 = 16 |

---

## 7. Verification battery

Measured from a **pristine out-of-repo extract** of `afd5f5f` (see §10 for why), whose three
Phase A blobs were verified byte-identical to the published objects before anything ran.

| Check | Command | Result |
| --- | --- | --- |
| Targeted | `pytest …test_task_38_12_phase_a_policy.py …test_task_38_10_phase_a_policy.py -q` | **24 passed** |
| Harness suite | `pytest tests/audit_harness -q` | **222 passed** |
| Full suite | `pytest -q` | **975 passed** |
| Ruff (scoped to Phase A paths) | `ruff check` on the three changed files | **All checks passed** |
| Ruff (repo-wide) | `ruff check .` | 75 errors — **all pre-existing**, see §7.1 |
| Whitespace | `git diff --check` | clean, exit 0 |

### 7.1 Repo-wide Ruff findings are pre-existing, not introduced

Ruff 0.16.1 reports 75 errors repo-wide: **UP042** × 68, **UP046** × 4, **B027** × 2,
**E501** × 1. Attribution was established two independent ways:

1. **File-level.** Every finding sits in a file Task 38.12 did not touch. The intersection
   of the finding set with the three Phase A paths is **empty**.
2. **Revision-level.** An out-of-repo extract of the parent commit `aa220b7` reports
   **exactly 75** under the same Ruff version and config. Head also reports 75.
   **Findings introduced by Task 38.12: 0.**

---

## 8. `uv.lock` — untouched

SHA-256 hashed before and after the full measurement and verification battery:

```
07982ccb31c51dd96c4a4936509c2c22ac25d753f9c20e831dcd500587ae05fb
```

Identical at both points. It remains **untracked**, was not staged, and was not written by
this phase.

---

## 9. Governance state — unchanged

| | State |
| --- | --- |
| ADR-032 | **INDETERMINATE / HOLD** — unchanged |
| Task 39 | **BLOCKED** — unchanged |
| Layer 1 blockers | `nodes_unresolved` 16, `calls_unresolved` 702, `unresolved_dispatches` 6888 — each independently sufficient to hold the gate |
| H-1 | Closed (Task 38.9B) — unchanged |
| H-2 | Closed (Task 38.9A) — unchanged |
| Open High findings | 0 |
| M-8 | Open — taxonomy incomplete; unaddressed by Task 38.12 |
| Phase C | **NOT STARTED** |

Task 38.12 materially reduced one Layer 1 blocker — `calls_unresolved` 901 → 702, a real
reduction against the same walked universe — but **did not clear it**. 702 is nonzero. No
claim is made that ADR-032 is ALLOWED, that Task 38.12 is complete, or that Task 39 is
unblocked, ready, or next.

---

## 10. Evidence integrity — unauthorized worktree drift, disclosed

`tests/audit_harness/test_task_38_12_phase_a_policy.py` was modified in the working tree
**twice** during this task by an agent outside this session. **The committed and published
object at `afd5f5f` was never affected.**

| # | When | Worktree blob | Change | Disposition |
| --- | --- | --- | --- | --- |
| 1 | Before the Phase A push | `683b8ff2…` | Removed the `bytearray.join` entry from `UNAUTHORIZED_JOINS` and its live-trace row (−7 lines) | Restored from `HEAD` under explicit authorization; the push was unaffected |
| 2 | During Phase B, mtime `03:02:03` | `375da807…` | Added an `IdentityVerdict` import, narrowed a return annotation, softened `str.join.__objclass__ is str` to a `getattr()` form | **Not restored** — Phase B scope prohibits modifying `tests/`. Still present in the worktree. |

**Why this evidence is unaffected.** The audit measurement never depended on the worktree
copy of a test: `run_audit` does not import `tests/`, fresh run 1 completed at `03:00:07`
(before the second drift at `03:02:03`), and runs 1 and 2 are byte-identical. The entire
test and Ruff battery was then re-run from a pristine `git archive` extract of `afd5f5f`,
with all three Phase A blobs verified against the published objects first. The extract
produced identical counters and identical test results.

**Why it still matters.** Both drifts weaken assurance in the same direction — occurrence 1
deleted a negative pin outright; occurrence 2 relaxed an assertion's failure mode. Both
still passed the suite, because a test that asserts less passes more easily. The suite is
not a detector for this; only a byte-level comparison against `HEAD` is.

**Action required before staging.** The live worktree does not match `afd5f5f`. Restore that
file from `HEAD` and identify the process making these edits before any Phase B artifact is
staged or committed.

---

## 11. Scope confirmation

| Constraint | Honoured |
| --- | --- |
| `audit_harness/` unmodified | Yes — `identity.py` verified byte-identical to `HEAD` |
| `tests/` unmodified *by this phase* | Yes — the drift in §10 was not made by this phase |
| `EXACT_IDENTITY_POLICY` unchanged | Yes |
| ADR-032 unmodified | Yes |
| `docs/audits/task-38.5-risk-register.md` unmodified | Yes |
| No test assertion added | Yes |
| Worktree-drift class not "fixed" | Correct — disclosed in §10 instead |
| `uv.lock` untouched | Yes |
| Nothing staged / committed / pushed / tagged | Yes |
| Phase C not started | Yes |
| Task 39 not started | Yes |

---

## 12. Artifact hash

**`docs/audits/task-38.12-result.json` — SHA-256:**

```
57ec61ec6a24b4a17855903ebbf3f8adaaab15e7b7fe78648f22c23d9d8e4118
```

Computed after the JSON was finalized and validated, and before this report was written, so
the hash above is of the exact bytes on disk. This report does **not** embed its own hash;
that is reported separately in the Phase B response.

---

## 13. Conclusion

**Mechanism conformance: PASS.** `builtins.str.join` — one identity, individually reviewed,
authorized in advance — resolves 199 records, leaves zero residuals, reconciles exactly
against baseline with zero residue, and drags in no neighbouring `.join` identity. Policy
version `2026-09-05.1`, 87 entries, +1. Full suite 975 passed. Zero Ruff findings
introduced. `uv.lock` untouched.

**Gate: unchanged. ADR-032 remains INDETERMINATE / HOLD. Task 39 remains BLOCKED.**
Phase C has not started.

**One caveat carried forward:** the working tree currently diverges from the published
commit through unauthorized edits this phase was not permitted to repair (§10). That is a
workspace-integrity problem, not a defect in the Phase A implementation or in this evidence
— but it should be resolved before these artifacts are staged.
