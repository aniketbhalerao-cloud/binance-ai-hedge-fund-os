# Task 38.9A — H-2 Exchange Adapter Composition Remediation: Assurance Report

**Executed against:** `main` `b8ebb23` (commit `b8ebb23531350d30924e777dfdcbd295311f4f10`, "fix(app): include exchange adapters in dry-run composition" — the Task 38.9A implementation commit, independently reviewed and approved before this evidence was generated). Harness source: `audit_harness/` (production package, never registered in `app/wiring.py:COMPONENT_REGISTRARS`, never imported by any production framework — unchanged by this task). Machine-readable result: `docs/audits/task-38.9a-result.json` (schema `38.8.0` — Task 38.9A adds no new schema fields, so no version bump is required; hash `a1a44b3b793c873a087db21a1e9e4af4e3be0995ba5350f8923a8b3008c6ebc6`, produced by `audit_harness.report.Report.canonical_json()` via the real `audit_harness.run_audit.run_full_audit()` entry point — never hand-edited). `docs/audits/task-38.8-result.json`/`task-38.8-assurance-report.md` and their hashes are unaltered by this task.

**This report answers two separate questions and never conflates them:**

## H-2 remediation evidence: **PASS**

## Overall audit gate: **HOLD**

---

## 1. H-2 evidence criterion — checked point by point

Per the H-2 finding (`docs/audits/task-38.5-risk-register.md`) and this task's own required criteria, fresh evidence from the real, committed `b8ebb23` implementation shows:

| Criterion | Required | Actual | Met |
|---|---|---|---|
| `discovery.missing_from_component_registrars` | must not contain `exchange_adapters` | `[]` | ✅ |
| `roots_traced` | `25` | `25` | ✅ |
| `runtime_denial_checks.bootstrap_status` | `SUCCESS` | `SUCCESS` | ✅ |
| `runtime_denial_checks.preflight_total/passed/failed` | `25/25/0` | `25/25/0` | ✅ |
| `runtime_denial_checks.forbidden_call_observed` | `None` | `None` | ✅ |
| `runtime_denial_checks.success` | `True` | `True` | ✅ |
| Real dry-run composition | `25/25` | `25/25` (`status=SUCCESS`, independently re-run via `run_dry_run_bootstrap` directly, outside the harness) | ✅ |
| `exchange_adapters.engine.DefaultExchangeEngine.start` under lifecycle protection | present | present in `labels_patched`/`lifecycle_methods_patched` | ✅ |

**All eight criteria are met on the real, committed run.** H-2's specific finding — `exchange_adapters` completed but absent from `COMPONENT_REGISTRARS`, contradicting the "prove the whole system wires" premise — is no longer true of the committed source: `exchange_adapters` is the 25th `COMPONENT_REGISTRARS` entry, its own DI graph resolves cleanly, and the newly discovered registered engine lifecycle target (`exchange_adapters.engine.DefaultExchangeEngine.start`) is covered by the same automatic, rule-based (non-allowlist) runtime-denial protection as every other framework's engine — it was not invoked during the real dry-run (`forbidden_call_observed=None`). This coverage is defensive: the walker's discovery mechanism sees the registered target and the runtime-denial layer patches it as a precaution; nothing about this evidence claims `start()` actually executes, or is reachable, on the dry-run's own execution path.

**This evidence supports formally closing H-2 in a subsequent, separately-authorized documentation phase.** It does not itself change any disposition — per this task's own explicit instruction, this report does not update `docs/audits/task-38.5-risk-register.md`'s H-2 entry or `ADR-032`.

---

## 2. Overall gate — unrelated residuals, honestly restated

H-2's remediation does **not** clear the gate. The real run shows every pre-existing, unrelated Layer-1/M-7/M-8 residual is still present, on a graph now legitimately larger because a 25th framework is reachable:

* **Layer 1 (explicit calls/nodes):** `nodes_total=268` (`nodes_unresolved=22`), `calls_total=7105` (`calls_unresolved=1092`) — both nonzero, both larger than Task 38.8's `261`/`22`/`6842`/`1071` baseline **because `exchange_adapters` is now walked as a 25th reachable root**, not because anything regressed. `nodes_unresolved` is unchanged at `22`; `calls_unresolved` grew by `21` (`1071 → 1092`), consistent with a new, previously-unwalked framework's own third-party/stdlib call surface now being enumerated for the first time. No claim is made that this growth is "bad" — it is the walker correctly seeing more of the real system, exactly what H-2 asked for.
* **`implicit_dispatch` (Task 38.8's Option D mechanism, unchanged, untouched by Task 38.9A):** `syntax_sites_total=10474`, `dispatch_candidates_total=7012` = `resolved_dispatches` (**124**) + `unresolved_dispatches` (**6888**) — reconciliation holds exactly (`124 + 6888 = 7012`). Both figures grew from Task 38.8's `10064`/`6724`/`119`/`6605` for the same reason: `exchange_adapters`' own context-manager/descriptor sites are now enumerated. `resolved_non_descriptor_exclusion=3777`, `explicit_path_duplicates=0`, `unsupported_protocol_families` unchanged (the same 9 named families). Per-method: `__enter__` 0/314, `__exit__` 0/314, `__get__` 124/6366, `__set__` 0/18, `__aenter__`/`__aexit__`/`__delete__` 0 candidates. Task 38.8's own accepted-HOLD discipline (ADR-032 Option D) is unmodified and untouched by this task, per instruction.
* **`self_test_failed=false`**, negative controls **7/7** detected — the harness's own detectors, including the two Task 38.8 implicit-dispatch controls, remain trustworthy on this run.

**`exit_code=1` (HOLD)** — `nodes_unresolved`, `calls_unresolved`, and `implicit_dispatch.unresolved_dispatches` are each independently nonzero, so the Gate Rule (`docs/prompts/task-38.6.md`, unchanged through every subsequent task) keeps `ADR-032` at HOLD. **This report makes no claim that `ADR-032` is ALLOWED, that Task 38.9A closes the overall gate, or that Task 39 is unblocked.** H-2 is only one independently tracked finding; unrelated existing gate blockers and assurance residuals remain (the Layer-1 coded predicate above, plus H-1 and M-8, each independently established by `ADR-032` as its own HOLD-keeper), so this task does not clear the overall gate.

---

## 3. Determinism — two independent real audit runs

Command run twice, from repo root, against the same committed state, no other input change:

```
.venv/bin/python -m audit_harness.run_audit
```

Both runs exited `1` (HOLD) and hashed identically:

```
sha256: 1a8a7cbf4fed8bd0cb3c062596919e9276c9c227e0173062cff9c1e4b9babb56  (run 1)
sha256: 1a8a7cbf4fed8bd0cb3c062596919e9276c9c227e0173062cff9c1e4b9babb56  (run 2)
```

Byte-identical. `docs/audits/task-38.9a-result.json` was written from a third, equivalent call to the same `run_full_audit()` entry point directly (never `print()`-captured stdout), so its content is identical to both runs above up to `canonical_json()`'s own single-trailing-newline convention; its independently-computed hash is `a1a44b3b793c873a087db21a1e9e4af4e3be0995ba5350f8923a8b3008c6ebc6`.

---

## 4. Verification battery

* **`tests/audit_harness/`:** 191 passed.
* **Full project suite:** `.venv/bin/python -m pytest -q` → **937 passed** (unchanged from the `b8ebb23` implementation commit's own recorded count — no source changed between that commit and this evidence run).
* **Lint:** `ruff check audit_harness/ tests/audit_harness/ app/wiring.py tests/test_app_flow.py` → All checks passed.
* **Type check:** `mypy audit_harness/ app/wiring.py` → Success, no issues found in 10 source files.
* **Real dry-run entry point:** `python -m app.main` → exit code `0`.
* **`git diff --check`:** clean.

---

## 5. Worktree and artifact provenance

* `HEAD`: `b8ebb23531350d30924e777dfdcbd295311f4f10` throughout this phase — no source file was modified, staged, or committed by evidence generation.
* `git status --short` before evidence generation: `?? uv.lock` only. After: the same, plus the two new untracked Task 38.9A evidence artifacts.
* `uv.lock` remains untracked and untouched.
* Nothing staged, nothing committed, nothing pushed.
* `docs/audits/task-38.8-result.json`/`task-38.8-assurance-report.md` and their commit/hash are unaltered.

---

## 6. Conclusion

**H-2 remediation evidence: PASS.** **Overall audit gate: HOLD.** These are separate, correctly-distinguished findings. `ADR-032` is not ALLOWED. Task 39 remains blocked. No risk-register or ADR-032 disposition was updated by this report — that update, grounded in this committed evidence, is a separately-authorized future phase.
