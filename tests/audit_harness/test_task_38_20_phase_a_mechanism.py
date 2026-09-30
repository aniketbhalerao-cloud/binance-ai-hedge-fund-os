"""Unit tests for Task 38.20 Phase B Canonical builtins.OverflowError Sentinel.

Validates the literal-derived primitive root-of-trust contract reused from
Task 38.17/38.19, four-tier anchor authentication (BaseException -> Exception
-> ArithmeticError -> OverflowError), CPython 3.12.13 type flags, two-factor
authorization separation (Factor A: provenance, Factor B: identity), hostile
startup failure modes (fail-closed to None), AST provenance negative controls,
global policy table isolation (strictly 87 entries v2026-09-05.1), N=2
direct builtins-lookup movement, sibling isolation, and whole-system
accounting.
"""

from __future__ import annotations

import builtins
import types
from pathlib import Path

from audit_harness.identity import (
    _CANONICAL_BUILTINS_OVERFLOWERROR,
    EXACT_IDENTITY_POLICY,
    EXACT_IDENTITY_POLICY_VERSION,
    Py_TPFLAGS_HEAPTYPE,
    Py_TPFLAGS_IMMUTABLETYPE,
    _capture_canonical_builtins_overflowerror,
    _dict_get,
    _dict_type,
    _object_getattribute,
    _object_root,
    _tuple_type,
    _type_base,
    _type_flags,
    _type_module,
    _type_mro,
    _type_name,
    _type_qualname,
    _type_type,
    classify_callable,
)
from audit_harness.run_audit import run_full_audit
from audit_harness.trace import StaticWalker, run_trace


class HostileExecutionError(Exception):
    """Raised when hostile code executes unexpectedly during static analysis."""


class HostileOverflowErrorCallable:
    """Hostile mock object pretending to be OverflowError."""

    def __call__(self, *args: object, **kwargs: object) -> object:
        raise HostileExecutionError(
            "HostileOverflowErrorCallable.__call__() executed!"
        )


class HostileModuleWithGetattribute(types.ModuleType):
    """Mock module with hostile __getattribute__ and __getattr__ hooks.

    Counters live in a private list stored via object.__setattr__ so reading
    them in the test never goes through the hostile hooks. Each hook
    increments its counter before raising, so a bypassed capture still
    yields quantitative zero-callback evidence.
    """

    def __init__(self, name: str = "mock_builtins") -> None:
        super().__init__(name)
        object.__setattr__(self, "_hostile_callbacks", [0, 0])

    def __getattribute__(self, name: str) -> object:
        counts = object.__getattribute__(self, "_hostile_callbacks")
        counts[0] += 1
        raise HostileExecutionError(f"Hostile __getattribute__({name!r}) invoked!")

    def __getattr__(self, name: str) -> object:
        counts = object.__getattribute__(self, "_hostile_callbacks")
        counts[1] += 1
        raise HostileExecutionError(f"Hostile __getattr__({name!r}) invoked!")


def _hostile_callback_counts(mod: object) -> tuple[int, int, int]:
    """Return (getattribute, getattr, total) without invoking hostile hooks."""
    counts = object.__getattribute__(mod, "_hostile_callbacks")
    getattribute_count = counts[0]
    getattr_count = counts[1]
    return getattribute_count, getattr_count, getattribute_count + getattr_count


def _sample_direct_overflowerror_fn() -> None:
    raise OverflowError("the repetition number is too large")


def _sample_aliased_overflowerror_fn() -> None:
    oe_alias = OverflowError
    raise oe_alias("Aliased OverflowError call")


def _sample_reassign_overflowerror_fn() -> None:
    _oe = OverflowError
    _oe = TypeError
    raise _oe("reassigned")


def _sample_del_overflowerror_fn() -> None:
    _oe = OverflowError
    del _oe


def _sample_walrus_overflowerror_fn() -> None:
    _oe = OverflowError
    if _oe := TypeError:  # type: ignore[assignment]
        raise _oe("walrus")


def _sample_augassign_overflowerror_fn() -> None:
    _oe = OverflowError
    _oe += 1  # type: ignore[operator]


def _sample_local_helper_overflowerror_fn() -> None:
    def OverflowError(msg: str) -> Exception:
        return RuntimeError(f"Local helper: {msg}")

    raise OverflowError("shadowed")


class _SampleClassWithOverflowErrorMethod:
    def OverflowError(self, msg: str) -> None:
        pass


def _sample_attr_overflowerror_fn() -> None:
    obj = _SampleClassWithOverflowErrorMethod()
    obj.OverflowError("method call")


def _create_mock_builtins_dict(
    be_obj: object = builtins.BaseException,
    exc_obj: object = builtins.Exception,
    ar_obj: object = builtins.ArithmeticError,
    oe_obj: object = builtins.OverflowError,
) -> object:
    """Helper to create a mock module with a populated dictionary."""
    mod = types.ModuleType("mock_builtins")
    raw_dict = _object_getattribute(mod, "__dict__")
    raw_dict["BaseException"] = be_obj
    raw_dict["Exception"] = exc_obj
    raw_dict["ArithmeticError"] = ar_obj
    raw_dict["OverflowError"] = oe_obj
    return mod


# ============================================================================
# Section 1: Literal-Derived Root of Trust & Four-Tier Anchor Capture
# ============================================================================


def test_literal_derived_root_primitives_authenticity() -> None:
    """Verify all root primitives derive from literals and match CPython types."""
    assert _tuple_type is tuple
    assert _type_type is type
    assert _object_root is object
    assert _dict_type is dict
    assert _object_getattribute is object.__getattribute__
    assert _dict_get is dict.get
    assert _type_flags is type.__dict__["__flags__"]
    assert _type_base is type.__dict__["__base__"]
    assert _type_mro is type.__dict__["__mro__"]
    assert _type_name is type.__dict__["__name__"]
    assert _type_qualname is type.__dict__["__qualname__"]
    assert _type_module is type.__dict__["__module__"]


def test_canonical_builtins_overflowerror_capture_success() -> None:
    """A/B/C/D/E/F: genuine capture, flags, and exact four-tier topology."""
    assert _CANONICAL_BUILTINS_OVERFLOWERROR is not None
    assert _CANONICAL_BUILTINS_OVERFLOWERROR is builtins.OverflowError

    oe_flags = _type_flags.__get__(_CANONICAL_BUILTINS_OVERFLOWERROR)
    assert (oe_flags & Py_TPFLAGS_HEAPTYPE) == 0
    assert (oe_flags & Py_TPFLAGS_IMMUTABLETYPE) != 0

    be = builtins.BaseException
    exc = builtins.Exception
    ar = builtins.ArithmeticError
    oe = builtins.OverflowError

    be_flags = _type_flags.__get__(be)
    assert (be_flags & Py_TPFLAGS_HEAPTYPE) == 0
    assert (be_flags & Py_TPFLAGS_IMMUTABLETYPE) != 0
    assert _type_module.__get__(be) == "builtins"
    assert _type_name.__get__(be) == "BaseException"
    assert _type_qualname.__get__(be) == "BaseException"
    assert _type_base.__get__(be) is _object_root
    assert _type_mro.__get__(be) == (be, _object_root)

    exc_flags = _type_flags.__get__(exc)
    assert (exc_flags & Py_TPFLAGS_HEAPTYPE) == 0
    assert (exc_flags & Py_TPFLAGS_IMMUTABLETYPE) != 0
    assert _type_module.__get__(exc) == "builtins"
    assert _type_name.__get__(exc) == "Exception"
    assert _type_qualname.__get__(exc) == "Exception"
    assert _type_base.__get__(exc) is be
    assert _type_mro.__get__(exc) == (exc, be, _object_root)

    ar_flags = _type_flags.__get__(ar)
    assert (ar_flags & Py_TPFLAGS_HEAPTYPE) == 0
    assert (ar_flags & Py_TPFLAGS_IMMUTABLETYPE) != 0
    assert _type_module.__get__(ar) == "builtins"
    assert _type_name.__get__(ar) == "ArithmeticError"
    assert _type_qualname.__get__(ar) == "ArithmeticError"
    assert _type_base.__get__(ar) is exc
    assert _type_mro.__get__(ar) == (ar, exc, be, _object_root)

    assert _type_base.__get__(oe) is ar
    assert _type_mro.__get__(oe) == (oe, ar, exc, be, _object_root)
    assert _type_module.__get__(oe) == "builtins"
    assert _type_name.__get__(oe) == "OverflowError"
    assert _type_qualname.__get__(oe) == "OverflowError"


def test_capture_bypasses_hostile_module_getattribute() -> None:
    """O: hostile module + genuine OverflowError; callbacks must be 0."""
    mod = HostileModuleWithGetattribute("mock_builtins")
    raw_dict = _object_getattribute(mod, "__dict__")
    raw_dict["BaseException"] = builtins.BaseException
    raw_dict["Exception"] = builtins.Exception
    raw_dict["ArithmeticError"] = builtins.ArithmeticError
    raw_dict["OverflowError"] = builtins.OverflowError

    result = _capture_canonical_builtins_overflowerror(mod)
    assert result is builtins.OverflowError
    getattribute_count, getattr_count, total_count = _hostile_callback_counts(mod)
    assert getattribute_count == 0
    assert getattr_count == 0
    assert total_count == 0


def test_capture_hostile_module_spoof_and_missing_fail_closed() -> None:
    """P/Q: hostile module + spoofed then missing leaf; callbacks must be 0."""
    mod = HostileModuleWithGetattribute("mock_builtins")
    raw_dict = _object_getattribute(mod, "__dict__")
    raw_dict["BaseException"] = builtins.BaseException
    raw_dict["Exception"] = builtins.Exception
    raw_dict["ArithmeticError"] = builtins.ArithmeticError

    class SpoofOverflowError(Exception):
        pass

    SpoofOverflowError.__module__ = "builtins"
    SpoofOverflowError.__name__ = "OverflowError"
    SpoofOverflowError.__qualname__ = "OverflowError"
    assert SpoofOverflowError is not builtins.OverflowError
    raw_dict["OverflowError"] = SpoofOverflowError

    spoof_result = _capture_canonical_builtins_overflowerror(mod)
    assert spoof_result is None
    getattribute_count, getattr_count, total_count = _hostile_callback_counts(mod)
    assert getattribute_count == 0
    assert getattr_count == 0
    assert total_count == 0

    del raw_dict["OverflowError"]
    missing_result = _capture_canonical_builtins_overflowerror(mod)
    assert missing_result is None
    getattribute_count, getattr_count, total_count = _hostile_callback_counts(mod)
    assert getattribute_count == 0
    assert getattr_count == 0
    assert total_count == 0


# ============================================================================
# Section 2: Hostile / Adversarial Startup Failure Scenarios (Fail-Closed)
# ============================================================================


def test_capture_scenario_01_non_module_or_no_dict() -> None:
    """N: fail-closed when builtins_mod has no valid __dict__."""
    assert _capture_canonical_builtins_overflowerror(None) is None
    assert _capture_canonical_builtins_overflowerror(12345) is None
    assert _capture_canonical_builtins_overflowerror("string") is None


def test_capture_scenario_02_dict_not_exact_dict_type() -> None:
    """Fail-closed when __dict__ is not exact dict type."""

    class FakeDictModule:
        pass

    mod = FakeDictModule()

    class CustomDict(dict):
        pass

    mod.__dict__ = CustomDict()  # type: ignore[assignment]
    assert _capture_canonical_builtins_overflowerror(mod) is None


def test_capture_scenario_03_baseexception_missing() -> None:
    """Fail-closed when BaseException is missing from module dict."""
    mod = _create_mock_builtins_dict(be_obj=None)
    raw_dict = _object_getattribute(mod, "__dict__")
    del raw_dict["BaseException"]
    assert _capture_canonical_builtins_overflowerror(mod) is None


def test_capture_scenario_04_baseexception_not_type_type() -> None:
    """Fail-closed when BaseException is an instance or function, not a type."""
    mod = _create_mock_builtins_dict(be_obj=HostileOverflowErrorCallable())
    assert _capture_canonical_builtins_overflowerror(mod) is None


def test_capture_scenario_05_baseexception_is_heap_type() -> None:
    """Fail-closed when BaseException is a heap-allocated user type."""

    class FakeBaseException(BaseException):
        pass

    mod = _create_mock_builtins_dict(be_obj=FakeBaseException)
    assert _capture_canonical_builtins_overflowerror(mod) is None


def test_capture_heap_overflowerror_subclass_fails_closed() -> None:
    """G: heap OverflowError subclass fails closed."""

    class HeapOverflow(OverflowError):
        pass

    mod = _create_mock_builtins_dict(oe_obj=HeapOverflow)
    assert _capture_canonical_builtins_overflowerror(mod) is None


def test_capture_spoofed_heap_module_name_qualname_fails_closed() -> None:
    """H: spoofed heap exception with builtins module/name/qualname fails closed."""
    spoof = type("OverflowError", (Exception,), {"__module__": "builtins"})
    spoof.__qualname__ = "OverflowError"
    mod = _create_mock_builtins_dict(oe_obj=spoof)
    assert _capture_canonical_builtins_overflowerror(mod) is None


def test_capture_arithmeticerror_sibling_fails_closed() -> None:
    """I: ArithmeticError sibling in the OverflowError slot fails closed."""
    mod = _create_mock_builtins_dict(oe_obj=builtins.ArithmeticError)
    assert _capture_canonical_builtins_overflowerror(mod) is None


def test_capture_valueerror_sibling_fails_closed() -> None:
    """J: ValueError sibling in the OverflowError slot fails closed."""
    mod = _create_mock_builtins_dict(oe_obj=builtins.ValueError)
    assert _capture_canonical_builtins_overflowerror(mod) is None


def test_capture_assertionerror_sibling_fails_closed() -> None:
    """K: AssertionError sibling in the OverflowError slot fails closed."""
    mod = _create_mock_builtins_dict(oe_obj=builtins.AssertionError)
    assert _capture_canonical_builtins_overflowerror(mod) is None


def test_capture_callable_object_fails_closed() -> None:
    """L: callable object in the OverflowError slot fails closed."""
    mod = _create_mock_builtins_dict(oe_obj=HostileOverflowErrorCallable())
    assert _capture_canonical_builtins_overflowerror(mod) is None


def test_capture_plain_function_fails_closed() -> None:
    """M: plain function in the OverflowError slot fails closed."""

    def fake(*args: object, **kwargs: object) -> None:
        raise HostileExecutionError("plain function executed")

    mod = _create_mock_builtins_dict(oe_obj=fake)
    assert _capture_canonical_builtins_overflowerror(mod) is None


def test_capture_none_and_missing_binding_fails_closed() -> None:
    """N: None or missing OverflowError binding fails closed."""
    mod = _create_mock_builtins_dict(oe_obj=None)
    raw_dict = _object_getattribute(mod, "__dict__")
    raw_dict["OverflowError"] = None
    assert _capture_canonical_builtins_overflowerror(mod) is None
    del raw_dict["OverflowError"]
    assert _capture_canonical_builtins_overflowerror(mod) is None


# ============================================================================
# Section 3: Two-Factor Authorization Quadrants (Factor A & Factor B)
# ============================================================================


def test_quadrant_1_factor_a_true_factor_b_true() -> None:
    """R: Factor A True and Factor B True (canonical identity)."""
    verdict = classify_callable(
        builtins.OverflowError,
        module="builtins",
        qualname="OverflowError",
        is_builtin_overflowerror_canonical=True,
    )
    assert verdict.category == "exact_identity_policy"
    assert verdict.rationale == "builtins.OverflowError-canonical-sentinel"
    assert verdict.source_available is False


def test_quadrant_2_factor_a_true_factor_b_false() -> None:
    """S: Factor A True but Factor B False (fake object)."""
    fake_oe = HostileOverflowErrorCallable()
    verdict = classify_callable(
        fake_oe,
        module="builtins",
        qualname="OverflowError",
        is_builtin_overflowerror_canonical=True,
    )
    assert verdict.category == "unresolved"
    assert verdict.rationale is None


def test_quadrant_3_factor_a_false_factor_b_true() -> None:
    """T: Factor A False (aliased/indirect) but Factor B True."""
    verdict = classify_callable(
        builtins.OverflowError,
        module="builtins",
        qualname="OverflowError",
        is_builtin_overflowerror_canonical=False,
    )
    assert verdict.category == "unresolved"
    assert verdict.rationale is None


def test_quadrant_4_factor_a_false_factor_b_false() -> None:
    """U: Factor A False and Factor B False."""
    fake_oe = HostileOverflowErrorCallable()
    verdict = classify_callable(
        fake_oe,
        module="some_module",
        qualname="fake_func",
        is_builtin_overflowerror_canonical=False,
    )
    assert verdict.category == "unresolved"
    assert verdict.rationale is None


# ============================================================================
# Section 4: AST Provenance Negative Controls (StaticWalker)
# ============================================================================


def test_walker_direct_overflowerror_authorized() -> None:
    """V: Direct OverflowError(...) with builtins lookup is authorized."""
    walker = StaticWalker()
    walker.walk(_sample_direct_overflowerror_fn, "sample_direct_overflowerror")

    records = [r for r in walker.call_records if r.callee_text == "OverflowError"]
    assert len(records) == 1
    rec = records[0]
    assert rec.resolution_mechanism == "builtins-lookup"
    assert rec.verdict.category == "exact_identity_policy"
    assert rec.verdict.rationale == "builtins.OverflowError-canonical-sentinel"


def test_walker_aliased_overflowerror_rejected_by_factor_a() -> None:
    """W: Local aliased oe_alias = OverflowError; oe_alias(...) is rejected."""
    walker = StaticWalker()
    walker.walk(_sample_aliased_overflowerror_fn, "sample_aliased_overflowerror")

    records = [r for r in walker.call_records if r.callee_text == "oe_alias"]
    assert len(records) == 1
    rec = records[0]
    assert rec.resolution_mechanism == "local-callable-alias"
    assert rec.verdict.category == "unresolved"
    assert rec.verdict.rationale is None


def test_walker_local_helper_overflowerror_not_sentinel() -> None:
    """X: Local nested def OverflowError(...) helper does not get sentinel rationale."""
    walker = StaticWalker()
    walker.walk(
        _sample_local_helper_overflowerror_fn, "sample_local_helper_overflowerror"
    )

    records = [r for r in walker.call_records if r.callee_text == "OverflowError"]
    assert len(records) == 1
    rec = records[0]
    assert rec.resolution_mechanism == "local-helper-inline"
    assert rec.verdict.category == "project_source_available"
    assert rec.verdict.rationale != "builtins.OverflowError-canonical-sentinel"


def test_walker_attribute_call_overflowerror_fails_closed() -> None:
    """Y: Method call obj.OverflowError(...) does not get sentinel rationale."""
    walker = StaticWalker()
    walker.walk(_sample_attr_overflowerror_fn, "sample_attr_overflowerror")

    records = [r for r in walker.call_records if "OverflowError" in r.callee_text]
    assert len(records) >= 1
    for rec in records:
        assert rec.verdict.rationale != "builtins.OverflowError-canonical-sentinel"


def test_walker_rebound_local_aliases_fail_closed() -> None:
    """Z: Local reassignments, deletions, walrus, and augmented assignments fail closed."""
    for fn, name in [
        (_sample_reassign_overflowerror_fn, "sample_reassign_overflowerror"),
        (_sample_del_overflowerror_fn, "sample_del_overflowerror"),
        (_sample_walrus_overflowerror_fn, "sample_walrus_overflowerror"),
        (_sample_augassign_overflowerror_fn, "sample_augassign_overflowerror"),
    ]:
        walker = StaticWalker()
        walker.walk(fn, name)
        for rec in walker.call_records:
            assert rec.verdict.rationale != "builtins.OverflowError-canonical-sentinel"


def test_post_startup_monkeypatching_mitigation() -> None:
    """AA: If builtins.OverflowError is faked, Factor B rejects the fake object."""
    fake_oe = HostileOverflowErrorCallable()
    verdict = classify_callable(
        fake_oe,
        module="builtins",
        qualname="OverflowError",
        is_builtin_overflowerror_canonical=True,
    )
    assert verdict.category == "unresolved"
    assert verdict.rationale is None


def test_walker_non_execution_safety_with_hostile_overflowerror() -> None:
    """AB: Hostile OverflowError callable placed in globals is never executed."""
    hostile = HostileOverflowErrorCallable()
    scope_fn = types.FunctionType(
        _sample_direct_overflowerror_fn.__code__,
        {"OverflowError": hostile, "__name__": "_sample_direct_overflowerror_fn"},
        name="_sample_direct_overflowerror_fn",
    )
    walker = StaticWalker()
    walker.walk(scope_fn, "sample_hostile_overflowerror")

    records = [r for r in walker.call_records if r.callee_text == "OverflowError"]
    assert len(records) == 1
    assert records[0].verdict.category == "unresolved"


# ============================================================================
# Section 5: Global Policy Table Isolation (87 entries, v2026-09-05.1)
# ============================================================================


def test_exact_identity_policy_isolation_and_size() -> None:
    """AC/AD: Verify EXACT_IDENTITY_POLICY strictly at 87 entries v2026-09-05.1."""
    assert len(EXACT_IDENTITY_POLICY) == 87
    assert EXACT_IDENTITY_POLICY_VERSION == "2026-09-05.1"
    assert "builtins.OverflowError" not in EXACT_IDENTITY_POLICY
    assert "OverflowError" not in EXACT_IDENTITY_POLICY
    assert ("builtins", "OverflowError") not in EXACT_IDENTITY_POLICY
    assert "builtins.AssertionError" not in EXACT_IDENTITY_POLICY
    assert "builtins.ValueError" not in EXACT_IDENTITY_POLICY
    assert "builtins.ord" not in EXACT_IDENTITY_POLICY
    assert "builtins.id" not in EXACT_IDENTITY_POLICY
    assert "builtins.chr" not in EXACT_IDENTITY_POLICY
    assert "builtins.OverflowError.__new__" in EXACT_IDENTITY_POLICY
    assert "builtins.OverflowError.__init__" in EXACT_IDENTITY_POLICY


# ============================================================================
# Section 6: Whole-System Trace Audit & Metric Invariants
# ============================================================================


def test_overflowerror_calls_exact_resolution_accounting() -> None:
    """AE: Verify N=2 direct OverflowError calls resolve via canonical sentinel."""
    tr = run_trace()
    explicit_calls = tr.explicit_calls

    assert len(explicit_calls) == 7420

    oe_calls = [
        c
        for c in explicit_calls
        if c.callee_text == "OverflowError"
        and c.verdict.rationale == "builtins.OverflowError-canonical-sentinel"
    ]
    assert len(oe_calls) == 2

    for c in oe_calls:
        assert c.verdict.category == "exact_identity_policy"
        assert c.verdict.rationale == "builtins.OverflowError-canonical-sentinel"
        assert c.resolution_mechanism == "builtins-lookup"
        assert c.verdict.module == "builtins"
        assert c.verdict.qualname == "OverflowError"


def test_prior_sentinels_and_siblings_do_not_move() -> None:
    """Preserve AssertionError=2, ValueError=12, ord=10; siblings get no OE rationale."""
    tr = run_trace()
    explicit_calls = tr.explicit_calls

    ae_calls = [
        c
        for c in explicit_calls
        if c.verdict.rationale == "builtins.AssertionError-canonical-sentinel"
    ]
    assert len(ae_calls) == 2
    for c in ae_calls:
        assert c.resolution_mechanism == "builtins-lookup"

    ve_calls = [
        c
        for c in explicit_calls
        if c.verdict.rationale == "builtins.ValueError-canonical-sentinel"
    ]
    assert len(ve_calls) == 12

    ord_calls = [
        c
        for c in explicit_calls
        if c.verdict.rationale == "builtins.ord-canonical-sentinel"
    ]
    assert len(ord_calls) == 10
    assert sum(1 for c in ord_calls if c.resolution_mechanism == "builtins-lookup") == 4
    assert (
        sum(1 for c in ord_calls if c.resolution_mechanism == "local-callable-alias")
        == 6
    )

    oe_rationale = "builtins.OverflowError-canonical-sentinel"
    sibling_callees = {
        "AssertionError",
        "ValueError",
        "RuntimeError",
        "ArithmeticError",
        "TypeError",
        "AttributeError",
        "NotImplementedError",
        "OSError",
        "SyntaxError",
        "KeyError",
        "Exception",
        "BaseException",
        "ord",
        "id",
        "chr",
        "int",
        "type",
        "range",
        "hasattr",
        "iter",
        "next",
        "issubclass",
        "list",
    }
    for c in explicit_calls:
        if c.callee_text in sibling_callees:
            assert c.verdict.rationale != oe_rationale


def test_whole_system_audit_invariants() -> None:
    """AF: Verify Task 38.20 whole-system counters: 3768 + 3130 + 5 + 517 = 7420."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    report = run_full_audit(repo_root)
    data = report.data

    identity_buckets = data["identity_resolution_buckets"]

    assert data["calls_total"] == 7420
    assert data["calls_unresolved"] == 517
    assert identity_buckets["project_source_available"] == 3768
    assert identity_buckets["exact_identity_policy"] == 3130
    assert identity_buckets["forbidden"] == 5
    assert identity_buckets["unresolved"] == 517
    assert data["nodes_total"] == 268
    assert data["nodes_unresolved"] == 16
    assert data["roots_traced"] == 25

    implicit = data["implicit_dispatch"]
    assert implicit["syntax_sites_total"] == 11405
    assert implicit["resolved_non_descriptor_exclusion"] == 4407
    assert implicit["dispatch_candidates_total"] == 7413
    assert implicit["resolved_dispatches"] == 124
    assert implicit["unresolved_dispatches"] == 7289

    assert data["module_state_candidates_total"] == 523
    assert data["module_state_unexplained"] == 0

    assert (
        identity_buckets["project_source_available"]
        + identity_buckets["exact_identity_policy"]
        + identity_buckets["forbidden"]
        + identity_buckets["unresolved"]
        == 7420
    )
    assert data["calls_unresolved"] == identity_buckets["unresolved"]

    assert data["negative_controls_total"] == 10
    assert data["negative_controls_detected"] == 10
    assert data["exit_code"] == 1
    assert EXACT_IDENTITY_POLICY_VERSION == "2026-09-05.1"
