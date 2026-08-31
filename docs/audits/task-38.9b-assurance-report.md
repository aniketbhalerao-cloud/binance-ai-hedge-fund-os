# Task 38.9B Phase B — H-1 Evidence (Committed-SHA Capture)

**Commit under evidence:** `78b5332197e03777b689794bdd9cbbd4b60e6e77`
(`test(architecture): enforce H-1 cross-framework boundary`)
**Phase:** B (evidence only; no production/test/doc source touched in this phase)
**Verdict:** **PASS** (methodology corrected after independent review;
substantive conclusions unchanged — see §0)

## 0. Methodology correction note

An independent evidence-methodology review of the first draft of this
evidence (scratch scan script `h1_phaseb_scan.py`) found three real
defects in the scan/aggregation code, not in the underlying facts:

1. **Dead bucket.** `runtime_concrete_business_lifecycle_call` was
   initialized to `0` but never actually derived by any code path in
   `classify_concrete_use()` — it was reported as if it were an
   independently regenerated import-classification bucket when it was
   not. **Fixed** by removing it from import classification entirely and
   modeling import classification and concrete-import *behavior* as two
   separate dimensions (§4 vs §5 below), per the reviewer's preferred
   structure.
2. **Unsound fallback.** `classify_concrete_use()` defaulted an unmatched
   concrete record (zero construction calls **and** zero
   `resolver.has`/`resolve` calls) to `"runtime_concrete_di_key"` by
   fallback, which would have silently mislabeled any future unsupported
   reference form as safe. **Fixed**: the corrected scanner
   (`h1_phaseb_scan_v2.py`) now assigns an explicit third bucket,
   `bare_reference_unclassified`, for that case. It is `0` today —
   confirmed by rerunning the corrected scan (§4).
3. **Debug-dump duplication.** A scratch diagnostic file (outside the
   repository, never a permanent artifact) concatenated
   `records + concrete_records`, where `concrete_records` entries are the
   *same* dict objects already present in `records` — producing duplicate
   rows in that one debug file. No permanent metric was ever computed
   from the duplicated list; all counts came from accumulator dicts
   incremented exactly once per unique record. **Fixed** in the corrected
   scanner, and reconfirmed here (§4).

The scan was **rerun from the corrected script**, twice independently,
with a new determinism hash (§9). All previously reported facts (203
total records, the 125/31/9/38 split, 9 `TradingEngine` importers, 9
`resolver.has`/9 `resolver.resolve`, 0 direct construction, 5/5 negative
controls, 7/944 test results) are **unchanged** — the defects were in how
two *dimensions* (import classification vs. behavioral/lifecycle
evidence) were being conflated and one fallback was being silently
applied, not in the underlying counts.

Additionally, per review: the "direct lifecycle calls = 0" and "other
runtime references = 0" claims are now explicitly attributed to the
**committed regression test**, not to the scratch scan — see §5/§6.

## 1. What this evidence proves, and what it does not

**Original false claim (Task 38 / pre-38.9B `app/wiring.py` docstring,
`docs/prompts/task-38.md`):**

> No framework imports another framework directly.

This claim is false against the current 25-framework repository and was
already corrected in the Phase A commit under evidence here.

**Corrected, evidenced invariant (what this Phase B run re-verifies from a
clean, independently regenerated scan against the committed SHA):**

- Frameworks may — and legitimately do — share public value/domain types
  and `Protocol`/ABC interfaces directly with one another. This is not a
  violation; it is an existing, intentional pattern.
- No framework directly constructs another framework's concrete class.
  Verified for all 203 raw cross-framework import records, under every
  reviewed import spelling.
- `trading.engine.TradingEngine` is the sole reviewed concrete
  cross-framework runtime type in the entire scan. It is used, exclusively,
  as an optional DI-key lookup (`resolver.has(TradingEngine)` /
  `resolver.resolve(TradingEngine)`) by exactly nine frameworks.
- Those nine importers do not directly invoke `TradingEngine.start()`,
  `.stop()`, `.pause()`, or `.resume()`.

**Explicitly not claimed:**

- H-1 is **not** Closed by this evidence. Disposition remains **Open**
  pending a separately authorized Phase C.
- This is **not** a claim that all cross-framework dependencies are
  interfaces — 125 of 203 records are domain/value-type imports (models,
  context, signals, state, enums, dataclasses, functions/modules), not
  Protocols.
- This is **not** a claim of global, repository-wide import isolation.
  Framework packages are demonstrably *not* import-isolated from one
  another; only the narrower "no direct concrete construction, one
  reviewed DI-key exception" invariant is evidenced.
- The regression guard is **not** purely static. AST-based import/call
  discovery is static, but classifying a resolved symbol as
  concrete-class / `Protocol` / ABC / dataclass / `Enum` uses runtime
  introspection (`importlib.import_module`, `getattr`, `inspect`,
  `dataclasses.is_dataclass`, `issubclass(..., enum.Enum)`) against the
  actual installed packages — not a name-pattern heuristic.

## 2. Baseline

```
$ git rev-parse HEAD
78b5332197e03777b689794bdd9cbbd4b60e6e77

$ git status --short
?? uv.lock
```

Matches the required baseline exactly.

## 3. Committed H-1 regression suite (targeted)

```
$ .venv/bin/python -m pytest tests/test_h1_cross_framework_boundary.py -v
tests/test_h1_cross_framework_boundary.py::test_no_framework_directly_instantiates_another_frameworks_concrete_class PASSED
tests/test_h1_cross_framework_boundary.py::test_the_one_evidenced_concrete_di_key_exception_is_exactly_scoped PASSED
tests/test_h1_cross_framework_boundary.py::test_trading_engine_runtime_uses_are_exactly_the_permitted_di_key_forms PASSED
tests/test_h1_cross_framework_boundary.py::test_trading_engine_lifecycle_methods_are_never_invoked_by_its_importers PASSED
tests/test_h1_cross_framework_boundary.py::test_negative_controls_construction_detected_under_every_import_spelling PASSED
tests/test_h1_cross_framework_boundary.py::test_positive_control_resolver_di_lookup_is_never_flagged PASSED
tests/test_h1_cross_framework_boundary.py::test_qualified_typing_type_checking_guard_is_also_recognized PASSED

7 passed in 0.62s
```

## 4. Fresh cross-framework import inventory (independently regenerated)

The Phase 0 scan script was **not** reused, and neither was the flawed
first Phase B draft (`h1_phaseb_scan.py`). The corrected script
(`h1_phaseb_scan_v2.py`) was written for this phase, using
`app.wiring.KNOWN_COMPONENT_IDS` (25 wired frameworks) plus `trading`
(the one unwired legitimate cross-framework target/source) as its
framework universe, then independently re-implementing AST import
discovery and runtime-introspection classification.

| Metric | Value |
|---|---|
| Wired frameworks (`app.wiring.KNOWN_COMPONENT_IDS`) | 25 |
| Packages scanned (25 wired + `trading`) | 26 |
| Raw cross-framework import records | 203 |
| Importing frameworks | 15 |

Exact importing set (alphabetical, matches the expected set exactly):

```
agents, backtesting, exchange_adapters, execution, learning, market_data,
optimization, order_management, paper_trading, performance, portfolio,
positions, risk, strategies, trades
```

### Import classification (sums to 203) — Dimension 1

This dimension classifies **what each import record refers to**. It is
deliberately kept separate from the *behavior* of the 9 concrete records
(§5) — an import being a concrete-class reference and that reference
later being used in a DI-key call are not naturally mutually-exclusive
categories of the same "import", so forcing them into one six-row table
(as the first draft did) overstated what the import-discovery pass alone
proves.

| Bucket | Count |
|---|---|
| runtime domain/value types | 125 |
| runtime Protocol/interface | 31 |
| runtime concrete class | 9 |
| TYPE_CHECKING-only | 38 |
| **Total** | **203** |

This independently regenerated count matches the Phase 0 figures exactly;
it was **not** copied — it was recomputed against the committed SHA,
cross-checked in two ways: (a) the production detector itself
(`tests/test_h1_cross_framework_boundary.py::find_direct_construction_violations`)
was called directly on synthetic snippets to confirm construction/DI-key
discrimination (§7 below), and (b) two independent runs of the fresh scan
were byte-compared (§9 below).

## 5. Concrete-type evidence — behavior analysis (Dimension 2)

A second, separate dimension analyzes the **behavior** of the 9
`runtime concrete class` import records identified in §4 — i.e. how each
imported concrete symbol is actually used at each call site.

| Metric | Value |
|---|---|
| Concrete cross-framework runtime types found | 1 (`trading.engine.TradingEngine`) |
| `TradingEngine` runtime import records | 9 |

Per-record classification of those 9 concrete records (mechanically
counted from real `ast.Call` nodes; **no fallback** — a record matching
neither construction nor a `resolver.has`/`resolve` argument is labeled
`bare_reference_unclassified`, not silently folded into `di_key`):

| Record class | Count |
|---|---|
| `direct_instantiation` | 0 |
| `di_key` | 9 |
| `bare_reference_unclassified` | 0 |

`bare_reference_unclassified` is `0` today; the scanner would surface a
future unsupported reference form here rather than silently classifying
it as safe DI-key use — this closes the fallback defect described in §0.

Exact `TradingEngine` runtime importer set (matches expected exactly):

```
exchange_adapters, execution, market_data, order_management, portfolio,
positions, risk, strategies, trades
```

Permitted runtime references to the imported `TradingEngine` symbol,
enumerated per importer (each of the 9 importers uses exactly one
`resolver.has(TradingEngine)` and one `resolver.resolve(TradingEngine)`
call, in each importer's `__init__.py` component-wiring code):

| Reference kind | Count |
|---|---|
| `resolver.has(TradingEngine)` | 9 |
| `resolver.resolve(TradingEngine)` | 9 |
| **Permitted runtime references total** | **18** |
| Direct instantiations | 0 |
| Other/disallowed runtime references | 0 |

**Evidence source for "other runtime references = 0":** the committed
test `test_trading_engine_runtime_uses_are_exactly_the_permitted_di_key_forms`,
which enumerates *every* runtime `Name`/`Attribute` reference to the
local `TradingEngine` binding — not just `Call` sites — and asserts each
one is a `resolver.has`/`resolve` argument. The fresh scratch scan's
mechanical call-site counts (construction=0, has=9, resolve=9) corroborate
this but, being a `Call`-site-only scan, are not themselves exhaustive
over every possible reference form (e.g. a bare assignment or return of
the symbol) — that exhaustiveness is what the committed test proves.

The import statement itself is not counted among the 18 permitted
references — only the call-argument references are. A separate 9
`TYPE_CHECKING`-only references to `trading.engine.TradingEngine` also
exist (each importer's `engine.py`/`service.py`/`manager.py`, for type
annotations only); these fall in the `TYPE_CHECKING-only` bucket in §4,
not this permitted-runtime-reference count.

## 6. Lifecycle evidence

| Metric | Value |
|---|---|
| Tracked lifecycle methods | `start`, `stop`, `pause`, `resume` |
| Direct lifecycle calls found on the 9 `TradingEngine` importers | 0 |

**Evidence source:** the committed, receiver-aware regression test
`test_trading_engine_lifecycle_methods_are_never_invoked_by_its_importers`,
which performs typed-collaborator/bound-attribute analysis to confirm the
call's receiver is actually the `TradingEngine` collaborator, not merely
a same-named method on an unrelated object.

The fresh scratch scan also ran a coarse, **non-receiver-aware** name scan
(any `ast.Call` node named `start`/`stop`/`pause`/`resume` anywhere in a
file that imports `TradingEngine`) purely as non-authoritative diagnostic
corroboration; it found 0 hits, consistent with the committed test. A
name-based scan cannot prove the call's receiver is actually a
`TradingEngine` instance, so it is explicitly **not** cited as the
evidence source for this metric — only the committed test is.

This is scoped strictly to the 9 evidenced `TradingEngine` importers. It
is **not** generalized into a repository-wide "no business method calls
anywhere" assertion — no such claim is made or tested.

## 7. Negative/positive control evidence

The committed production detector
(`find_direct_construction_violations`) was invoked directly (not
reimplemented) against five synthetic direct-construction spellings and
two synthetic DI-lookup spellings:

| Construction form | Detected |
|---|---|
| `TradingEngine(...)` | ✅ |
| `TE(...)` (aliased import) | ✅ |
| `trading.engine.TradingEngine(...)` (module-qualified) | ✅ |
| `te.TradingEngine(...)` (aliased module import) | ✅ |
| `engine.TradingEngine(...)` (`from trading import engine`) | ✅ |

Construction negative controls detected: **5/5**.

| DI-lookup form | Flagged |
|---|---|
| `resolver.has(TradingEngine)` | not flagged (correct) |
| `resolver.resolve(TradingEngine)` | not flagged (correct) |

Permitted DI positive control: **PASS**.
Qualified `typing.TYPE_CHECKING` guard control: **PASS** (proven by
`test_qualified_typing_type_checking_guard_is_also_recognized` in the
targeted suite, §3).

## 8. Full project verification

```
$ .venv/bin/python -m pytest -q
944 passed in 41.89s

$ .venv/bin/ruff check app/wiring.py tests/test_h1_cross_framework_boundary.py
All checks passed!

$ .venv/bin/python -m mypy app/wiring.py tests/test_h1_cross_framework_boundary.py
Success: no issues found in 2 source files

$ git diff --check
(clean, no output)

$ .venv/bin/python -m app.main
(no output)
$ echo $?
0
```

`python -m app.main` exits 0 as a dry-run composition build only — no
live network/DB/Redis/exchange operation is performed. This does not
itself re-verify or change the existing 25/25 H-2 composition evidence
recorded in Task 38.9A (`docs/audits/task-38.9a-result.json`,
`docs/audits/task-38.9a-assurance-report.md`); it is reported here only as
a required verification-battery entry for the H-1 evidence run.

## 9. Determinism

The **corrected** fresh scan/classification script (`h1_phaseb_scan_v2.py`,
§0) was run twice, independently, against the same committed SHA. Both
runs' canonical output (JSON, `sort_keys=True, indent=2`) were
byte-compared.

| Metric | Value |
|---|---|
| Deterministic | true |
| Canonical SHA-256 (both runs, v2 script) | `6a016ffd51343663685a5f0735653ca64d5251f29479acddc214666a26b00fa1` |

The two runs' output files were confirmed byte-identical via `diff`
(no output) prior to hashing. This supersedes the schema-38.9b.0 hash
`08f0120028ecd2dbe896cbe8fda967071008af827e32877dcd276bb42a3c29ef`
computed from the pre-correction (v1) script, which carried the Issue 1/3
methodology defects described in §0. The underlying facts the hash covers
are unchanged; only the aggregation shape and fallback-safety changed.

## 10. Artifact hash

`docs/audits/task-38.9b-result.json` SHA-256 (schema `38.9b.1`, corrected):
`633ab16e1c85a61c85ca232e53af68c03f1db3aceb087bac53066db5af964b6c`

This value is computed after the JSON file's content was finalized, so it
is safe to embed here — the JSON file does not itself contain this
report's hash. This report's **own** final hash is a different matter:
embedding it here would change the very bytes being hashed (a
self-referential fixed-point problem), so it is deliberately **not**
embedded in this file. It is instead reported externally, in the Phase B
review/commit record, as the hash of this file's content as finalized.

## 11. Disposition (explicit, unchanged by this phase)

- **H-1 remediation evidence:** PASS
- **H-1 disposition:** still **Open**, pending separately-authorized
  Phase C
- **Overall ADR-032 gate:** **HOLD** (unchanged)
- **Task 39:** blocked (unchanged)

This report does not modify, and must not be read as modifying,
`docs/audits/task-38.5-risk-register.md` or
`docs/architecture/decisions/ADR-032-structural-audit-gate.md`. H-1 is not
Closed. No claim is made here that the repository has global
cross-framework import isolation, or that all cross-framework
dependencies are interfaces.
