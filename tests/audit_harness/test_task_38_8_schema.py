"""Task 38.8 Phase A.1 (§8, §9, §11): schema/report-wiring tests for the
new ``implicit_dispatch`` section -- `docs/prompts/task-38.8.md` §9
requires the mechanized-architecture schema fields be added to
``audit_harness/report.py`` "with a deliberate, documented
schema-version bump" once Option A/B/D is selected (ADR-032 selected
Option D, 2026-08-24).

These tests exercise the schema at the level a real consumer would --
``build_report``'s own gating and shape, and the full ``run_audit``
pipeline's real wiring -- distinct from
``test_task_38_8_phase_a1_mechanism.py``, which exercises the walker's
own ``call_records``/counters directly.
"""

from __future__ import annotations

import pytest

from audit_harness.identity import IdentityVerdict
from audit_harness.report import SCHEMA_VERSION, build_report
from audit_harness.trace import (
    UNSUPPORTED_PROTOCOL_FAMILIES,
    CallRecord,
    StaticWalker,
    TraceResult,
)
from tests.audit_harness.fixtures import implicit_dispatch as fx
from tests.audit_harness.fixtures import implicit_dispatch_phase_a1 as fx_a1
from tests.audit_harness.test_harness_properties import _CLEAN_IMPLICIT_DISPATCH


def _base_report_kwargs() -> dict[str, object]:
    """A minimal, otherwise-all-clear set of the other four required
    sections -- shared so each test below varies only the one thing
    under test."""
    return {
        "commit_sha": "deadbeef",
        "discovery": {
            "parse_errors_total": 0,
            "missing_from_component_registrars": [],
        },
        "trace": {
            "roots_traced": 24,
            "roots_with_error": (),
            "roots_with_error_total": 0,
            "nodes_total": 1,
            "nodes_unresolved": 0,
            "nodes_unresolved_detail": [],
            "calls_total": 1,
            "calls_unresolved": 0,
            "calls_unresolved_detail": [],
            "calls_unresolved_detail_multiplicity": {},
            "identity_resolution_buckets": {},
            "exact_identity_policy_version": "test",
        },
        "module_state": {
            "candidates_total": 1,
            "unexplained_total": 0,
            "unexplained_detail": [],
            "buckets": {},
            "parse_errors": [],
            "parse_errors_total": 0,
        },
        "runtime_denial": {"success": True},
        "negative_controls": {"total": 7, "detected": 7, "detail": []},
    }


# ---------------------------------------------------------------------
# 1. The schema-version bump is deliberate and covered
# ---------------------------------------------------------------------


def test_schema_version_bumped_to_38_8_0() -> None:
    assert SCHEMA_VERSION == "38.8.0"


def test_build_report_requires_implicit_dispatch_explicitly() -> None:
    """No silent default: a caller that forgets this section gets a
    loud `TypeError`, never a quietly-assumed-clean result."""
    kwargs = _base_report_kwargs()
    with pytest.raises(TypeError):
        build_report(**kwargs)  # type: ignore[call-arg, arg-type]


def test_build_report_emits_the_implicit_dispatch_section_additively() -> None:
    report = build_report(
        **_base_report_kwargs(), implicit_dispatch=_CLEAN_IMPLICIT_DISPATCH
    )
    assert report.data["schema_version"] == "38.8.0"
    assert report.data["implicit_dispatch"] == _CLEAN_IMPLICIT_DISPATCH
    # Every existing field this schema bump must not remove or rename:
    for existing_field in (
        "nodes_total",
        "nodes_unresolved",
        "calls_total",
        "calls_unresolved",
        "calls_unresolved_detail_multiplicity",
        "negative_controls_total",
        "self_test_failed",
        "exit_code",
    ):
        assert existing_field in report.data


# ---------------------------------------------------------------------
# 2. Fail-closed gating: unresolved_dispatches nonzero keeps HOLD,
# exactly like nodes_unresolved/calls_unresolved (§6)
# ---------------------------------------------------------------------


def test_nonzero_unresolved_dispatches_alone_forces_exit_code_nonzero() -> None:
    dirty = dict(_CLEAN_IMPLICIT_DISPATCH)
    dirty["unresolved_dispatches"] = 1
    report = build_report(**_base_report_kwargs(), implicit_dispatch=dirty)
    assert report.data["exit_code"] != 0, (
        "a nonzero implicit-dispatch unresolved count must independently "
        "keep the gate at HOLD, the same discipline nodes_unresolved/"
        "calls_unresolved already hold explicit calls to"
    )


def test_zero_unresolved_dispatches_with_clean_rest_allows_exit_code_zero() -> None:
    report = build_report(
        **_base_report_kwargs(), implicit_dispatch=_CLEAN_IMPLICIT_DISPATCH
    )
    assert report.data["exit_code"] == 0


# ---------------------------------------------------------------------
# 3. Existing report consumers continue working consistently
# ---------------------------------------------------------------------


def test_existing_false_negative_fixture_test_still_passes() -> None:
    """`test_harness_properties.py::test_false_negative_fixture_sets_self_test_failed`
    already re-verifies this end-to-end; this test only documents,
    in-place, that updating its two ``build_report`` calls to include
    ``implicit_dispatch`` was the correct, minimal, additive fix -- not
    a schema redefinition."""
    from tests.audit_harness.test_harness_properties import (
        test_false_negative_fixture_sets_self_test_failed,
    )

    test_false_negative_fixture_sets_self_test_failed()


# ---------------------------------------------------------------------
# 4. Reconciliation invariants (§11): a valid partition, never invented
# ---------------------------------------------------------------------


def _trace_result_from(*triggers: object) -> TraceResult:
    walker = StaticWalker()
    for i, trigger in enumerate(triggers):
        walker.walk(trigger, f"schema-test:{i}")
    return TraceResult(
        roots_traced=0,
        roots_with_error=(),
        resolve_events=(),
        distinct_provider_symbols=0,
        distinct_result_types=0,
        market_data_provider_runtime_type=None,
        nodes=(),
        calls=tuple(walker.call_records),
        sites_without_source=(),
        implicit_syntax_sites_total=walker.implicit_syntax_sites_total,
        implicit_resolved_non_descriptor_exclusion_total=(
            walker.implicit_resolved_non_descriptor_exclusion_total
        ),
    )


def test_dispatch_candidates_equals_resolved_plus_unresolved() -> None:
    """`dispatch_candidates_total == resolved_dispatches +
    unresolved_dispatches` -- a genuine partition (§11), covering both
    families and the ambiguous-hence-unresolved descriptor case."""
    tr = _trace_result_from(
        fx.trigger_with_statement_enter_only,
        fx.trigger_with_statement,
        fx.trigger_descriptor_get,
        fx.trigger_descriptor_set,
        fx.trigger_descriptor_delete,
        fx.trigger_property_get,
        fx_a1.trigger_augassign_get_forbidden,
        fx_a1.trigger_context_manager_unresolved_receiver,
        fx_a1.trigger_descriptor_get_unresolved_receiver,
    )
    assert (
        tr.implicit_dispatch_resolved + tr.implicit_dispatch_unresolved
        == tr.implicit_dispatch_candidates_total
    )
    assert tr.implicit_dispatch_candidates_total > 0
    assert tr.implicit_dispatch_resolved > 0
    assert tr.implicit_dispatch_unresolved > 0


def test_explicit_path_duplicates_is_an_annotation_not_a_fifth_addend() -> None:
    tr = _trace_result_from(fx_a1.trigger_with_and_explicit_enter_duplicate)
    assert tr.implicit_dispatch_explicit_path_duplicates == 1
    # The duplicate-flagged site is still counted exactly once inside
    # resolved_dispatches -- never folded into a separate sum that
    # would double-count it.
    assert (
        tr.implicit_dispatch_resolved + tr.implicit_dispatch_unresolved
        == tr.implicit_dispatch_candidates_total
    )


def test_resolved_non_descriptor_exclusion_is_excluded_from_the_partition() -> None:
    """A site with zero descriptor dispatch produces no `CallRecord` at
    all -- it must not appear in `dispatch_candidates_total`, and must
    be visible only via its own dedicated counter."""
    tr = _trace_result_from(fx_a1.trigger_plain_attribute_get)
    assert tr.implicit_resolved_non_descriptor_exclusion_total > 0
    # None of that shows up as a dispatch candidate:
    assert tr.implicit_dispatch_candidates_total == 0


def test_unsupported_protocol_families_is_the_exact_adr032_list() -> None:
    assert UNSUPPORTED_PROTOCOL_FAMILIES == (
        "iteration/comprehensions",
        "unpacking",
        "await/async iteration",
        "equality/ordering/arithmetic operators including reflected forms",
        "truth testing",
        "membership",
        "subscription/assignment/deletion",
        "hashing",
        "formatting including __str__/__repr__ fallback",
    )
    assert len(UNSUPPORTED_PROTOCOL_FAMILIES) == 9


# ---------------------------------------------------------------------
# 5. Per-method independence (item 2): context-manager enter/exit and
# descriptor get/set/delete each counted independently, never collapsed
# ---------------------------------------------------------------------


def test_context_manager_methods_counted_independently_in_by_method_breakdown() -> (
    None
):
    tr = _trace_result_from(
        fx.trigger_with_statement_enter_only,  # forbidden __enter__ only
        fx.trigger_async_with_statement,  # forbidden __aexit__ only
    )
    by_method = tr.implicit_dispatch_by_method
    assert by_method["__enter__"]["candidates"] == 1
    assert by_method["__exit__"]["candidates"] == 1
    assert by_method["__aenter__"]["candidates"] == 1
    assert by_method["__aexit__"]["candidates"] == 1
    assert by_method["__exit__"]["unresolved"] == 0
    assert by_method["__aexit__"]["resolved"] == 1


def test_descriptor_methods_counted_independently_in_by_method_breakdown() -> None:
    tr = _trace_result_from(
        fx.trigger_descriptor_get,
        fx.trigger_descriptor_set,
        fx.trigger_descriptor_delete,
    )
    by_method = tr.implicit_dispatch_by_method
    assert by_method["__get__"]["candidates"] == 1
    assert by_method["__set__"]["candidates"] == 1
    assert by_method["__delete__"]["candidates"] == 1
    assert by_method["__set__"]["resolved"] == 1
    assert by_method["__delete__"]["resolved"] == 1


# ---------------------------------------------------------------------
# 6. Deterministic serialization -- a real re-run, not just the walker
# ---------------------------------------------------------------------


def test_real_run_full_audit_produces_deterministic_implicit_dispatch_section() -> (
    None
):
    from pathlib import Path

    from audit_harness.run_audit import run_full_audit

    repo_root = Path(__file__).resolve().parents[2]
    first = run_full_audit(repo_root)
    second = run_full_audit(repo_root)
    assert first.data["implicit_dispatch"] == second.data["implicit_dispatch"]
    assert first.canonical_json() == second.canonical_json()


# =======================================================================
# Semantic-correctness audit (patch pass): item 1 (legacy call metrics
# stay explicit-call-only) and item 8 (report-section validation).
# =======================================================================


def _explicit_record(site: str, callee: str, category: str) -> CallRecord:
    verdict = IdentityVerdict(None, None, category, None, False)
    return CallRecord(site, callee, "attribute-lookup", verdict)


def _implicit_record(
    site: str, callee: str, mechanism: str, category: str
) -> CallRecord:
    verdict = IdentityVerdict(None, None, category, None, False)
    return CallRecord(site, callee, mechanism, verdict)


# ---------------------------------------------------------------------
# Item 1: implicit-dispatch records never contaminate the legacy,
# explicit-call-only aggregates.
# ---------------------------------------------------------------------


def test_explicit_calls_excludes_every_implicit_tagged_record() -> None:
    explicit_resolved = _explicit_record("s1", "foo", "project_source_available")
    explicit_unresolved = _explicit_record("s2", "bar", "unresolved")
    implicit_unresolved = _implicit_record(
        "s3", "obj.attr", "implicit-descriptor-__get__", "unresolved"
    )
    tr = TraceResult(
        roots_traced=0,
        roots_with_error=(),
        resolve_events=(),
        distinct_provider_symbols=0,
        distinct_result_types=0,
        market_data_provider_runtime_type=None,
        nodes=(),
        calls=(explicit_resolved, explicit_unresolved, implicit_unresolved),
        sites_without_source=(),
    )
    assert tr.explicit_calls == (explicit_resolved, explicit_unresolved)
    assert len(tr.calls) == 3, "the raw, unfiltered collection is untouched"
    assert tr.calls_unresolved == 1, (
        "calls_unresolved must count only the one explicit unresolved "
        "record, never the implicit one alongside it"
    )


def test_adding_one_unresolved_implicit_record_does_not_move_legacy_counters() -> (
    None
):
    """`docs/prompts/task-38.8.md`-adjacent patch requirement, stated
    exactly: adding one unresolved implicit-dispatch record alone must
    not alter legacy calls_total/calls_unresolved, while the new
    implicit unresolved counter must still increase."""
    explicit_resolved = _explicit_record("s1", "foo", "project_source_available")
    implicit_unresolved = _implicit_record(
        "s2", "obj.attr", "implicit-descriptor-__get__", "unresolved"
    )

    def _tr(calls: tuple[CallRecord, ...]) -> TraceResult:
        return TraceResult(
            roots_traced=0,
            roots_with_error=(),
            resolve_events=(),
            distinct_provider_symbols=0,
            distinct_result_types=0,
            market_data_provider_runtime_type=None,
            nodes=(),
            calls=calls,
            sites_without_source=(),
        )

    before = _tr((explicit_resolved,))
    after = _tr((explicit_resolved, implicit_unresolved))

    assert len(before.explicit_calls) == len(after.explicit_calls) == 1
    assert before.calls_unresolved == after.calls_unresolved == 0
    assert after.implicit_dispatch_unresolved == before.implicit_dispatch_unresolved + 1


def test_run_audit_legacy_fields_are_explicit_call_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end proof at the real `run_full_audit` wiring level (not
    just `TraceResult`'s own properties): `calls_total`,
    `calls_unresolved`, `calls_unresolved_detail`, and
    `identity_resolution_buckets` must all be built from
    `tr.explicit_calls`, never `tr.calls`."""
    from pathlib import Path

    import audit_harness.run_audit as run_audit_module

    explicit_unresolved = _explicit_record("site:explicit", "some_call", "unresolved")
    implicit_unresolved = _implicit_record(
        "site:implicit", "obj.attr", "implicit-descriptor-__get__", "unresolved"
    )
    synthetic = TraceResult(
        roots_traced=24,
        roots_with_error=(),
        resolve_events=(),
        distinct_provider_symbols=0,
        distinct_result_types=0,
        market_data_provider_runtime_type=None,
        nodes=(),
        calls=(explicit_unresolved, implicit_unresolved),
        sites_without_source=(),
        implicit_syntax_sites_total=1,
        implicit_resolved_non_descriptor_exclusion_total=0,
    )
    monkeypatch.setattr(run_audit_module, "run_trace", lambda: synthetic)

    repo_root = Path(__file__).resolve().parents[2]
    report = run_audit_module.run_full_audit(repo_root)
    data = report.data

    assert data["calls_total"] == 1, "the implicit record must not inflate calls_total"
    assert data["calls_unresolved"] == 1
    assert data["calls_unresolved_detail"] == ["site:explicit :: some_call"]
    assert data["identity_resolution_buckets"] == {
        "project_source_available": 0,
        "exact_identity_policy": 0,
        "forbidden": 0,
        "unresolved": 1,
    }
    assert data["implicit_dispatch"]["unresolved_dispatches"] == 1, (
        "the implicit unresolved counter must still see and count the "
        "implicit record, independently of the legacy fields above"
    )


# ---------------------------------------------------------------------
# Item 8: report-section validation.
# ---------------------------------------------------------------------


def test_build_report_fails_closed_on_malformed_implicit_dispatch_input() -> None:
    """`build_report` never defaults a missing/malformed
    `implicit_dispatch` key to a clean result -- plain dict indexing
    (never `.get(..., 0)`) means a malformed section raises loudly
    instead of silently producing an apparently-valid all-clear report."""
    with pytest.raises(KeyError):
        build_report(**_base_report_kwargs(), implicit_dispatch={})


def test_dispatch_events_by_method_totals_reconcile_with_global_totals() -> None:
    """§8/§11: `dispatch_events_by_method`'s own per-method candidate
    counts must sum to the same `dispatch_candidates_total` (and
    likewise resolved/unresolved) the global properties report --
    two independently-computed views of the same underlying
    `call_records`, which must never drift apart."""
    walker = StaticWalker()
    walker.walk(fx.trigger_with_statement_enter_only, "item8:a")
    walker.walk(fx.trigger_descriptor_get, "item8:b")
    walker.walk(fx_a1.trigger_augassign_get_forbidden, "item8:c")
    tr = TraceResult(
        roots_traced=0,
        roots_with_error=(),
        resolve_events=(),
        distinct_provider_symbols=0,
        distinct_result_types=0,
        market_data_provider_runtime_type=None,
        nodes=(),
        calls=tuple(walker.call_records),
        sites_without_source=(),
        implicit_syntax_sites_total=walker.implicit_syntax_sites_total,
        implicit_resolved_non_descriptor_exclusion_total=(
            walker.implicit_resolved_non_descriptor_exclusion_total
        ),
    )
    by_method = tr.implicit_dispatch_by_method
    assert sum(m["candidates"] for m in by_method.values()) == (
        tr.implicit_dispatch_candidates_total
    )
    assert (
        sum(m["resolved"] for m in by_method.values()) == tr.implicit_dispatch_resolved
    )
    assert (
        sum(m["unresolved"] for m in by_method.values())
        == tr.implicit_dispatch_unresolved
    )
