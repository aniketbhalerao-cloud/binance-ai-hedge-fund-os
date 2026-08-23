# Task 38.8 — Implicit-Execution Discovery Boundary

---

# Sprint 18.8

## Type

Residual-scoping specification. Inserted between Sprint 18.7 (Task 38.7 — Audit Residual Resolution and Gate Re-evaluation, whose Phase A/B work is committed at `dcb1ebc6b7fd34e89979fd9adf8ed0d57bc8ac58`/`77bd080009f0669cc3d23637383f7afee6f2ce03`, with a post-evidence addendum recording **M-8** on 2026-08-23) and Sprint 19 (Task 39, which remains blocked until `ADR-032` reaches ALLOWED). **This is a specification-writing pass only: it authors this one file and performs no implementation, simulates no mechanism, and runs no harness.** The future implementation task this spec defines gives `docs/audits/task-38.5-risk-register.md`'s **M-8** a source-controlled path to closure — either a general discovery-mechanism extension, or an explicitly bounded, documented residual — and re-evaluates `ADR-032` on that task's own evidence.

## Scope

`audit_harness.trace.StaticWalker` discovers call sites by iterating literal `ast.Call` nodes found via `_shallow_descendants` inside a walked callable's own source, and resolves each one through `audit_harness.identity.classify_callable`'s three-bucket scheme (`project_source_available` / `exact_identity_policy` / `unresolved`, with a fourth `forbidden` bucket that pre-empts the other three per `FORBIDDEN_IDENTITIES`). M-8, recorded in the risk register as Medium/Open, establishes — via reproducible, non-executed fixture evidence spanning every named protocol family — that this discovery mechanism has no counterpart for execution CPython's interpreter dispatches **implicitly**, in response to syntax rather than a literal `ast.Call` node: iteration, unpacking, context managers, `await`/async iteration, property/descriptor access, comparison/ordering/arithmetic operators (including reflected forms), truth testing, membership, subscription, hashing, and formatting. Such execution currently produces zero trace of any kind — not a `CallRecord`, not an `unresolved` marker, not a gate-counter increment.

This task's scope is exactly that boundary: giving the walker (or an explicitly documented, bounded alternative) a way to see this class of execution, without weakening `EXACT_IDENTITY_POLICY`'s callable-identity discipline, without touching the currently-paused `builtins.str.join` Phase 0 review, and without disturbing any of the four existing `Category` buckets or any counter Task 38.6/38.7 already defined except by deliberate, versioned, additive extension. This task does **not** re-open H-1, H-2, M-1 through M-7, or L-10; does not re-litigate Task 38.7's Layer 1–3 gate re-evaluation; and does not resolve `builtins.str.join`'s ADR-032 Phase 0 authorization, which remains paused and unrecorded throughout.

---

# Objective

M-8's own recorded evidence is a discovery-reach gap, not a discovered unsafe path: no currently reachable production call site is shown to route a forbidden operation through implicit dispatch. But the gap is real and structural — a future or currently-unreviewed class implementing a protocol method with a forbidden body, reached through the ordinary syntax that triggers that protocol from a path reachable off `app.main.main`/`app.bootstrap.run_dry_run_bootstrap`, would go completely undetected by the static walker, with the coded `exit_code` predicate reporting a clean result regardless.

Task 38.8 exists to give this gap the same discipline Task 38.6 gave M-7 and Task 38.7 gave its own residual: a source-controlled, deterministic, testable mechanism (or an explicitly bounded, evidence-backed decision not to build one yet) — never a name/attribute/package/decorator/dunder-name allowlist standing in for real resolution, and never a claim of safety for anything the mechanism cannot soundly resolve. This is a **specification-writing pass only**. It defines Phase 0 (architecture decision), Phase A (mechanism + tests), Phase B (full re-run + evidence), and Phase C (M-8/ADR-032 update from that evidence) for a future implementation task — it does not perform any of them.

---

# 1. Exact Problem Statement

State, verbatim in the future task's own report, the same distinction M-8's evidence already established:

* **Explicit calls** — a literal `ast.Call` AST node in a walked callable's own source. `StaticWalker.walk()`'s `_shallow_descendants` loop finds every one of these; each is resolved via `_resolve_target` and classified via `classify_callable` into one of the four `Category` buckets, and counted in `nodes_total`/`nodes_unresolved`/`calls_total`/`calls_unresolved`.
* **Implicit interpreter dispatch** — execution the CPython interpreter performs in direct response to syntax (an operator, a `for`/`with`/`async with`/`async for` statement, unpacking, a comprehension, subscription, membership testing, an f-string/`format()`/`str()`/`repr()` call site, a set/dict literal or insertion, `await`, or a bare attribute read that happens to invoke a `@property`/descriptor getter) with **no corresponding `ast.Call` node anywhere in the walked source**. This produces zero trace: not a `CallRecord`, not an entry in `nodes_unresolved_detail`/`calls_unresolved_detail`, not any other counter. It is invisible by construction, not merely unresolved.
* **Unreachable source** — a callable the walker never reaches at all, because no traced root, registrar, provider, or already-discovered node's body leads to it. Distinct from both of the above: this is a graph-reachability gap, not a discovery-mechanism gap, and is out of this task's scope (it is the general subject of the walker's own root/recursion design, unchanged here).
* **Methods independently reached through another explicit path** — a protocol method (e.g. `__eq__` also called directly as `obj.__eq__(other)` somewhere else in source) that the walker *does* discover, via an ordinary `ast.Call` node, at some other call site. Such a method is not a gap instance for this task's accounting even though the *same method*, reached implicitly elsewhere (e.g. via `==`), would still be invisible at that other, implicit call site — the census in §4 below must count sites, not methods, precisely so this distinction is not lost.
* **Runtime-denial coverage** — `audit_harness.runtime_denial.run_paper_only_denial_check`'s patch-and-observe mechanism operates at actual execution time, on the one real, paper-only `run_dry_run_bootstrap()` call the harness's own re-run performs. It is complementary, not a substitute: it would catch a forbidden operation reached via implicit dispatch *if and only if that exact code path is actually executed during that one run*. It says nothing about implicit-dispatch paths that exist in source but are not exercised by that run's own execution — the persisted `forbidden_call_observed=None` result is circumstantial evidence about the paths actually taken during that run, never a general proof about paths the static walker cannot see.

The future task's report must keep these four categories textually distinct wherever it reports counts or conclusions — never merged into a single "issues found" figure.

---

# 2. Required Protocol Families

The future task's negative-control fixtures and census (§3, §4) must cover, at minimum, every family below. Each is named because it is a real CPython interpreter-dispatch mechanism with no corresponding `ast.Call` node in the dispatching code:

* **Iteration and comprehensions** — `__iter__`, `__next__` (a `for` statement, a list/set/dict/generator comprehension, or any construct CPython desugars to the iterator protocol).
* **Unpacking** — `a, *b = obj` and `*a, b = obj`, which invoke `__iter__`/`__next__` the same way iteration does but via a distinct AST shape (`ast.Starred`, tuple/list assignment targets).
* **Context managers** — `__enter__`, `__exit__`, and their async equivalents `__aenter__`/`__aexit__` (`with`/`async with`).
* **Await and async iteration** — `__await__` (a bare `await expr`), and `__aiter__`/`__anext__` (`async for`).
* **Properties and descriptors** — `__get__`, `__set__`, `__delete__` (a `@property`/custom-descriptor getter/setter/deleter invoked via a bare `ast.Attribute` read/write/`del`, with zero `ast.Call` node of any kind — the sharpest instance, per M-8's own recorded evidence).
* **Equality, ordering, and arithmetic operators, including reflected forms** — `__eq__`/`__ne__`/`__lt__`/`__le__`/`__gt__`/`__ge__`, `__add__`/`__sub__`/`__mul__`/etc., and their `__r*__` reflected counterparts (invoked when the left operand's own method returns `NotImplemented` or does not define the operation).
* **Truth testing** — `__bool__`, and CPython's own documented fallback to `__len__` when `__bool__` is undefined (an `if obj:`/`while obj:`/`not obj`/any implicit truth context).
* **Membership and its iteration fallback** — `__contains__`, and CPython's own fallback to the iteration protocol when `__contains__` is undefined (`in`/`not in`).
* **Subscription and assignment/deletion** — `__getitem__`, `__setitem__`, `__delitem__` (`obj[k]`, `obj[k] = v`, `del obj[k]`).
* **Hashing** — `__hash__`, triggered by set/dict-key insertion (`{obj}`, `{obj: v}`, `some_set.add(obj)` where `obj`'s hash is computed on insertion, not the `.add(` call site itself).
* **Formatting** — `__format__`, with its documented fallback to `__str__`/`__repr__` where applicable (an f-string, `format(obj, ...)`, `str(obj)`, `repr(obj)`, `"{}".format(obj)`).

Any protocol family this task's implementation ultimately does not cover must be named explicitly as an unsupported family (§8), never silently omitted from the report.

---

# 3. Source-Controlled Negative Controls

Every fixture and its assertion belong under `tests/audit_harness/` (a new fixtures module alongside the existing `tests/audit_harness/fixtures/`), version-controlled and permanent — never a `/tmp` scratch script. Each fixture:

* Embeds a real forbidden identity — `builtins.open` (a member of `audit_harness.identity.FORBIDDEN_IDENTITIES`) is the reference choice, matching every prior negative control this harness already uses — inside the body of the one dunder method that implements the protocol family under test.
* Is triggered **only** through the ordinary syntax that invokes that protocol (a `for` loop, a `with` statement, a comparison operator, `in`, an f-string, a set/dict literal, `+`, a bare attribute read, etc.) — never through a direct, explicit call to the dunder method by name, which would defeat the fixture's own purpose.
* Is **never executed**. The fixture module is imported only for its `ast`-parseable source (via `StaticWalker.walk`, exactly as every other fixture in `tests/audit_harness/fixtures/` is already consumed) and the sentinel `open(...)` call inside it is never reached at runtime, by construction — the same non-execution discipline this repository has held to for every implicit-dispatch fixture built during M-8's own diagnostic work.

Required tests, per family named in §2:

* **Pre-remediation (characterization) test** — proves the *current* behavior: walking the fixture produces zero `CallRecord` referencing the embedded sentinel, for every family. This test must exist and pass **before** any Phase A mechanism work begins, so the future task has a committed, reproducible baseline for exactly what M-8 claims, not a re-derivation from memory or from `/tmp` evidence.
* **Post-remediation test** — added or updated once a Phase A mechanism exists, proving the chosen mechanism either (a) detects the embedded sentinel and correctly classifies it `forbidden`, or (b) — if the chosen architecture (§5) is Option C (bounded scope) — produces an explicit, deterministic, machine-readable implicit-dispatch record for that site (never a silent pass), consistent with the fail-closed requirements in §6.

**Detection-assertion discipline (binding on every test above and on any future test in this area):** assertions must key on callable identity or `IdentityVerdict.category`/`module`/`qualname` — e.g. `verdict.category == "forbidden"`, or `module == "builtins" and qualname == "open"` — **never** on a substring match against the sentinel's file path, function name, or any other string incidental to how the fixture happens to be written. A path-substring check does not actually verify identity and can produce a false pass with no `CallRecord` present at all to search — this is the exact methodological defect M-8's own v1/v2 diagnostic passes made and had to correct; the permanent test suite must not repeat it.

---

# 4. Correct Census Methodology

Any implementation-phase or evidence-phase claim about how many implicit-dispatch sites exist, how many are covered, or how the walker's real workload changed must be grounded in instrumentation of the **real, accepted** `StaticWalker.walk()` states — not a file-level or unrestricted-`ast.walk()` approximation. Specifically, a callable counts as genuinely visited only once, for a given state, it has:

* passed specialization-key deduplication (`visit_key = (fid, specialization_key)` not already in `self.visited_funcs`);
* passed the total-work budget (`len(self.visited_funcs) < self.max_total_walk_steps`, i.e. not appended to `self.depth_exceeded`);
* retrievable, parseable source (`_dedented_source(real_func)` not `None`, and `ast.parse` not raising — i.e. not appended to `self.sites_without_source`);
* and genuinely descended into (its body's nodes iterated via `_shallow_descendants`, not returned from early).

Instrumentation proving this must diff `self.visited_funcs`/`self.sites_without_source`/`self.depth_exceeded` before and after each `walk()` call, not merely count wrapper-entry invocations — a raw invocation count conflates dedup no-ops and source-unavailable rejections with genuine acceptances, which M-8's own v2 diagnostic pass demonstrated inflates the apparent workload by more than half.

Node enumeration for the census must use `audit_harness.trace._shallow_descendants(tree)` directly — the same traversal `walk()` itself uses — never an unrestricted `ast.walk()` over the whole parsed module, which risks mis-attributing nested-function/lambda-body nodes to the wrong enclosing scope (the one documented, accepted traversal-parity gap: `_shallow_descendants` does not filter a lambda's body out of its enclosing statement, a documented `inspect.getsource` quirk — this must be noted, not silently assumed away, wherever the census reports on lambda-bodied implicit dispatch).

The census must report each of the following as a **separate** figure, never collapsed into one number:

* raw `walk()` invocations (including dedup no-ops and source-unavailable rejections);
* accepted specialization-distinct states (post-dedup, post-budget, post-source-availability);
* distinct callable identities (module+qualname) among the accepted states;
* raw implicit-protocol-dispatch-shaped AST nodes found within accepted states' own bodies (e.g. `ast.Compare`, `ast.With`, `ast.Attribute(Load)` on a known-property owner, a `for`/comprehension target, etc. — the concrete node shapes the chosen mechanism, per §5, actually inspects);
* unique source locations (module+qualname+line+col+family) among those raw nodes, deduplicated;
* unresolved-polymorphic sites — a site whose receiver type cannot be soundly determined statically;
* concrete resolved protocol targets — a site whose receiver type *is* soundly determined, and whose target dunder method is a known, classified identity;
* targets independently covered by explicit call paths — a protocol method also reached via an ordinary `ast.Call` node elsewhere in the trace (§1's fourth category), reported to make clear these are not double-counted as newly-covered by any implicit-dispatch mechanism.

Any property-access claim specifically must be counted by actual attribute-access **site**, not by "property exists on a class" — enumerating every `@property`/descriptor definition on a discovered class and stopping there conflates definition with use and was the specific defect M-8's own v2 diagnostic pass made and its v3 pass corrected by scanning bare `ast.Attribute(Load)` nodes in accepted callables' own bodies and cross-referencing them against known property names on a receiver type resolved via the walker's own existing type-inference methods (`_collect_local_var_types`, `_enclosing_function_param_hints`, `_real_param_types`) — reused as-is, never reimplemented, for this purpose.

---

# 5. Architecture Evaluation

Phase 0 (§9) requires an evidence-backed decision among the following four options — not a decision made because it happens to reduce an unresolved counter. For each option, the Phase 0 record must assess all nine criteria below, with concrete reasoning, not a checklist tick:

**A. AST-node-to-protocol expansion** — extend `StaticWalker`'s per-node loop to also recognize the AST shapes each protocol family in §2 produces (`ast.Compare`, `ast.With`/`ast.AsyncWith`, `ast.For`/`ast.AsyncFor`/comprehension generators, `ast.Subscript` in `Store`/`Del` context, `ast.Attribute` in `Load`/`Store`/`Del` context, `ast.BinOp`/`ast.UnaryOp`, `ast.Await`, set/dict literals, f-strings), resolve the receiver's static type the same way `_resolve_target` already does for an ordinary call, and look up the corresponding dunder method on that type to classify via the existing three-bucket scheme.

**B. Bytecode-assisted discovery** — compile the walked source (or read `real_func.__code__`) and scan for the bytecode instructions CPython actually emits for these operations (`COMPARE_OP`, `GET_ITER`, `FOR_ITER`, `BEFORE_WITH`/`SETUP_WITH`, `BINARY_OP`, `LOAD_ATTR`/`STORE_ATTR` when the target is a known descriptor, `CONTAINS_OP`, `BINARY_SUBSCR`/`STORE_SUBSCR`, `FORMAT_VALUE`), to catch dispatch shapes that AST inspection alone might miss or that vary across desugaring.

**C. Explicitly bounded static scope plus documented residual** — do not attempt general implicit-dispatch discovery at all. Instead, formally document the boundary as a permanent, versioned statement in the assurance report and `EXACT_IDENTITY_POLICY`'s own module docstring (not a code mechanism): the walker discovers explicit `ast.Call` nodes only; implicit dispatch is categorically out of its static scope; closure depends entirely on the complementary runtime-denial layer plus this task's own negative-control regression suite (§3) proving the boundary is stable and tested, not silently eroding.

**D. A justified hybrid** — e.g. Option A for a narrowly bounded, high-value subset (property/descriptor access, since it is the one family with no `ast.Call` node of any shape, and context managers, since `__exit__` guards resource-release code most likely to perform real I/O) combined with Option C's documented-residual treatment for the remaining, lower-priority families, with the boundary between "mechanized" and "documented residual" stated exactly, per family.

For each option, the Phase 0 record must assess:

* **Soundness** — does a positive resolution (a receiver's type, a dunder target) ever risk being wrong in a way that could misclassify a genuinely forbidden call as safe?
* **Behavior under polymorphism and duck typing** — what happens when a receiver's static type cannot be pinned to one concrete class (a `Protocol`, a union, an untyped parameter)? Does the mechanism degrade to an explicit unresolved-polymorphic record (required, see §6), or does it silently skip the site?
* **False negatives** — which real implicit-dispatch shapes would still go undiscovered under this option, named specifically, not asserted away in general language.
* **False positives or manufactured confidence** — could this option produce a resolved/safe verdict for a site that is not actually safe, e.g. by resolving a receiver's *declared* type when the *runtime* type differs (the same duck-typing risk the existing walker's parameter-annotation substitution already carries and documents)?
* **Deterministic termination** — does the option risk opening new unbounded recursion (e.g. Option A's dunder-method targets are themselves callables that may need walking, at which point Termination requirements in §7 govern them identically to any other discovered callable)?
* **Specialization-state growth** — does the option meaningfully increase `self.visited_funcs`' size on the real trace, and by how much, relative to the ~1,519-state baseline `_MAX_TOTAL_WALK_STEPS`'s own docstring records?
* **CPython-version coupling** — does the option depend on bytecode instruction names/shapes (Option B specifically) that are not stable across CPython minor versions, and if so, how is that coupling documented and guarded (a version check, a fallback, an explicit unsupported-version report)?
* **Maintenance burden** — how much new, ongoing surface does the option add to `audit_harness/`, and how does that compare to Option C's near-zero code footprint?
* **Implementation size** — a rough, honest estimate of new lines/functions, for comparison across options.
* **Compatibility with the existing fail-closed gate** — does the option's own failure mode (an exception, a partial result, an unresolved receiver) route into the existing `unresolved`/HOLD machinery, or does it require new plumbing, and if so, does that new plumbing itself risk a silent-pass path?

**This task explicitly forbids selecting a mechanism merely because it reduces an unresolved counter.** The Phase 0 record must justify its choice on the nine criteria above; a rationale that cites only "this closes M-8" or "this reduces `calls_unresolved`" without addressing soundness, false positives, and termination is not an acceptable Phase 0 record.

---

# 6. Fail-Closed Requirements

Binding on whichever architecture Phase 0 selects, and on any future revision of it:

* The eventual implementation must **never classify an uncertain protocol target as safe.** A resolution is only ever reported as concrete/resolved when the receiver's type and the dispatched method are both soundly established by the same identity-first discipline `_resolve_target`/`classify_callable` already use for explicit calls — never a guess, a most-likely-type heuristic, or a "probably fine" default.
* If a concrete receiver or protocol target **cannot** be soundly resolved, the implementation must produce an **explicit, deterministic, machine-readable unresolved/implicit-dispatch record** — a new, additive field (§8) distinct from, but held to the same "nonzero keeps the gate at HOLD" discipline as, the existing `nodes_unresolved`/`calls_unresolved` counters. It must never be silently dropped, and it must never be reported as `resolved-safe` by default.
* **No name, attribute-text, package-origin, decorator-text, or dunder-name allowlist** may convert an unresolved implicit dispatch into a resolved one. A table that says "any class's `__iter__` is safe" or "any `@property` getter is safe" — regardless of how the table is framed or how narrowly its authors intend it — is exactly the blanket, non-individually-reviewed trust `audit_harness.identity`'s own design (and Task 38.7's "No Allowlists, No Blanket Trust" section) already forbids, extended here explicitly to this new surface. Every accepted resolution must be an individual, identity-based classification of the one real, live callable object reached, the same discipline `EXACT_IDENTITY_POLICY` already applies to explicit calls — never a pattern over the syntax or the dunder name that triggered dispatch.
* `EXACT_IDENTITY_POLICY` must remain **callable-identity-based** (module+qualname of a real, live object) and may **not** be repurposed as, or supplemented by, an attribute-name or protocol-name policy. A dunder method reached via implicit dispatch and resolved to a concrete callable is classified through the *existing* three-bucket scheme on that callable's own identity, exactly as an explicit call would be — this task adds no new classification category and no new kind of policy table.

---

# 7. Termination and Determinism

The eventual implementation must define, and its Phase A tests must prove:

* **Specialization-aware cycle handling** — a discovered protocol-dispatch target that is itself walked (e.g. under Option A/D, once resolved) is subject to the exact same `(callable identity, specialization)` visited-state dedup `walk()` already applies to every other discovered callable — never a separate, parallel cache that could diverge from it.
* **Deterministic total-work limits** — any new recursion this mechanism opens counts against the existing `max_total_walk_steps` budget, not a separate, additional budget that could let total work grow unboundedly across the two mechanisms combined.
* **Stable ordering and deduplication** — implicit-dispatch sites are enumerated and reported in a deterministic order (e.g. sorted by module+qualname+line+col+family), preserving Harness Requirement 1's byte-identical-output guarantee across repeated runs against the same commit.
* **Explicit reporting when a limit is reached** — budget exhaustion during implicit-dispatch discovery is reported the same way existing budget exhaustion is (`self.depth_exceeded`-equivalent, or an explicitly named new field), never silently truncated.
* **No package-origin depth cap** — consistent with the existing walker's own documented termination discipline (`_MAX_TOTAL_WALK_STEPS`'s docstring), any new bound this mechanism introduces must be package-neutral, never conditioned on whether a frame is project-owned or third-party.
* **No silent drops caused by recursion, polymorphism, or unsupported syntax** — a site the mechanism cannot classify for any reason (recursion budget, an unresolvable receiver, a protocol shape the implementation does not yet cover) is always reported via the explicit unresolved/implicit-dispatch record (§6), never omitted from output entirely.

---

# 8. Evidence and Report Changes

The future implementation task's machine-readable output and assurance report must add, additively (never replacing or renaming an existing field):

* **Observed implicit sites** — total count of implicit-dispatch-shaped syntax sites found, per §4's census methodology.
* **Resolved concrete protocol targets** — sites where a receiver type and dunder target were both soundly resolved, classified via the existing three-bucket scheme.
* **Unresolved/polymorphic sites** — sites where the receiver type could not be soundly pinned; required nonzero-keeps-HOLD treatment identical to `nodes_unresolved`/`calls_unresolved`.
* **Explicit-path duplicates** — targets also independently reached via an ordinary `ast.Call` node elsewhere (§1's fourth category), reported separately so they are never double-counted as "newly covered."
* **Unsupported protocol families** — any family named in §2 the chosen architecture does not attempt to cover, named explicitly (this is the required content of an Option C/D "documented residual," not merely implied by its absence from a table).
* **Work-budget exhaustion** — any implicit-dispatch-specific budget-exhaustion event (§7), with the same explicit, non-silent reporting discipline as existing budget exhaustion.
* **Negative-control results** — pass/fail detail for every fixture in §3, per family, mirroring the existing `negative_controls_detail`/`negative_controls_detected`/`negative_controls_total` shape.

**Explicit clarification, binding on the future task:** the existing `nodes_unresolved` and `calls_unresolved` fields (schema `38.7.0`, `audit_harness/report.py`) remain **explicit-call counters** — they must not be redefined to silently absorb implicit-dispatch counts. If a future implementation deliberately decides implicit-dispatch results belong inside those same counters, that is a **new, deliberately versioned schema change** (a new `SCHEMA_VERSION`, documented exactly as the `38.6.0` → `38.7.0` bump was), never an undocumented behavior change to what an existing field means on a re-run someone might diff against `docs/audits/task-38.7-result.json`'s committed baseline.

---

# 9. Phase Discipline

The future implementation task follows four separate phases, each producing its own non-overlapping deliverable set — no phase's deliverable is committed alongside another phase's:

* **Phase 0 — architecture and safety-boundary approval.** A human reviewer records, in `ADR-032`, an explicit decision among the four options in §5 (or a justified variant), addressing all nine evaluation criteria, before any Phase A code is written. Phase 0 produces one `ADR-032` edit standing alone — no code, no test, no other document.
* **Phase A — source-controlled mechanism and tests.** Implements the Phase-0-selected architecture in `audit_harness/`, adds the negative-control fixtures and both pre- and post-remediation tests (§3) under `tests/audit_harness/`, and adds any new schema fields (§8) to `audit_harness/report.py` (with a deliberate, documented schema-version bump). No evidence document, JSON result, risk-register disposition change, or `ADR-032` re-evaluation is part of Phase A.
* **Phase B — full harness run and evidence regeneration.** Run strictly after Phase A is committed: the harness's own full test suite, the full project test suite, and a real re-run against the Phase A commit, producing a new, canonical JSON result and narrative assurance report — named and committed the same way `docs/audits/task-38.7-result.json`/`task-38.7-assurance-report.md` were, never overwriting either.
* **Phase C — M-8 and `ADR-032` update from committed Phase B evidence only.** Updates `docs/audits/task-38.5-risk-register.md`'s M-8 disposition (closed, narrowed, or left open with the exact remaining blocker named) and `ADR-032`'s re-evaluation, citing Phase B's committed result and hash — never a claim made ahead of, or independent of, that committed evidence.

**No Phase A code may precede the recorded Phase 0 decision.** This mirrors Task 38.7's own Two-Phase Provenance discipline exactly, extended here to the four-phase shape this task's architecture-selection step requires.

---

# 10. Gate and Policy Constraints

Binding on the future implementation task, restated because they are the ways this task could fail silently:

* `ADR-032` remains **HOLD** throughout this specification and throughout the future implementation task's own work, unless and until all existing gate layers (Task 38.7's Layers 1–3: the eight-condition coded predicate, `unimportable_nodes`, and H-1/H-2/other independent findings) independently pass — this task's own work is additive to, never a substitute for, any of those.
* **H-1 and H-2 remain separate, individually-named blockers** throughout — never merged into a single "open findings" line, never touched by this task or the one it defines.
* **M-8 remains Open** until the future implementation task's Phase C update, grounded in committed Phase B evidence, satisfies M-8's own recorded closure criteria (a general mechanism proven by regression tests, or an explicitly bounded and documented residual with equivalent evidence) — not before, and not by this spec-writing pass.
* **`builtins.str.join`'s ADR-032 Phase 0 authorization remains paused and unrecorded.** This task neither authorizes nor rejects it, in this spec-writing pass or in any phase of the future implementation task it defines — the two are unrelated identity-policy questions, and this task does not resolve one as a side effect of the other.
* **`EXACT_IDENTITY_POLICY` is not modified by this spec-writing pass.** Any future modification belongs to the future implementation task's own Phase A, and even there, only through the exact identity-based discipline §6 restates — never repurposed as an attribute/protocol-name policy.
* **`docs/audits/task-38.7-result.json` and its hash (`bdbe9cffd1b770140af150e2d66a6524e078f17a817f99bb5d1ec771a7731c0b`) are not altered** by this spec-writing pass or by any phase of the future implementation task prior to that task's own Phase B re-run producing a new, separately named result file.

---

# 11. Verification Requirements

The future implementation task must run and report, verbatim, before its Phase C update:

* **All existing `audit_harness` tests** — the full `tests/audit_harness/` suite (currently `test_harness_properties.py`, `test_lifecycle_denial_completeness.py`, `test_negative_controls.py`, `test_task_38_7_categories.py`, plus `fixtures/`), passing unmodified in intent, with an explicit "N existing + M new" accounting, never a replacement count.
* **New per-family negative controls** — every fixture and test named in §3, for every protocol family named in §2 (or explicitly named as unsupported per §8 if the selected architecture does not cover it).
* **Deterministic repeated runs** — running the harness twice against the same commit, with no other input change, produces byte-identical (or hash-equal, after canonicalization) machine-readable output, including the new implicit-dispatch fields — the same discipline Harness Requirement 1/9 already established, extended to this new surface.
* **Targeted lint and type checks** — `ruff check` and a type check (`mypy` or equivalent) scoped to any new/modified `audit_harness/` source, matching this repository's existing per-package baseline discipline.
* **Full project test suite** — `python -m pytest -q` from repo root under `.venv/bin/python` (never `uv`), with the resulting pass count compared against the last recorded baseline, any delta explained.
* **Paper-only runtime denial at 24/24** — `run_paper_only_denial_check` against the real `app.bootstrap.run_dry_run_bootstrap`, confirming `status=SUCCESS, total=24, passed=24, failed=0, forbidden_call_observed=None`, "paper-only" stated explicitly, restating (never relaxing) the no-live-connection invariant.
* **Formula/counter reconciliation** — the new implicit-dispatch counters (§8) cross-checked for internal consistency (e.g. `observed implicit sites == resolved concrete targets + unresolved/polymorphic sites + explicit-path duplicates + unsupported-family sites`, or an equivalent stated invariant) across the JSON result, the assurance report, the risk register's M-8 entry, and `ADR-032` — the same reconciliation discipline this repository already required for `calls_unresolved_detail_multiplicity` in Task 38.7.
* **Exact worktree and artifact provenance** — final `git status`/HEAD/stash state reported at the end of each phase, and every cited evidence artifact is a committed file at a stated path and hash — never a `/tmp` scratch path cited as durable evidence, consistent with the discipline this repository has already held to throughout M-8's own diagnostic history.

---

# Non-Goals

Explicitly out of scope for both this spec-writing pass and the future implementation task it defines, at every phase:

* **No implementation or simulation of any discovery mechanism by this spec-writing pass.** This task writes one specification document; it builds nothing, runs nothing, and instruments nothing.
* **No decision on `builtins.str.join`'s ADR-032 Phase 0 review.** That review remains paused and unrecorded; this task does not authorize, reject, or otherwise advance it.
* **No modification of `EXACT_IDENTITY_POLICY`** by this spec-writing pass, in any form.
* **No re-litigation of H-1, H-2, M-1 through M-7, or L-10.** All remain exactly as `docs/audits/task-38.5-risk-register.md` and `ADR-032` currently record them.
* **No re-opening of Task 38.7's Layer 1–3 gate re-evaluation.** This task's future implementation work is additive to that evaluation, never a redo of it.
* **No live operations, at any phase.** No real trade, live inference call, or live broker/exchange/DB/Redis/network connection, under any configuration — including inside any new fixture this task or its implementation adds.
* **No dependency change.** No package added, removed, or upgraded; `uv` never invoked in any form; `uv.lock` stays untracked and untouched by this spec-writing pass, and by the future implementation task unless that task explicitly justifies and documents a harness-only dev dependency — which this spec does not authorize.
* **No commit, push, or tag** by this spec-writing pass. The future implementation task's own commit/push/tag policy follows this repository's standing phased workflow — this spec grants no new exception.

---

# Constraints

* This spec-writing pass modifies no production code, test file, or existing documentation file — it creates exactly one new file, `docs/prompts/task-38.8.md`.
* Do NOT add, remove, or upgrade a dependency. Do NOT run `uv` in any form. `uv.lock` stays untracked and untouched.
* Do NOT commit, push, or tag.
* Every requirement above binds the **future** implementation task, not this spec-writing pass — this pass performs no implementation, runs no harness, simulates no mechanism, and modifies no code.

---

# Acceptance Criteria

✓ `docs/prompts/task-38.8.md` exists and defines a source-controlled follow-up for M-8 — no implementation or simulation performed by this spec-writing pass

✓ §1 states the exact problem cleanly, separating explicit calls, implicit interpreter dispatch, unreachable source, methods independently reached through another explicit path, and runtime-denial's execution-time-only coverage

✓ §2 names every required protocol family from M-8's own recorded evidence, including property/descriptor access as the sharpest instance

✓ §3 requires permanent, non-executed, git-tracked fixtures and both pre- and post-remediation tests, with detection assertions keyed on callable identity/verdict category — never sentinel path-string matching

✓ §4 requires census instrumentation grounded in `StaticWalker.walk()`'s real acceptance gating and `trace._shallow_descendants`, with eight separately reported figures, never collapsed

✓ §5 requires an evidence-backed choice among four named architecture options, assessed against nine named criteria, explicitly forbidding selection merely because it reduces an unresolved counter

✓ §6 requires the eventual implementation to never classify an uncertain protocol target as safe, to produce an explicit unresolved/implicit-dispatch record for anything unresolved, to forbid any name/attribute/protocol allowlist, and to keep `EXACT_IDENTITY_POLICY` callable-identity-based only

✓ §7 defines specialization-aware cycle handling, deterministic total-work limits, stable ordering, explicit limit reporting, no package-origin depth cap, and no silent drops

✓ §8 specifies the required new machine-readable counters and report sections, and explicitly clarifies that `nodes_unresolved`/`calls_unresolved` remain explicit-call-only unless deliberately versioned and redefined

✓ §9 defines four non-overlapping phases (0/A/B/C) with Phase 0 preceding all Phase A code

✓ §10 restates every binding gate/policy constraint: `ADR-032` stays HOLD pending all layers, H-1/H-2 stay separate, M-8 stays Open pending Phase C, `str.join` stays paused, `EXACT_IDENTITY_POLICY` untouched by this pass, and the Task 38.7 result JSON/hash untouched

✓ §11 requires the full verification battery: existing tests, new negative controls, deterministic repeated runs, lint/type checks, full project suite, 24/24 paper-only runtime denial, counter reconciliation, and exact provenance reporting

✓ Non-Goals explicitly forbid implementation by this pass, a `str.join` decision, an `EXACT_IDENTITY_POLICY` change, re-litigating other findings/layers, live operations, dependency changes, and commit/push/tag

✓ Constraints explicitly forbid this spec-writing pass from implementing anything, modifying `uv.lock`, or committing/pushing/tagging

---

# Completion Checklist

After writing this spec, stop. Do not begin implementing any mechanism. Report:

1. The one file created
2. A summary of the eleven numbered sections (problem statement, protocol families, negative controls, census methodology, architecture evaluation, fail-closed requirements, termination/determinism, evidence/report changes, phase discipline, gate/policy constraints, verification requirements)
3. Exact output of `git diff --check`, confirmation that only `docs/prompts/task-38.8.md` and the pre-existing untracked `uv.lock` appear in `git status --short --untracked-files=all`, and final HEAD/origin/stash confirmation
4. An explicit statement that no mechanism, policy entry, `str.join` decision, or gate change was made

Stop after reporting completion.
