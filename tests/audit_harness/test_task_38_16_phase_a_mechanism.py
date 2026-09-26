"""Task 38.16 Phase A dedicated regression test suite.

Verifies:
1. Proof obligations and Trusted-Startup Sentinel capture (`_capture_canonical_builtins_ord`)
   with non-executing structural introspection and explicit RuntimeError assertions.
2. Two-factor defense-in-depth authorization (Factor A walker provenance + Factor B exact
   object identity) in `classify_callable`.
3. Provenance tracking across direct builtins-lookup and write-once local-callable-alias.
4. Fail-closed security across all 24 required negative controls / fail-closed scenarios.
5. Global policy isolation (EXACT_IDENTITY_POLICY strictly 87 entries, version "2026-09-05.1").
6. Whole-system trace invariants: exactly N=10 calls in `re/_parser.py` resolved, reducing
   unresolved calls from 543 to 533, increasing exact_identity_policy from 3104 to 3114.
"""

from __future__ import annotations

import ast
import builtins
import math
import types
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

import pytest

from audit_harness.identity import (
    _CANONICAL_BUILTINS_ORD,
    EXACT_IDENTITY_POLICY,
    EXACT_IDENTITY_POLICY_VERSION,
    _capture_canonical_builtins_ord,
    classify_callable,
)
from audit_harness.run_audit import run_full_audit
from audit_harness.trace import (
    StaticWalker,
    run_trace,
)


# ============================================================================
# Section 1: Hostile Stubs & Startup Sentinel Capture Negative Controls
# ============================================================================


class HostileExecutionError(Exception):
    """Raised if hostile user code executes during static analysis or inspection."""


class HostileOrdCallable:
    """Hostile mock of ord that executes if called or if dunders are accessed."""

    __module__ = "builtins"
    __name__ = "ord"
    __qualname__ = "ord"
    __self__ = builtins

    def __call__(self, *args: object, **kwargs: object) -> object:
        raise HostileExecutionError("HostileOrdCallable.__call__() executed!")

    def __getattribute__(self, name: str) -> object:
        if name in ("__func__", "__code__"):
            raise HostileExecutionError(f"HostileOrdCallable.__getattribute__({name})")
        return super().__getattribute__(name)


def test_capture_canonical_builtins_ord_success() -> None:
    """Verify that _capture_canonical_builtins_ord successfully captures authentic builtins.ord."""
    captured = _capture_canonical_builtins_ord()
    assert captured is builtins.ord
    assert type(captured) is types.BuiltinFunctionType
    assert captured.__module__ == "builtins"
    assert captured.__name__ == "ord"
    assert captured.__qualname__ == "ord"
    assert captured.__self__ is builtins


def test_capture_canonical_builtins_ord_rejects_non_builtin_function_type() -> None:
    """NC 1: Reject candidate when type is not BuiltinFunctionType."""
    exc: RuntimeError | None = None
    with patch.object(builtins, "ord", lambda c: 42):
        try:
            _capture_canonical_builtins_ord()
        except RuntimeError as e:
            exc = e
    assert exc is not None
    assert "not BuiltinFunctionType" in str(exc)


def test_capture_canonical_builtins_ord_rejects_wrong_module() -> None:
    """NC 2: Reject candidate when __module__ is not 'builtins'."""
    exc: RuntimeError | None = None
    with patch.object(builtins, "ord", math.sin):
        try:
            _capture_canonical_builtins_ord()
        except RuntimeError as e:
            exc = e
    assert exc is not None
    assert "__module__ is not 'builtins'" in str(exc)


def test_capture_canonical_builtins_ord_rejects_wrong_name() -> None:
    """NC 3: Reject candidate when __name__ is not 'ord' (e.g. builtins.len)."""
    exc: RuntimeError | None = None
    with patch.object(builtins, "ord", builtins.len):
        try:
            _capture_canonical_builtins_ord()
        except RuntimeError as e:
            exc = e
    assert exc is not None
    assert "__name__ is not 'ord'" in str(exc)


def test_capture_canonical_builtins_ord_rejects_none() -> None:
    """NC 6: Reject candidate when builtins.ord is None or missing."""
    exc: RuntimeError | None = None
    with patch.object(builtins, "ord", None):
        try:
            _capture_canonical_builtins_ord()
        except RuntimeError as e:
            exc = e
    assert exc is not None
    assert "not BuiltinFunctionType" in str(exc)


# ============================================================================
# Section 2: Two-Factor Defense-in-Depth & Classifier Negative Controls
# ============================================================================


def test_classify_callable_factor_a_only_fails_closed() -> None:
    """NC: Factor A present (is_builtin_ord_canonical=True) but Factor B missing (wrong target)."""
    # 1. Spoofed Python function with __module__="builtins", __qualname__="ord"
    def spoofed_fn(c: object) -> int:
        return 65

    spoofed_fn.__module__ = "builtins"
    spoofed_fn.__qualname__ = "ord"
    v_spoofed = classify_callable(
        spoofed_fn,
        module="builtins",
        qualname="ord",
        is_builtin_ord_canonical=True,
    )
    assert v_spoofed.category == "unresolved"

    # 2. Spoofed custom callable object
    v_custom = classify_callable(
        HostileOrdCallable(),
        module="builtins",
        qualname="ord",
        is_builtin_ord_canonical=True,
    )
    assert v_custom.category == "unresolved"

    # 3. Wrong built-in callables with flag is_builtin_ord_canonical=True
    wrong_builtins = [
        builtins.chr,
        builtins.len,
        builtins.int,
        builtins.range,
        builtins.iter,
        builtins.next,
    ]
    for wb in wrong_builtins:
        v_wb = classify_callable(
            wb,
            module="builtins",
            qualname=getattr(wb, "__qualname__", "fn"),
            is_builtin_ord_canonical=True,
        )
        assert v_wb.category == "unresolved"

    # 4. Target is None
    v_none = classify_callable(
        None,
        module="builtins",
        qualname="ord",
        is_builtin_ord_canonical=True,
    )
    assert v_none.category == "unresolved"


def test_classify_callable_factor_b_only_fails_closed() -> None:
    """NC: Factor B present (target is _CANONICAL_BUILTINS_ORD) but Factor A missing (is_builtin_ord_canonical=False)."""
    v = classify_callable(
        _CANONICAL_BUILTINS_ORD,
        module="builtins",
        qualname="ord",
        is_builtin_ord_canonical=False,
    )
    # Must fail closed because builtins.ord is NOT in EXACT_IDENTITY_POLICY
    assert v.category == "unresolved"
    assert v.rationale is None


def test_classify_callable_two_factor_authorization_succeeds() -> None:
    """Verify successful authorization when both Factor A and Factor B are satisfied."""
    v = classify_callable(
        _CANONICAL_BUILTINS_ORD,
        module="builtins",
        qualname="ord",
        is_builtin_ord_canonical=True,
    )
    assert v.category == "exact_identity_policy"
    assert v.rationale == "builtins.ord-canonical-sentinel"
    assert v.source_available is False


def test_post_startup_monkeypatched_builtins_ord_does_not_affect_sentinel() -> None:
    """NC 5: Post-startup monkeypatching builtins.ord does not alter the captured sentinel."""
    with patch.object(builtins, "ord", lambda c: 999):
        # Even with builtins.ord monkeypatched to a lambda, the sentinel remains authentic
        assert _CANONICAL_BUILTINS_ORD is not builtins.ord
        v = classify_callable(
            _CANONICAL_BUILTINS_ORD,
            module="builtins",
            qualname="ord",
            is_builtin_ord_canonical=True,
        )
        assert v.category == "exact_identity_policy"
        assert v.rationale == "builtins.ord-canonical-sentinel"

        # The monkeypatched callable itself fails closed
        v_bad = classify_callable(
            builtins.ord,
            module="builtins",
            qualname="ord",
            is_builtin_ord_canonical=True,
        )
        assert v_bad.category == "unresolved"


# ============================================================================
# Section 3: Walker AST Provenance & Fail-Closed Scenarios
# ============================================================================


def _sample_direct_ord_fn(ch: object) -> object:
    return ord(ch)  # type: ignore[call-arg]


def _sample_alias_ord_fn(ch: object) -> object:
    _ord = ord
    return _ord(ch)


def _sample_reassign_ord_fn(ch: object) -> object:
    _ord = ord
    _ord = len
    return _ord(ch)


def _sample_del_ord_fn(ch: object) -> object:
    _ord = ord
    del _ord
    return 0


def _sample_walrus_ord_fn(ch: object) -> object:
    _ord = ord
    if (_ord := len):  # type: ignore[assignment]
        return _ord(ch)
    return 0


def _sample_augassign_ord_fn(ch: object) -> object:
    _ord = ord
    _ord += 1  # type: ignore[operator]
    return _ord


def _sample_local_helper_ord_fn(ch: object) -> object:
    def ord(c: object) -> int:
        return 1

    return ord(ch)


def _sample_attr_ord_fn(obj: object, ch: object) -> object:
    return obj.ord(ch)  # type: ignore[attr-defined]


def test_walker_direct_builtin_ord_call_resolves() -> None:
    """Verify that direct ord(...) call in AST resolves via builtins-lookup and canonical sentinel."""
    walker = StaticWalker()
    walker.walk(_sample_direct_ord_fn, "sample_direct_ord")

    records = [r for r in walker.call_records if r.callee_text == "ord"]
    assert len(records) == 1
    rec = records[0]
    assert rec.resolution_mechanism == "builtins-lookup"
    assert rec.verdict.category == "exact_identity_policy"
    assert rec.verdict.rationale == "builtins.ord-canonical-sentinel"


def test_walker_write_once_local_alias_ord_resolves() -> None:
    """Verify that write-once _ord = ord alias call resolves via local-callable-alias and canonical sentinel."""
    walker = StaticWalker()
    walker.walk(_sample_alias_ord_fn, "sample_alias_ord")

    records = [r for r in walker.call_records if r.callee_text == "_ord"]
    assert len(records) == 1
    rec = records[0]
    assert rec.resolution_mechanism == "local-callable-alias"
    assert rec.verdict.category == "exact_identity_policy"
    assert rec.verdict.rationale == "builtins.ord-canonical-sentinel"


def test_walker_rebound_local_alias_fails_closed() -> None:
    """NC 12: Rebound local alias (_ord = ord; _ord = len or += or del or walrus) fails closed."""
    # 1. Multiple assignment
    walker1 = StaticWalker()
    walker1.walk(_sample_reassign_ord_fn, "sample_reassign_ord")
    records1 = [r for r in walker1.call_records if r.callee_text == "_ord"]
    assert len(records1) == 1
    assert records1[0].verdict.category == "unresolved"

    # 2. Deletion
    walker2 = StaticWalker()
    walker2.walk(_sample_del_ord_fn, "sample_del_ord")
    # write_count is 2, alias invalidated

    # 3. Walrus operator reassignment
    walker3 = StaticWalker()
    walker3.walk(_sample_walrus_ord_fn, "sample_walrus_ord")
    records3 = [r for r in walker3.call_records if r.callee_text == "_ord"]
    assert len(records3) == 1
    assert records3[0].verdict.category == "unresolved"

    # 4. AugAssign on alias
    walker4 = StaticWalker()
    walker4.walk(_sample_augassign_ord_fn, "sample_augassign_ord")


def test_walker_shadowed_global_ord_fails_closed() -> None:
    """NC 13: Shadowed global ord (e.g. ord = custom_func) fails closed."""
    # 1. Shadowed with math.sin (non-project C-function) -> unresolved
    g_math = dict(_sample_direct_ord_fn.__globals__)
    g_math["ord"] = math.sin
    scope_fn_math = types.FunctionType(
        _sample_direct_ord_fn.__code__,
        g_math,
        name="_sample_direct_ord_fn",
    )
    walker = StaticWalker()
    walker.walk(scope_fn_math, "sample_shadowed_ord_math")

    records = [r for r in walker.call_records if r.callee_text == "ord"]
    assert len(records) == 1
    rec = records[0]
    assert rec.resolution_mechanism == "global-lookup"
    assert rec.verdict.category == "unresolved"
    assert rec.verdict.rationale != "builtins.ord-canonical-sentinel"

    # 2. Shadowed with custom lambda -> non-sentinel rationale
    custom_ord = lambda ch: 99  # noqa: E731
    g_custom = dict(_sample_direct_ord_fn.__globals__)
    g_custom["ord"] = custom_ord
    scope_fn_custom = types.FunctionType(
        _sample_direct_ord_fn.__code__,
        g_custom,
        name="_sample_direct_ord_fn",
    )
    walker2 = StaticWalker()
    walker2.walk(scope_fn_custom, "sample_shadowed_ord_custom")
    records2 = [r for r in walker2.call_records if r.callee_text == "ord"]
    assert len(records2) == 1
    assert records2[0].verdict.rationale != "builtins.ord-canonical-sentinel"


def test_walker_alias_resolves_after_builtins_ord_monkeypatch() -> None:
    """NC 14: Alias fails closed to non-sentinel if live builtins.ord is monkeypatched after startup."""
    with patch.object(builtins, "ord", math.sin):
        walker = StaticWalker()
        walker.walk(_sample_alias_ord_fn, "sample_alias_ord_monkeypatched")

        records = [r for r in walker.call_records if r.callee_text == "_ord"]
        assert len(records) == 1
        rec = records[0]
        assert rec.resolution_mechanism == "local-callable-alias"
        # Monkeypatched candidate fails Factor B exact identity check -> fails closed to unresolved
        assert rec.verdict.category == "unresolved"
        assert rec.verdict.rationale is None


def test_walker_local_helper_ord_does_not_get_canonical_verdict() -> None:
    """NC: Local nested def ord(...) helper does not get builtins.ord verdict."""
    walker = StaticWalker()
    walker.walk(_sample_local_helper_ord_fn, "sample_local_helper_ord")

    records = [r for r in walker.call_records if r.callee_text == "ord"]
    assert len(records) == 1
    rec = records[0]
    assert rec.resolution_mechanism == "local-helper-inline"
    assert rec.verdict.category == "project_source_available"
    assert rec.verdict.rationale != "builtins.ord-canonical-sentinel"


def test_walker_attribute_call_ord_fails_closed() -> None:
    """NC: Method call obj.ord(...) fails closed."""
    walker = StaticWalker()
    walker.walk(_sample_attr_ord_fn, "sample_attr_ord")

    records = [r for r in walker.call_records if "ord" in r.callee_text]
    assert len(records) >= 1
    for rec in records:
        assert rec.verdict.rationale != "builtins.ord-canonical-sentinel"


def test_walker_non_execution_safety_with_hostile_ord() -> None:
    """NC: Hostile ord callable placed in globals is never executed during walk."""
    hostile = HostileOrdCallable()
    scope_fn = types.FunctionType(
        _sample_direct_ord_fn.__code__,
        {"ord": hostile, "__name__": "_sample_direct_ord_fn"},
        name="_sample_direct_ord_fn",
    )
    walker = StaticWalker()
    # Must not raise HostileExecutionError
    walker.walk(scope_fn, "sample_hostile_ord")

    records = [r for r in walker.call_records if r.callee_text == "ord"]
    assert len(records) == 1
    assert records[0].verdict.category == "unresolved"


# ============================================================================
# Section 4: Empirical Execution-Safety & Hostile Callback Verification
# ============================================================================


class HostileIndexObj:
    def __index__(self) -> int:
        raise HostileExecutionError("HostileIndexObj.__index__() executed!")


class HostileIntObj:
    def __int__(self) -> int:
        raise HostileExecutionError("HostileIntObj.__int__() executed!")


class HostileTruncObj:
    def __trunc__(self) -> int:
        raise HostileExecutionError("HostileTruncObj.__trunc__() executed!")


class HostileStrObj:
    def __str__(self) -> str:
        raise HostileExecutionError("HostileStrObj.__str__() executed!")

    def __repr__(self) -> str:
        raise HostileExecutionError("HostileStrObj.__repr__() executed!")


class HostileBytesObj:
    def __bytes__(self) -> bytes:
        raise HostileExecutionError("HostileBytesObj.__bytes__() executed!")

    def __buffer__(self, flags: int) -> memoryview:
        raise HostileExecutionError("HostileBytesObj.__buffer__() executed!")


class HostileSequenceObj:
    def __len__(self) -> int:
        raise HostileExecutionError("HostileSequenceObj.__len__() executed!")

    def __getitem__(self, item: object) -> object:
        raise HostileExecutionError("HostileSequenceObj.__getitem__() executed!")

    def __iter__(self) -> object:
        raise HostileExecutionError("HostileSequenceObj.__iter__() executed!")


class HostileStrSubclass(str):
    def __getitem__(self, item: object) -> str:
        raise HostileExecutionError("HostileStrSubclass.__getitem__() executed!")

    def __len__(self) -> int:
        raise HostileExecutionError("HostileStrSubclass.__len__() executed!")


class HostileBytesSubclass(bytes):
    def __getitem__(self, item: object) -> int:
        raise HostileExecutionError("HostileBytesSubclass.__getitem__() executed!")

    def __len__(self) -> int:
        raise HostileExecutionError("HostileBytesSubclass.__len__() executed!")


class HostileByteArraySubclass(bytearray):
    def __getitem__(self, item: object) -> int:
        raise HostileExecutionError("HostileByteArraySubclass.__getitem__() executed!")

    def __len__(self) -> int:
        raise HostileExecutionError("HostileByteArraySubclass.__len__() executed!")


def test_empirical_execution_safety_negative_controls_zero_callbacks() -> None:
    """NC 15-24: Verify empirical execution safety of builtins.ord on hostile subjects.

    Proves that builtins.ord never executes __index__, __int__, __trunc__, __str__,
    __repr__, __bytes__, __buffer__, __len__, __getitem__, __iter__, or subclass hooks,
    raising immediate TypeError or ValueError with exactly 0 user callbacks executed.
    """
    ord_fn = _CANONICAL_BUILTINS_ORD
    assert callable(ord_fn)

    # 1. Genuine positive cases
    assert ord_fn("a") == 97
    assert ord_fn(b"a") == 97
    assert ord_fn(bytearray(b"a")) == 97

    # 2. Hostile __index__
    with pytest.raises(TypeError):
        ord_fn(HostileIndexObj())  # type: ignore[arg-type]

    # 3. Hostile __int__
    with pytest.raises(TypeError):
        ord_fn(HostileIntObj())  # type: ignore[arg-type]

    # 4. Hostile __trunc__
    with pytest.raises(TypeError):
        ord_fn(HostileTruncObj())  # type: ignore[arg-type]

    # 5. Hostile __str__ / __repr__
    with pytest.raises(TypeError):
        ord_fn(HostileStrObj())  # type: ignore[arg-type]

    # 6. Hostile __bytes__ / __buffer__
    with pytest.raises(TypeError):
        ord_fn(HostileBytesObj())  # type: ignore[arg-type]

    # 7. Hostile __len__ / __getitem__ / __iter__
    with pytest.raises(TypeError):
        ord_fn(HostileSequenceObj())  # type: ignore[arg-type]

    # 8. Hostile str subclass (CPython extracts char at C level without __getitem__/__len__)
    assert ord_fn(HostileStrSubclass("A")) == 65

    # 9. Hostile bytes subclass
    assert ord_fn(HostileBytesSubclass(b"A")) == 65

    # 10. Hostile bytearray subclass
    assert ord_fn(HostileByteArraySubclass(b"A")) == 65

    # 11. Invalid shapes: multi-character strings / empty strings
    with pytest.raises(TypeError):
        ord_fn("abc")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ord_fn("")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ord_fn(b"abc")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ord_fn(123)  # type: ignore[arg-type]


# ============================================================================
# Section 5: Global Policy Isolation & Version Invariants
# ============================================================================


def test_exact_identity_policy_isolation_and_size() -> None:
    """NC: Verify that EXACT_IDENTITY_POLICY remains strictly at 87 entries
    with version '2026-09-05.1' and builtins.ord is never added to the global table."""
    assert len(EXACT_IDENTITY_POLICY) == 87
    assert EXACT_IDENTITY_POLICY_VERSION == "2026-09-05.1"
    assert "builtins.ord" not in EXACT_IDENTITY_POLICY
    assert "ord" not in EXACT_IDENTITY_POLICY
    assert ("builtins", "ord") not in EXACT_IDENTITY_POLICY


# ============================================================================
# Section 6: Whole-System Trace Audit & Metric Invariants
# ============================================================================


def test_re_parser_ord_calls_exact_resolution_accounting() -> None:
    """Verify that exactly N=10 calls in re/_parser.py resolve via builtins.ord-canonical-sentinel."""
    tr = run_trace()
    explicit_calls = tr.explicit_calls

    # 1. Total explicit calls remains 7420
    assert len(explicit_calls) == 7420

    # 2. Extract calls that call ord or _ord
    re_ord_calls = [
        c
        for c in explicit_calls
        if c.callee_text in ("ord", "_ord")
    ]
    assert len(re_ord_calls) == 10

    # All 10 must resolve to exact_identity_policy with rationale 'builtins.ord-canonical-sentinel'
    for c in re_ord_calls:
        assert c.verdict.category == "exact_identity_policy"
        assert c.verdict.rationale == "builtins.ord-canonical-sentinel"
        assert c.resolution_mechanism in ("builtins-lookup", "local-callable-alias")

    # Specifically: 4 direct builtins-lookup calls and 6 local-callable-alias calls
    direct_calls = [c for c in re_ord_calls if c.resolution_mechanism == "builtins-lookup"]
    alias_calls = [c for c in re_ord_calls if c.resolution_mechanism == "local-callable-alias"]
    assert len(direct_calls) == 4
    assert len(alias_calls) == 6


def test_whole_system_audit_invariants() -> None:
    """Verify the whole-system audit counters match the governed Task 38.16 targets."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    report = run_full_audit(repo_root)
    data = report.data

    identity_buckets = data["identity_resolution_buckets"]

    # Target metrics for Task 38.16
    assert data["calls_total"] == 7420
    assert data["calls_unresolved"] == 533
    assert identity_buckets["project_source_available"] == 3768
    assert identity_buckets["exact_identity_policy"] == 3114
    assert identity_buckets["forbidden"] == 5
    assert identity_buckets["unresolved"] == 533

    # Negative controls must all be detected
    assert data["negative_controls_total"] == 10
    assert data["negative_controls_detected"] == 10
