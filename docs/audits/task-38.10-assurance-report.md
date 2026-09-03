# Task 38.10 Phase B — Exact-Identity Authorization Evidence (Committed-SHA Capture)

**Authorization under evidence:** `25dd84c8cc3e82676c4fa7c16ae07bacf1494fc7`
(`docs(audit): authorize Task 38.10 exact identities`)
**Implementation under evidence:** `d7fbd32f24227389b851e1165b30cf455a7a15c6`
(`test(audit): implement Task 38.10 exact identities`)
**Phase:** B (evidence only; no production, test, or governance source touched in this phase)
**Verdict:** **PASS**
**Machine-readable result:** `docs/audits/task-38.10-result.json`, schema `38.10.1`

---

## 1. What this evidence proves, and what it does not

**Proves.** Task 38.10 Phase A's implementation behaved exactly as ADR-032's
Task 38.10 Phase 0 section authorized: nine exact callable-**slot** identities
were added to `EXACT_IDENTITY_POLICY`, no more and no fewer; **no unauthorized
policy identity was added**; the policy version moved `2026-08-22.1` →
`2026-09-02.1`; the entry count moved `77` → `86`; the full verification battery
passes; and a freshly re-run structural audit, executed twice and byte-identical
across both runs, measures the resulting residual directly rather than inheriting
any figure from a prior report.

**Does not prove.** Nothing about gate clearance. Every Layer 1 counter remains
independently nonzero and the audit still exits `1`. This phase does not amend
`ADR-032` or `docs/audits/task-38.5-risk-register.md`; the permanent governance
correction — including correcting ADR-032's own recorded `31 → 19` prediction —
is **Phase C's** exclusive responsibility and has not been started.

This phase also makes no claim that the nine authorized identities are the
*right* boundary, only that the implemented boundary is *exactly* the authorized
one. The safety argument for each identity lives in ADR-032's Phase 0 section and
is not re-litigated here.

---

## 2. Baseline

* `HEAD` = `origin/main` = `d7fbd32f24227389b851e1165b30cf455a7a15c6`, verified by
  `git fetch origin main -q && git rev-parse origin/main` at the start of this phase.
* Unpushed commits: **none**.
* `git status --short` at the start of this phase: `?? uv.lock` — unchanged,
  untracked, untouched throughout.
* Interpreter of record: **CPython 3.12.13** (`.venv`, matching
  `pyproject.toml`'s `requires-python = "==3.12.*"`).

**Two-Phase Provenance holds by construction:** `25dd84c` (the human
authorization) is the direct parent of `d7fbd32` (the implementation), which git
itself attests — the authorization was recorded and pushed before any code
implementing it existed.

---

## 3. Policy delta — measured mechanically, not asserted by tests

Both revisions of `audit_harness/identity.py` were extracted with `git show` and
parsed with `ast`; the `EXACT_IDENTITY_POLICY` dict-literal key sets were diffed
directly. This is deliberately independent of the committed test assertions — a
test could only prove what it was written to check, whereas the diff enumerates
the *whole* change.

| | `25dd84c` (parent) | `d7fbd32` (Phase A) |
|---|---|---|
| `EXACT_IDENTITY_POLICY_VERSION` | `2026-08-22.1` | **`2026-09-02.1`** |
| Entry count | 77 | **86** |

**Added — exactly nine, set-equal to the authorized nine:**

1. `_thread.RLock.__new__`
2. `builtins.AssertionError.__new__`
3. `builtins.AssertionError.__init__`
4. `builtins.AttributeError.__init__`
5. `builtins.NotImplementedError.__new__`
6. `builtins.NotImplementedError.__init__`
7. `builtins.OverflowError.__new__`
8. `builtins.OverflowError.__init__`
9. `functools.partial.__new__`

**Removed:** 0. **Unauthorized keys added:** 0. **Duplicate keys:** none.
**Wildcard/pattern keys anywhere in the table:** none — every key remains a
fully-qualified exact identity, which is the property the three-bucket scheme
rests on.

No **type-level** identity entered the table: `_thread.RLock`,
`builtins.AssertionError`, `builtins.AttributeError`,
`builtins.NotImplementedError`, `builtins.OverflowError` and `functools.partial`
are all absent, as the authorization requires — calling a type runs both slots
plus whatever the type's own construction protocol dispatches.

No deferred, rejected, or deliberately-withheld identity entered the table,
including the seven representative exclusions the Phase A brief named:
`builtins.int.__new__`, `builtins.SyntaxError.__init__`, `builtins.type.__new__`,
`weakref.ReferenceType.__new__`, `_io.TextIOWrapper.__init__`,
`builtins.bytearray.__new__`, `collections.deque.__new__`.

---

## 4. Verification battery, re-run from the pushed HEAD

| Check | Command | Result |
|---|---|---|
| Targeted | `.venv/bin/pytest tests/audit_harness/test_task_38_10_phase_a_policy.py -q` | **13 passed** |
| Audit harness | `.venv/bin/pytest tests/audit_harness -q` | **204 passed** |
| Full suite | `.venv/bin/pytest -q` | **957 passed** |
| Lint | `.venv/bin/ruff check audit_harness tests/audit_harness` | **clean** |
| Types (targeted) | `.venv/bin/mypy audit_harness tests/audit_harness` | **0 errors** in `audit_harness/identity.py` and `tests/audit_harness/test_task_38_10_phase_a_policy.py` |

The targeted mypy result is scoped to the two paths Phase A touched. Other
pre-existing errors elsewhere in that run's wider file set are untouched by this
task and are **not** claimed clean here.

### 4.1 Repository-wide mypy — pre-existing, explicitly not a Task 38.10 regression

`.venv/bin/mypy .` (the `Makefile` `typecheck` target's scope) fails with:

```
adapters/binance/adapter.py: error: Source file found twice under different
module names: "binance.adapter" and "adapters.binance.adapter"
```

This was reproduced **identically** by extracting each commit with `git archive`
into a scratch directory outside the repository and running the same command
there: at pristine `d7fbd32`, and at pre-Phase-A `25dd84c`. It therefore predates
Phase A entirely. Phase A neither introduces nor fixes it, and this report does
not describe it as a Task 38.10 regression. It is recorded here only because the
repository-wide command is part of the Task 38 verification baseline and a reader
running it would otherwise be surprised.

---

## 5. Fresh structural audit — two runs, byte-identical

`.venv/bin/python -m audit_harness.run_audit` was executed **twice**,
independently, against the same pushed HEAD. Both captures were written outside
the repository; neither is committed.

* Both runs exit **`1`** — the expected, correct outcome while ADR-032 is HOLD.
* `cmp` reports the two stdout captures **byte-for-byte identical**.
* Raw SHA-256 (both runs): `6f42aba92c80f0b58ed95ed752786e65f322b18da9d03b7cb3a617754222f1fa`
* Canonical SHA-256 (`sort_keys`/`indent=2`, both runs):
  `e5476f87077ec3928629c7b1c54ae75e9169597cb63adb9698b3b141c1621b41`
* Both stderr captures: empty.

These hashes are of the **audit run's output**, not of this report or of the
result JSON — no circular or self-referential hash claim is made anywhere.

### 5.1 Measured metrics (verified against expectation, not assumed)

| Metric | Measured |
|---|---|
| `commit_sha` | `d7fbd32f24227389b851e1165b30cf455a7a15c6` |
| `exact_identity_policy_version` | `2026-09-02.1` |
| harness `schema_version` | `38.8.0` |
| `roots_traced` / `roots_with_error` | 25 / `[]` |
| `nodes_total` | 268 |
| **`nodes_unresolved`** | **16** |
| `calls_total` | 7105 |
| **`calls_unresolved`** | **1092** |
| `identity_resolution_buckets` | `project_source_available` 3363 · `exact_identity_policy` 2645 · `forbidden` 5 · `unresolved` 1092 |
| `implicit_dispatch.syntax_sites_total` | 10474 |
| `implicit_dispatch.dispatch_candidates_total` | 7012 |
| `implicit_dispatch.resolved_dispatches` | 124 |
| **`implicit_dispatch.unresolved_dispatches`** | **6888** |
| `implicit_dispatch.resolved_non_descriptor_exclusion` | 3777 |
| `implicit_dispatch.explicit_path_duplicates` | 0 |
| `module_state_candidates_total` / `module_state_unexplained` | 523 / 0 |
| runtime denial | `bootstrap_status=SUCCESS`, preflight **25 / 25 / 0**, `forbidden_call_observed=None`, `success=true` |
| negative controls | **7 / 7 detected**, `self_test_failed=false` |
| `exit_code` | **1** |

`124 + 6888 == 7012` — the implicit-dispatch partition is genuine, with
`resolved_non_descriptor_exclusion` counted separately and never summed into it.
The negative controls were satisfied *before* any other part of the result was
trusted, as in every prior task.

---

## 6. Unresolved node components — measured through production code

The harness's JSON does not expose a total count of unresolved node
*components*, so it was measured directly through the production trace, not
recomputed by a parallel implementation: `audit_harness.trace.run_trace()` is
invoked, and for each `NodeRecord` whose `.unresolved` is `True` the components
counted are exactly the verdict fields `NodeRecord.unresolved` itself inspects —
`.init`, `.new`, `.post_init` (when present), and every `.default_factories`
entry. **Callable classification is not reimplemented anywhere in this
measurement.**

The pre-Phase-A baseline was measured the same way, against `25dd84c` extracted
with `git archive` into a scratch directory outside the repository — so the `31`
figure is re-derived here, not quoted from a prior report.

| | `25dd84c` | `d7fbd32` |
|---|---|---|
| Unresolved nodes | 22 | **16** |
| Unresolved components | 31 | **22** |
| Delta | — | **−9** |

**The −9 reconciles one-to-one, with no residue, to the nine authorized
identities.** The components that became resolved are exactly:

```
_thread.RLock.__new__
builtins.AssertionError.__init__
builtins.AssertionError.__new__
builtins.AttributeError.__init__
builtins.NotImplementedError.__init__
builtins.NotImplementedError.__new__
builtins.OverflowError.__init__
builtins.OverflowError.__new__
functools.partial.__new__
```

Nothing else moved. No component became unresolved.

---

## 7. Node reconciliation

**Six nodes resolved by Phase A** (each had *all* of its unresolved components
authorized):

```
_thread.RLock
builtins.AssertionError
builtins.AttributeError
builtins.NotImplementedError
builtins.OverflowError
functools.partial
```

**Sixteen nodes remain unresolved**, with their still-unresolved slots:

| Node | Unresolved components |
|---|---|
| `_io.StringIO` | `__init__`, `__new__` |
| `_io.TextIOWrapper` | `__init__` |
| `_thread._ExceptHookArgs` | `__new__` |
| `builtins.OSError` | `__init__`, `__new__` |
| `builtins.SyntaxError` | `__init__` |
| `builtins.bytearray` | `__init__`, `__new__` |
| `builtins.bytes` | `__new__` |
| `builtins.int` | `__new__` |
| `builtins.map` | `__new__` |
| `builtins.memoryview` | `__new__` |
| `builtins.range` | `__new__` |
| `builtins.type` | `__init__`, `__new__` |
| `collections.OrderedDict` | `__init__` |
| `collections.deque` | `__init__`, `__new__` |
| `itertools.islice` | `__new__` |
| `weakref.ReferenceType` | `__init__`, `__new__` |

**Nodes newly unresolved: none.** Arithmetic closes exactly:
**6 resolved + 16 remaining = 22 baseline**, and the 22 remaining components in
the table above sum to the measured `22`.

Both sets were measured mechanically from fresh `run_trace()` executions. **No
node in either list is inferred from Phase A's own report.**

Note that `builtins.OSError`, `builtins.bytearray` and `collections.deque` each
retain **both** or the *other* of their slots as unresolved — which is precisely
why the three evidence-safe-but-withheld identities were withheld: authorizing
them would have resolved no node.

---

## 8. Prediction reconciliation

| Metric | Predicted (ADR-032 Phase 0) | Measured (this phase) | Result |
|---|---|---|---|
| `nodes_unresolved` | 22 → 16 | **22 → 16** | **prediction confirmed** |
| `calls_unresolved` | 1092 → 1092 | **1092 → 1092** | **prediction confirmed** |
| unresolved node components | 31 → 19 | **31 → 22** | **prediction SUPERSEDED** |

**`calls_unresolved` delta of exactly zero is correct, not a null result.** All
nine authorized identities are per-**slot** keys. Every corresponding explicit
call site in `calls_unresolved_detail` targets the **type** object
(`AssertionError(...)`, `RLock()`, …), and no type identity is authorized. Zero
is the predicted and the correct outcome.

`implicit_dispatch.unresolved_dispatches` is unchanged at **6888**, as expected:
a slot-identity policy addition cannot alter implicit-dispatch *site
enumeration*. No side effect was observed and none was expected.

### 8.1 🚩 `31 → 19` was a prediction error. `31 → 22` is the measured result and governs.

Stating this prominently because it is the one place this task's recorded
documentation is wrong.

**Cause, precisely.** The `31 → 19` figure recorded in ADR-032's Task 38.10
Phase 0 section was computed from a **12-key** in-memory `SAFE_FOR_EXACT_POLICY`
simulation performed during Phase 0.2. Human authorization then **deliberately
narrowed the implemented set to 9 identities**, withholding three that met the
safety predicate but resolve no node while their sibling slot remains deferred:

```
builtins.OSError.__init__
builtins.bytearray.__new__
collections.deque.__new__
```

The prediction was carried into the ADR from the 12-key simulation rather than
recomputed against the 9-key authorized set. Therefore:

```
31 − 9 = 22
```

**What this is not.** It is **not a harness defect** — the harness measured
correctly, and the two independent runs agree byte-for-byte. It does **not**
retroactively alter the Phase 0 authorization decision, which stands exactly as
recorded and reviewed. It does **not** imply the three withheld identities
should now be added — they remain deliberately unauthorized, for the reason
recorded at the time and re-confirmed by §7 above.

ADR-032's own Phase 0 text anticipated this case: *"Should Phase B's measured
figures differ from the predictions above, the measured figures govern and these
predictions are superseded, not defended."* Accordingly, **`31 → 22` governs.**
Amending the recorded prediction in ADR-032 is a **Phase C** action; this phase
does not touch that file.

---

## 9. Scope confirmation

* Unauthorized identities added: **0**
* Type-level identities added: **0**
* Deferred / rejected / withheld identities added: **0**
* Keys removed: **0**
* **Task 38.10 Phase A implementation behaved as authorized.**
* **No unauthorized policy identity was added.**

---

## 10. Governance state — unchanged by this phase

| Item | State |
|---|---|
| **H-1** | **Closed** (Task 38.9B) |
| **H-2** | **Closed** (Task 38.9A) |
| Open High findings | **0** |
| **M-8** | **`Open — taxonomy incomplete; narrowed only within the original 11-family taxonomy`** |
| **ADR-032** | **INDETERMINATE / HOLD** |
| **Task 39** | **BLOCKED** |
| `builtins.str.join` Phase 0 review | paused and unrecorded — neither authorized nor rejected here |

Layer 1 remains independently sufficient to keep the gate at HOLD:
`nodes_unresolved=16`, `calls_unresolved=1092`, and
`implicit_dispatch.unresolved_dispatches=6888` are each nonzero, and each alone
suffices. The audit's own exit code is `1`.

**No claim is made that `ADR-032` is ALLOWED, that Task 38.10 is complete, or
that Task 39 is unblocked.** Task 39 must not begin.

**This phase does not amend `ADR-032`.** Neither
`docs/architecture/decisions/ADR-032-structural-audit-gate.md` nor
`docs/audits/task-38.5-risk-register.md` was modified. Recording this evidence
into the ADR and the risk register — including the `31 → 19` → `31 → 22`
correction from §8.1 — is **Phase C's** exclusive responsibility, grounded in
this committed Phase B evidence, and has **not been started**.

---

## 11. Worktree and artifact provenance

* `HEAD` = `origin/main` = `d7fbd32f24227389b851e1165b30cf455a7a15c6` — unchanged
  by this phase; no source file was modified, staged, or committed.
* No `audit_harness/`, `tests/`, `app/`, `core/`, `docs/architecture/` or
  `docs/prompts/` file was touched. `uv.lock` remains untracked and untouched.
* `git status --short` at the end of this phase: `?? uv.lock` plus the two new
  evidence artifacts this phase creates
  (`docs/audits/task-38.10-result.json`, `docs/audits/task-38.10-assurance-report.md`),
  both untracked pending a future, separately-authorized commit. Nothing staged,
  nothing committed, nothing pushed.
* All intermediate captures (both audit runs, the component measurements, the
  policy-diff output, and the `git archive` extractions of `d7fbd32` and
  `25dd84c`) were written to a scratch directory **outside** the repository and
  are not committed.

---

## 12. Artifact hash

`docs/audits/task-38.10-result.json` SHA-256 (schema `38.10.1`):
`2c7a584e6a7f17241b7405cb6f558c2f633c4c14d2291a91ae930848c1e10531`

This value was computed after the JSON file's content was finalized, so it is
safe to embed here — that JSON does not contain this report's hash. This
report's **own** final hash is deliberately **not** embedded in this file:
doing so would change the very bytes being hashed. It is reported externally, in
the Phase B review record, as the hash of this file's content as finalized.

---

## 13. Conclusion

**Task 38.10 Phase B verdict: PASS.** The Phase A implementation is exactly the
authorized one — nine slot identities, zero unauthorized additions, zero
removals, policy `77 → 86` at version `2026-09-02.1` — and the measured residual
is recorded from a fresh, deterministic, twice-run audit rather than inherited
from any earlier claim. Two of the three Phase 0 predictions are confirmed; the
third (`31 → 19`) is a recorded prediction error, superseded by the measured
`31 → 22`, whose cause is fully accounted for and whose correction belongs to
Phase C.

The gate does not move. `ADR-032` remains **INDETERMINATE / HOLD** and **Task 39
remains BLOCKED**.
