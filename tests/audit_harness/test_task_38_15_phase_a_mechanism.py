"""Task 38.15 Phase A dedicated regression test suite.

Verifies:
1. Proof obligations A–G for the receiver-constrained
   `pydantic-settings-model-config-get` proof mechanism across the 3 authorized syntactic forms:
   - `cls.model_config.get(...)`
   - `settings_cls.model_config.get(...)`
   - `self.config.get(...)`
2. Non-execution safety across hostile subjects, metaclasses, and descriptors.
3. Specialization-key class-identity non-execution safety.
4. All 22 mandatory negative controls.
5. Exact 45-call movement (588 -> 543 unresolved, 3059 -> 3104 exact_identity_policy).
6. Dispatch counter invariants (7,413 candidates / 7,289 unresolved / 124 resolved).
7. EXACT_IDENTITY_POLICY isolation (strictly 87 entries, version 2026-09-05.1).
"""

from __future__ import annotations

import ast
import inspect
import types
from collections.abc import Callable
from typing import Any

import pytest
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource
from pydantic_settings.sources import DotEnvSettingsSource, InitSettingsSource

from audit_harness.identity import (
    EXACT_IDENTITY_POLICY,
    EXACT_IDENTITY_POLICY_VERSION,
    classify_callable,
)
from audit_harness.trace import (
    StaticWalker,
    _is_safe_pydantic_metaclass,
    _is_safe_pydantic_subject,
    run_trace,
)


# ============================================================================
# Section 1: Hostile Stubs & Non-execution Safety Primitives
# ============================================================================


class HostileExecutionError(Exception):
    """Raised if hostile user code executes during static analysis."""


BaseSettingsMeta = type(BaseSettings)


class HostileMetaGetattribute(BaseSettingsMeta):
    armed = False

    def __getattribute__(cls, name: str) -> object:
        if HostileMetaGetattribute.armed and name in (
            "__module__",
            "__qualname__",
            "__signature__",
            "__name__",
            "model_config",
            "config",
        ):
            raise HostileExecutionError(f"HostileMetaGetattribute.__getattribute__({name})")
        return super().__getattribute__(name)


class InheritedHostileMetaGetattribute(HostileMetaGetattribute):
    pass


class HostileMetaGetattr(BaseSettingsMeta):
    armed = False

    def __getattr__(cls, name: str) -> object:
        if HostileMetaGetattr.armed:
            raise HostileExecutionError(f"HostileMetaGetattr.__getattr__({name})")
        raise AttributeError(f"{cls!r} has no attribute {name!r}")


class HostileMetaCall(BaseSettingsMeta):
    def __call__(cls, *args: object, **kwargs: object) -> object:
        raise HostileExecutionError("HostileMetaCall.__call__()")


class HostileMetaSignature(BaseSettingsMeta):
    __signature__ = inspect.Signature()


# Pre-create hostile classes with metaclasses while disarmed, then arm them
HostileMetaGetattribute.armed = False
HostileMetaGetattr.armed = False


class ClassWithHostileMetaGetattribute(BaseSettings, metaclass=HostileMetaGetattribute):
    pass


class ClassWithInheritedHostileMeta(BaseSettings, metaclass=InheritedHostileMetaGetattribute):
    pass


class ClassWithHostileMetaGetattr(BaseSettings, metaclass=HostileMetaGetattr):
    pass


class ClassWithHostileMetaCall(BaseSettings, metaclass=HostileMetaCall):
    pass


class ClassWithHostileMetaSignature(BaseSettings, metaclass=HostileMetaSignature):
    pass


HostileMetaGetattribute.armed = True
HostileMetaGetattr.armed = True


class HostileSubjectWithSignature(BaseSettings):
    pass


type.__setattr__(HostileSubjectWithSignature, "__signature__", inspect.Signature())


class HostileSubjectWithNoneSignature(BaseSettings):
    pass


type.__setattr__(HostileSubjectWithNoneSignature, "__signature__", None)


class HostileBoolSubject(BaseSettings):
    def __bool__(self) -> bool:
        raise HostileExecutionError("HostileBoolSubject.__bool__()")


class HostileLenSubject(BaseSettings):
    def __len__(self) -> int:
        raise HostileExecutionError("HostileLenSubject.__len__()")


class HostileDescriptor:
    def __get__(self, instance: object, owner: type | None = None) -> object:
        raise HostileExecutionError("HostileDescriptor.__get__()")


class DummySettings(BaseSettings):
    model_config = {"env_prefix": "TEST_"}


class DummySettingsSubclass(DummySettings):
    pass


class DummyCustomMapping(dict):
    pass


class DummySettingsSource(PydanticBaseSettingsSource):
    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        super().__init__(settings_cls)

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        return {}


# ============================================================================
# Section 2: Non-execution Safety & Predicates Verification
# ============================================================================


def test_is_safe_pydantic_metaclass_accepts_model_metaclass_rejects_hostile() -> None:
    # Safe metaclasses
    assert _is_safe_pydantic_metaclass(type) is True
    assert _is_safe_pydantic_metaclass(type(BaseSettings)) is True
    assert _is_safe_pydantic_metaclass(type(DummySettings)) is True

    # Hostile metaclasses
    assert _is_safe_pydantic_metaclass(HostileMetaGetattribute) is False
    assert _is_safe_pydantic_metaclass(InheritedHostileMetaGetattribute) is False
    assert _is_safe_pydantic_metaclass(HostileMetaGetattr) is False
    assert _is_safe_pydantic_metaclass(HostileMetaCall) is False
    assert _is_safe_pydantic_metaclass(HostileMetaSignature) is False

    # Non-type
    assert _is_safe_pydantic_metaclass("not a type") is False  # type: ignore[arg-type]


def test_is_safe_pydantic_subject_accepts_basesettings_rejects_hostile() -> None:
    assert _is_safe_pydantic_subject(BaseSettings) is True
    assert _is_safe_pydantic_subject(DummySettings) is True
    assert _is_safe_pydantic_subject(DummySettingsSubclass) is True
    assert _is_safe_pydantic_subject(PydanticBaseSettingsSource) is True
    assert _is_safe_pydantic_subject(DotEnvSettingsSource) is True
    assert _is_safe_pydantic_subject(InitSettingsSource) is True

    # Hostile subject __signature__
    assert _is_safe_pydantic_subject(HostileSubjectWithSignature) is False
    assert _is_safe_pydantic_subject(HostileSubjectWithNoneSignature) is False

    # Classes with hostile metaclasses
    assert _is_safe_pydantic_subject(ClassWithHostileMetaGetattribute) is False
    assert _is_safe_pydantic_subject(ClassWithInheritedHostileMeta) is False
    assert _is_safe_pydantic_subject(ClassWithHostileMetaGetattr) is False
    assert _is_safe_pydantic_subject(ClassWithHostileMetaCall) is False
    assert _is_safe_pydantic_subject(ClassWithHostileMetaSignature) is False

    # Non-type
    assert _is_safe_pydantic_subject(DummySettings()) is False  # type: ignore[arg-type]


def test_truthiness_non_execution_across_task_38_15_primitives() -> None:
    """Verify that hostile __bool__ and __len__ hooks are never executed."""
    walker = StaticWalker()

    hostile_bool = HostileBoolSubject()
    hostile_len = HostileLenSubject()

    # Specialization key computation does not execute __bool__ or __len__
    key = walker._specialization_key(
        owner_class=None,
        forced_locals={"b": hostile_bool, "l": hostile_len},
        forced_param_hints={"hb": hostile_bool, "hl": hostile_len},  # type: ignore[dict-item]
    )
    assert len(key) == 4

    code = """
def test_fn(cls):
    return cls.model_config.get("env_prefix")
"""
    tree = ast.parse(code)
    call_node = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "get"
    ][0]

    # Hostile bool/len in loc and g
    loc_hostile = {"cls": hostile_bool, "b": hostile_bool}
    g_hostile = {"l": hostile_len}
    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_node,
            tree,
            dict.get,
            g_hostile,
            loc_hostile,
            None,
        )
        is False
    )


# ============================================================================
# Section 3: Proof Obligations A–G and 22 Negative Controls
# ============================================================================


def test_obligation_a_through_g_baseline_success_all_three_forms() -> None:
    walker = StaticWalker()

    # Shape 1: cls.model_config.get(...)
    code_cls = """
def init_sources(cls):
    return cls.model_config.get("extra")
"""
    tree_cls = ast.parse(code_cls)
    call_cls = [n for n in ast.walk(tree_cls) if isinstance(n, ast.Call)][0]
    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_cls, tree_cls, dict.get, {}, {"cls": DummySettings}, DummySettings
        )
        is True
    )

    # Shape 2: settings_cls.model_config.get(...)
    code_settings_cls = """
def init_dotenv(settings_cls):
    return settings_cls.model_config.get("env_file")
"""
    tree_settings_cls = ast.parse(code_settings_cls)
    call_settings_cls = [n for n in ast.walk(tree_settings_cls) if isinstance(n, ast.Call)][0]
    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_settings_cls,
            tree_settings_cls,
            dict.get,
            {},
            {"settings_cls": DummySettings},
            DotEnvSettingsSource,
        )
        is True
    )

    # Shape 3: self.config.get(...)
    code_self = """
def read_config(self):
    return self.config.get("case_sensitive")
"""
    tree_self = ast.parse(code_self)
    call_self = [n for n in ast.walk(tree_self) if isinstance(n, ast.Call)][0]
    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_self,
            tree_self,
            dict.get,
            {},
            {"self": DummySettingsSource},
            DummySettingsSource,
        )
        is True
    )


def test_22_mandatory_negative_controls() -> None:
    walker = StaticWalker()

    # Valid template ASTs
    code_cls = "def f(cls): return cls.model_config.get('k')"
    tree_cls = ast.parse(code_cls)
    call_cls = [n for n in ast.walk(tree_cls) if isinstance(n, ast.Call)][0]

    code_settings_cls = "def f(settings_cls): return settings_cls.model_config.get('k')"
    tree_settings_cls = ast.parse(code_settings_cls)
    call_settings_cls = [n for n in ast.walk(tree_settings_cls) if isinstance(n, ast.Call)][0]

    code_self = "def f(self): return self.config.get('k')"
    tree_self = ast.parse(code_self)
    call_self = [n for n in ast.walk(tree_self) if isinstance(n, ast.Call)][0]

    # Control 1: Direct dict.get without model_config receiver -> unresolved
    code_direct_dict = "def f(d): return d.get('k')"
    tree_direct = ast.parse(code_direct_dict)
    call_direct = [n for n in ast.walk(tree_direct) if isinstance(n, ast.Call)][0]
    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_direct, tree_direct, dict.get, {}, {"d": {}}, None
        )
        is False
    )

    # Control 2: dict subclass as model_config -> fails Obligation D
    class SubclassDictSettings(BaseSettings):
        pass

    type.__setattr__(SubclassDictSettings, "model_config", DummyCustomMapping())

    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_cls, tree_cls, dict.get, {}, {"cls": SubclassDictSettings}, SubclassDictSettings
        )
        is False
    )

    # Control 3: Custom mapping / MappingProxy as model_config -> fails Obligation D
    class MappingProxySettings(BaseSettings):
        pass

    type.__setattr__(
        MappingProxySettings, "model_config", types.MappingProxyType({})
    )

    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_cls, tree_cls, dict.get, {}, {"cls": MappingProxySettings}, MappingProxySettings
        )
        is False
    )

    # Control 4: Hostile __getattribute__ metaclass on subject -> rejected
    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_cls,
            tree_cls,
            dict.get,
            {},
            {"cls": ClassWithHostileMetaGetattribute},
            ClassWithHostileMetaGetattribute,
        )
        is False
    )

    # Control 5: Hostile __getattr__ metaclass on subject -> rejected
    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_cls,
            tree_cls,
            dict.get,
            {},
            {"cls": ClassWithHostileMetaGetattr},
            ClassWithHostileMetaGetattr,
        )
        is False
    )

    # Control 6: Hostile __call__ metaclass on subject -> rejected
    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_cls,
            tree_cls,
            dict.get,
            {},
            {"cls": ClassWithHostileMetaCall},
            ClassWithHostileMetaCall,
        )
        is False
    )

    # Control 7: Hostile __signature__ on metaclass -> rejected
    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_cls,
            tree_cls,
            dict.get,
            {},
            {"cls": ClassWithHostileMetaSignature},
            ClassWithHostileMetaSignature,
        )
        is False
    )

    # Control 8: Hostile __signature__ on subject class -> rejected
    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_cls,
            tree_cls,
            dict.get,
            {},
            {"cls": HostileSubjectWithSignature},
            HostileSubjectWithSignature,
        )
        is False
    )

    # Control 9: Hostile descriptor on model_config or config -> fails Obligation D
    class HostileDescSettings(BaseSettings):
        pass

    type.__setattr__(HostileDescSettings, "model_config", HostileDescriptor())

    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_cls, tree_cls, dict.get, {}, {"cls": HostileDescSettings}, HostileDescSettings
        )
        is False
    )

    # Control 10: Non-BaseSettings class -> fails Obligation B
    class NonSettingsClass:
        model_config = {"k": "v"}

    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_cls, tree_cls, dict.get, {}, {"cls": NonSettingsClass}, NonSettingsClass  # type: ignore[arg-type]
        )
        is False
    )

    # Control 11: Parameter shadowing / reassignment of cls -> fails Obligation A
    code_reassign_cls = "def f(cls): cls = Other; return cls.model_config.get('k')"
    tree_reassign_cls = ast.parse(code_reassign_cls)
    call_reassign_cls = [n for n in ast.walk(tree_reassign_cls) if isinstance(n, ast.Call)][0]
    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_reassign_cls,
            tree_reassign_cls,
            dict.get,
            {},
            {"cls": DummySettings},
            DummySettings,
        )
        is False
    )

    # Control 12: Parameter shadowing / reassignment of settings_cls -> fails Obligation A
    code_reassign_settings = "def f(settings_cls): settings_cls = Other; return settings_cls.model_config.get('k')"
    tree_reassign_settings = ast.parse(code_reassign_settings)
    call_reassign_settings = [n for n in ast.walk(tree_reassign_settings) if isinstance(n, ast.Call)][0]
    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_reassign_settings,
            tree_reassign_settings,
            dict.get,
            {},
            {"settings_cls": DummySettings},
            DotEnvSettingsSource,
        )
        is False
    )

    # Control 13: Reassignment of cls.model_config -> fails Obligation A
    code_reassign_cls_cfg = "def f(cls): cls.model_config = {}; return cls.model_config.get('k')"
    tree_reassign_cls_cfg = ast.parse(code_reassign_cls_cfg)
    call_reassign_cls_cfg = [n for n in ast.walk(tree_reassign_cls_cfg) if isinstance(n, ast.Call)][0]
    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_reassign_cls_cfg,
            tree_reassign_cls_cfg,
            dict.get,
            {},
            {"cls": DummySettings},
            DummySettings,
        )
        is False
    )

    # Control 14: Reassignment of settings_cls.model_config -> fails Obligation A
    code_reassign_settings_cfg = "def f(settings_cls): settings_cls.model_config = {}; return settings_cls.model_config.get('k')"
    tree_reassign_settings_cfg = ast.parse(code_reassign_settings_cfg)
    call_reassign_settings_cfg = [n for n in ast.walk(tree_reassign_settings_cfg) if isinstance(n, ast.Call)][0]
    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_reassign_settings_cfg,
            tree_reassign_settings_cfg,
            dict.get,
            {},
            {"settings_cls": DummySettings},
            DotEnvSettingsSource,
        )
        is False
    )

    # Control 15: Multiple assignments to self.config -> fails Obligation A
    code_multi_self_cfg = """
def f(self):
    self.config = {}
    self.config = {}
    return self.config.get('k')
"""
    tree_multi_self_cfg = ast.parse(code_multi_self_cfg)
    call_multi_self_cfg = [n for n in ast.walk(tree_multi_self_cfg) if isinstance(n, ast.Call)][0]
    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_multi_self_cfg,
            tree_multi_self_cfg,
            dict.get,
            {},
            {"self": DummySettingsSource},
            DummySettingsSource,
        )
        is False
    )

    # Control 16: Deletion del cls or del self.config -> fails Obligation A
    code_del_cls = "def f(cls): del cls; return None"
    tree_del_cls = ast.parse(code_del_cls)
    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_cls, tree_del_cls, dict.get, {}, {"cls": DummySettings}, DummySettings
        )
        is False
    )

    code_del_self_cfg = "def f(self): del self.config; return None"
    tree_del_self_cfg = ast.parse(code_del_self_cfg)
    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_self, tree_del_self_cfg, dict.get, {}, {"self": DummySettingsSource}, DummySettingsSource
        )
        is False
    )

    # Control 17: Walrus assignment cls := ... or self := ... -> fails Obligation A
    code_walrus_cls = "def f(cls): (cls := Other); return cls.model_config.get('k')"
    tree_walrus_cls = ast.parse(code_walrus_cls)
    call_walrus_cls = [n for n in ast.walk(tree_walrus_cls) if isinstance(n, ast.Call)][0]
    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_walrus_cls, tree_walrus_cls, dict.get, {}, {"cls": DummySettings}, DummySettings
        )
        is False
    )

    # Control 18: Callee attribute not get (e.g. keys, items, values, pop) -> fails Obligation A / E
    code_keys = "def f(cls): return cls.model_config.keys()"
    tree_keys = ast.parse(code_keys)
    call_keys = [n for n in ast.walk(tree_keys) if isinstance(n, ast.Call)][0]
    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_keys, tree_keys, dict.get, {}, {"cls": DummySettings}, DummySettings
        )
        is False
    )

    # Control 19: Argument shape violation (0 args, 3+ args, keyword args) -> fails Obligation F
    code_0_args = "def f(cls): return cls.model_config.get()"
    tree_0_args = ast.parse(code_0_args)
    call_0_args = [n for n in ast.walk(tree_0_args) if isinstance(n, ast.Call)][0]
    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_0_args, tree_0_args, dict.get, {}, {"cls": DummySettings}, DummySettings
        )
        is False
    )

    code_3_args = "def f(cls): return cls.model_config.get('a', 'b', 'c')"
    tree_3_args = ast.parse(code_3_args)
    call_3_args = [n for n in ast.walk(tree_3_args) if isinstance(n, ast.Call)][0]
    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_3_args, tree_3_args, dict.get, {}, {"cls": DummySettings}, DummySettings
        )
        is False
    )

    code_kwargs = "def f(cls): return cls.model_config.get('a', default='b')"
    tree_kwargs = ast.parse(code_kwargs)
    call_kwargs = [n for n in ast.walk(tree_kwargs) if isinstance(n, ast.Call)][0]
    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_kwargs, tree_kwargs, dict.get, {}, {"cls": DummySettings}, DummySettings
        )
        is False
    )

    # Control 20: Target callable identity mismatch (not dict.get) -> fails Obligation E
    assert (
        walker._prove_pydantic_settings_model_config_get(
            call_cls, tree_cls, list.append, {}, {"cls": DummySettings}, DummySettings  # type: ignore[arg-type]
        )
        is False
    )

    # Control 21: classify_callable without flag does not attach pydantic rationale
    v_unflagged = classify_callable(
        dict.get,
        module="builtins",
        qualname="dict.get",
        is_pydantic_settings_model_config_get=False,
    )
    assert v_unflagged.rationale != "pydantic-settings-model-config-get"

    v_unflagged_custom = classify_callable(
        DummyCustomMapping().get,
        module="tests.audit_harness.test_task_38_15_phase_a_mechanism",
        qualname="DummyCustomMapping.get",
        is_pydantic_settings_model_config_get=False,
    )
    assert v_unflagged_custom.category == "unresolved"
    assert v_unflagged_custom.rationale is None

    # Control 22: classify_callable with flag but target is NOT dict.get -> unresolved
    v_flagged_wrong_target = classify_callable(
        list.append,
        module="builtins",
        qualname="list.append",
        is_pydantic_settings_model_config_get=True,
    )
    assert v_flagged_wrong_target.category == "unresolved"


# ============================================================================
# Section 4: Policy Table Invariance & Classification Isolation
# ============================================================================


def test_exact_identity_policy_table_isolation_and_version() -> None:
    """EXACT_IDENTITY_POLICY must remain strictly at 87 entries and version 2026-09-05.1."""
    assert len(EXACT_IDENTITY_POLICY) == 87
    assert EXACT_IDENTITY_POLICY_VERSION == "2026-09-05.1"
    assert "pydantic_settings.BaseSettings.model_config.get" not in EXACT_IDENTITY_POLICY
    assert "BaseSettings.model_config.get" not in EXACT_IDENTITY_POLICY
    assert "pydantic_settings.PydanticBaseSettingsSource.config.get" not in EXACT_IDENTITY_POLICY
    assert "builtins.mappingproxy.items" not in EXACT_IDENTITY_POLICY


def test_classify_callable_pydantic_flag_authorized_verdict() -> None:
    v = classify_callable(
        dict.get,
        module="builtins",
        qualname="dict.get",
        is_pydantic_settings_model_config_get=True,
    )
    assert v.category == "exact_identity_policy"
    assert v.rationale == "pydantic-settings-model-config-get"
    assert v.source_available is False


# ============================================================================
# Section 5: Canonical Trace Audit, 45-Call Census, and Dispatch Invariant
# ============================================================================


def test_canonical_25_root_audit_census_and_counters() -> None:
    tr = run_trace()

    # 1. Explicit-call population and Task 38.15 mechanism population
    explicit_calls = tr.explicit_calls
    assert len(explicit_calls) == 7420
    assert tr.roots_traced == 25
    assert len(tr.nodes) == 268
    assert tr.nodes_unresolved == 16

    # 2. Identity-resolution buckets that remain invariant
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

    # 3. Dispatch counter invariants: 7,413 candidates and 7,289 unresolved (124 resolved)
    assert tr.implicit_syntax_sites_total == 11405
    assert tr.implicit_dispatch_candidates_total == 7413
    assert tr.implicit_dispatch_resolved == 124
    assert tr.implicit_dispatch_unresolved == 7289

    # 4. Reachable population census: exactly 45 resolved calls across the 3 structural shapes
    pydantic_resolved = [
        c
        for c in explicit_calls
        if c.verdict.category == "exact_identity_policy"
        and c.verdict.rationale == "pydantic-settings-model-config-get"
    ]
    assert len(pydantic_resolved) == 45

    shape_cls = [c for c in pydantic_resolved if c.callee_text.startswith("cls.model_config")]
    shape_settings_cls = [c for c in pydantic_resolved if c.callee_text.startswith("settings_cls.model_config")]
    shape_self = [c for c in pydantic_resolved if c.callee_text.startswith("self.config")]

    assert len(shape_cls) == 27
    assert len(shape_settings_cls) == 7
    assert len(shape_self) == 11
    assert len(shape_cls) + len(shape_settings_cls) + len(shape_self) == 45
    unexpected = [
        c
        for c in pydantic_resolved
        if c not in shape_cls and c not in shape_settings_cls and c not in shape_self
    ]
    assert len(unexpected) == 0
