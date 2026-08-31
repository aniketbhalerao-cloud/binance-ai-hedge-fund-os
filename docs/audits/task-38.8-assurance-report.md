# Task 38.8 — Implicit-Execution Discovery Boundary: Assurance Report

**Executed against:** `main` `b338484` (commit `b338484f8e6e5cd1af1f69260cdb2b044b0db0c5`, "fix(audit): correct Task 38.8 Phase A.1 implicit dispatch semantics" — the Phase A.1 mechanism + post-remediation-tests commit). Harness source: `audit_harness/` (production package, never registered in `app/wiring.py:COMPONENT_REGISTRARS`, never imported by any production framework). Tests and negative-control fixtures: `tests/audit_harness/`. Machine-readable result: `docs/audits/task-38.8-result.json` (schema `38.8.0`, result hash `7f5ffdf883339fa3e363db8d4a394ba49bb8b0e2416a4e47d7b9790395a7ae53`, produced by `audit_harness.report.Report.canonical_json()` via the real `audit_harness.run_audit.run_full_audit()` entry point — never hand-edited). `docs/audits/task-38.7-result.json` and its hash are unaltered by this phase.

**Gate outcome: HOLD.** `nodes_unresolved=22`, `calls_unresolved=1071`, and the new `implicit_dispatch.unresolved_dispatches=6605` are all nonzero. Per the Gate Rule (`docs/prompts/task-38.6.md`, restated unchanged through Task 38.7 and this task), any nonzero unresolved count keeps the gate at HOLD. This report makes **no claim that `ADR-032` is ALLOWED, that Task 38.8 is complete, or that Task 39 is unblocked.** The 6,605 unresolved implicit-dispatch records are the expected, accepted, conservative result of Phase 0's fail-closed discipline (ADR-032 Option D, amendment 2) — they are not attempted to be reduced by this phase, and this phase makes no attempt to reduce them.

---

## 1. What Phase A.1 implemented (context, not re-litigated here)

Per ADR-032's Phase 0 decision (2026-08-24) and `docs/prompts/task-38.8.md` §5/§9, Phase A.1 mechanized exactly 2 of the 11 §2 protocol families — **context managers** (`__enter__`/`__exit__`/`__aenter__`/`__aexit__`) and **descriptors** (`__get__`/`__set__`/`__delete__`) — in `audit_harness/trace.py`, wired the new `implicit_dispatch` report section into `audit_harness/report.py`/`run_audit.py` (schema bump `38.7.0` → `38.8.0`), added two new production negative controls in `audit_harness/self_test.py`, fixed a real classmethod-descriptor corruption risk in `audit_harness/runtime_denial.py`'s save/restore path, and upgraded 8 of the existing 36 Phase A.0 characterization cases to positive regression-protection tests while leaving the remaining 28 (the 9 still-unsupported families) as unchanged boundary characterization. Committed at `b338484f8e6e5cd1af1f69260cdb2b044b0db0c5`. This phase (B) does not modify, extend, or re-implement any of that — it runs it, for real, against the committed state, and records what it produces.

---

## 2. Self-test result (run before the real audit, same as every prior task)

7/7 negative controls detected on this run (5 original Task 38.6 controls + 2 Task 38.8 Phase A.1 controls):

* `forbidden_post_init`: detected — `open(self.path)` inside a fixture `__post_init__`
* `unresolvable_call_reported`: detected — `mystery.do_something_unverifiable()`
* `module_global_mutation_from_plain_function`: detected
* `direct_os_open_call`: detected — `os.open(...)` called directly
* `db_redis_exchange_connection_intercepted`: detected — all three fake clients intercepted before any connection
* `implicit_context_manager_dispatch_detected`: detected — `open(...)` inside `ForbiddenEnterOnly.__enter__`, triggered via `with obj:`
* `implicit_descriptor_dispatch_detected`: detected — `open(...)` inside `ForbiddenProperty.value`'s `fget`, triggered via a bare attribute read

`self_test_failed: false`.

---

## 3. Explicit discovery — unchanged legacy counters, now explicit-call-only

`nodes_total=261`, `nodes_unresolved=22`; `calls_total=6842`, `calls_unresolved=1071`. These are computed over `TraceResult.explicit_calls` — every `CallRecord` **excluding** the new `implicit-*`-tagged records — per `docs/prompts/task-38.8.md` §8's explicit requirement that these fields remain explicit-call-only. They are not directly comparable to a pre-38.8 baseline that had no such exclusion to make, since the underlying walker now also produces implicit-dispatch records that this legacy population deliberately never included.

`roots_traced=24`, `roots_with_error=[]` (no budget exhaustion, no source-unavailable root failure on this run).

---

## 4. Implicit dispatch — the new §8 section, in full

```json
"implicit_dispatch": {
  "mechanized_protocol_families": ["context_manager", "descriptor"],
  "unsupported_protocol_families": [
    "iteration/comprehensions",
    "unpacking",
    "await/async iteration",
    "equality/ordering/arithmetic operators including reflected forms",
    "truth testing",
    "membership",
    "subscription/assignment/deletion",
    "hashing",
    "formatting including __str__/__repr__ fallback"
  ],
  "syntax_sites_total": 10064,
  "dispatch_candidates_total": 6724,
  "resolved_dispatches": 119,
  "unresolved_dispatches": 6605,
  "resolved_non_descriptor_exclusion": 3642,
  "explicit_path_duplicates": 0,
  "dispatch_events_by_method": {
    "__enter__":  {"candidates": 301,  "resolved": 0,   "unresolved": 301},
    "__exit__":   {"candidates": 301,  "resolved": 0,   "unresolved": 301},
    "__aenter__": {"candidates": 0,    "resolved": 0,   "unresolved": 0},
    "__aexit__":  {"candidates": 0,    "resolved": 0,   "unresolved": 0},
    "__get__":    {"candidates": 6104, "resolved": 119, "unresolved": 5985},
    "__set__":    {"candidates": 18,   "resolved": 0,   "unresolved": 18},
    "__delete__": {"candidates": 0,    "resolved": 0,   "unresolved": 0}
  }
}
```

**Reconciliation proof (§11):**

```
resolved_dispatches (119) + unresolved_dispatches (6605) == dispatch_candidates_total (6724)
119 + 6605 = 6724  ✓
```

A genuine partition — every enumerated dispatch candidate is either resolved or unresolved, never both, never neither. `resolved_non_descriptor_exclusion=3642` sits outside this partition entirely (a descriptor-family site soundly proven to dispatch nothing at all — no candidate, no `CallRecord`). `explicit_path_duplicates=0` is an annotation on already-counted sites, never a fifth addend. `unsupported_protocol_families` reconciles separately as a 9-entry name list, matching ADR-032's own enumeration verbatim, with no numeric site count implied or computed for it (no enumerator ran against those 9 families).

Every `__enter__`/`__exit__` candidate on this real run resolved to `unresolved` (301/301 each) — the codebase's real context-manager receivers are predominantly untyped/polymorphic parameters this walker's single-hop, statically-typed receiver resolution cannot soundly pin, so it fails closed rather than guess. `__get__` shows the only nonzero resolved count (119 of 6104) — the codebase's real `@property`/descriptor receivers are more frequently a soundly-inferrable `self`-typed instance. This is the accepted, conservative result: no site here is misclassified safe: every uncertain case reports `unresolved`, never a guess.

---

## 5. Module-state (unchanged mechanism, not touched by this task)

`module_state_candidates_total`/`module_state_unexplained`/`module_state_buckets`/`module_state_parse_errors` are produced by the same Task 38.6/38.7 mechanism, untouched by Task 38.8. See `docs/audits/task-38.8-result.json` for the full figures.

---

## 6. Runtime denial — paper-only, 24/24

`bootstrap_status=SUCCESS`, `preflight_total=24`, `preflight_passed=24`, `preflight_failed=0`, `forbidden_call_observed=None`, `success=true`. **Paper-only** — the one real, paper-only `run_dry_run_bootstrap()` call the harness's own re-run performs; no live network/DB/Redis/exchange connection was made. `db_clients_found=[]`, `redis_clients_found=[]`; `exchange_adapter_connections_found` still names the pre-existing H-2 residual (`exchange_adapters (present, not wired into COMPONENT_REGISTRARS -- see H-2)`) — unchanged, not remediated by this task. `unimportable_nodes=[]`.

---

## 7. Determinism — two independent real audit runs

Command run twice, from repo root, against the same committed state, no other input change:

```
.venv/bin/python -m audit_harness.run_audit
```

Both runs' stdout captured independently; both exited `1` (HOLD); both hashed identically:

```
sha256: 0cf9a066679f0b064f94efd516ab8d2529298f9e3551b1b6d037af827ece55b7  (run 1)
sha256: 0cf9a066679f0b064f94efd516ab8d2529298f9e3551b1b6d037af827ece55b7  (run 2)
```

Byte-identical. (The `docs/audits/task-38.8-result.json` artifact itself was written directly from `Report.canonical_json()` via a third, equivalent invocation of the same `run_full_audit()` entry point — its content is identical to both runs above up to the trailing-newline convention `canonical_json()` itself defines; its own independently-computed hash, `7f5ffdf883339fa3e363db8d4a394ba49bb8b0e2416a4e47d7b9790395a7ae53`, differs only because that convention has a single trailing newline where two `print()`-captured stdout runs each carry one extra.) This satisfies §11's "byte-identical (or hash-equal, after canonicalization)" determinism requirement, extended to the new implicit-dispatch fields.

---

## 8. Verification battery (§11)

* **Existing `audit_harness` tests:** `tests/audit_harness/` — **191 passed** (all pre-existing suites: `test_harness_properties.py`, `test_lifecycle_denial_completeness.py`, `test_negative_controls.py`, `test_task_38_7_categories.py`, `test_task_38_8_characterization.py`, `test_task_38_8_phase_a1_mechanism.py`, `test_task_38_8_schema.py`, plus `fixtures/`), passing unmodified in intent.
* **New per-family negative controls:** all 36 Phase A.0 characterization cases present and passing (8 now regression-protection for the 2 mechanized families, 28 unchanged boundary characterization for the 9 unsupported families); 2 new self-test negative controls (§2 above).
* **Deterministic repeated runs:** confirmed, §7 above — byte-identical across two independent real runs, including the new implicit-dispatch fields.
* **Targeted lint and type checks:** `ruff check audit_harness/ tests/audit_harness/` → **All checks passed!**. `mypy audit_harness/` → **Success: no issues found in 9 source files**.
* **Full project test suite:** `.venv/bin/python -m pytest -q` from repo root → **932 passed** (unchanged from the Phase A.1 commit's own recorded count — no source changed between that commit and this run, so no delta to explain).
* **Paper-only runtime denial at 24/24:** confirmed, §6 above.
* **Formula/counter reconciliation:** confirmed, §4 above — the only valid partition (`resolved_dispatches + unresolved_dispatches == dispatch_candidates_total`), `explicit_path_duplicates` as an annotation, `unsupported_protocol_families` reconciled separately as a name list.
* **Exact worktree and artifact provenance:** see §9 below.

---

## 9. Worktree and artifact provenance

* `HEAD`: `b338484f8e6e5cd1af1f69260cdb2b044b0db0c5` (unchanged by this phase — no source file was modified, staged, or committed).
* `origin/main`: `2d21051161b7caccd9cebcc79b536d9ab9abf967` (unchanged; nothing pushed).
* `git stash list`: empty throughout.
* `git status --short` at the end of this phase: `?? uv.lock` (unchanged, untracked, untouched) plus the two new evidence artifacts this phase creates (`docs/audits/task-38.8-result.json`, `docs/audits/task-38.8-assurance-report.md`), both untracked pending a future, separately-authorized commit. Nothing staged, nothing committed.
* No Phase A.1 source file (`audit_harness/*.py`, `tests/audit_harness/*`) was modified by this phase. No unrelated file was touched.

---

## 10. H-1, H-2, `str.join`, `EXACT_IDENTITY_POLICY` — unchanged, not addressed by this task

`H-1` and `H-2` remain separate, individually-named, open blockers — unmerged, untouched. `builtins.str.join`'s `ADR-032` Phase 0 authorization remains paused and unrecorded — this task neither authorizes nor rejects it. `EXACT_IDENTITY_POLICY` was not modified by any phase of this task, in any form.

---

## 11. M-8 disposition — not updated by this report

Per `docs/prompts/task-38.8.md` §9/§10, this Phase B report is evidence only; it does not itself update `docs/audits/task-38.5-risk-register.md`'s M-8 entry or `ADR-032`'s re-evaluation. That is Phase C's exclusive responsibility, grounded in this committed Phase B evidence, and has not been started. Per §10, since Option D mechanizes only 2 of the 11 required families with a nonzero unresolved count on both of those (`__enter__`/`__exit__`: 301/301 unresolved; `__get__`: 5985/6104 unresolved; `__set__`: 18/18 unresolved), this evidence could support, at most, `Open, narrowed` for the mechanized families and `Open` for the 9 unsupported ones when Phase C is eventually run — it does not, on its own, support `Closed` for any family, since no family here achieves zero unresolved sites on this run.

---

## 12. Conclusion

**Gate outcome: HOLD.** `ADR-032` is not ALLOWED. Task 38.8 is not complete — Phase C remains outstanding. Task 39 is not unblocked. The 6,605 unresolved implicit-dispatch records, and the pre-existing 1,071 unresolved explicit calls and 22 unresolved nodes, are the real, accepted, conservative state of the committed `b338484` implementation — none were reduced, suppressed, or reclassified to produce this report. **Next required phase: Phase C** (M-8/`ADR-032` update from this committed Phase B evidence) — not started by this report.
