"""Unit tests for Task 38.19 Phase A/B Canonical builtins.AssertionError Sentinel.

Validates the literal-derived primitive root-of-trust contract reused from
Task 38.17, three-tier anchor authentication (BaseException -> Exception ->
AssertionError), CPython 3.12.13 type flags, two-factor authorization
separation (Factor A: provenance, Factor B: identity), hostile startup
failure modes (fail-closed to None), AST provenance negative controls,
global policy table isolation (strictly 87 entries v2026-09-05.1), N=2
direct builtins-lookup movement, and whole-system accounting.
"""

from __future__ import annotations

import builtins
import types
from pathlib import Path

from audit_harness.identity import (
    _CANONICAL_BUILTINS_ASSERTIONERROR,
    EXACT_IDENTITY_POLICY,
    EXACT_IDENTITY_POLICY_VERSION,
    Py_TPFLAGS_HEAPTYPE,
    Py_TPFLAGS_IMMUTABLETYPE,
    _capture_canonical_builtins_assertionerror,
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


class HostileAssertionErrorCallable:
    """Hostile mock object pretending to be AssertionError."""

    def __call__(self, *args: object, **kwargs: object) -> object:
        raise HostileExecutionError(
            "HostileAssertionErrorCallable.__call__() executed!"
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


def _sample_direct_assertionerror_fn() -> None:
    raise AssertionError("unsupported quantifier")


def _sample_aliased_assertionerror_fn() -> None:
    ae_alias = AssertionError
    raise ae_alias("Aliased AssertionError call")


def _sample_reassign_assertionerror_fn() -> None:
    _ae = AssertionError
    _ae = TypeError
    raise _ae("reassigned")


def _sample_del_assertionerror_fn() -> None:
    _ae = AssertionError
    del _ae


def _sample_walrus_assertionerror_fn() -> None:
    _ae = AssertionError
    if _ae := TypeError:  # type: ignore[assignment]
        raise _ae("walrus")


def _sample_augassign_assertionerror_fn() -> None:
    _ae = AssertionError
    _ae += 1  # type: ignore[operator]


def _sample_local_helper_assertionerror_fn() -> None:
    def AssertionError(msg: str) -> Exception:
        return RuntimeError(f"Local helper: {msg}")

    raise AssertionError("shadowed")


class _SampleClassWithAssertionErrorMethod:
    def AssertionError(self, msg: str) -> None:
        pass


def _sample_attr_assertionerror_fn() -> None:
    obj = _SampleClassWithAssertionErrorMethod()
    obj.AssertionError("method call")


def _create_mock_builtins_dict(
    be_obj: object = builtins.BaseException,
    exc_obj: object = builtins.Exception,
    ae_obj: object = builtins.AssertionError,
) -> object:
    """Helper to create a mock module with a populated dictionary."""
    mod = types.ModuleType("mock_builtins")
    raw_dict = _object_getattribute(mod, "__dict__")
    raw_dict["BaseException"] = be_obj
    raw_dict["Exception"] = exc_obj
    raw_dict["AssertionError"] = ae_obj
    return mod


# ============================================================================
# Section 1: Literal-Derived Root of Trust & Three-Tier Anchor Capture
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


def test_canonical_builtins_assertionerror_capture_success() -> None:
    """Verify startup capture successfully resolves canonical builtins.AssertionError."""
    assert _CANONICAL_BUILTINS_ASSERTIONERROR is not None
    assert _CANONICAL_BUILTINS_ASSERTIONERROR is builtins.AssertionError

    ae_flags = _type_flags.__get__(_CANONICAL_BUILTINS_ASSERTIONERROR)
    assert (ae_flags & Py_TPFLAGS_HEAPTYPE) == 0
    assert (ae_flags & Py_TPFLAGS_IMMUTABLETYPE) != 0

    assert (
        _type_base.__get__(_CANONICAL_BUILTINS_ASSERTIONERROR) is builtins.Exception
    )
    assert _type_base.__get__(builtins.Exception) is builtins.BaseException
    assert _type_base.__get__(builtins.BaseException) is _object_root
    assert _type_mro.__get__(_CANONICAL_BUILTINS_ASSERTIONERROR) == (
        builtins.AssertionError,
        builtins.Exception,
        builtins.BaseException,
        _object_root,
    )
    assert _type_module.__get__(_CANONICAL_BUILTINS_ASSERTIONERROR) == "builtins"
    assert _type_name.__get__(_CANONICAL_BUILTINS_ASSERTIONERROR) == "AssertionError"
    assert (
        _type_qualname.__get__(_CANONICAL_BUILTINS_ASSERTIONERROR) == "AssertionError"
    )


def test_capture_bypasses_hostile_module_getattribute() -> None:
    """K: hostile module + genuine AssertionError; callbacks must be 0."""
    mod = HostileModuleWithGetattribute("mock_builtins")
    raw_dict = _object_getattribute(mod, "__dict__")
    raw_dict["BaseException"] = builtins.BaseException
    raw_dict["Exception"] = builtins.Exception
    raw_dict["AssertionError"] = builtins.AssertionError

    result = _capture_canonical_builtins_assertionerror(mod)
    assert result is builtins.AssertionError
    getattribute_count, getattr_count, total_count = _hostile_callback_counts(mod)
    assert getattribute_count == 0
    assert getattr_count == 0
    assert total_count == 0
    print(
        f"genuine: getattribute={getattribute_count} "
        f"getattr={getattr_count} total={total_count}"
    )


def test_capture_hostile_module_spoof_and_missing_fail_closed() -> None:
    """L/M: hostile module + spoofed then missing leaf; callbacks must be 0."""
    mod = HostileModuleWithGetattribute("mock_builtins")
    raw_dict = _object_getattribute(mod, "__dict__")
    raw_dict["BaseException"] = builtins.BaseException
    raw_dict["Exception"] = builtins.Exception

    class SpoofAssertionError(Exception):
        pass

    SpoofAssertionError.__module__ = "builtins"
    SpoofAssertionError.__name__ = "AssertionError"
    SpoofAssertionError.__qualname__ = "AssertionError"
    assert SpoofAssertionError is not builtins.AssertionError
    raw_dict["AssertionError"] = SpoofAssertionError

    spoof_result = _capture_canonical_builtins_assertionerror(mod)
    assert spoof_result is None
    getattribute_count, getattr_count, total_count = _hostile_callback_counts(mod)
    assert getattribute_count == 0
    assert getattr_count == 0
    assert total_count == 0
    print(
        f"spoof: getattribute={getattribute_count} "
        f"getattr={getattr_count} total={total_count}"
    )

    del raw_dict["AssertionError"]
    missing_result = _capture_canonical_builtins_assertionerror(mod)
    assert missing_result is None
    getattribute_count, getattr_count, total_count = _hostile_callback_counts(mod)
    assert getattribute_count == 0
    assert getattr_count == 0
    assert total_count == 0
    print(
        f"missing: getattribute={getattribute_count} "
        f"getattr={getattr_count} total={total_count}"
    )


# ============================================================================
# Section 2: Hostile / Adversarial Startup Failure Scenarios (Fail-Closed)
# ============================================================================


def test_capture_scenario_01_non_module_or_no_dict() -> None:
    """Fail-closed when builtins_mod has no valid __dict__."""
    assert _capture_canonical_builtins_assertionerror(None) is None
    assert _capture_canonical_builtins_assertionerror(12345) is None
    assert _capture_canonical_builtins_assertionerror("string") is None


def test_capture_scenario_02_dict_not_exact_dict_type() -> None:
    """Fail-closed when __dict__ is not exact dict type."""

    class FakeDictModule:
        pass

    mod = FakeDictModule()

    class CustomDict(dict):
        pass

    mod.__dict__ = CustomDict()  # type: ignore[assignment]
    assert _capture_canonical_builtins_assertionerror(mod) is None


def test_capture_scenario_03_baseexception_missing() -> None:
    """Fail-closed when BaseException is missing from module dict."""
    mod = _create_mock_builtins_dict(be_obj=None)
    raw_dict = _object_getattribute(mod, "__dict__")
    del raw_dict["BaseException"]
    assert _capture_canonical_builtins_assertionerror(mod) is None


def test_capture_scenario_04_baseexception_not_type_type() -> None:
    """Fail-closed when BaseException is an instance or function, not a type."""
    mod = _create_mock_builtins_dict(be_obj=HostileAssertionErrorCallable())
    assert _capture_canonical_builtins_assertionerror(mod) is None


def test_capture_scenario_05_baseexception_is_heap_type() -> None:
    """Fail-closed when BaseException is a heap-allocated user type."""

    class FakeBaseException(BaseException):
        pass

    mod = _create_mock_builtins_dict(be_obj=FakeBaseException)
    assert _capture_canonical_builtins_assertionerror(mod) is None


def test_capture_scenario_06_baseexception_wrong_module() -> None:
    """Fail-closed when BaseException has __module__ != 'builtins'."""

    class SubBE(BaseException):
        __module__ = "other_module"

    mod = _create_mock_builtins_dict(be_obj=SubBE)
    assert _capture_canonical_builtins_assertionerror(mod) is None


def test_capture_scenario_07_baseexception_wrong_name() -> None:
    """Fail-closed when BaseException has wrong __name__ or __qualname__."""
    mod = _create_mock_builtins_dict(be_obj=builtins.TypeError)
    assert _capture_canonical_builtins_assertionerror(mod) is None


def test_capture_scenario_08_baseexception_wrong_base() -> None:
    """Fail-closed when BaseException has base other than object."""
    mod = _create_mock_builtins_dict(be_obj=builtins.Exception)
    assert _capture_canonical_builtins_assertionerror(mod) is None


def test_capture_scenario_09_baseexception_wrong_mro() -> None:
    """Fail-closed when BaseException has unexpected MRO."""
    mod = _create_mock_builtins_dict(be_obj=builtins.ArithmeticError)
    assert _capture_canonical_builtins_assertionerror(mod) is None


def test_capture_scenario_10_exception_missing() -> None:
    """Fail-closed when Exception is missing from module dict."""
    mod = _create_mock_builtins_dict()
    raw_dict = _object_getattribute(mod, "__dict__")
    del raw_dict["Exception"]
    assert _capture_canonical_builtins_assertionerror(mod) is None


def test_capture_scenario_11_exception_not_type_type() -> None:
    """Fail-closed when Exception is not a type."""
    mod = _create_mock_builtins_dict(exc_obj="not_a_type")
    assert _capture_canonical_builtins_assertionerror(mod) is None


def test_capture_scenario_12_exception_is_heap_type() -> None:
    """Fail-closed when Exception is a heap type."""

    class FakeException(Exception):
        pass

    mod = _create_mock_builtins_dict(exc_obj=FakeException)
    assert _capture_canonical_builtins_assertionerror(mod) is None


def test_capture_scenario_13_exception_wrong_base() -> None:
    """Fail-closed when Exception base is not the verified BaseException."""
    mod = _create_mock_builtins_dict(exc_obj=builtins.BaseException)
    assert _capture_canonical_builtins_assertionerror(mod) is None


def test_capture_scenario_14_assertionerror_missing() -> None:
    """Fail-closed when AssertionError is missing from module dict."""
    mod = _create_mock_builtins_dict()
    raw_dict = _object_getattribute(mod, "__dict__")
    del raw_dict["AssertionError"]
    assert _capture_canonical_builtins_assertionerror(mod) is None


def test_capture_scenario_15_assertionerror_not_type_type() -> None:
    """Fail-closed when AssertionError is not a type."""
    mod = _create_mock_builtins_dict(ae_obj=HostileAssertionErrorCallable())
    assert _capture_canonical_builtins_assertionerror(mod) is None


def test_capture_scenario_16_assertionerror_is_heap_type() -> None:
    """Fail-closed when AssertionError is a heap type."""

    class FakeAssertionError(AssertionError):
        pass

    mod = _create_mock_builtins_dict(ae_obj=FakeAssertionError)
    assert _capture_canonical_builtins_assertionerror(mod) is None


def test_capture_scenario_17_assertionerror_wrong_name_or_module() -> None:
    """Fail-closed when AssertionError has wrong name or module."""
    mod = _create_mock_builtins_dict(ae_obj=builtins.TypeError)
    assert _capture_canonical_builtins_assertionerror(mod) is None


def test_capture_scenario_18_assertionerror_wrong_base_or_mro() -> None:
    """Fail-closed when AssertionError base is not the authenticated Exception."""
    mod = _create_mock_builtins_dict(ae_obj=builtins.KeyError)
    assert _capture_canonical_builtins_assertionerror(mod) is None


def test_capture_scenario_19_sibling_valueerror_spoof() -> None:
    """Fail-closed when the AssertionError slot holds genuine ValueError."""
    mod = _create_mock_builtins_dict(ae_obj=builtins.ValueError)
    assert _capture_canonical_builtins_assertionerror(mod) is None


def test_capture_scenario_20_plain_function_spoof() -> None:
    """Fail-closed when the AssertionError slot holds a plain function."""

    def fake(*args: object, **kwargs: object) -> None:
        raise HostileExecutionError("plain function executed")

    mod = _create_mock_builtins_dict(ae_obj=fake)
    assert _capture_canonical_builtins_assertionerror(mod) is None


# ============================================================================
# Section 3: Two-Factor Authorization Quadrants (Factor A & Factor B)
# ============================================================================


def test_quadrant_1_factor_a_true_factor_b_true() -> None:
    """Q1: Factor A True and Factor B True (canonical identity)."""
    verdict = classify_callable(
        builtins.AssertionError,
        module="builtins",
        qualname="AssertionError",
        is_builtin_assertionerror_canonical=True,
    )
    assert verdict.category == "exact_identity_policy"
    assert verdict.rationale == "builtins.AssertionError-canonical-sentinel"
    assert verdict.source_available is False


def test_quadrant_2_factor_a_true_factor_b_false() -> None:
    """Q2: Factor A True but Factor B False (fake object)."""
    fake_ae = HostileAssertionErrorCallable()
    verdict = classify_callable(
        fake_ae,
        module="builtins",
        qualname="AssertionError",
        is_builtin_assertionerror_canonical=True,
    )
    assert verdict.category == "unresolved"
    assert verdict.rationale is None


def test_quadrant_3_factor_a_false_factor_b_true() -> None:
    """Q3: Factor A False (aliased/indirect) but Factor B True."""
    verdict = classify_callable(
        builtins.AssertionError,
        module="builtins",
        qualname="AssertionError",
        is_builtin_assertionerror_canonical=False,
    )
    assert verdict.category == "unresolved"
    assert verdict.rationale is None


def test_quadrant_4_factor_a_false_factor_b_false() -> None:
    """Q4: Factor A False and Factor B False."""
    fake_ae = HostileAssertionErrorCallable()
    verdict = classify_callable(
        fake_ae,
        module="some_module",
        qualname="fake_func",
        is_builtin_assertionerror_canonical=False,
    )
    assert verdict.category == "unresolved"
    assert verdict.rationale is None


# ============================================================================
# Section 4: AST Provenance Negative Controls (StaticWalker)
# ============================================================================


def test_walker_direct_assertionerror_authorized() -> None:
    """Direct AssertionError(...) with builtins lookup is authorized."""
    walker = StaticWalker()
    walker.walk(_sample_direct_assertionerror_fn, "sample_direct_assertionerror")

    records = [r for r in walker.call_records if r.callee_text == "AssertionError"]
    assert len(records) == 1
    rec = records[0]
    assert rec.resolution_mechanism == "builtins-lookup"
    assert rec.verdict.category == "exact_identity_policy"
    assert rec.verdict.rationale == "builtins.AssertionError-canonical-sentinel"


def test_walker_aliased_assertionerror_rejected_by_factor_a() -> None:
    """Local aliased ae_alias = AssertionError; ae_alias(...) is rejected."""
    walker = StaticWalker()
    walker.walk(_sample_aliased_assertionerror_fn, "sample_aliased_assertionerror")

    records = [r for r in walker.call_records if r.callee_text == "ae_alias"]
    assert len(records) == 1
    rec = records[0]
    assert rec.resolution_mechanism == "local-callable-alias"
    assert rec.verdict.category == "unresolved"
    assert rec.verdict.rationale is None


def test_walker_local_helper_assertionerror_not_sentinel() -> None:
    """Local nested def AssertionError(...) helper resolves as project source."""
    walker = StaticWalker()
    walker.walk(
        _sample_local_helper_assertionerror_fn, "sample_local_helper_assertionerror"
    )

    records = [r for r in walker.call_records if r.callee_text == "AssertionError"]
    assert len(records) == 1
    rec = records[0]
    assert rec.resolution_mechanism == "local-helper-inline"
    assert rec.verdict.category == "project_source_available"
    assert rec.verdict.rationale != "builtins.AssertionError-canonical-sentinel"


def test_walker_attribute_call_assertionerror_fails_closed() -> None:
    """Method call obj.AssertionError(...) fails closed."""
    walker = StaticWalker()
    walker.walk(_sample_attr_assertionerror_fn, "sample_attr_assertionerror")

    records = [r for r in walker.call_records if "AssertionError" in r.callee_text]
    assert len(records) >= 1
    for rec in records:
        assert rec.verdict.rationale != "builtins.AssertionError-canonical-sentinel"


def test_walker_rebound_local_aliases_fail_closed() -> None:
    """Local reassignments, deletions, walrus, and augmented assignments fail closed."""
    for fn, name in [
        (_sample_reassign_assertionerror_fn, "sample_reassign_assertionerror"),
        (_sample_del_assertionerror_fn, "sample_del_assertionerror"),
        (_sample_walrus_assertionerror_fn, "sample_walrus_assertionerror"),
        (_sample_augassign_assertionerror_fn, "sample_augassign_assertionerror"),
    ]:
        walker = StaticWalker()
        walker.walk(fn, name)
        for rec in walker.call_records:
            assert rec.verdict.rationale != "builtins.AssertionError-canonical-sentinel"


def test_post_startup_monkeypatching_mitigation() -> None:
    """If builtins.AssertionError is faked, Factor B rejects the fake object."""
    fake_ae = HostileAssertionErrorCallable()
    verdict = classify_callable(
        fake_ae,
        module="builtins",
        qualname="AssertionError",
        is_builtin_assertionerror_canonical=True,
    )
    assert verdict.category == "unresolved"
    assert verdict.rationale is None


def test_walker_non_execution_safety_with_hostile_assertionerror() -> None:
    """Hostile AssertionError callable placed in globals is never executed."""
    hostile = HostileAssertionErrorCallable()
    scope_fn = types.FunctionType(
        _sample_direct_assertionerror_fn.__code__,
        {"AssertionError": hostile, "__name__": "_sample_direct_assertionerror_fn"},
        name="_sample_direct_assertionerror_fn",
    )
    walker = StaticWalker()
    walker.walk(scope_fn, "sample_hostile_assertionerror")

    records = [r for r in walker.call_records if r.callee_text == "AssertionError"]
    assert len(records) == 1
    assert records[0].verdict.category == "unresolved"


# ============================================================================
# Section 5: Global Policy Table Isolation (87 entries, v2026-09-05.1)
# ============================================================================


def test_exact_identity_policy_isolation_and_size() -> None:
    """Verify EXACT_IDENTITY_POLICY strictly at 87 entries v2026-09-05.1."""
    assert len(EXACT_IDENTITY_POLICY) == 87
    assert EXACT_IDENTITY_POLICY_VERSION == "2026-09-05.1"
    assert "builtins.AssertionError" not in EXACT_IDENTITY_POLICY
    assert "AssertionError" not in EXACT_IDENTITY_POLICY
    assert ("builtins", "AssertionError") not in EXACT_IDENTITY_POLICY
    assert "builtins.AssertionError.__new__" in EXACT_IDENTITY_POLICY
    assert "builtins.AssertionError.__init__" in EXACT_IDENTITY_POLICY


# ============================================================================
# Section 6: Whole-System Trace Audit & Metric Invariants
# ============================================================================


def test_assertionerror_calls_exact_resolution_accounting() -> None:
    """Verify N=2 direct AssertionError calls resolve via canonical sentinel."""
    tr = run_trace()
    explicit_calls = tr.explicit_calls

    assert len(explicit_calls) == 7420

    ae_calls = [
        c
        for c in explicit_calls
        if c.callee_text == "AssertionError"
        and c.verdict.rationale == "builtins.AssertionError-canonical-sentinel"
    ]
    assert len(ae_calls) == 2

    for c in ae_calls:
        assert c.verdict.category == "exact_identity_policy"
        assert c.verdict.rationale == "builtins.AssertionError-canonical-sentinel"
        assert c.resolution_mechanism == "builtins-lookup"


def test_sibling_families_do_not_move() -> None:
    """Ord, ValueError, and unauthorized siblings must not inherit this sentinel."""
    tr = run_trace()
    explicit_calls = tr.explicit_calls

    ord_calls = [
        c
        for c in explicit_calls
        if c.verdict.rationale == "builtins.ord-canonical-sentinel"
    ]
    assert len(ord_calls) == 10

    ve_calls = [
        c
        for c in explicit_calls
        if c.verdict.rationale == "builtins.ValueError-canonical-sentinel"
    ]
    assert len(ve_calls) == 12

    ae_rationale = "builtins.AssertionError-canonical-sentinel"
    for c in explicit_calls:
        if c.callee_text in ("chr", "id", "RuntimeError", "ord", "ValueError"):
            assert c.verdict.rationale != ae_rationale


def test_whole_system_audit_invariants() -> None:
    """Verify Task 38.19 whole-system counters: 3768 + 3128 + 5 + 519 = 7420."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    report = run_full_audit(repo_root)
    data = report.data

    identity_buckets = data["identity_resolution_buckets"]

    assert data["calls_total"] == 7420
    assert data["calls_unresolved"] == 519
    assert identity_buckets["project_source_available"] == 3768
    assert identity_buckets["exact_identity_policy"] == 3128
    assert identity_buckets["forbidden"] == 5
    assert identity_buckets["unresolved"] == 519
    assert data["nodes_total"] == 268
    assert data["nodes_unresolved"] == 16

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
