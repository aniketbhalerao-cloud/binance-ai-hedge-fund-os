"""Task 38.8 Phase A.1: post-remediation tests for the mechanized
context-manager/descriptor implicit-dispatch detection ADR-032 Option D
selected (2026-08-24), scoped to exactly these two of the eleven
protocol families `docs/prompts/task-38.8.md` §2 names:

* context managers -- ``__enter__``/``__exit__``/``__aenter__``/``__aexit__``
* descriptors -- ``__get__``/``__set__``/``__delete__``

These tests prove the mechanism, not merely that it changed something:
every assertion below keys on ``verdict.category``/``module``/
``qualname`` (never a path/name substring), per §3's detection-
assertion discipline -- the same discipline
``test_task_38_8_characterization.py`` already holds itself to, reused
here rather than re-derived.

``tests/audit_harness/fixtures/implicit_dispatch.py`` (Phase A.0) is
frozen and unmodified; this file only imports it and
``tests/audit_harness/fixtures/implicit_dispatch_phase_a1.py`` (a few
Phase A.1-only additions covering shapes A.0 deliberately did not
need -- see that module's own docstring).
"""

from __future__ import annotations

from audit_harness.identity import module_and_qualname
from audit_harness.trace import CallRecord, StaticWalker
from tests.audit_harness.fixtures import implicit_dispatch as fx
from tests.audit_harness.fixtures import implicit_dispatch_phase_a1 as fx_a1
from tests.audit_harness.test_task_38_8_characterization import (
    _OPEN_MODULE,
    _OPEN_QUALNAME,
)


def _forbidden_open_records(records: list[CallRecord]) -> list[CallRecord]:
    return [
        r
        for r in records
        if r.verdict.module == _OPEN_MODULE and r.verdict.qualname == _OPEN_QUALNAME
    ]


def _walk(trigger: object, site_label: str) -> StaticWalker:
    walker = StaticWalker()
    walker.walk(trigger, site_label)
    return walker


# ---------------------------------------------------------------------
# 1. All four context-manager events are detected independently
# ---------------------------------------------------------------------


def test_sync_enter_now_detected() -> None:
    w = _walk(fx.trigger_with_statement_enter_only, "phase-a1:cm:sync-enter")
    found = _forbidden_open_records(w.call_records)
    assert found, "the embedded sentinel in __enter__ must now be discovered"
    assert all(r.resolution_mechanism == "builtins-lookup" for r in found)


def test_sync_exit_now_detected() -> None:
    w = _walk(fx.trigger_with_statement, "phase-a1:cm:sync-exit")
    found = _forbidden_open_records(w.call_records)
    assert found, "the embedded sentinel in __exit__ must now be discovered"


def test_async_aenter_now_detected() -> None:
    w = _walk(
        fx.trigger_async_with_statement_enter_only, "phase-a1:cm:async-aenter"
    )
    found = _forbidden_open_records(w.call_records)
    assert found, "the embedded sentinel in __aenter__ must now be discovered"


def test_async_aexit_now_detected() -> None:
    w = _walk(fx.trigger_async_with_statement, "phase-a1:cm:async-aexit")
    found = _forbidden_open_records(w.call_records)
    assert found, "the embedded sentinel in __aexit__ must now be discovered"


# ---------------------------------------------------------------------
# 2. All three descriptor events are detected independently
# ---------------------------------------------------------------------


def test_descriptor_get_now_detected() -> None:
    w = _walk(fx.trigger_descriptor_get, "phase-a1:descriptor:raw-get")
    assert _forbidden_open_records(w.call_records)


def test_descriptor_set_now_detected() -> None:
    w = _walk(fx.trigger_descriptor_set, "phase-a1:descriptor:raw-set")
    assert _forbidden_open_records(w.call_records)


def test_descriptor_delete_now_detected() -> None:
    w = _walk(fx.trigger_descriptor_delete, "phase-a1:descriptor:raw-delete")
    assert _forbidden_open_records(w.call_records)


def test_property_get_now_detected_as_sharpest_instance() -> None:
    """M-8's own "sharpest instance": a bare ``ast.Attribute`` read with
    zero ``ast.Call`` node of any kind, via a ``@property`` getter --
    correctly unwrapped to its own ``fget``, not left pointing at
    ``property.__get__`` (a C slot that would never reveal the embedded
    sentinel at all)."""
    w = _walk(fx.trigger_property_get, "phase-a1:descriptor:property-get")
    found = _forbidden_open_records(w.call_records)
    assert found, (
        "the property getter's own fget body must be walked, not the "
        "property object's own C-level __get__ slot"
    )


# ---------------------------------------------------------------------
# 3. Sync and async remain distinct -- never conflated
# ---------------------------------------------------------------------


def test_sync_and_async_context_manager_dunders_are_not_conflated() -> None:
    sync = _walk(fx.trigger_with_statement_enter_only, "phase-a1:cm:distinct-sync")
    aio = _walk(
        fx.trigger_async_with_statement_enter_only, "phase-a1:cm:distinct-async"
    )
    sync_mechanisms = {r.resolution_mechanism for r in sync.call_records}
    async_mechanisms = {r.resolution_mechanism for r in aio.call_records}
    assert "implicit-context-manager-__enter__" in sync_mechanisms
    assert "implicit-context-manager-__enter__" not in async_mechanisms
    assert "implicit-context-manager-__aenter__" in async_mechanisms
    assert "implicit-context-manager-__aenter__" not in sync_mechanisms


# ---------------------------------------------------------------------
# 4. A clean partner method never masks a forbidden one, and vice versa
# ---------------------------------------------------------------------


def test_clean_exit_does_not_mask_forbidden_enter() -> None:
    """``ForbiddenEnterOnly`` carries the sentinel only in ``__enter__``'s
    own body; ``__exit__`` is clean. The dispatch record for the method
    *itself* is ``project_source_available`` either way (the sentinel
    lives one hop deeper, in the recursively-walked body, per the
    outer-call/nested-dispatch distinction §1 draws) -- what must never
    happen is the forbidden sentinel discovered via ``__enter__``'s own
    recursion being confused with, or suppressed by, ``__exit__``'s
    clean one. One walk of one trigger must independently report both
    events, and the forbidden nested call must be attributable to
    ``__enter__``'s own site specifically."""
    w = _walk(
        fx.trigger_with_statement_enter_only, "phase-a1:cm:no-masking-enter"
    )
    enter_records = [
        r for r in w.call_records if r.callee_text == "obj.__enter__"
    ]
    exit_records = [r for r in w.call_records if r.callee_text == "obj.__exit__"]
    assert len(enter_records) == 1, "exactly one __enter__ dispatch record"
    assert len(exit_records) == 1, "exactly one __exit__ dispatch record"

    forbidden = _forbidden_open_records(w.call_records)
    assert forbidden, "the sentinel inside __enter__'s body must be discovered"
    assert all(r.site.endswith("obj.__enter__()") for r in forbidden), (
        "the forbidden sentinel must be attributed to __enter__'s own "
        "recursion, never to the clean __exit__ branch"
    )


def test_clean_enter_does_not_mask_forbidden_exit() -> None:
    """The mirror case: ``ForbiddenExitOnly`` carries the sentinel only
    in ``__exit__``'s own body."""
    w = _walk(fx.trigger_with_statement, "phase-a1:cm:no-masking-exit")
    enter_records = [
        r for r in w.call_records if r.callee_text == "obj.__enter__"
    ]
    exit_records = [r for r in w.call_records if r.callee_text == "obj.__exit__"]
    assert len(enter_records) == 1
    assert len(exit_records) == 1

    forbidden = _forbidden_open_records(w.call_records)
    assert forbidden, "the sentinel inside __exit__'s body must be discovered"
    assert all(r.site.endswith("obj.__exit__()") for r in forbidden), (
        "the forbidden sentinel must be attributed to __exit__'s own "
        "recursion, never to the clean __enter__ branch"
    )


# ---------------------------------------------------------------------
# 5. Source/identity correctness, and no duplicate CallRecords
# ---------------------------------------------------------------------


def test_identity_is_exact_not_a_substring_match() -> None:
    w = _walk(fx.trigger_descriptor_set, "phase-a1:identity-exactness")
    found = _forbidden_open_records(w.call_records)
    assert len(found) == 1
    record = found[0]
    assert record.verdict.module == _OPEN_MODULE
    assert record.verdict.qualname == _OPEN_QUALNAME
    assert record.verdict.category == "forbidden"
    assert record.site == "phase-a1:identity-exactness -> obj.attr [__set__]"
    assert record.callee_text == "open"


def test_no_duplicate_call_records_for_one_dispatch_event() -> None:
    w = _walk(fx.trigger_with_statement, "phase-a1:no-duplicates")
    matching = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-context-manager-__exit__"
    ]
    assert len(matching) == 1, (
        "one with-item must produce exactly one __exit__ dispatch "
        f"CallRecord, not {len(matching)}"
    )


# ---------------------------------------------------------------------
# 6. Fail-closed: an unresolved receiver never defaults to safe
# ---------------------------------------------------------------------


def test_context_manager_unresolved_receiver_is_explicit_not_silent() -> None:
    w = _walk(
        fx_a1.trigger_context_manager_unresolved_receiver,
        "phase-a1:cm:unresolved-receiver",
    )
    unresolved = [
        r
        for r in w.call_records
        if r.resolution_mechanism.startswith("implicit-context-manager-")
        and r.verdict.category == "unresolved"
    ]
    dunders = {r.resolution_mechanism for r in unresolved}
    assert dunders == {
        "implicit-context-manager-__enter__",
        "implicit-context-manager-__exit__",
    }, "both events of an unresolvable receiver must be explicitly unresolved"


def test_descriptor_unresolved_receiver_is_explicit_not_silent() -> None:
    w = _walk(
        fx_a1.trigger_descriptor_get_unresolved_receiver,
        "phase-a1:descriptor:unresolved-receiver",
    )
    unresolved = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-descriptor-__get__"
        and r.verdict.category == "unresolved"
    ]
    assert unresolved, (
        "an unresolvable descriptor receiver must produce an explicit "
        "unresolved record, never a silent skip"
    )


# ---------------------------------------------------------------------
# 7. Ordinary explicit-call behaviour is unchanged
# ---------------------------------------------------------------------


def test_inline_constructor_call_still_resolves_explicitly() -> None:
    """``with CleanContextManager(): pass`` -- the constructor call is a
    distinct, already-discovered ``ast.Call`` the existing call-handling
    path resolves exactly as before; the two new dispatch events sit
    alongside it, not in place of it."""
    w = _walk(
        fx_a1.trigger_with_inline_construction, "phase-a1:explicit-call-preserved"
    )
    module, qualname = module_and_qualname(fx_a1.CleanContextManager)
    ctor_records = [
        r
        for r in w.call_records
        if r.resolution_mechanism not in (
            "implicit-context-manager-__enter__",
            "implicit-context-manager-__exit__",
        )
        and r.callee_text == "CleanContextManager"
    ]
    assert ctor_records, "the constructor call must still be recorded explicitly"

    enter_records = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-context-manager-__enter__"
    ]
    exit_records = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-context-manager-__exit__"
    ]
    assert len(enter_records) == 1
    assert len(exit_records) == 1
    assert enter_records[0].verdict.module == module
    assert enter_records[0].verdict.qualname == f"{qualname}.__enter__"


def test_ordinary_method_call_attribute_lookup_is_now_independently_modeled() -> None:
    """Semantic-correctness correction (item 5): a normal ``obj.method()``
    explicit call is still resolved by the existing, separately-tested
    call-handling path -- but the attribute *load* half of that same
    syntax (``obj.method``, before the call) is itself a non-data-
    descriptor Load, and the previous version of this test asserted the
    opposite (a stale exclusion this same patch pass removed as a real
    blind spot -- see ``walk()``'s own updated skip-set comment). The
    descriptor record is additive, independent, and never replaces or
    duplicates the outer call's own record."""
    w = _walk(fx.trigger_hash_set_add, "phase-a1:explicit-method-call-unaffected")
    descriptor_records = [
        r
        for r in w.call_records
        if r.resolution_mechanism.startswith("implicit-descriptor-")
    ]
    assert len(descriptor_records) == 1, (
        "the attribute-load half of receiver.add(...) must now be "
        "modeled as its own descriptor-dispatch candidate"
    )
    assert descriptor_records[0].verdict.category == "unresolved"

    outer_call_records = [
        r
        for r in w.call_records
        if not r.resolution_mechanism.startswith("implicit-")
        and r.callee_text == "receiver.add"
    ]
    assert len(outer_call_records) == 1, (
        "the outer explicit .add(...) call must still be recorded "
        "exactly once, unaffected by the new descriptor record"
    )


# ---------------------------------------------------------------------
# 8. The remaining nine families stay unsupported (unaffected)
# ---------------------------------------------------------------------


def test_unsupported_families_remain_unsupported_after_mechanism_added() -> None:
    """A cross-section of the 9 families this Phase A.1 decision does
    not mechanize (iteration, hashing, formatting) must still produce
    zero forbidden CallRecords -- proving the new context-manager/
    descriptor code paths did not accidentally widen detection beyond
    ADR-032's own named 2-of-11 scope."""
    still_uncovered = (
        (fx.trigger_for_loop_iter_only, "phase-a1:still-unsupported:iteration"),
        (fx.trigger_hash_set_literal, "phase-a1:still-unsupported:hashing"),
        (fx.trigger_fstring_format, "phase-a1:still-unsupported:formatting"),
        (fx.trigger_equality, "phase-a1:still-unsupported:operator"),
        (fx.trigger_subscript_get, "phase-a1:still-unsupported:subscription"),
    )
    for trigger, site_label in still_uncovered:
        w = _walk(trigger, site_label)
        assert not _forbidden_open_records(w.call_records), (
            f"{site_label}: an unmechanized family must still report zero "
            "forbidden CallRecords for its embedded sentinel"
        )


# =======================================================================
# Correction pass: non-execution safety, corrected descriptor semantics,
# augmented assignment, and multi-item context managers.
# =======================================================================


# ---------------------------------------------------------------------
# 9. Non-execution safety (item 3): resolving a candidate must never
# itself invoke a descriptor's __get__/__set__/__delete__ or a
# metaclass hook. Each hostile fixture raises the instant its own
# dunder is actually called -- a passing test (no exception propagates)
# is direct, mechanical proof, not an assertion about intent.
# ---------------------------------------------------------------------


def test_resolving_instance_get_never_invokes_the_descriptor() -> None:
    w = _walk(fx_a1.trigger_hostile_instance_get, "phase-a1:hostile:instance-get")
    assert _forbidden_open_records(w.call_records), (
        "the sentinel must still be found via static source parsing"
    )


def test_resolving_instance_set_never_invokes_the_descriptor() -> None:
    w = _walk(fx_a1.trigger_hostile_instance_set, "phase-a1:hostile:instance-set")
    assert _forbidden_open_records(w.call_records)


def test_resolving_instance_delete_never_invokes_the_descriptor() -> None:
    w = _walk(
        fx_a1.trigger_hostile_instance_delete, "phase-a1:hostile:instance-delete"
    )
    assert _forbidden_open_records(w.call_records)


def test_resolving_class_level_attribute_never_invokes_the_descriptor() -> None:
    """`HostileClassLevelHost.attr` -- the class-receiver resolution
    path (item 4) is exercised here too, and must be exactly as
    non-executing as the instance path above."""
    w = _walk(
        fx_a1.trigger_hostile_class_level_get, "phase-a1:hostile:class-level-get"
    )
    assert _forbidden_open_records(w.call_records)


# ---------------------------------------------------------------------
# 10. Corrected descriptor semantics (item 4)
# ---------------------------------------------------------------------


def test_class_level_metaclass_data_descriptor_is_detected() -> None:
    """`C.attr` must never be silently excluded merely because the
    receiver is a class -- a metaclass-level *data* descriptor takes
    priority, exactly matching `type.__getattribute__`'s own algorithm."""
    w = _walk(
        fx_a1.trigger_class_level_metaclass_descriptor_get,
        "phase-a1:class-level:metaclass-priority",
    )
    found = _forbidden_open_records(w.call_records)
    assert found, "a metaclass-level data descriptor's __get__ must be detected"


def test_class_level_own_mro_descriptor_is_detected() -> None:
    """A descriptor assigned directly in the class body, accessed via
    the class itself (no instance) -- the class's own MRO path, not the
    metaclass path."""
    w = _walk(
        fx_a1.trigger_class_level_own_mro_descriptor_get,
        "phase-a1:class-level:own-mro",
    )
    assert _forbidden_open_records(w.call_records)


def test_non_data_descriptor_on_instance_load_is_ambiguous_not_safe() -> None:
    """A non-data descriptor (only ``__get__``) found via an instance
    receiver's class -- an instance's own ``__dict__`` could shadow it,
    which cannot be proven absent statically. Must be reported
    ``unresolved`` (never a default-safe verdict), keyed on the
    resolution mechanism and category alone -- this fixture's own body
    is deliberately clean, so any resolved-safe verdict here would be a
    real fail-closed violation, not merely an incomplete detection."""
    w = _walk(
        fx_a1.trigger_clean_non_data_descriptor_get,
        "phase-a1:descriptor:non-data-ambiguous",
    )
    matching = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-descriptor-__get__"
    ]
    assert len(matching) == 1
    assert matching[0].verdict.category == "unresolved"
    assert "instance's own __dict__" in (matching[0].verdict.rationale or "")


def test_property_missing_fset_still_reaches_a_dispatch_target() -> None:
    """A ``@property`` with no ``.setter`` -- assignment still reaches
    ``property``'s own ``__set__`` slot (which unconditionally raises),
    never silently treated as "no dispatch occurs" (item 4)."""
    w = _walk(
        fx_a1.trigger_readonly_property_set, "phase-a1:descriptor:property-no-fset"
    )
    matching = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-descriptor-__set__"
    ]
    assert len(matching) == 1
    assert matching[0].verdict.module == "builtins"
    assert matching[0].verdict.qualname == "property.__set__"
    # An irreducible C slot: correctly unresolved, never claimed safe.
    assert matching[0].verdict.category == "unresolved"


def test_property_missing_fdel_still_reaches_a_dispatch_target() -> None:
    w = _walk(
        fx_a1.trigger_readonly_property_delete,
        "phase-a1:descriptor:property-no-fdel",
    )
    matching = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-descriptor-__delete__"
    ]
    assert len(matching) == 1
    assert matching[0].verdict.module == "builtins"
    assert matching[0].verdict.qualname == "property.__delete__"
    assert matching[0].verdict.category == "unresolved"


# ---------------------------------------------------------------------
# 11. Augmented assignment (item 5): obj.attr += value models both
# __get__ and __set__, independently, without duplicates.
# ---------------------------------------------------------------------


def test_augassign_models_both_get_and_set_independently() -> None:
    w = _walk(fx_a1.trigger_augassign_get_forbidden, "phase-a1:augassign:shape")
    get_records = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-descriptor-__get__"
    ]
    set_records = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-descriptor-__set__"
    ]
    assert len(get_records) == 1, "exactly one __get__ event, never duplicated"
    assert len(set_records) == 1, "exactly one __set__ event, never duplicated"


def test_augassign_get_sentinel_detected_independently_of_clean_set() -> None:
    w = _walk(
        fx_a1.trigger_augassign_get_forbidden, "phase-a1:augassign:get-forbidden"
    )
    found = _forbidden_open_records(w.call_records)
    assert found, "the sentinel inside the __get__ half must be discovered"
    assert all(
        "[__get__]" in r.site or r.site.endswith("[__get__] (augmented assignment)")
        for r in found
    )


def test_augassign_set_sentinel_detected_independently_of_clean_get() -> None:
    """The mirror case -- the clean __get__ half must never mask the
    forbidden __set__ half."""
    w = _walk(
        fx_a1.trigger_augassign_set_forbidden, "phase-a1:augassign:set-forbidden"
    )
    found = _forbidden_open_records(w.call_records)
    assert found, "the sentinel inside the __set__ half must be discovered"


# ---------------------------------------------------------------------
# 12. Multi-item context managers (item 6): with a, b: / async with a, b:
# ---------------------------------------------------------------------


def test_multi_item_with_events_exactly_once_reverse_exit_order() -> None:
    w = _walk(fx_a1.trigger_multi_item_with, "phase-a1:multi-item:sync")
    cm_records = [
        r
        for r in w.call_records
        if r.resolution_mechanism.startswith("implicit-context-manager-")
    ]
    assert len(cm_records) == 4, "two items, enter+exit each, no duplicates"
    ordering = [(r.callee_text, r.resolution_mechanism) for r in cm_records]
    assert ordering == [
        ("a.__enter__", "implicit-context-manager-__enter__"),
        ("b.__enter__", "implicit-context-manager-__enter__"),
        ("b.__exit__", "implicit-context-manager-__exit__"),
        ("a.__exit__", "implicit-context-manager-__exit__"),
    ], (
        "enter must fire in program order (a, b) and exit in *reverse* "
        f"order (b, a), matching real interpreter cleanup semantics: {ordering}"
    )


def test_multi_item_async_with_events_exactly_once_reverse_exit() -> None:
    w = _walk(fx_a1.trigger_multi_item_async_with, "phase-a1:multi-item:async")
    cm_records = [
        r
        for r in w.call_records
        if r.resolution_mechanism.startswith("implicit-context-manager-")
    ]
    assert len(cm_records) == 4
    ordering = [(r.callee_text, r.resolution_mechanism) for r in cm_records]
    assert ordering == [
        ("a.__aenter__", "implicit-context-manager-__aenter__"),
        ("b.__aenter__", "implicit-context-manager-__aenter__"),
        ("b.__aexit__", "implicit-context-manager-__aexit__"),
        ("a.__aexit__", "implicit-context-manager-__aexit__"),
    ], ordering


# ---------------------------------------------------------------------
# 13. Recursion reuses existing visited-state/budget machinery (item 8)
# ---------------------------------------------------------------------


def test_descriptor_recursion_is_specialization_deduped_like_any_other_walk() -> None:
    """Walking the same descriptor-dispatch target twice in one walker
    instance (via two independent sites reaching the identical
    receiver class) must dedup through the exact same
    `(callable identity, specialization)` visited-state set every other
    discovered callable already uses -- never a separate, parallel
    cache."""
    walker = StaticWalker()
    walker.walk(fx.trigger_descriptor_get, "phase-a1:dedup:first")
    visited_after_first = set(walker.visited_funcs)
    walker.walk(fx.trigger_descriptor_get, "phase-a1:dedup:second")
    assert walker.visited_funcs == visited_after_first, (
        "revisiting the identical (callable, specialization) state must "
        "be a no-op against the walker's own existing dedup set"
    )


def test_implicit_dispatch_recursion_counts_against_the_shared_work_budget() -> None:
    """A tiny shared budget exhausts deterministically -- implicit
    dispatch recursion is not a separate, additional budget."""
    walker = StaticWalker(max_total_walk_steps=1)
    walker.walk(fx.trigger_with_statement_enter_only, "phase-a1:budget:cm")
    # The outer walk() call itself consumes the one available slot;
    # recursing into __enter__'s body is deterministically refused and
    # explicitly reported, never silently dropped.
    assert len(walker.visited_funcs) == 1
    assert walker.depth_exceeded, (
        "budget exhaustion during implicit-dispatch recursion must be "
        "reported the same way any other budget exhaustion is"
    )


# =======================================================================
# Semantic-correctness audit (Task 38.8 Phase A.1 patch pass): items
# 2-7, each a demonstrated defect in the mechanism above, not a new
# family or architecture change.
# =======================================================================


def _implicit_candidate_count(records: list[CallRecord]) -> int:
    return sum(1 for r in records if r.resolution_mechanism.startswith("implicit-"))


# ---------------------------------------------------------------------
# Item 2: syntax-site vs. dispatch-candidate counter ownership -- exact
# counts for all five required shapes.
# ---------------------------------------------------------------------


def test_ordinary_descriptor_attribute_is_one_site_one_candidate() -> None:
    w = _walk(fx.trigger_descriptor_get, "item2:ordinary-attribute")
    assert w.implicit_syntax_sites_total == 1
    assert _implicit_candidate_count(w.call_records) == 1


def test_augassign_attribute_is_one_site_two_candidates() -> None:
    w = _walk(fx_a1.trigger_augassign_get_forbidden, "item2:augassign")
    assert w.implicit_syntax_sites_total == 1
    assert _implicit_candidate_count(w.call_records) == 2


def test_one_with_item_is_one_site_two_candidates() -> None:
    w = _walk(fx.trigger_with_statement_enter_only, "item2:one-with-item")
    assert w.implicit_syntax_sites_total == 1
    assert _implicit_candidate_count(w.call_records) == 2


def test_with_a_b_is_two_sites_four_candidates() -> None:
    w = _walk(fx_a1.trigger_multi_item_with, "item2:with-a-b")
    assert w.implicit_syntax_sites_total == 2
    assert _implicit_candidate_count(w.call_records) == 4


def test_async_with_a_b_reconciles_identically() -> None:
    w = _walk(fx_a1.trigger_multi_item_async_with, "item2:async-with-a-b")
    assert w.implicit_syntax_sites_total == 2
    assert _implicit_candidate_count(w.call_records) == 4


# ---------------------------------------------------------------------
# Item 3: a statically-known-missing context-manager protocol method is
# a fail-closed unresolved dispatch candidate, never the descriptor-
# only `resolved_non_descriptor_exclusion` counter.
# ---------------------------------------------------------------------


def test_missing_enter_is_unresolved_not_descriptor_exclusion() -> None:
    w = _walk(fx_a1.trigger_missing_enter, "item3:missing-enter")
    matching = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-context-manager-__enter__"
    ]
    assert len(matching) == 1, "still a dispatch candidate, never silently dropped"
    assert matching[0].verdict.category == "unresolved"
    assert w.implicit_resolved_non_descriptor_exclusion_total == 0


def test_missing_exit_is_unresolved_not_descriptor_exclusion() -> None:
    w = _walk(fx_a1.trigger_missing_exit, "item3:missing-exit")
    matching = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-context-manager-__exit__"
    ]
    assert len(matching) == 1
    assert matching[0].verdict.category == "unresolved"
    assert w.implicit_resolved_non_descriptor_exclusion_total == 0


def test_missing_aenter_is_unresolved_not_descriptor_exclusion() -> None:
    w = _walk(fx_a1.trigger_missing_aenter, "item3:missing-aenter")
    matching = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-context-manager-__aenter__"
    ]
    assert len(matching) == 1
    assert matching[0].verdict.category == "unresolved"
    assert w.implicit_resolved_non_descriptor_exclusion_total == 0


def test_missing_aexit_is_unresolved_not_descriptor_exclusion() -> None:
    w = _walk(fx_a1.trigger_missing_aexit, "item3:missing-aexit")
    matching = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-context-manager-__aexit__"
    ]
    assert len(matching) == 1
    assert matching[0].verdict.category == "unresolved"
    assert w.implicit_resolved_non_descriptor_exclusion_total == 0


# ---------------------------------------------------------------------
# Item 4: class-level store/delete descriptor semantics -- only a
# metaclass data descriptor can intercept `C.attr = value`/`del C.attr`;
# a descriptor merely stored in `C.__dict__` is never consulted.
# ---------------------------------------------------------------------


def test_class_level_set_never_dispatches_into_class_body_descriptor() -> None:
    w = _walk(
        fx_a1.trigger_class_level_set_never_calls_class_body_descriptor,
        "item4:class-set-no-dispatch",
    )
    assert not _forbidden_open_records(w.call_records), (
        "C.attr = value must never invoke a class-body descriptor's __set__"
    )
    matching = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-descriptor-__set__"
    ]
    assert matching == [], (
        "a class-body (non-metaclass) descriptor is not consulted for "
        "Store at all -- a sound no-dispatch exclusion, not a resolved "
        "or unresolved candidate"
    )
    assert w.implicit_resolved_non_descriptor_exclusion_total == 1


def test_class_level_delete_never_dispatches_into_class_body_descriptor() -> None:
    w = _walk(
        fx_a1.trigger_class_level_delete_never_calls_class_body_descriptor,
        "item4:class-delete-no-dispatch",
    )
    assert not _forbidden_open_records(w.call_records)
    matching = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-descriptor-__delete__"
    ]
    assert matching == []
    assert w.implicit_resolved_non_descriptor_exclusion_total == 1


def test_class_level_set_dispatches_through_metaclass_data_descriptor() -> None:
    w = _walk(
        fx_a1.trigger_class_level_set_via_metaclass_data_descriptor,
        "item4:class-set-metaclass-intercept",
    )
    assert _forbidden_open_records(w.call_records), (
        "a metaclass-level data descriptor's __set__ must intercept "
        "C.attr = value"
    )


def test_class_level_delete_dispatches_through_metaclass_data_descriptor() -> None:
    w = _walk(
        fx_a1.trigger_class_level_delete_via_metaclass_data_descriptor,
        "item4:class-delete-metaclass-intercept",
    )
    assert _forbidden_open_records(w.call_records), (
        "a metaclass-level data descriptor's __delete__ must intercept "
        "del C.attr"
    )


def test_class_level_get_still_dispatches_into_class_body_descriptor() -> None:
    """The mirror, already-passing case, restated here for contrast:
    ``Load`` (unlike Store/Del) *does* consult a class-body descriptor."""
    w = _walk(
        fx_a1.trigger_class_level_own_mro_descriptor_get,
        "item4:class-get-still-dispatches",
    )
    assert _forbidden_open_records(w.call_records)


# ---------------------------------------------------------------------
# Item 5: descriptor dispatch via ast.Call.func, and chained (non-Name)
# receivers -- neither silently omitted.
# ---------------------------------------------------------------------


def test_callable_returning_data_descriptor_used_as_call_func_is_detected() -> None:
    """``obj.descriptor_returning_callable()`` -- the descriptor access
    itself (``__get__``) is an independent event from the outer call,
    and must be discovered on its own. The attribute-access event's own
    record resolves to ``__get__`` itself (``implicit-descriptor-
    __get__``, ``project_source_available``) -- the embedded sentinel
    is found one hop deeper, via the *recursive* walk into that
    ``__get__`` body finding it as an ordinary, already-discovered
    explicit ``ast.Call`` node there (the exact same outer-event/
    nested-dispatch distinction §1 draws for every other mechanized
    family)."""
    w = _walk(
        fx_a1.trigger_descriptor_returning_callable_used_as_call_func,
        "item5:call-func-data-descriptor",
    )
    found = _forbidden_open_records(w.call_records)
    assert found, "the descriptor's own __get__ body must be discovered"

    access_records = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-descriptor-__get__"
    ]
    assert len(access_records) == 1
    assert access_records[0].verdict.category != "unresolved"
    assert access_records[0].verdict.qualname == (
        "_CallableReturningDataDescriptor.__get__"
    )


def test_ordinary_bound_method_call_now_produces_a_descriptor_candidate() -> None:
    """Correction of the prior (incorrect) exclusion: ``obj.method()``
    reads ``obj.method`` (a non-data descriptor) before calling it --
    same ambiguous/unresolved treatment as any other bare non-data-
    descriptor Load, never silently skipped merely because it happens
    to be called immediately. The outer call itself is untouched --
    still resolved by the existing, separate call-handling path."""
    w = _walk(
        fx_a1.trigger_ordinary_bound_method_call, "item5:call-func-ordinary-method"
    )
    descriptor_records = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-descriptor-__get__"
    ]
    assert len(descriptor_records) == 1, (
        "the attribute-load half of obj.method() must now be modeled as "
        "its own descriptor-dispatch candidate"
    )
    assert descriptor_records[0].verdict.category == "unresolved"

    outer_call_records = [
        r
        for r in w.call_records
        if not r.resolution_mechanism.startswith("implicit-")
        and r.callee_text == "obj.method"
    ]
    assert len(outer_call_records) == 1, (
        "the outer explicit call must still be recorded exactly once by "
        "the existing call-handling path -- never merged with, replaced "
        "by, or duplicated because of the new descriptor record"
    )


def test_chained_descriptor_read_is_unresolved_not_silently_dropped() -> None:
    w = _walk(
        fx_a1.trigger_chained_descriptor_read, "item5:chained-read"
    )
    matching = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-descriptor-__get__"
        and r.site == "item5:chained-read"
    ]
    assert len(matching) == 1, "a chained receiver must still produce one record"
    assert matching[0].verdict.category == "unresolved"
    assert matching[0].verdict.qualname is None


def test_chained_descriptor_write_is_unresolved_not_silently_dropped() -> None:
    w = _walk(fx_a1.trigger_chained_descriptor_write, "item5:chained-write")
    matching = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-descriptor-__set__"
    ]
    assert len(matching) == 1
    assert matching[0].verdict.category == "unresolved"


def test_chained_descriptor_delete_is_unresolved_not_silently_dropped() -> None:
    w = _walk(fx_a1.trigger_chained_descriptor_delete, "item5:chained-delete")
    matching = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-descriptor-__delete__"
    ]
    assert len(matching) == 1
    assert matching[0].verdict.category == "unresolved"


def test_call_func_descriptor_record_does_not_double_count_the_outer_call() -> None:
    """§11's own reconciliation discipline, exercised directly: the
    descriptor-access record and the outer explicit call are two
    distinct entries, never one merged/duplicated record."""
    w = _walk(
        fx_a1.trigger_descriptor_returning_callable_used_as_call_func,
        "item5:no-double-count",
    )
    implicit_records = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-descriptor-__get__"
        and r.site == "item5:no-double-count"
    ]
    assert len(implicit_records) == 1
    explicit_records = [
        r
        for r in w.call_records
        if not r.resolution_mechanism.startswith("implicit-")
        and r.callee_text == "obj.descriptor_returning_callable"
    ]
    assert len(explicit_records) == 1


# ---------------------------------------------------------------------
# Item 6: attribute-access overrides -- a class (or its metaclass)
# overriding the base attribute-access machinery downgrades the site to
# ambiguous/unresolved, never resolved-safe, and the override itself is
# never executed to detect it.
# ---------------------------------------------------------------------


def test_custom_getattribute_makes_get_ambiguous_not_safe() -> None:
    w = _walk(
        fx_a1.trigger_custom_getattribute_get, "item6:custom-getattribute"
    )
    matching = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-descriptor-__get__"
    ]
    assert len(matching) == 1
    assert matching[0].verdict.category == "unresolved"
    assert "__getattribute__" in (matching[0].verdict.rationale or "")


def test_custom_setattr_makes_set_ambiguous_not_safe() -> None:
    w = _walk(fx_a1.trigger_custom_setattr_set, "item6:custom-setattr")
    matching = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-descriptor-__set__"
    ]
    assert len(matching) == 1
    assert matching[0].verdict.category == "unresolved"
    assert "__setattr__" in (matching[0].verdict.rationale or "")


def test_custom_delattr_makes_delete_ambiguous_not_safe() -> None:
    w = _walk(fx_a1.trigger_custom_delattr_delete, "item6:custom-delattr")
    matching = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-descriptor-__delete__"
    ]
    assert len(matching) == 1
    assert matching[0].verdict.category == "unresolved"
    assert "__delattr__" in (matching[0].verdict.rationale or "")


def test_metaclass_getattribute_makes_class_get_ambiguous_not_safe() -> None:
    w = _walk(
        fx_a1.trigger_meta_getattribute_class_get, "item6:meta-getattribute"
    )
    matching = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-descriptor-__get__"
    ]
    assert len(matching) == 1
    assert matching[0].verdict.category == "unresolved"
    assert "__getattribute__" in (matching[0].verdict.rationale or "")


def test_metaclass_setattr_makes_class_set_ambiguous_not_safe() -> None:
    w = _walk(fx_a1.trigger_meta_setattr_class_set, "item6:meta-setattr")
    matching = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-descriptor-__set__"
    ]
    assert len(matching) == 1
    assert matching[0].verdict.category == "unresolved"
    assert "__setattr__" in (matching[0].verdict.rationale or "")


def test_metaclass_delattr_makes_class_delete_ambiguous_not_safe() -> None:
    w = _walk(fx_a1.trigger_meta_delattr_class_delete, "item6:meta-delattr")
    matching = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-descriptor-__delete__"
    ]
    assert len(matching) == 1
    assert matching[0].verdict.category == "unresolved"
    assert "__delattr__" in (matching[0].verdict.rationale or "")


# ---------------------------------------------------------------------
# Item 7: context-manager target binding -- staticmethod/classmethod/
# descriptor-backed protocol methods must never be misclassified as
# their own wrapper object, and a descriptor-backed one must never be
# executed to resolve it.
# ---------------------------------------------------------------------


def test_staticmethod_wrapped_enter_unwraps_to_the_real_function() -> None:
    w = _walk(fx_a1.trigger_staticmethod_enter, "item7:staticmethod-enter")
    matching = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-context-manager-__enter__"
    ]
    assert len(matching) == 1
    assert matching[0].verdict.category != "unresolved", (
        "a staticmethod-wrapped __enter__ must unwrap to its own "
        "function, not stay stuck on the staticmethod wrapper object"
    )
    module, qualname = module_and_qualname(fx_a1._static_enter_impl)
    assert matching[0].verdict.module == module
    assert matching[0].verdict.qualname == qualname


def test_classmethod_wrapped_enter_unwraps_to_the_real_function() -> None:
    w = _walk(fx_a1.trigger_classmethod_enter, "item7:classmethod-enter")
    matching = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-context-manager-__enter__"
    ]
    assert len(matching) == 1
    assert matching[0].verdict.category != "unresolved"
    assert matching[0].verdict.module == fx_a1.__name__
    assert matching[0].verdict.qualname == "ClassmethodContextManager.__enter__"


def test_descriptor_backed_enter_fails_closed_and_is_never_executed() -> None:
    """A genuine descriptor (not a function/staticmethod/classmethod)
    placed as ``__enter__`` -- this walker must never execute its
    ``__get__`` to discover what it would return; a passing test (no
    exception propagates) is direct proof, and the site must still be
    reported, unresolved, never silently dropped."""
    w = _walk(
        fx_a1.trigger_descriptor_backed_enter, "item7:descriptor-backed-enter"
    )
    matching = [
        r
        for r in w.call_records
        if r.resolution_mechanism == "implicit-context-manager-__enter__"
    ]
    assert len(matching) == 1
    assert matching[0].verdict.category == "unresolved"
