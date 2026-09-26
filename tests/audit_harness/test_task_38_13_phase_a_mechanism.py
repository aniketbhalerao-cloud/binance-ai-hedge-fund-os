"""Task 38.13 Phase A dedicated regression test suite.

Verifies:
1. Proof obligations A–G for the receiver-constrained
   `inspect-signature-parameters-mappingproxy-items` proof mechanism.
2. Non-execution safety across hostile subjects, metaclasses, and descriptors.
3. Specialization-key class-identity non-execution safety.
4. Dual-grain accounting (specialization grain vs. trace-record grain).
"""

from __future__ import annotations

import ast
import inspect
import types
from collections.abc import Callable

import pytest

from audit_harness.identity import EXACT_IDENTITY_POLICY, classify_callable
from audit_harness.trace import (
    StaticWalker,
    _is_safe_metaclass,
    _is_safe_subject,
    run_trace,
)
from core.container import ServiceContainer


# ============================================================================
# Section 1: Non-execution Safety Primitives & Obligations A–G
# ============================================================================


class HostileExecutionError(Exception):
    """Raised if hostile user code executes during static analysis."""


class MetaWithGetattribute(type):
    def __getattribute__(cls, name: str) -> object:
        if name in ("__module__", "__qualname__", "__signature__", "__name__"):
            raise HostileExecutionError(f"MetaWithGetattribute.__getattribute__({name})")
        return super().__getattribute__(name)


class InheritedMetaGetattribute(MetaWithGetattribute):
    pass


class MetaWithGetattr(type):
    def __getattr__(cls, name: str) -> object:
        raise HostileExecutionError(f"MetaWithGetattr.__getattr__({name})")


class MetaWithCall(type):
    def __call__(cls, *args: object, **kwargs: object) -> object:
        raise HostileExecutionError("MetaWithCall.__call__()")


class MetaWithSignature(type):
    __signature__ = inspect.Signature()


class HostileSubjectWithSignature:
    __signature__ = inspect.Signature()


class HostileSubjectWithNoneSignature:
    __signature__ = None


class HostileBoolSubject:
    def __bool__(self) -> bool:
        raise HostileExecutionError("HostileBoolSubject.__bool__()")


class HostileLenSubject:
    def __len__(self) -> int:
        raise HostileExecutionError("HostileLenSubject.__len__()")


class HostileDescriptor:
    def __get__(self, instance: object, owner: type | None = None) -> object:
        raise HostileExecutionError("HostileDescriptor.__get__()")


class SubjectWithHostileDescriptor:
    items = HostileDescriptor()


def test_is_safe_metaclass_rejects_hostile_hooks() -> None:
    assert _is_safe_metaclass(type) is True

    # Hostile metaclass variations
    assert _is_safe_metaclass(MetaWithGetattribute) is False
    assert _is_safe_metaclass(InheritedMetaGetattribute) is False
    assert _is_safe_metaclass(MetaWithGetattr) is False
    assert _is_safe_metaclass(MetaWithCall) is False
    assert _is_safe_metaclass(MetaWithSignature) is False

    # Non-type
    assert _is_safe_metaclass("not a type") is False  # type: ignore[arg-type]


def test_is_safe_subject_rejects_hostile_signatures_and_metaclasses() -> None:
    class SafeClass:
        pass

    assert _is_safe_subject(SafeClass) is True
    assert _is_safe_subject(int) is True
    assert _is_safe_subject(ServiceContainer) is True

    # Hostile subject __signature__
    assert _is_safe_subject(HostileSubjectWithSignature) is False
    assert _is_safe_subject(HostileSubjectWithNoneSignature) is False

    # Classes with hostile metaclasses
    class ClassWithHostileMetaGetattribute(metaclass=MetaWithGetattribute):
        pass

    class ClassWithInheritedHostileMeta(metaclass=InheritedMetaGetattribute):
        pass

    class ClassWithHostileMetaGetattr(metaclass=MetaWithGetattr):
        pass

    class ClassWithHostileMetaCall(metaclass=MetaWithCall):
        pass

    class ClassWithHostileMetaSignature(metaclass=MetaWithSignature):
        pass

    assert _is_safe_subject(ClassWithHostileMetaGetattribute) is False
    assert _is_safe_subject(ClassWithInheritedHostileMeta) is False
    assert _is_safe_subject(ClassWithHostileMetaGetattr) is False
    assert _is_safe_subject(ClassWithHostileMetaCall) is False
    assert _is_safe_subject(ClassWithHostileMetaSignature) is False

    # Non-type
    assert _is_safe_subject(SafeClass()) is False  # type: ignore[arg-type]


def test_truthiness_non_execution_across_task_38_13_primitives() -> None:
    """Verify that hostile __bool__ and __len__ dunder hooks are never executed
    in Task 38.13 specialization key calculation or proof obligations."""
    walker = StaticWalker()

    hostile_bool = HostileBoolSubject()
    hostile_len = HostileLenSubject()

    # 1. Specialization key computation does not execute __bool__ or __len__
    key = walker._specialization_key(
        owner_class=None,
        forced_locals={"b": hostile_bool, "l": hostile_len},
        forced_param_hints={"hb": hostile_bool, "hl": hostile_len},  # type: ignore[dict-item]
    )
    assert len(key) == 4

    # 2. _prove_inspect_signature_parameters_mappingproxy_items with hostile subject in loc/g
    code = """
def test_fn(cls):
    sig = inspect.signature(cls)
    for name, param in sig.parameters.items():
        pass
"""
    tree = ast.parse(code)
    call_node = None
    for n in ast.walk(tree):
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "items"
        ):
            call_node = n
            break
    assert call_node is not None

    # Hostile bool/len in loc and g
    loc_hostile = {"cls": hostile_bool, "inspect": inspect, "b": hostile_bool}
    g_hostile = {"inspect": inspect, "l": hostile_len}
    assert (
        walker._prove_inspect_signature_parameters_mappingproxy_items(
            call_node,
            tree,
            types.MappingProxyType.items,
            g_hostile,
            loc_hostile,
            {"sig": inspect.Signature},
        )
        is False
    )

    # Hostile bool/len as inspect module or inspect.signature
    loc_hostile_inspect = {"cls": ServiceContainer, "inspect": hostile_bool}
    assert (
        walker._prove_inspect_signature_parameters_mappingproxy_items(
            call_node,
            tree,
            types.MappingProxyType.items,
            {},
            loc_hostile_inspect,
            {"sig": inspect.Signature},
        )
        is False
    )


def test_proof_obligations_a_through_g_breakdowns() -> None:
    """Explicitly verify each Proof Obligation A through G in isolation."""
    walker = StaticWalker()

    # Valid template AST
    code_template = """
def valid_fn(target_cls):
    sig = inspect.signature(target_cls)
    return sig.parameters.items()
"""
    tree = ast.parse(code_template)
    call_node = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "items"
    ][0]

    # Baseline valid resolution
    g_valid = {"inspect": inspect}
    loc_valid = {"target_cls": ServiceContainer, "inspect": inspect}
    local_types_valid = {"sig": inspect.Signature}

    assert (
        walker._prove_inspect_signature_parameters_mappingproxy_items(
            call_node, tree, g_valid, loc_valid, local_types_valid
        )
        is True
    )

    # Obligation A: Callee is not inspect.signature -> False
    code_non_sig = """
def invalid_fn(target_cls):
    sig = other_func(target_cls)
    return sig.parameters.items()
"""
    tree_non_sig = ast.parse(code_non_sig)
    call_non_sig = [
        n
        for n in ast.walk(tree_non_sig)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "items"
    ][0]
    assert (
        walker._prove_inspect_signature_parameters_mappingproxy_items(
            call_non_sig,
            tree_non_sig,
            types.MappingProxyType.items,
            {"other_func": lambda x: None},
            {"target_cls": ServiceContainer},
            {"sig": inspect.Signature},
        )
        is False
    )

    # Obligation A: Multiple writes to sig variable (write-once violation) -> False
    code_multiple_assign = """
def invalid_fn(target_cls):
    sig = inspect.signature(target_cls)
    sig = inspect.signature(target_cls)
    return sig.parameters.items()
"""
    tree_multi = ast.parse(code_multiple_assign)
    call_multi = [
        n
        for n in ast.walk(tree_multi)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "items"
    ][0]
    assert (
        walker._prove_inspect_signature_parameters_mappingproxy_items(
            call_multi,
            tree_multi,
            types.MappingProxyType.items,
            g_valid,
            loc_valid,
            local_types_valid,
        )
        is False
    )

    # Obligation A: Re-assignment via delete or walrus -> False
    code_del = """
def invalid_fn(target_cls):
    sig = inspect.signature(target_cls)
    del sig
    return None
"""
    tree_del = ast.parse(code_del)
    assert (
        walker._prove_inspect_signature_parameters_mappingproxy_items(
            call_node,
            tree_del,
            types.MappingProxyType.items,
            g_valid,
            loc_valid,
            local_types_valid,
        )
        is False
    )

    # Obligation B: Type of sig is not inspect.Signature -> False
    assert (
        walker._prove_inspect_signature_parameters_mappingproxy_items(
            call_node,
            tree,
            types.MappingProxyType.items,
            g_valid,
            loc_valid,
            {"sig": dict},  # type: ignore[dict-item]
        )
        is False
    )

    # Obligation C: Hostile subject __signature__ or hostile metaclass -> False
    assert (
        walker._prove_inspect_signature_parameters_mappingproxy_items(
            call_node,
            tree,
            types.MappingProxyType.items,
            g_valid,
            {"target_cls": HostileSubjectWithSignature, "inspect": inspect},
            local_types_valid,
        )
        is False
    )

    # Obligation E: Target is not types.MappingProxyType.items -> False
    assert (
        walker._prove_inspect_signature_parameters_mappingproxy_items(
            call_node,
            tree,
            types.MappingProxyType.keys,
            g_valid,
            loc_valid,
            local_types_valid,
        )
        is False
    )
    assert (
        walker._prove_inspect_signature_parameters_mappingproxy_items(
            call_node,
            tree,
            dict.items,
            g_valid,
            loc_valid,
            local_types_valid,
        )
        is False
    )

    # Obligation F: Call has arguments or keywords -> False
    code_with_args = """
def invalid_fn(target_cls):
    sig = inspect.signature(target_cls)
    return sig.parameters.items(1)
"""
    tree_with_args = ast.parse(code_with_args)
    call_with_args = [
        n
        for n in ast.walk(tree_with_args)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "items"
    ][0]
    assert (
        walker._prove_inspect_signature_parameters_mappingproxy_items(
            call_with_args,
            tree_with_args,
            types.MappingProxyType.items,
            g_valid,
            loc_valid,
            local_types_valid,
        )
        is False
    )

    # Obligation G: Fail closed on missing subject or unknown names
    assert (
        walker._prove_inspect_signature_parameters_mappingproxy_items(
            call_node, tree, types.MappingProxyType.items, {}, {}, local_types_valid
        )
        is False
    )


# ============================================================================
# Section 2: Specialization-Key Non-Execution Safety
# ============================================================================


def test_specialization_key_does_not_execute_hostile_metaclass_getattribute() -> None:
    class ClassWithHostileMeta(metaclass=MetaWithGetattribute):
        pass

    walker = StaticWalker()
    # Must compute key without triggering HostileExecutionError
    key = walker._specialization_key(
        owner_class=ClassWithHostileMeta,
        forced_locals={"target": ClassWithHostileMeta},
        forced_param_hints={"cls": ClassWithHostileMeta},
    )
    assert len(key) == 3
    assert key[0][0] == "owner"
    assert "ClassWithHostileMeta" in key[0][2]


def test_specialization_key_does_not_execute_inherited_hostile_metaclass() -> None:
    class ClassWithInheritedHostileMeta(metaclass=InheritedMetaGetattribute):
        pass

    walker = StaticWalker()
    key = walker._specialization_key(
        owner_class=ClassWithInheritedHostileMeta,
        forced_locals={"target": ClassWithInheritedHostileMeta},
        forced_param_hints={"cls": ClassWithInheritedHostileMeta},
    )
    assert len(key) == 3
    assert "ClassWithInheritedHostileMeta" in key[0][2]


def test_specialization_key_normal_class_unchanged() -> None:
    walker = StaticWalker()
    key1 = walker._specialization_key(
        owner_class=ServiceContainer,
        forced_locals={"target": ServiceContainer},
        forced_param_hints={"cls": ServiceContainer},
    )
    expected_mod_qn = f"{ServiceContainer.__module__}.{ServiceContainer.__qualname__}"
    assert key1 == (
        ("owner", "", expected_mod_qn),
        ("local", "target", expected_mod_qn),
        ("hint", "cls", expected_mod_qn),
    )


# ============================================================================
# Section 3: Identity Layer Classification
# ============================================================================


def test_classify_callable_mappingproxy_items_flag() -> None:
    # When flag is False, MappingProxyType.items without global policy entry is unresolved
    v_unresolved = classify_callable(
        types.MappingProxyType({}).items,
        module="builtins",
        qualname="mappingproxy.items",
        is_inspect_signature_parameters_mappingproxy_items=False,
    )
    assert v_unresolved.category == "unresolved"

    # When flag is True, it receives exact_identity_policy with the specific rationale
    v_resolved = classify_callable(
        types.MappingProxyType({}).items,
        module="builtins",
        qualname="mappingproxy.items",
        is_inspect_signature_parameters_mappingproxy_items=True,
    )
    assert v_resolved.category == "exact_identity_policy"
    assert v_resolved.rationale == "inspect-signature-parameters-mappingproxy-items"


def test_exact_identity_policy_isolation_and_size() -> None:
    """Verify that EXACT_IDENTITY_POLICY remains strictly at 87 entries
    and mappingproxy.items is never added to the global table."""
    assert len(EXACT_IDENTITY_POLICY) == 87
    assert "builtins.mappingproxy.items" not in EXACT_IDENTITY_POLICY
    assert "mappingproxy.items" not in EXACT_IDENTITY_POLICY
    assert ("builtins", "mappingproxy.items") not in EXACT_IDENTITY_POLICY


# ============================================================================
# Section 4: Dual-Grain Residual Accounting & Trace Audit Verification
# ============================================================================


def test_trace_dual_grain_accounting_and_audit_totals() -> None:
    tr = run_trace()

    # 1. Explicit-call population (invariant across Task 38.15).
    # Live whole-system unresolved / exact_identity_policy totals are
    # Task 38.15 census (543 / 3104), not a Task 38.13 live invariant.
    explicit_calls = tr.explicit_calls
    assert len(explicit_calls) == 7420

    # 2. Identity-resolution buckets that remain Task 38.13-invariant.
    buckets = {
        "project_source_available": sum(
            1 for c in explicit_calls if c.verdict.category == "project_source_available"
        ),
        "forbidden": sum(
            1 for c in explicit_calls if c.verdict.category == "forbidden"
        ),
    }
    assert buckets["project_source_available"] == 3768
    assert buckets["forbidden"] == 5

    # 3. Verify MappingProxy.items calls across all records:
    # Specialization grain: 115 calls total -> 114 resolved, 1 unresolved (unspecialized root)
    # Trace-record grain (including implicit descriptors): 230 records total ->
    # 114 exact_identity_policy, 116 unresolved (115 descriptor + 1 unspecialized root)
    build_items_explicit = [
        c
        for c in explicit_calls
        if "signature.parameters.items" in c.callee_text
        or "parameters.items" in c.callee_text
    ]
    assert len(build_items_explicit) == 115
    resolved_explicit = [
        c for c in build_items_explicit if c.verdict.category == "exact_identity_policy"
    ]
    unresolved_explicit = [
        c for c in build_items_explicit if c.verdict.category == "unresolved"
    ]
    assert len(resolved_explicit) == 114
    assert len(unresolved_explicit) == 1

    # Check all records (explicit + implicit descriptors)
    build_items_all = [
        c
        for c in tr.calls
        if "signature.parameters.items" in c.callee_text
        or "parameters.items" in c.callee_text
    ]
    assert len(build_items_all) == 230
    resolved_all = [
        c for c in build_items_all if c.verdict.category == "exact_identity_policy"
    ]
    unresolved_all = [
        c for c in build_items_all if c.verdict.category == "unresolved"
    ]
    assert len(resolved_all) == 114
    assert len(unresolved_all) == 116
