"""Unit tests for Task 38.17 Phase A/B3 Canonical builtins.ValueError Sentinel.

Validates the literal-derived primitive root-of-trust contract (B2G), three-tier
anchor authentication (BaseException -> Exception -> ValueError), CPython 3.12.13
type flags, two-factor authorization separation (Factor A: provenance, Factor B:
identity), hostile startup failure modes (fail-closed to None), AST provenance
negative controls, global policy table isolation (strictly 87 entries
v2026-09-05.1), and whole-system accounting.
"""

from __future__ import annotations

import builtins
import types
from pathlib import Path

from audit_harness.identity import (
    _CANONICAL_BUILTINS_VALUEERROR,
    EXACT_IDENTITY_POLICY,
    EXACT_IDENTITY_POLICY_VERSION,
    Py_TPFLAGS_HEAPTYPE,
    Py_TPFLAGS_IMMUTABLETYPE,
    _capture_canonical_builtins_valueerror,
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


class HostileValueErrorCallable:
    """Hostile mock object pretending to be ValueError."""

    def __call__(self, *args: object, **kwargs: object) -> object:
        raise HostileExecutionError("HostileValueErrorCallable.__call__() executed!")


class HostileModuleWithGetattribute(types.ModuleType):
    """Mock module with hostile __getattribute__ and __getattr__ hooks."""

    def __init__(self, name: str = "mock_builtins") -> None:
        super().__init__(name)

    def __getattribute__(self, name: str) -> object:
        raise HostileExecutionError(f"Hostile __getattribute__({name!r}) invoked!")

    def __getattr__(self, name: str) -> object:
        raise HostileExecutionError(f"Hostile __getattr__({name!r}) invoked!")


# Sample test functions for StaticWalker AST testing
def _sample_direct_valueerror_fn() -> None:
    raise ValueError("Invalid configuration parameter")


def _sample_aliased_valueerror_fn() -> None:
    ve_alias = ValueError
    raise ve_alias("Aliased ValueError call")


def _sample_reassign_valueerror_fn() -> None:
    _ve = ValueError
    _ve = TypeError
    raise _ve("reassigned")


def _sample_del_valueerror_fn() -> None:
    _ve = ValueError
    del _ve


def _sample_walrus_valueerror_fn() -> None:
    _ve = ValueError
    if _ve := TypeError:  # type: ignore[assignment]
        raise _ve("walrus")


def _sample_augassign_valueerror_fn() -> None:
    _ve = ValueError
    _ve += 1  # type: ignore[operator]


def _sample_local_helper_valueerror_fn() -> None:
    def ValueError(msg: str) -> Exception:
        return RuntimeError(f"Local helper: {msg}")

    raise ValueError("shadowed")


class _SampleClassWithValueErrorMethod:
    def ValueError(self, msg: str) -> None:
        pass


def _sample_attr_valueerror_fn() -> None:
    obj = _SampleClassWithValueErrorMethod()
    obj.ValueError("method call")


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


def test_canonical_builtins_valueerror_capture_success() -> None:
    """Verify startup capture successfully resolves canonical builtins.ValueError."""
    assert _CANONICAL_BUILTINS_VALUEERROR is not None
    assert _CANONICAL_BUILTINS_VALUEERROR is builtins.ValueError

    # Verify type flags on genuine builtins.ValueError
    ve_flags = _type_flags.__get__(_CANONICAL_BUILTINS_VALUEERROR)
    assert (ve_flags & Py_TPFLAGS_HEAPTYPE) == 0
    assert (ve_flags & Py_TPFLAGS_IMMUTABLETYPE) != 0

    # Verify hierarchy
    assert _type_base.__get__(_CANONICAL_BUILTINS_VALUEERROR) is builtins.Exception
    assert _type_base.__get__(builtins.Exception) is builtins.BaseException
    assert _type_base.__get__(builtins.BaseException) is _object_root


def test_capture_bypasses_hostile_module_getattribute() -> None:
    """Verify capture uses descriptors to bypass hostile hooks."""
    mod = HostileModuleWithGetattribute("mock_builtins")
    # Safely populate __dict__ using _object_getattribute
    raw_dict = _object_getattribute(mod, "__dict__")
    raw_dict["BaseException"] = builtins.BaseException
    raw_dict["Exception"] = builtins.Exception
    raw_dict["ValueError"] = builtins.ValueError

    # Capture must succeed without triggering HostileModuleWithGetattribute hooks
    result = _capture_canonical_builtins_valueerror(mod)
    assert result is builtins.ValueError


# ============================================================================
# Section 2: 18 Hostile / Adversarial Startup Failure Scenarios (Fail-Closed)
# ============================================================================


def _create_mock_builtins_dict(
    be_obj: object = builtins.BaseException,
    exc_obj: object = builtins.Exception,
    ve_obj: object = builtins.ValueError,
) -> object:
    """Helper to create a mock module with a populated dictionary."""
    mod = types.ModuleType("mock_builtins")
    raw_dict = _object_getattribute(mod, "__dict__")
    raw_dict["BaseException"] = be_obj
    raw_dict["Exception"] = exc_obj
    raw_dict["ValueError"] = ve_obj
    return mod


def test_capture_scenario_01_non_module_or_no_dict() -> None:
    """Fail-closed when builtins_mod has no valid __dict__."""
    assert _capture_canonical_builtins_valueerror(None) is None
    assert _capture_canonical_builtins_valueerror(12345) is None
    assert _capture_canonical_builtins_valueerror("string") is None


def test_capture_scenario_02_dict_not_exact_dict_type() -> None:
    """Fail-closed when __dict__ is not exact dict type."""

    class FakeDictModule:
        pass

    mod = FakeDictModule()

    # Test if raw_dict.__class__ is not _dict_type
    class CustomDict(dict):
        pass

    # Replace module __dict__ descriptor or object
    # In CPython module __dict__ is a dict, but if someone proxies it:
    mod.__dict__ = CustomDict()  # type: ignore[assignment]
    assert _capture_canonical_builtins_valueerror(mod) is None


def test_capture_scenario_03_baseexception_missing() -> None:
    """Fail-closed when BaseException is missing from module dict."""
    mod = _create_mock_builtins_dict(be_obj=None)
    raw_dict = _object_getattribute(mod, "__dict__")
    del raw_dict["BaseException"]
    assert _capture_canonical_builtins_valueerror(mod) is None


def test_capture_scenario_04_baseexception_not_type_type() -> None:
    """Fail-closed when BaseException is an instance or function, not a type."""
    mod = _create_mock_builtins_dict(be_obj=HostileValueErrorCallable())
    assert _capture_canonical_builtins_valueerror(mod) is None


def test_capture_scenario_05_baseexception_is_heap_type() -> None:
    """Fail-closed when BaseException is a heap-allocated user type."""

    class FakeBaseException(BaseException):
        pass

    mod = _create_mock_builtins_dict(be_obj=FakeBaseException)
    assert _capture_canonical_builtins_valueerror(mod) is None


def test_capture_scenario_06_baseexception_wrong_module() -> None:
    """Fail-closed when BaseException has __module__ != 'builtins'."""
    mod = _create_mock_builtins_dict(
        be_obj=Exception
    )  # Exception is builtins, but let's test custom static type or mismatch

    # If we create a type with wrong module:
    class SubBE(BaseException):
        __module__ = "other_module"

    mod = _create_mock_builtins_dict(be_obj=SubBE)
    assert _capture_canonical_builtins_valueerror(mod) is None


def test_capture_scenario_07_baseexception_wrong_name() -> None:
    """Fail-closed when BaseException has wrong __name__ or __qualname__."""
    mod = _create_mock_builtins_dict(be_obj=builtins.TypeError)
    assert _capture_canonical_builtins_valueerror(mod) is None


def test_capture_scenario_08_baseexception_wrong_base() -> None:
    """Fail-closed when BaseException has base other than object."""
    mod = _create_mock_builtins_dict(be_obj=builtins.Exception)
    assert _capture_canonical_builtins_valueerror(mod) is None


def test_capture_scenario_09_baseexception_wrong_mro() -> None:
    """Fail-closed when BaseException has unexpected MRO."""
    mod = _create_mock_builtins_dict(be_obj=builtins.ArithmeticError)
    assert _capture_canonical_builtins_valueerror(mod) is None


def test_capture_scenario_10_exception_missing() -> None:
    """Fail-closed when Exception is missing from module dict."""
    mod = _create_mock_builtins_dict()
    raw_dict = _object_getattribute(mod, "__dict__")
    del raw_dict["Exception"]
    assert _capture_canonical_builtins_valueerror(mod) is None


def test_capture_scenario_11_exception_not_type_type() -> None:
    """Fail-closed when Exception is not a type."""
    mod = _create_mock_builtins_dict(exc_obj="not_a_type")
    assert _capture_canonical_builtins_valueerror(mod) is None


def test_capture_scenario_12_exception_is_heap_type() -> None:
    """Fail-closed when Exception is a heap type."""

    class FakeException(Exception):
        pass

    mod = _create_mock_builtins_dict(exc_obj=FakeException)
    assert _capture_canonical_builtins_valueerror(mod) is None


def test_capture_scenario_13_exception_wrong_base() -> None:
    """Fail-closed when Exception base is not the verified BaseException."""
    mod = _create_mock_builtins_dict(exc_obj=builtins.BaseException)
    assert _capture_canonical_builtins_valueerror(mod) is None


def test_capture_scenario_14_valueerror_missing() -> None:
    """Fail-closed when ValueError is missing from module dict."""
    mod = _create_mock_builtins_dict()
    raw_dict = _object_getattribute(mod, "__dict__")
    del raw_dict["ValueError"]
    assert _capture_canonical_builtins_valueerror(mod) is None


def test_capture_scenario_15_valueerror_not_type_type() -> None:
    """Fail-closed when ValueError is not a type."""
    mod = _create_mock_builtins_dict(ve_obj=HostileValueErrorCallable())
    assert _capture_canonical_builtins_valueerror(mod) is None


def test_capture_scenario_16_valueerror_is_heap_type() -> None:
    """Fail-closed when ValueError is a heap type."""

    class FakeValueError(ValueError):
        pass

    mod = _create_mock_builtins_dict(ve_obj=FakeValueError)
    assert _capture_canonical_builtins_valueerror(mod) is None


def test_capture_scenario_17_valueerror_wrong_name_or_module() -> None:
    """Fail-closed when ValueError has wrong name or module."""
    mod = _create_mock_builtins_dict(ve_obj=builtins.TypeError)
    assert _capture_canonical_builtins_valueerror(mod) is None


def test_capture_scenario_18_valueerror_wrong_base_or_mro() -> None:
    """Fail-closed when ValueError base is not the authenticated Exception."""
    mod = _create_mock_builtins_dict(ve_obj=builtins.KeyError)
    assert _capture_canonical_builtins_valueerror(mod) is None


# ============================================================================
# Section 3: Two-Factor Authorization Quadrants (Factor A & Factor B)
# ============================================================================


def test_quadrant_1_factor_a_true_factor_b_true() -> None:
    """Q1: Factor A True and Factor B True (canonical identity).

    Resolves to exact_identity_policy with rationale
    'builtins.ValueError-canonical-sentinel'.
    """
    verdict = classify_callable(
        builtins.ValueError,
        module="builtins",
        qualname="ValueError",
        is_builtin_valueerror_canonical=True,
    )
    assert verdict.category == "exact_identity_policy"
    assert verdict.rationale == "builtins.ValueError-canonical-sentinel"
    assert verdict.source_available is False


def test_quadrant_2_factor_a_true_factor_b_false() -> None:
    """Q2: Factor A True but Factor B False (fake object).

    Must fail closed to unresolved.
    """
    fake_ve = HostileValueErrorCallable()
    verdict = classify_callable(
        fake_ve,
        module="builtins",
        qualname="ValueError",
        is_builtin_valueerror_canonical=True,
    )
    assert verdict.category == "unresolved"
    assert verdict.rationale is None


def test_quadrant_3_factor_a_false_factor_b_true() -> None:
    """Q3: Factor A False (aliased/indirect) but Factor B True (ValueError).

    Must fail closed to unresolved.
    """
    verdict = classify_callable(
        builtins.ValueError,
        module="builtins",
        qualname="ValueError",
        is_builtin_valueerror_canonical=False,
    )
    assert verdict.category == "unresolved"
    assert verdict.rationale is None


def test_quadrant_4_factor_a_false_factor_b_false() -> None:
    """Q4: Factor A False and Factor B False.
    Must fail closed to unresolved.
    """
    fake_ve = HostileValueErrorCallable()
    verdict = classify_callable(
        fake_ve,
        module="some_module",
        qualname="fake_func",
        is_builtin_valueerror_canonical=False,
    )
    assert verdict.category == "unresolved"
    assert verdict.rationale is None


# ============================================================================
# Section 4: AST Provenance Negative Controls (StaticWalker)
# ============================================================================


def test_walker_direct_valueerror_authorized() -> None:
    """Direct ValueError(...) with builtins lookup is authorized."""
    walker = StaticWalker()
    walker.walk(_sample_direct_valueerror_fn, "sample_direct_valueerror")

    records = [r for r in walker.call_records if r.callee_text == "ValueError"]
    assert len(records) == 1
    rec = records[0]
    assert rec.resolution_mechanism == "builtins-lookup"
    assert rec.verdict.category == "exact_identity_policy"
    assert rec.verdict.rationale == "builtins.ValueError-canonical-sentinel"


def test_walker_aliased_valueerror_rejected_by_factor_a() -> None:
    """Local aliased ve_alias = ValueError; ve_alias(...) is rejected by Factor A."""
    walker = StaticWalker()
    walker.walk(_sample_aliased_valueerror_fn, "sample_aliased_valueerror")

    records = [r for r in walker.call_records if r.callee_text == "ve_alias"]
    assert len(records) == 1
    rec = records[0]
    assert rec.resolution_mechanism == "local-callable-alias"
    assert rec.verdict.category == "unresolved"
    assert rec.verdict.rationale is None


def test_walker_local_helper_valueerror_not_sentinel() -> None:
    """Local nested def ValueError(...) helper resolves as project source."""
    walker = StaticWalker()
    walker.walk(_sample_local_helper_valueerror_fn, "sample_local_helper_valueerror")

    records = [r for r in walker.call_records if r.callee_text == "ValueError"]
    assert len(records) == 1
    rec = records[0]
    assert rec.resolution_mechanism == "local-helper-inline"
    assert rec.verdict.category == "project_source_available"
    assert rec.verdict.rationale != "builtins.ValueError-canonical-sentinel"


def test_walker_attribute_call_valueerror_fails_closed() -> None:
    """Method call obj.ValueError(...) fails closed."""
    walker = StaticWalker()
    walker.walk(_sample_attr_valueerror_fn, "sample_attr_valueerror")

    records = [r for r in walker.call_records if "ValueError" in r.callee_text]
    assert len(records) >= 1
    for rec in records:
        assert rec.verdict.rationale != "builtins.ValueError-canonical-sentinel"


def test_walker_rebound_local_aliases_fail_closed() -> None:
    """Local reassignments, deletions, walrus, and augmented assignments fail closed."""
    for fn, name in [
        (_sample_reassign_valueerror_fn, "sample_reassign_valueerror"),
        (_sample_del_valueerror_fn, "sample_del_valueerror"),
        (_sample_walrus_valueerror_fn, "sample_walrus_valueerror"),
        (_sample_augassign_valueerror_fn, "sample_augassign_valueerror"),
    ]:
        walker = StaticWalker()
        walker.walk(fn, name)
        for rec in walker.call_records:
            assert rec.verdict.rationale != "builtins.ValueError-canonical-sentinel"


def test_post_startup_monkeypatching_mitigation() -> None:
    """If builtins.ValueError monkeypatched, Factor B rejects fake object."""
    fake_ve = HostileValueErrorCallable()
    # Direct classify_callable with fake object even if Factor A claims True
    verdict = classify_callable(
        fake_ve,
        module="builtins",
        qualname="ValueError",
        is_builtin_valueerror_canonical=True,
    )
    assert verdict.category == "unresolved"
    assert verdict.rationale is None


def test_walker_non_execution_safety_with_hostile_valueerror() -> None:
    """Hostile ValueError callable placed in globals is never executed."""
    hostile = HostileValueErrorCallable()
    scope_fn = types.FunctionType(
        _sample_direct_valueerror_fn.__code__,
        {"ValueError": hostile, "__name__": "_sample_direct_valueerror_fn"},
        name="_sample_direct_valueerror_fn",
    )
    walker = StaticWalker()
    # Must not raise HostileExecutionError
    walker.walk(scope_fn, "sample_hostile_valueerror")

    records = [r for r in walker.call_records if r.callee_text == "ValueError"]
    assert len(records) == 1
    assert records[0].verdict.category == "unresolved"


# ============================================================================
# Section 5: Global Policy Table Invariance (87 entries, v2026-09-05.1)
# ============================================================================


def test_exact_identity_policy_isolation_and_size() -> None:
    """Verify EXACT_IDENTITY_POLICY strictly at 87 entries v2026-09-05.1."""
    assert len(EXACT_IDENTITY_POLICY) == 87
    assert EXACT_IDENTITY_POLICY_VERSION == "2026-09-05.1"
    assert "builtins.ValueError" not in EXACT_IDENTITY_POLICY
    assert "ValueError" not in EXACT_IDENTITY_POLICY
    assert ("builtins", "ValueError") not in EXACT_IDENTITY_POLICY


# ============================================================================
# Section 6: Whole-System Trace Audit & Metric Invariants
# ============================================================================


def test_valueerror_calls_exact_resolution_accounting() -> None:
    """Verify N=12 direct ValueError calls resolve via canonical sentinel."""
    tr = run_trace()
    explicit_calls = tr.explicit_calls

    # 1. Total explicit calls remains 7420
    assert len(explicit_calls) == 7420

    # 2. Extract calls that call ValueError
    ve_calls = [
        c
        for c in explicit_calls
        if c.callee_text == "ValueError"
        and c.verdict.rationale == "builtins.ValueError-canonical-sentinel"
    ]
    assert len(ve_calls) == 12

    # All 12 must resolve to exact_identity_policy with builtins-lookup mechanism
    for c in ve_calls:
        assert c.verdict.category == "exact_identity_policy"
        assert c.verdict.rationale == "builtins.ValueError-canonical-sentinel"
        assert c.resolution_mechanism == "builtins-lookup"


def test_whole_system_audit_invariants() -> None:
    """Verify the whole-system audit counters match the governed Task 38.17 targets."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    report = run_full_audit(repo_root)
    data = report.data

    identity_buckets = data["identity_resolution_buckets"]

    # Target metrics for Task 38.17 post-state
    assert data["calls_total"] == 7420
    assert data["calls_unresolved"] == 521
    assert identity_buckets["project_source_available"] == 3768
    assert identity_buckets["exact_identity_policy"] == 3126
    assert identity_buckets["forbidden"] == 5
    assert identity_buckets["unresolved"] == 521

    # Invariant: 3768 + 3126 + 5 + 521 = 7420
    assert (
        identity_buckets["project_source_available"]
        + identity_buckets["exact_identity_policy"]
        + identity_buckets["forbidden"]
        + identity_buckets["unresolved"]
        == 7420
    )

    # Negative controls must all be detected
    assert data["negative_controls_total"] == 10
    assert data["negative_controls_detected"] == 10
