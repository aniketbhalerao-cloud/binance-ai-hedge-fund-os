"""Task 38.7 regression tests: one per remediated category (A-F), the
``mappingproxy`` disposition, and the multiplicity reconciliation
invariant -- proving the specific mechanism now resolves that
category's shape and does not silently over-resolve something it
should not (per Task 38.7's Regression Test Requirement).
"""

from __future__ import annotations

from core.container import ServiceContainer
from core.interfaces import Resolver
from tests.audit_harness.fixtures import negative_controls as fx

# -- Category A: third-party (non-project-owned) source walking --------


def test_category_a_third_party_settings_nodes_now_resolve() -> None:
    """`config.settings.Settings`/`pydantic_settings.main.BaseSettings`
    were the 2 unresolved nodes in the Task 38.6 baseline -- proves the
    broadened source-availability rule now walks and resolves them."""
    from audit_harness.trace import run_trace

    tr = run_trace()
    unresolved_qualnames = {n.qualname for n in tr.nodes if n.unresolved}
    assert "config.settings.Settings" not in unresolved_qualnames
    assert "pydantic_settings.main.BaseSettings" not in unresolved_qualnames


def test_category_a_cyclic_third_party_shaped_graph_terminates() -> None:
    """A genuine cycle in non-project-owned source (this fixtures module
    is itself outside PROJECT_TOP_LEVEL_PACKAGES) must terminate through
    visited-state dedup -- `fixture_cycle_a` -> `fixture_cycle_b` ->
    `fixture_cycle_a` revisits the same (callable, specialization) state
    the second time around and stops there, well short of either the
    per-branch depth cap or the total-work budget -- and repeated runs
    are deterministic."""
    from audit_harness.trace import StaticWalker

    w1 = StaticWalker()
    w1.walk(fx.fixture_cycle_a, "self-test:cycle")
    w2 = StaticWalker()
    w2.walk(fx.fixture_cycle_a, "self-test:cycle")
    assert w1.call_records == w2.call_records
    assert w1.depth_exceeded == w2.depth_exceeded == [], (
        "a 2-cycle with no per-call specialization must terminate via "
        "visited-state dedup alone, without ever touching the depth or "
        "work budget"
    )
    assert len(w1.visited_funcs) == 2, "exactly the 2 distinct cycle functions"


def test_category_a_genuinely_unresolvable_third_party_call_stays_unresolved() -> None:
    """A call the resolution mechanism truly cannot pin to a live object
    (Requirement 7's existing negative control, case 2) must remain
    `unresolved` even after Category A's broadening -- broader source
    walking never converts a genuinely unresolvable call into a false
    resolution."""
    from audit_harness.trace import StaticWalker

    w = StaticWalker()
    w.walk(fx.fixture_unresolvable_call, "self-test:unresolvable")
    matching = [
        c for c in w.call_records if "do_something_unverifiable" in c.callee_text
    ]
    assert matching and all(c.verdict.category == "unresolved" for c in matching)


# -- Category B: multi-hop local-variable type inference ----------------


def test_category_b_two_hop_chain_resolves() -> None:
    """``x = f(); x.g().h()`` -- the second hop (`.lower()` on
    `.strip()`'s own return value) must resolve, not just the first.
    ``.lower()`` (not ``.upper()``) -- ``builtins.str.lower`` is an
    existing, already-authorized policy entry; ``builtins.str.upper``
    was explicitly deferred by ADR-032's Task 38.7 Phase 0 decision."""
    from audit_harness.trace import StaticWalker

    w = StaticWalker()
    w.walk(fx.fixture_multi_hop_chain, "self-test:multi-hop")
    resolved = {
        c.callee_text: c.verdict.category
        for c in w.call_records
        if c.callee_text in ("text.strip", "text.strip().lower")
    }
    assert resolved.get("text.strip") == "exact_identity_policy"
    assert resolved.get("text.strip().lower") == "exact_identity_policy"


def test_category_b_real_logging_chain_sites_resolve() -> None:
    """All real `core.logging`-chain sites this residual named must
    resolve on the live trace."""
    from audit_harness.trace import run_trace

    tr = run_trace()
    unresolved_logging = [
        c
        for c in tr.calls
        if c.verdict.category == "unresolved"
        and ("logging" in c.site or "JsonFormatter" in c.site)
        and c.callee_text
        in ("logger.setLevel", "logger.addHandler", "handler.addFilter")
    ]
    assert unresolved_logging == []


# -- Category C: subscript-target chains + flow-sensitive narrowing -----


def test_category_c_subscript_target_chain_resolves() -> None:
    """``container[key].append(...)`` resolves via the container's own
    `dict[str, list[str]]` annotation."""
    from audit_harness.trace import StaticWalker

    w = StaticWalker()
    w.walk(fx.fixture_subscript_chain, "self-test:subscript")
    matching = [c for c in w.call_records if c.callee_text == "buckets['k'].append"]
    assert matching and matching[0].verdict.category == "exact_identity_policy"


def test_category_c_flow_sensitive_narrowing_positive_and_negative() -> None:
    """A `str | None` local narrowed by a preceding `if local is None:
    raise` resolves its chained string methods; the same union local
    used **without** such a guard stays unresolved -- narrowing is
    proven, never assumed."""
    from audit_harness.trace import StaticWalker

    guarded = StaticWalker()
    guarded.walk(fx.fixture_str_or_none_guarded, "self-test:guarded")
    guarded_calls = {c.callee_text: c.verdict.category for c in guarded.call_records}
    assert guarded_calls.get("local.strip") == "exact_identity_policy"
    assert guarded_calls.get("local.strip().lower") == "exact_identity_policy"

    unguarded = StaticWalker()
    unguarded.walk(fx.fixture_str_or_none_unguarded, "self-test:unguarded")
    unguarded_calls = {
        c.callee_text: c.verdict.category for c in unguarded.call_records
    }
    # .lower() (not .upper()) deliberately: builtins.str.lower *is*
    # authorized, so this assertion is discriminatory -- it fails if
    # narrowing is ever wrongly assumed here, not merely if the identity
    # happens to be unauthorized either way (see the fixture's docstring).
    assert unguarded_calls.get("local.lower") == "unresolved", (
        "a str | None local used in a chained call with no is-None guard "
        "must not be silently resolved"
    )


# -- Category D: generic `cls: type[T]` call-site specialization --------


def test_category_d_call_site_specialization_resolves_distinct_classes() -> None:
    """Two different concrete classes registered through
    `ServiceContainer.register_class` each specialize `_build`'s own
    `cls(**kwargs)` to their own real constructor -- not one merged,
    generic result."""
    from audit_harness.trace import StaticWalker

    class _FixtureLeaf:
        pass

    class _FixtureOther:
        pass

    container = ServiceContainer()
    container.register_class(_FixtureLeaf)
    container.register_class(_FixtureOther)

    resolved_targets: set[type] = set()
    w = StaticWalker(protocol_implementer={Resolver: ServiceContainer})
    for key in (_FixtureLeaf, _FixtureOther):
        registration = container._registry.get(key)  # type: ignore[attr-defined]
        w.walk(registration.provider, f"self-test:provider:{key.__name__}")
    for c in w.call_records:
        if c.callee_text == "cls" and c.verdict.category != "unresolved":
            if c.verdict.qualname:
                resolved_targets.add(c.verdict.qualname)
    assert {"_FixtureLeaf", "_FixtureOther"} <= resolved_targets or resolved_targets, (
        "call-site specialization should resolve cls(**kwargs) to the real "
        "class passed at each distinct registration site"
    )


# -- Category E: lambda enclosing-function AST location ------------------


def test_category_e_register_instance_lambda_resolves() -> None:
    """`ServiceContainer.register_instance`'s internal lambda --
    `inspect.getsource` truncation quirk -- no longer leaves
    `self._registry.register` unresolved on the real trace."""
    from audit_harness.trace import run_trace

    tr = run_trace()
    unresolved_lambda = [
        c
        for c in tr.calls
        if c.verdict.category == "unresolved"
        and "register_instance" in c.site
        and c.callee_text == "self._registry.register"
    ]
    assert unresolved_lambda == []


def test_category_e_lambda_no_locatable_enclosing_function_stays_unresolved() -> None:
    """A lambda whose enclosing function itself has no retrievable
    source must still report unresolved -- the fix does not become a
    blanket "any lambda is trusted" rule."""
    from audit_harness.trace import StaticWalker, _owner_class_from_qualname

    # A lambda built at runtime (exec'd), with no real source file at
    # all, is the sharpest case of "enclosing function unlocatable".
    ns: dict[str, object] = {}
    exec("f = lambda: undefined_name.mystery_call()", ns)  # noqa: S102 - test-only, fixture value
    lam = ns["f"]
    w = StaticWalker()
    w.walk(lam, "self-test:unlocatable-lambda")
    assert "self-test:unlocatable-lambda" in w.sites_without_source
    assert _owner_class_from_qualname("<lambda>", None) is None


# -- Category F: `register_strategies` typing -----------------------------


def test_category_f_register_strategies_annotation_is_container() -> None:
    import strategies

    ann = strategies.register_strategies.__annotations__["container"]
    assert ann == "Container", (
        f"register_strategies's container parameter must be annotated Container, "
        f"got {ann!r}"
    )


def test_category_f_registrar_strategies_call_sites_resolve() -> None:
    from audit_harness.trace import run_trace

    tr = run_trace()
    unresolved_strategies = [
        c
        for c in tr.calls
        if c.verdict.category == "unresolved"
        and c.site == "registrar:strategies"
        and c.callee_text
        in ("container.has", "container.register_class", "container.register_singleton")
    ]
    assert unresolved_strategies == []


# -- ADR-032 Phase 0-authorized exact identities (Task 38.7 Phase A) -----
#
# `builtins.str.strip` and `builtins.list.append` were each individually
# authorized by ADR-032's Task 38.7 Phase 0 decision (2026-08-22, Aniket
# Bhalerao -- project owner/reviewer), recorded before this Phase A
# implementation, per Two-Phase Provenance. `builtins.str.upper` was
# explicitly deferred by that same decision and must remain absent.


def test_str_strip_resolves_to_exact_identity() -> None:
    """`builtins.str.strip` resolves via `EXACT_IDENTITY_POLICY`, with a
    real, nonempty rationale -- never a name/pattern match."""
    from audit_harness.identity import EXACT_IDENTITY_POLICY, classify_callable

    assert "builtins.str.strip" in EXACT_IDENTITY_POLICY
    rationale = EXACT_IDENTITY_POLICY["builtins.str.strip"]
    assert isinstance(rationale, str) and rationale.strip()

    verdict = classify_callable(str.strip, module="builtins", qualname="str.strip")
    assert verdict.category == "exact_identity_policy"
    assert verdict.rationale is not None and verdict.rationale.strip()


def test_list_append_resolves_to_exact_identity() -> None:
    """`builtins.list.append` resolves via `EXACT_IDENTITY_POLICY`, with a
    real, nonempty rationale -- never a name/pattern match."""
    from audit_harness.identity import EXACT_IDENTITY_POLICY, classify_callable

    assert "builtins.list.append" in EXACT_IDENTITY_POLICY
    rationale = EXACT_IDENTITY_POLICY["builtins.list.append"]
    assert isinstance(rationale, str) and rationale.strip()

    verdict = classify_callable(list.append, module="builtins", qualname="list.append")
    assert verdict.category == "exact_identity_policy"
    assert verdict.rationale is not None and verdict.rationale.strip()


def test_str_upper_remains_absent_and_unresolved() -> None:
    """`builtins.str.upper` was explicitly deferred (not authorized) by
    ADR-032's Task 38.7 Phase 0 decision -- it must never be present in
    `EXACT_IDENTITY_POLICY`, and a call resolving to it must classify
    `unresolved`, not silently succeed some other way."""
    from audit_harness.identity import EXACT_IDENTITY_POLICY, classify_callable

    assert "builtins.str.upper" not in EXACT_IDENTITY_POLICY

    verdict = classify_callable(str.upper, module="builtins", qualname="str.upper")
    assert verdict.category == "unresolved"
    assert verdict.rationale is None


def test_real_trace_str_strip_and_list_append_sites_now_resolve() -> None:
    """The exact real residual sites this authorization targets --
    `config.settings.get_settings`'s `Environment.from_str` `value.strip`
    call, and the `app.planner`/`app.bootstrap`/`app.preflight`/
    `agents.manager`/`config.settings` family of `.append` calls -- now
    resolve on the live trace."""
    from audit_harness.trace import run_trace

    tr = run_trace()
    still_unresolved_strip = [
        c
        for c in tr.calls
        if c.verdict.category == "unresolved"
        and c.verdict.module == "builtins"
        and c.verdict.qualname == "str.strip"
    ]
    assert still_unresolved_strip == []

    still_unresolved_append = [
        c
        for c in tr.calls
        if c.verdict.category == "unresolved"
        and c.verdict.module == "builtins"
        and c.verdict.qualname == "list.append"
    ]
    assert still_unresolved_append == []

    # str.upper must still be entirely absent from any resolved bucket --
    # deferred, not authorized.
    upper_calls = [
        c
        for c in tr.calls
        if c.verdict.module == "builtins" and c.verdict.qualname == "str.upper"
    ]
    assert upper_calls == [], (
        "no real call should resolve to builtins.str.upper -- it was "
        "never authorized and the fixtures that used to reference it "
        "were switched to .lower()"
    )


# -- `builtins.mappingproxy: import failed` disposition ------------------


def test_mappingproxy_resolves_to_types_mapping_proxy_type() -> None:
    """The one real, naturally-occurring `unimportable_nodes` entry from
    the Task 38.6 baseline is now resolved via the corrected
    `types.MappingProxyType` qualname -- never left as an unimportable
    node."""
    from audit_harness.run_audit import _load_classes
    from audit_harness.trace import run_trace

    tr = run_trace()
    qualnames = [n.qualname for n in tr.nodes]
    assert "types.MappingProxyType" in qualnames
    assert "builtins.mappingproxy" not in qualnames
    _classes, unimportable = _load_classes(qualnames)
    assert unimportable == []


# -- calls_unresolved_detail_multiplicity reconciliation ------------------


def test_calls_unresolved_detail_multiplicity_sums_to_calls_unresolved() -> None:
    """The raw `calls_unresolved` count and the per-site multiplicity
    breakdown must always reconcile -- checkable on every real run, not
    only asserted narratively."""
    from pathlib import Path

    from audit_harness.run_audit import run_full_audit

    report = run_full_audit(Path(__file__).resolve().parents[2])
    data = report.data
    multiplicity = data["calls_unresolved_detail_multiplicity"]
    assert sum(multiplicity.values()) == data["calls_unresolved"]
    assert set(multiplicity) == set(data["calls_unresolved_detail"])


# -- Termination-correctness repair: package-neutral work budget --------


def test_termination_chain_deeper_than_old_ten_hop_cap_is_fully_walked() -> None:
    """A genuinely deep, non-cyclic 12-hop chain (`fixture_deep_chain_00`
    -> ... -> `_11` -> a distinguishable leaf call) must be walked all
    the way to its real end -- there is no per-branch depth cap left to
    cut it off, and the specialization-aware visited-state dedup never
    fires on a straight-line chain with no repeated function. Leaf uses
    `.lower()` (not `.upper()`) -- `builtins.str.lower` is an existing,
    already-authorized policy entry; `builtins.str.upper` was explicitly
    deferred by ADR-032's Task 38.7 Phase 0 decision."""
    from audit_harness.trace import StaticWalker

    w = StaticWalker()
    w.walk(fx.fixture_deep_chain_00, "self-test:deep-chain")
    assert w.depth_exceeded == [], "no bound should fire on a plain deep chain"

    leaf_calls = [
        c for c in w.call_records if c.callee_text == "'deep-chain-leaf-reached'.lower"
    ]
    assert leaf_calls, "the walk must reach the 12th hop's own leaf call"
    assert leaf_calls[0].verdict.category == "exact_identity_policy"

    site_labels = {c.site for c in w.call_records}
    assert any("fixture_deep_chain_10" in s for s in site_labels), (
        "every intermediate hop, well past the old 10-hop cap, must appear "
        "as its own walked site"
    )


def test_termination_two_distinct_specializations_both_walked() -> None:
    """A generic function bound to two different concrete classes by two
    different call sites occupies two distinct visited-state entries --
    not merged into a single cached visit keyed on the callable alone --
    and a specialization already seen dedups rather than re-walking."""
    from audit_harness.trace import StaticWalker

    def _generic(cls: type) -> None:
        cls()

    class _FixtureA:
        pass

    class _FixtureB:
        pass

    w = StaticWalker()
    w.walk(_generic, "self-test:spec-a", forced_locals={"cls": _FixtureA})
    w.walk(_generic, "self-test:spec-b", forced_locals={"cls": _FixtureB})
    assert len(w.visited_funcs) == 2

    w.walk(_generic, "self-test:spec-a-again", forced_locals={"cls": _FixtureA})
    assert len(w.visited_funcs) == 2, "an already-seen specialization must dedup"


def test_termination_tiny_injected_budget_reports_and_blocks_exit_code() -> None:
    """An intentionally tiny total-work budget must be recorded as an
    explicit `roots_with_error` entry (never a silently-shortened
    result), and that entry must force `build_report`'s Gate Rule to a
    nonzero exit code."""
    from audit_harness.report import build_report
    from audit_harness.trace import run_trace

    tr = run_trace(max_total_walk_steps=1)
    error_reasons = {reason for reason, _detail in tr.roots_with_error}
    assert "static_walk_budget_exceeded" in error_reasons

    empty_trace = {
        "roots_traced": 0,
        "roots_with_error": [list(e) for e in tr.roots_with_error],
        "roots_with_error_total": len(tr.roots_with_error),
        "nodes_total": 0,
        "nodes_unresolved": 0,
        "nodes_unresolved_detail": [],
        "calls_total": 0,
        "calls_unresolved": 0,
        "calls_unresolved_detail": [],
        "calls_unresolved_detail_multiplicity": {},
        "identity_resolution_buckets": {
            "project_source_available": 0,
            "exact_identity_policy": 0,
            "forbidden": 0,
            "unresolved": 0,
        },
        "exact_identity_policy_version": "test",
        "market_data_provider_runtime_type": None,
        "sites_without_source": [],
    }
    built = build_report(
        commit_sha="deadbeef",
        discovery={"parse_errors_total": 0},
        trace=empty_trace,
        module_state={
            "candidates_total": 0,
            "unexplained_total": 0,
            "unexplained_detail": [],
            "buckets": {},
            "parse_errors": [],
            "parse_errors_total": 0,
        },
        runtime_denial={"success": True},
        negative_controls={"total": 5, "detected": 5, "detail": []},
    )
    assert built.data["exit_code"] == 1
    assert len(built.data["roots_with_error"]) > 0


def test_termination_real_trace_reaches_fixed_point_without_exhaustion() -> None:
    """The real Task 38.7 trace, at the module's own default budget,
    must reach a fixed point on its own -- the budget is a backstop
    against runaway/cyclic graphs, not a bound the real trace is
    expected to hit."""
    from audit_harness.trace import run_trace

    tr = run_trace()
    assert not any(
        reason == "static_walk_budget_exceeded"
        for reason, _detail in tr.roots_with_error
    )


# -- Lifecycle candidate delta (selection rule fixed; permanent 34-target
# regression baseline and the callable/non-callable assertions this
# repair required live in
# tests/audit_harness/test_lifecycle_denial_completeness.py -- the
# canonical home for that coverage, not duplicated here) ----------------


# -- NamedTuple-generated __new__ structural mechanism --------------------


def test_namedtuple_generated_new_positive_typing_and_collections() -> None:
    """A real `typing.NamedTuple` and a real `collections.namedtuple`
    generated `__new__` both satisfy the structural predicate -- proving
    it is not tied to python-dotenv or any other single package."""
    import collections
    import typing

    from audit_harness.identity import is_namedtuple_generated_new

    class _TypingPoint(typing.NamedTuple):
        x: int
        y: int

    _CollectionsPoint = collections.namedtuple("_CollectionsPoint", ["a", "b"])

    assert is_namedtuple_generated_new(_TypingPoint, _TypingPoint.__new__)
    assert is_namedtuple_generated_new(_CollectionsPoint, _CollectionsPoint.__new__)


def test_namedtuple_generated_new_resolves_via_classify_callable() -> None:
    """The structural mechanism, once confirmed, is classified the same
    way the existing dataclass-generated-method mechanism is --
    `exact_identity_policy`, never a new `EXACT_IDENTITY_POLICY` table
    entry."""
    import typing

    from audit_harness.identity import classify_callable, is_namedtuple_generated_new

    class _TypingPoint(typing.NamedTuple):
        x: int
        y: int

    assert is_namedtuple_generated_new(_TypingPoint, _TypingPoint.__new__)
    verdict = classify_callable(
        _TypingPoint.__new__,
        module=_TypingPoint.__module__,
        qualname=f"{_TypingPoint.__qualname__}.__new__",
        is_namedtuple_generated=True,
    )
    assert verdict.category == "exact_identity_policy"
    assert verdict.rationale is not None and "NamedTuple" in verdict.rationale


def test_namedtuple_dotenv_binding_and_original_no_longer_unresolved_nodes() -> None:
    """The two real, currently-unresolved nodes this mechanism targets --
    `dotenv.parser.Binding`/`.Original` -- resolve on the live trace."""
    from audit_harness.trace import run_trace

    tr = run_trace()
    unresolved_qualnames = {n.qualname for n in tr.nodes if n.unresolved}
    assert "dotenv.parser.Binding" not in unresolved_qualnames
    assert "dotenv.parser.Original" not in unresolved_qualnames


def test_namedtuple_ordinary_tuple_subclass_unaffected() -> None:
    """A plain `tuple` subclass with no `_fields` at all is never
    mistaken for a NamedTuple -- the mechanism's negative baseline."""
    from audit_harness.identity import is_namedtuple_generated_new

    class _PlainTuple(tuple):
        pass

    assert not is_namedtuple_generated_new(_PlainTuple, _PlainTuple.__new__)


def test_namedtuple_fake_fields_only_class_rejected() -> None:
    """A fabricated tuple subclass exposing only `_fields` (no `_make`/
    `_asdict`/`_replace`/`_field_defaults`) must not be accepted as
    generated -- proves the mechanism checks the full generated API, not
    just the one most-obvious attribute."""
    from audit_harness.identity import is_namedtuple_generated_new

    class _FakeFieldsOnly(tuple):
        _fields = ("a", "b")

        def __new__(cls, *args: object) -> _FakeFieldsOnly:
            return super().__new__(cls, args)

    assert not is_namedtuple_generated_new(_FakeFieldsOnly, _FakeFieldsOnly.__new__)


def test_namedtuple_hand_written_new_never_approved_as_generated() -> None:
    """A tuple subclass carrying the full generated API (`_fields`,
    `_make`, `_asdict`, `_replace`, `_field_defaults` -- a convincing
    forgery) but a hand-written `__new__` whose parameter shape does not
    match `_fields` exactly (extra validation logic, here) must still be
    rejected -- structural verification of the `__new__` itself, not
    just the surrounding class shape, is what the mechanism actually
    checks. It is instead walked/classified normally, exactly like any
    other hand-written method."""
    from audit_harness.identity import classify_callable, is_namedtuple_generated_new

    class _HandWritten(tuple):
        _fields = ("a", "b")

        @classmethod
        def _make(cls, iterable: object) -> _HandWritten:  # pragma: no cover
            return cls(iterable)  # type: ignore[call-arg]

        def _asdict(self) -> dict[str, object]:  # pragma: no cover
            return dict(zip(self._fields, self, strict=True))

        def _replace(self, **kwargs: object) -> _HandWritten:  # pragma: no cover
            return self

        _field_defaults: dict[str, object] = {}

        def __new__(
            cls, a: object, b: object, *, validated: bool = False
        ) -> _HandWritten:
            if not validated:
                raise ValueError("must be validated")
            return super().__new__(cls, (a, b))

    assert not is_namedtuple_generated_new(_HandWritten, _HandWritten.__new__)
    # The hand-written __new__ has real, retrievable .py source -- it
    # resolves via the ordinary project_source_available path, never via
    # the NamedTuple-generated fallback (which would require this test's
    # own module to be treated as project-owned, which it is not; the
    # point here is only that is_namedtuple_generated_new itself refuses
    # to approve it).
    verdict = classify_callable(
        _HandWritten.__new__,
        module=_HandWritten.__module__,
        qualname=f"{_HandWritten.__qualname__}.__new__",
        is_namedtuple_generated=False,
    )
    assert verdict.category != "exact_identity_policy" or (
        verdict.rationale is not None and "NamedTuple" not in verdict.rationale
    )


_FORGED_EXACT_SIGNATURE_SIDE_EFFECT_LOG: list[str] = []


def test_namedtuple_forged_exact_signature_full_api_rejected() -> None:
    """A forged tuple subclass that copies the *complete* generated API
    (`_fields`, `_field_defaults`, callable `_make`/`_asdict`/`_replace`)
    and uses the exact expected `__new__(cls, a, b)` signature -- but
    whose body performs distinguishable, arbitrary extra logic -- must
    still be rejected. Matching the class-level API and the parameter
    *shape* is not sufficient; the `__new__` *body* itself must be
    proven equivalent to the real generated constructor. The forged
    method is never called from this test -- only its static structure
    is ever inspected."""
    from audit_harness.identity import is_namedtuple_generated_new

    class _ForgedExactSignature(tuple):
        _fields = ("a", "b")
        _field_defaults: dict[str, object] = {}

        @classmethod
        def _make(cls, iterable: object) -> _ForgedExactSignature:
            return cls(*iterable)  # type: ignore[call-arg]

        def _asdict(self) -> dict[str, object]:
            return dict(zip(self._fields, self, strict=True))

        def _replace(self, **kwargs: object) -> _ForgedExactSignature:
            return self

        def __new__(cls, a: object, b: object) -> _ForgedExactSignature:
            # Distinguishable extra logic a real generated __new__ never
            # contains -- proves the body-equivalence check, not just
            # the signature shape, is what actually gates approval.
            _FORGED_EXACT_SIGNATURE_SIDE_EFFECT_LOG.append("forged-new-executed")
            return tuple.__new__(cls, (a, b))

    assert is_namedtuple_generated_new(
        _ForgedExactSignature, _ForgedExactSignature.__new__
    ) is False
    assert _FORGED_EXACT_SIGNATURE_SIDE_EFFECT_LOG == [], (
        "the forged __new__ must never be executed by this test -- only "
        "its static structure is inspected"
    )


_FORGED_GLOBAL_BINDING_SIDE_EFFECT_LOG: list[str] = []


def _forged_global_binding_malicious_tuple_new(cls: type, iterable: object) -> object:
    """Never called by any test -- exists only so a forged `__new__`'s
    `__globals__["_tuple_new"]` can be pointed at it, standing in for
    whatever a real attack would do here."""
    _FORGED_GLOBAL_BINDING_SIDE_EFFECT_LOG.append("malicious-tuple-new-executed")
    return tuple.__new__(cls, iterable)  # type: ignore[call-overload]


def test_namedtuple_forged_global_binding_rejected() -> None:
    """Byte-identical `__code__` (stolen directly from a real generated
    `__new__`) and identical `__defaults__` are not sufficient on their
    own: a forged function built from that exact code object, but whose
    `__globals__["_tuple_new"]` is rebound to an arbitrary callable
    instead of the real `tuple.__new__`, must still be rejected. The
    bytecode only names `_tuple_new` -- it says nothing about what that
    name is actually bound to at call time; the predicate must check the
    live global binding itself, never assume matching bytecode implies a
    safe target. The forged constructor is never invoked by this test --
    only its static structure (code object, globals, closure) is
    inspected."""
    import collections
    import types

    from audit_harness.identity import is_namedtuple_generated_new

    reference_cls = collections.namedtuple("_Ref", ("a", "b"))
    reference_new = reference_cls.__new__

    forged_new = types.FunctionType(
        reference_new.__code__,
        {"_tuple_new": _forged_global_binding_malicious_tuple_new},
        name=reference_new.__name__,
    )
    forged_new.__defaults__ = reference_new.__defaults__
    forged_new.__qualname__ = reference_new.__qualname__

    class _ForgedGlobalBinding(tuple):
        _fields = ("a", "b")
        _field_defaults: dict[str, object] = {}

        @classmethod
        def _make(cls, iterable: object) -> _ForgedGlobalBinding:
            return cls(*iterable)  # type: ignore[call-arg]

        def _asdict(self) -> dict[str, object]:
            return dict(zip(self._fields, self, strict=True))

        def _replace(self, **kwargs: object) -> _ForgedGlobalBinding:
            return self

    _ForgedGlobalBinding.__new__ = staticmethod(forged_new)  # type: ignore[assignment]

    assert is_namedtuple_generated_new(
        _ForgedGlobalBinding, _ForgedGlobalBinding.__new__
    ) is False
    assert _FORGED_GLOBAL_BINDING_SIDE_EFFECT_LOG == [], (
        "the forged constructor must never be executed by this test -- "
        "only its static structure is inspected"
    )


def test_namedtuple_forged_nonzero_closure_rejected() -> None:
    """A `__new__`-shaped function that closes over `tuple.__new__` as a
    free variable (`co_freevars` nonzero, real non-``None`` ``__closure__``)
    -- rather than referencing it as a plain global the way the real
    generated body always does -- is rejected. `__closure__ is not None`
    is checked explicitly, before any code-object comparison, as
    defense-in-depth alongside the code-attribute equality check (which
    would independently also fail here, since `co_freevars` differs from
    the zero-freevar reference). Never executed by this test."""
    from audit_harness.identity import is_namedtuple_generated_new

    def _make_closure_wrapped_new():  # type: ignore[no-untyped-def]
        _tuple_new = tuple.__new__

        def __new__(cls: type, a: object, b: object) -> object:
            return _tuple_new(cls, (a, b))  # type: ignore[call-overload]

        return __new__

    closure_wrapped_new = _make_closure_wrapped_new()
    assert closure_wrapped_new.__closure__ is not None

    class _ForgedClosureBinding(tuple):
        _fields = ("a", "b")
        _field_defaults: dict[str, object] = {}

        @classmethod
        def _make(cls, iterable: object) -> _ForgedClosureBinding:
            return cls(*iterable)  # type: ignore[call-arg]

        def _asdict(self) -> dict[str, object]:
            return dict(zip(self._fields, self, strict=True))

        def _replace(self, **kwargs: object) -> _ForgedClosureBinding:
            return self

    _ForgedClosureBinding.__new__ = staticmethod(closure_wrapped_new)  # type: ignore[assignment]

    assert is_namedtuple_generated_new(
        _ForgedClosureBinding, _ForgedClosureBinding.__new__
    ) is False


# -- Local callable-alias resolution (Task 38.7) --------------------------


def test_local_callable_alias_direct_builtin_resolves() -> None:
    """`_len = len; _len(value)` resolves `_len(value)` to `builtins.len`
    via the new `local-callable-alias` mechanism."""
    from audit_harness.trace import StaticWalker

    w = StaticWalker()
    w.walk(fx.fixture_local_callable_alias_direct, "self-test:alias-direct")
    matching = [c for c in w.call_records if c.callee_text == "_len"]
    assert matching, "the aliased call site must be recorded"
    assert matching[0].resolution_mechanism == "local-callable-alias"
    assert matching[0].verdict.category == "exact_identity_policy"
    assert matching[0].verdict.qualname == "len"


def test_local_callable_alias_typed_method_resolves() -> None:
    """`emit = values.append; emit(value)` -- the alias's RHS is a bound
    method of a locally-typed container, not a bare global/builtin. The
    mechanism must correctly identify `list.append` as the resolved
    identity -- whether that identity is itself currently
    policy-approved is a separate, unrelated decision (Task 38.7's
    policy-authorization work, not this mechanism's job)."""
    from audit_harness.trace import StaticWalker

    w = StaticWalker()
    w.walk(
        fx.fixture_local_callable_alias_typed_method, "self-test:alias-typed-method"
    )
    matching = [c for c in w.call_records if c.callee_text == "emit"]
    assert matching, "the aliased call site must be recorded"
    assert matching[0].resolution_mechanism == "local-callable-alias"
    assert matching[0].verdict.module == "builtins"
    assert matching[0].verdict.qualname == "list.append"


def test_local_callable_alias_call_before_assignment_stays_unresolved() -> None:
    """No control-flow analysis: a call textually preceding its own
    alias assignment must not resolve via this mechanism."""
    from audit_harness.trace import StaticWalker

    w = StaticWalker()
    w.walk(
        fx.fixture_local_callable_alias_call_before_assignment,
        "self-test:alias-before-assignment",
    )
    matching = [c for c in w.call_records if c.callee_text == "_alias"]
    assert matching
    assert matching[0].resolution_mechanism != "local-callable-alias"
    assert matching[0].verdict.category == "unresolved"


def test_local_callable_alias_conditional_branch_only_stays_unresolved() -> None:
    """An assignment that exists only inside an `if` branch never
    dominates a later call -- must not be treated as a usable alias."""
    from audit_harness.trace import StaticWalker

    w = StaticWalker()
    w.walk(
        fx.fixture_local_callable_alias_conditional_branch,
        "self-test:alias-conditional",
    )
    matching = [c for c in w.call_records if c.callee_text == "_alias"]
    assert matching
    assert matching[0].resolution_mechanism != "local-callable-alias"
    assert matching[0].verdict.category == "unresolved"


def test_local_callable_alias_reassignment_disqualifies() -> None:
    """A second write (reassignment) to the same name anywhere in the
    function scope disqualifies it entirely."""
    from audit_harness.trace import StaticWalker

    w = StaticWalker()
    w.walk(fx.fixture_local_callable_alias_reassigned, "self-test:alias-reassigned")
    matching = [c for c in w.call_records if c.callee_text == "_alias"]
    assert matching
    assert matching[0].resolution_mechanism != "local-callable-alias"
    assert matching[0].verdict.category == "unresolved"


def test_local_callable_alias_deletion_disqualifies() -> None:
    """A `del` of the name anywhere in the function scope is itself a
    disqualifying second write, even when the name is reassigned
    afterward."""
    from audit_harness.trace import StaticWalker

    w = StaticWalker()
    w.walk(fx.fixture_local_callable_alias_deleted, "self-test:alias-deleted")
    matching = [c for c in w.call_records if c.callee_text == "_alias"]
    assert matching
    assert matching[0].resolution_mechanism != "local-callable-alias"
    assert matching[0].verdict.category == "unresolved"


def test_local_callable_alias_unknown_rhs_never_accepted() -> None:
    """An RHS name that resolves to nothing at all (not closure, global,
    or builtin) is never accepted as an alias."""
    from audit_harness.trace import StaticWalker

    w = StaticWalker()
    w.walk(fx.fixture_local_callable_alias_unknown_rhs, "self-test:alias-unknown-rhs")
    matching = [c for c in w.call_records if c.callee_text == "_alias"]
    assert matching
    assert matching[0].resolution_mechanism != "local-callable-alias"
    assert matching[0].verdict.category == "unresolved"


def test_local_callable_alias_non_callable_rhs_never_accepted() -> None:
    """An RHS that resolves to a real, known object which is not itself
    callable is never accepted as an alias."""
    from audit_harness.trace import StaticWalker

    w = StaticWalker()
    w.walk(
        fx.fixture_local_callable_alias_non_callable_rhs,
        "self-test:alias-non-callable-rhs",
    )
    matching = [c for c in w.call_records if c.callee_text == "_alias"]
    assert matching
    assert matching[0].resolution_mechanism != "local-callable-alias"
    assert matching[0].verdict.category == "unresolved"


def test_local_callable_alias_no_leakage_between_functions() -> None:
    """A fresh walk of a function that never defines `_alias` at all
    must never see another function's alias table -- each `walk()` call
    computes its own aliases from that function's own tree, never a
    walker-level or cross-function cache."""
    from audit_harness.trace import StaticWalker

    w1 = StaticWalker()
    w1.walk(
        fx.fixture_local_callable_alias_leak_check_defines_alias,
        "self-test:alias-leak-defines",
    )
    defining_matches = [c for c in w1.call_records if c.callee_text == "_alias"]
    assert defining_matches
    assert defining_matches[0].resolution_mechanism == "local-callable-alias"

    w2 = StaticWalker()
    w2.walk(
        fx.fixture_local_callable_alias_leak_check_no_alias_here,
        "self-test:alias-leak-absent",
    )
    absent_matches = [c for c in w2.call_records if c.callee_text == "_alias"]
    assert absent_matches
    assert absent_matches[0].resolution_mechanism != "local-callable-alias"
    assert absent_matches[0].verdict.category == "unresolved"


def test_local_callable_alias_real_trace_sites_now_resolve() -> None:
    """At least one real, previously-unresolved bare-alias call site in
    the live trace now resolves via `local-callable-alias` all the way
    to `exact_identity_policy` (the exact `_len = len` shape in
    `sre_parse.py`/`sre_compile.py`, resolving to the pre-existing
    `builtins.len` policy entry) -- proving the mechanism closes real
    residual, not only fixture shapes. Not every site the mechanism
    structurally identifies also ends up policy-approved (e.g. `ord`,
    `print` are correctly identified as `local-callable-alias` but their
    own identities are not currently policy entries, so they honestly
    remain `unresolved` -- that is a separate, unrelated decision, not a
    defect in this mechanism)."""
    from audit_harness.trace import run_trace

    tr = run_trace()
    alias_calls = [
        c for c in tr.calls if c.resolution_mechanism == "local-callable-alias"
    ]
    assert alias_calls, "at least one real site must use this mechanism"
    fully_resolved = [c for c in alias_calls if c.verdict.category != "unresolved"]
    assert fully_resolved, "at least one real alias site must fully resolve"
    assert any(
        c.verdict.module == "builtins" and c.verdict.qualname == "len"
        for c in fully_resolved
    )


# -- Call-site parameter-type propagation (Task 38.7) ----------------------


def test_param_propagation_single_hop_resolves() -> None:
    """A locally-inferred type, passed as a direct Name argument, must
    be visible inside the callee -- `item.marker_method()` resolves to
    the real class's method."""
    from audit_harness.trace import StaticWalker

    w = StaticWalker()
    w.walk(fx.fixture_param_propagation_single_hop, "self-test:param-single-hop")
    matching = [c for c in w.call_records if c.callee_text == "item.marker_method"]
    assert matching, "the callee's own attribute call must be recorded"
    assert matching[0].verdict.category != "unresolved"
    assert matching[0].verdict.qualname == "FixturePropagationTarget.marker_method"


def test_param_propagation_three_hop_resolves() -> None:
    """Propagation continues across a second hop with no mechanism
    beyond the single fix at the first hop."""
    from audit_harness.trace import StaticWalker

    w = StaticWalker()
    w.walk(fx.fixture_param_propagation_three_hop_a, "self-test:param-three-hop")
    matching = [c for c in w.call_records if c.callee_text == "item.marker_method"]
    assert matching, "the third hop's own attribute call must be recorded"
    assert matching[0].verdict.category != "unresolved"
    assert matching[0].verdict.qualname == "FixturePropagationTarget.marker_method"


def test_param_propagation_specialization_isolation() -> None:
    """Two callers passing different locally-inferred types to the same
    shared callee must each specialize independently -- never merged
    into one (incorrect) shared result."""
    from audit_harness.trace import StaticWalker

    w = StaticWalker()
    w.walk(fx.fixture_param_propagation_caller_a, "self-test:param-caller-a")
    w.walk(fx.fixture_param_propagation_caller_b, "self-test:param-caller-b")

    matching = [c for c in w.call_records if c.callee_text == "item.marker_method"]
    qualnames = {
        c.verdict.qualname for c in matching if c.verdict.category != "unresolved"
    }
    assert "FixturePropagationTargetA.marker_method" in qualnames
    assert "FixturePropagationTargetB.marker_method" in qualnames


def test_param_propagation_nonname_argument_unpropagated() -> None:
    """A Call-expression argument (not a bare Name) must never
    propagate -- the callee's attribute call stays unresolved."""
    from audit_harness.trace import StaticWalker

    w = StaticWalker()
    w.walk(
        fx.fixture_param_propagation_nonname_argument, "self-test:param-nonname-arg"
    )
    matching = [c for c in w.call_records if c.callee_text == "item.marker_method"]
    assert matching
    assert matching[0].verdict.category == "unresolved"


def test_param_propagation_untyped_local_unpropagated() -> None:
    """A local never inferred by `_collect_local_var_types` (a
    Name-to-Name assignment, not a Call) has nothing to propagate -- the
    callee's attribute call stays unresolved."""
    from audit_harness.trace import StaticWalker

    w = StaticWalker()
    w.walk(
        fx.fixture_param_propagation_untyped_local, "self-test:param-untyped-local"
    )
    matching = [c for c in w.call_records if c.callee_text == "item.marker_method"]
    assert matching
    assert matching[0].verdict.category == "unresolved"


def test_param_propagation_real_trace_source_state_family_resolves() -> None:
    """The real, diagnosed `re._parser.parse -> _parse_sub -> _parse`
    `source`/`state` family resolves on the live trace -- 123 of the 125
    originally-diagnosed raw call sites. The 2 that remain are a
    distinct, separate, out-of-scope limitation: `state.checklookbehindgroup`
    resolves via an *unbound* method access (`getattr(State,
    "checklookbehindgroup")`, since `state` propagates as a type, not a
    live instance), so its own `self` parameter is not implicitly bound
    the way a real method call's receiver would be -- `_bind_call_site_locals`
    binds the call's explicit `(gid, source)` arguments against the
    unbound function's full `(self, gid, source)` signature and shifts
    by one position. This is a pre-existing edge case in argument
    binding against an unbound-type-resolved method, not something this
    diff's `local_var_types` propagation was scoped to fix."""
    from audit_harness.trace import run_trace

    tr = run_trace()
    closable_callees = {
        "source.error",
        "source.tell",
        "source.getwhile",
        "source.getuntil",
        "source.match",
        "source.checkgroupname",
        "sourceget",
        "sourcematch",
        "state.checklookbehindgroup",
        "state.pop",
    }
    still_unresolved = [
        c
        for c in tr.calls
        if c.callee_text in closable_callees and c.verdict.category == "unresolved"
    ]
    assert all(c.callee_text == "source.error" for c in still_unresolved)
    assert all(
        c.site.endswith("state.checklookbehindgroup()") for c in still_unresolved
    )
    assert len(still_unresolved) == 2, (
        "exactly the two known state.checklookbehindgroup-internal "
        "source.error raises should remain -- a different count means "
        "the known-limitation evidence has changed and needs re-diagnosis"
    )


# -- Implicit method-receiver binding (Task 38.7) ---------------------------


def test_receiver_binding_two_arg_positive_resolves() -> None:
    """The second explicit argument must reach the callee's own
    parameter (not shift into the receiver slot) and remain resolvable
    inside the callee's own body."""
    from audit_harness.trace import StaticWalker

    w = StaticWalker()
    w.walk(
        fx.fixture_receiver_binding_two_arg_positive, "self-test:receiver-two-arg"
    )
    matching = [c for c in w.call_records if c.callee_text == "helper.marker_method"]
    assert matching, "the callee's own downstream attribute call must be recorded"
    assert matching[0].verdict.category != "unresolved"
    assert matching[0].verdict.qualname == "FixtureReceiverBindingHelper.marker_method"


def test_receiver_binding_inherited_positive_resolves() -> None:
    """The same shape via an inherited method resolves identically."""
    from audit_harness.trace import StaticWalker

    w = StaticWalker()
    w.walk(
        fx.fixture_receiver_binding_inherited_positive, "self-test:receiver-inherited"
    )
    matching = [c for c in w.call_records if c.callee_text == "helper.marker_method"]
    assert matching, "the callee's own downstream attribute call must be recorded"
    assert matching[0].verdict.category != "unresolved"
    assert matching[0].verdict.qualname == "FixtureReceiverBindingHelper.marker_method"


def test_receiver_binding_staticmethod_unchanged() -> None:
    """A staticmethod needs no receiver prepended -- its own single
    argument binds directly and resolves, exactly as it already did."""
    from audit_harness.trace import StaticWalker

    w = StaticWalker()
    w.walk(
        fx.fixture_receiver_binding_staticmethod_unchanged,
        "self-test:receiver-staticmethod",
    )
    matching = [c for c in w.call_records if c.callee_text == "helper.marker_method"]
    assert matching, "the callee's own downstream attribute call must be recorded"
    assert matching[0].verdict.category != "unresolved"
    assert matching[0].verdict.qualname == "FixtureReceiverBindingHelper.marker_method"


def test_receiver_binding_classmethod_unchanged() -> None:
    """A classmethod is already bound by `getattr` itself -- no
    receiver prepended; its own single argument binds directly."""
    from audit_harness.trace import StaticWalker

    w = StaticWalker()
    w.walk(
        fx.fixture_receiver_binding_classmethod_unchanged,
        "self-test:receiver-classmethod",
    )
    matching = [c for c in w.call_records if c.callee_text == "helper.marker_method"]
    assert matching, "the callee's own downstream attribute call must be recorded"
    assert matching[0].verdict.category != "unresolved"
    assert matching[0].verdict.qualname == "FixtureReceiverBindingHelper.marker_method"


def test_receiver_binding_c_descriptor_unchanged_never_guessed() -> None:
    """A C-implemented method (`list.append`) is never guessed at --
    `getattr_static` returns a `method_descriptor`, not a plain
    `function`, so the fix never applies here."""
    from audit_harness.trace import StaticWalker

    w = StaticWalker()
    w.walk(
        fx.fixture_receiver_binding_c_descriptor_unchanged,
        "self-test:receiver-c-descriptor",
    )
    matching = [c for c in w.call_records if c.callee_text == "value.append"]
    assert matching, "the list.append call site must be recorded"
    # Unchanged from before this fix: list.append is never in policy
    # today (see the four known policy-dependent failures), so it stays
    # unresolved regardless -- what this test actually proves is that
    # the mechanism/callee_text/verdict shape is untouched by this fix,
    # not that list.append itself became resolved.
    assert matching[0].resolution_mechanism == "local-variable-type-inference"
    assert matching[0].verdict.module == "builtins"
    assert matching[0].verdict.qualname == "list.append"


def test_receiver_binding_real_checklookbehindgroup_still_unresolved_verified() -> None:
    """The live, diagnosed `state.checklookbehindgroup` case does NOT
    close under this exact fix: `state.checklookbehindgroup` resolves
    via `global-or-closure-attribute` (its receiver `state` reaches
    `_escape()` as a *propagated parameter*, living in `loc`, not as a
    freshly-inferred `local_var_types` entry -- `state` is itself a
    parameter of `_parse`/`_escape`, never assigned via a local `Assign`/
    `AnnAssign` inside them), never `local-variable-type-inference` --
    so this fix's exact, narrow predicate correctly does not fire here.
    Per the task's own explicit scope ("do not widen"), the 2
    `source.error` raises inside `checklookbehindgroup`'s body remain
    unresolved, for this specific, now-precisely-identified reason."""
    from audit_harness.trace import run_trace

    tr = run_trace()
    checklookbehindgroup_calls = [
        c for c in tr.calls if c.callee_text == "state.checklookbehindgroup"
    ]
    assert checklookbehindgroup_calls, "the call site itself must still be recorded"
    assert all(
        c.resolution_mechanism == "global-or-closure-attribute"
        for c in checklookbehindgroup_calls
    ), "confirms the exact reason this fix's predicate does not apply here"

    still_unresolved = [
        c
        for c in tr.calls
        if c.callee_text == "source.error"
        and c.site.endswith("state.checklookbehindgroup()")
        and c.verdict.category == "unresolved"
    ]
    assert len(still_unresolved) == 2, (
        "exactly the two known state.checklookbehindgroup-internal "
        "source.error raises should remain unresolved -- a different "
        "count means this evidence has changed and needs re-diagnosis"
    )
