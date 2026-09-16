"""Tests for Task 38.14 Phase A: owner-class-attribute binder repair.

Verifies:
1. Positive controls: plain Python instance functions resolved via
   owner-class-attribute correctly receive implicit receiver prepending,
   preventing argument left-shift.
2. Negative controls: staticmethods, classmethods, properties, custom
   descriptors, C method descriptors, callable attributes, ambiguous descriptors,
   double prepends, and unrelated mechanisms remain unchanged (fail-closed).
3. Non-execution controls: static inspection uses safe CPython descriptor
   getters and never invokes:
   - Hostile metaclass __getattribute__
   - Hostile metaclass __getattr__
   - Hostile module __getattribute__
   - Hostile module __getattr__ (PEP 562)
   - Property getters
   - Descriptor __get__ methods
   - Callable class attribute invocations
   - Hostile __bool__ / __len__ hooks
   - Instance __getattr__ / __getattribute__ hooks
"""

import ast
import inspect
import sys
import types
import pytest

from audit_harness.trace import (
    StaticWalker,
    _owner_class_from_qualname,
    _safe_raw_class_attribute,
    _safe_owner_class_from_qualname,
)


# --- Fixtures / Test classes for Positive Controls ---

class FixtureHelper:
    def marker(self) -> str:
        return "reached_helper"


class FixtureServiceTarget:
    def marker(self) -> str:
        return "target_marker"


class FixturePositiveBase:
    def instance_two_arg(self, first_arg: object, helper: object) -> None:
        helper.marker()  # type: ignore[attr-defined]

    def inherited_two_arg(self, first_arg: object, helper: object) -> None:
        helper.marker()  # type: ignore[attr-defined]

    def overridden_method(self, first_arg: object, helper: object) -> None:
        helper.marker()  # type: ignore[attr-defined]


class FixturePositiveChild(FixturePositiveBase):
    def caller_instance_method(self) -> None:
        helper = FixtureHelper()
        self.instance_two_arg("arg1_val", helper)

    def caller_inherited_method(self) -> None:
        helper = FixtureHelper()
        self.inherited_two_arg("arg1_val", helper)

    def overridden_method(self, first_arg: object, helper: object) -> None:
        helper.marker()  # type: ignore[attr-defined]

    def caller_overridden_method(self) -> None:
        helper = FixtureHelper()
        self.overridden_method("arg1_val", helper)


class FixtureServiceContainerMock:
    def _build(self, target_cls: type, resolver: object) -> object:
        target_cls.marker()  # type: ignore[attr-defined]
        return target_cls

    def register(self, service_type: type, instance: object) -> None:
        instance.marker()  # type: ignore[attr-defined]

    def register_class(self, target: type) -> None:
        resolver = FixtureHelper()
        self._build(target, resolver)

    def register_instance(self, target_cls: type) -> None:
        inst = FixtureHelper()
        self.register(target_cls, inst)


# --- Fixtures / Test classes for Negative Controls ---

class FixtureNegativeStaticAndClass:
    @staticmethod
    def my_static(helper: object) -> None:
        helper.marker()  # type: ignore[attr-defined]

    @classmethod
    def my_classmethod(cls, helper: object) -> None:
        helper.marker()  # type: ignore[attr-defined]

    def caller_static(self) -> None:
        helper = FixtureHelper()
        self.my_static(helper)

    def caller_classmethod(self) -> None:
        helper = FixtureHelper()
        self.my_classmethod(helper)


class CustomDescriptor:
    def __get__(self, instance: object, owner: type | None = None) -> object:
        return self


class CallableAttr:
    def __call__(self, *args: object, **kwargs: object) -> None:
        pass


class UnknownDescriptor:
    pass


class FixtureNegativeDescriptors:
    custom_desc = CustomDescriptor()
    callable_obj = CallableAttr()
    unknown_desc = UnknownDescriptor()

    @property
    def my_property(self) -> str:
        return "prop_val"

    def caller_custom_desc(self) -> None:
        helper = FixtureHelper()
        self.custom_desc(helper)  # type: ignore[operator]


# --- Hostile Exception Classes for Non-Execution Controls ---

class HostileMetaGetattributeExecuted(Exception):
    pass


class HostileMetaGetattrExecuted(Exception):
    pass


class HostileModuleGetattributeExecuted(Exception):
    pass


class HostileModuleGetattrExecuted(Exception):
    pass


class HostilePropertyExecuted(Exception):
    pass


class HostileDescriptorExecuted(Exception):
    pass


class HostileCallableExecuted(Exception):
    pass


class HostileBoolExecuted(Exception):
    pass


class HostileLenExecuted(Exception):
    pass


class HostileGetattrExecuted(Exception):
    pass


class HostileGetattributeExecuted(Exception):
    pass


# --- Hostile Fixtures ---

class HostileDescriptor:
    def __init__(self) -> None:
        self.exec_count = 0

    def __get__(self, instance: object, owner: type | None = None) -> object:
        self.exec_count += 1
        raise HostileDescriptorExecuted("Hostile descriptor __get__ was executed!")


class HostileCallable:
    def __init__(self) -> None:
        self.exec_count = 0

    def __call__(self, *args: object, **kwargs: object) -> None:
        self.exec_count += 1
        raise HostileCallableExecuted("Hostile callable object was executed!")


class HostileMetaGetattribute(type):
    def __getattribute__(self, name: str) -> object:
        raise HostileMetaGetattributeExecuted(
            f"Hostile metaclass __getattribute__ executed for {name}!"
        )


class HostileMetaGetattr(type):
    def __getattr__(self, name: str) -> object:
        raise HostileMetaGetattrExecuted(
            f"Hostile metaclass __getattr__ executed for {name}!"
        )


class HostileMetaBoolLen(type):
    def __bool__(self) -> bool:
        raise HostileBoolExecuted("Hostile metaclass __bool__ was executed!")

    def __len__(self) -> int:
        raise HostileLenExecuted("Hostile metaclass __len__ was executed!")


class HostileClassWithHostileMetaGetattribute(metaclass=HostileMetaGetattribute):
    def target_method(self, helper: object) -> None:
        helper.marker()  # type: ignore[attr-defined]


class HostileClassWithHostileMetaGetattr(metaclass=HostileMetaGetattr):
    def target_method(self, helper: object) -> None:
        helper.marker()  # type: ignore[attr-defined]


class HostileClassWithHostileBoolLen(metaclass=HostileMetaBoolLen):
    def target_method(self, helper: object) -> None:
        helper.marker()  # type: ignore[attr-defined]

    def __bool__(self) -> bool:
        raise HostileBoolExecuted("Hostile class instance __bool__ was executed!")

    def __len__(self) -> int:
        raise HostileLenExecuted("Hostile class instance __len__ was executed!")


class HostileModuleGetattribute(types.ModuleType):
    def __getattribute__(self, name: str) -> object:
        raise HostileModuleGetattributeExecuted(
            f"Hostile module __getattribute__ executed for {name}!"
        )


class HostileModuleGetattr(types.ModuleType):
    def __getattr__(self, name: str) -> object:
        raise HostileModuleGetattrExecuted(
            f"Hostile module __getattr__ executed for {name}!"
        )


class FixtureHostileClass:
    hostile_desc = HostileDescriptor()
    hostile_callable = HostileCallable()

    @property
    def hostile_prop(self) -> str:
        raise HostilePropertyExecuted("Hostile property getter was executed!")

    def __getattr__(self, name: str) -> object:
        raise HostileGetattrExecuted(f"Hostile __getattr__ was executed for {name}!")

    def __getattribute__(self, name: str) -> object:
        if name in ("hostile_prop", "hostile_desc", "hostile_hook"):
            raise HostileGetattributeExecuted(f"Hostile __getattribute__ for {name}!")
        return super().__getattribute__(name)

    def caller_hostile(self) -> None:
        pass


# ==============================================================================
# Positive Controls
# ==============================================================================

def test_positive_plain_instance_method_owner_class_attribute() -> None:
    """Positive control 1: Plain instance method resolved through
    owner-class-attribute receives implicit receiver binding so second
    positional argument binds to its parameter and resolves downstream."""
    walker = StaticWalker()
    walker.walk(
        FixturePositiveChild.caller_instance_method,
        "self-test:task3814:plain-instance",
        owner_class=FixturePositiveChild,
    )
    matching = [c for c in walker.call_records if c.callee_text == "helper.marker"]
    assert len(matching) >= 1, "Downstream helper.marker call must be reached and recorded"
    assert matching[0].verdict.category != "unresolved"
    assert matching[0].verdict.qualname == "FixtureHelper.marker"


def test_positive_service_container_build_binding() -> None:
    """Positive control 2: ServiceContainer._build binding ensures:
    self -> receiver
    target_cls -> target
    resolver -> resolver."""
    walker = StaticWalker()
    walker.walk(
        FixtureServiceContainerMock.register_class,
        "self-test:task3814:container-build",
        owner_class=FixtureServiceContainerMock,
        forced_locals={"target": FixtureServiceTarget},
    )
    matching = [c for c in walker.call_records if c.callee_text == "target_cls.marker"]
    assert len(matching) >= 1, "Downstream target_cls.marker call must resolve via target_cls local"
    assert matching[0].verdict.category != "unresolved"
    assert matching[0].verdict.qualname == "FixtureServiceTarget.marker"


def test_positive_service_container_register_binding() -> None:
    """Positive control 3: ServiceContainer.register binding ensures:
    self -> receiver
    service_type -> target_cls
    instance -> inst."""
    walker = StaticWalker()
    walker.walk(
        FixtureServiceContainerMock.register_instance,
        "self-test:task3814:container-register",
        owner_class=FixtureServiceContainerMock,
        forced_locals={"target_cls": FixtureServiceTarget},
    )
    matching = [c for c in walker.call_records if c.callee_text == "instance.marker"]
    assert len(matching) >= 1, "Downstream instance.marker call must resolve via instance local"
    assert matching[0].verdict.category != "unresolved"
    assert matching[0].verdict.qualname == "FixtureHelper.marker"


def test_positive_inherited_instance_method() -> None:
    """Positive control 4: Inherited plain instance method receives correct
    receiver prepend."""
    walker = StaticWalker()
    walker.walk(
        FixturePositiveChild.caller_inherited_method,
        "self-test:task3814:inherited-instance",
        owner_class=FixturePositiveChild,
    )
    matching = [c for c in walker.call_records if c.callee_text == "helper.marker"]
    assert len(matching) >= 1, "Downstream helper.marker call must be reached for inherited method"
    assert matching[0].verdict.category != "unresolved"
    assert matching[0].verdict.qualname == "FixtureHelper.marker"


def test_positive_overridden_instance_method() -> None:
    """Positive control 5: Overridden plain instance method receives correct
    receiver prepend."""
    walker = StaticWalker()
    walker.walk(
        FixturePositiveChild.caller_overridden_method,
        "self-test:task3814:overridden-instance",
        owner_class=FixturePositiveChild,
    )
    matching = [c for c in walker.call_records if c.callee_text == "helper.marker"]
    assert len(matching) >= 1, "Downstream helper.marker call must be reached for overridden method"
    assert matching[0].verdict.category != "unresolved"
    assert matching[0].verdict.qualname == "FixtureHelper.marker"


# ==============================================================================
# Negative Controls
# ==============================================================================

def test_negative_staticmethod_no_receiver_prepend() -> None:
    """Negative control 6: staticmethod on owner class must not have receiver
    prepended; its explicit single argument binds directly to its parameter."""
    walker = StaticWalker()
    walker.walk(
        FixtureNegativeStaticAndClass.caller_static,
        "self-test:task3814:static-method",
        owner_class=FixtureNegativeStaticAndClass,
    )
    matching = [c for c in walker.call_records if c.callee_text == "helper.marker"]
    assert len(matching) >= 1, "Downstream helper.marker call must be reached for staticmethod"
    assert matching[0].verdict.category != "unresolved"
    assert matching[0].verdict.qualname == "FixtureHelper.marker"


def test_negative_classmethod_no_receiver_prepend() -> None:
    """Negative control 7: classmethod on owner class must not have instance
    receiver prepended."""
    walker = StaticWalker()
    walker.walk(
        FixtureNegativeStaticAndClass.caller_classmethod,
        "self-test:task3814:class-method",
        owner_class=FixtureNegativeStaticAndClass,
    )
    matching = [c for c in walker.call_records if c.callee_text == "helper.marker"]
    assert len(matching) >= 1, "Downstream helper.marker call must be reached for classmethod"
    assert matching[0].verdict.category != "unresolved"
    assert matching[0].verdict.qualname == "FixtureHelper.marker"


def test_negative_property_descriptor_fail_closed() -> None:
    """Negative control 8: property on owner class is not a plain function and
    fails closed."""
    walker = StaticWalker()
    call_node = ast.Call(
        func=ast.Attribute(
            value=ast.Name(id="self", ctx=ast.Load()),
            attr="my_property",
            ctx=ast.Load(),
        ),
        args=[],
        keywords=[],
    )
    raw_prop = _safe_raw_class_attribute(FixtureNegativeDescriptors, "my_property")
    bound = walker._bind_call_site_locals(
        call_node,
        raw_prop,
        g={},
        loc={"self": FixtureNegativeDescriptors()},
        local_var_types=None,
        mechanism="owner-class-attribute",
    )
    assert bound == {}, "Property target must fail closed and bind nothing"


def test_negative_custom_descriptor_fail_closed() -> None:
    """Negative control 9: Custom descriptor on owner class fails closed."""
    walker = StaticWalker()
    call_node = ast.Call(
        func=ast.Attribute(
            value=ast.Name(id="self", ctx=ast.Load()),
            attr="custom_desc",
            ctx=ast.Load(),
        ),
        args=[ast.Name(id="arg1", ctx=ast.Load())],
        keywords=[],
    )
    bound = walker._bind_call_site_locals(
        call_node,
        FixtureNegativeDescriptors.custom_desc,
        g={},
        loc={"self": FixtureNegativeDescriptors(), "arg1": FixtureHelper()},
        local_var_types=None,
        mechanism="owner-class-attribute",
    )
    assert bound == {}, "Custom descriptor target must fail closed and bind nothing"


def test_negative_c_descriptor_fail_closed() -> None:
    """Negative control 10: C method descriptor on owner class fails closed.
    Implicit receiver is not prepended, so the explicit argument is not shifted."""
    walker = StaticWalker()
    call_node = ast.Call(
        func=ast.Attribute(
            value=ast.Name(id="self", ctx=ast.Load()),
            attr="append",
            ctx=ast.Load(),
        ),
        args=[ast.Name(id="item", ctx=ast.Load())],
        keywords=[],
    )
    bound = walker._bind_call_site_locals(
        call_node,
        list.append,
        g={},
        loc={"self": ["receiver_list"], "item": "val"},
        local_var_types=None,
        mechanism="owner-class-attribute",
    )
    # Since receiver is NOT prepended, list.append's first parameter 'self'
    # receives explicit argument 'item' ('val') rather than loc['self'].
    assert bound == {"self": "val"}
    assert bound.get("self") != ["receiver_list"]


def test_negative_callable_class_attribute_fail_closed() -> None:
    """Negative control 11: Callable object stored on class attribute fails closed."""
    walker = StaticWalker()
    call_node = ast.Call(
        func=ast.Attribute(
            value=ast.Name(id="self", ctx=ast.Load()),
            attr="callable_obj",
            ctx=ast.Load(),
        ),
        args=[ast.Name(id="arg1", ctx=ast.Load())],
        keywords=[],
    )
    bound = walker._bind_call_site_locals(
        call_node,
        FixtureNegativeDescriptors.callable_obj,
        g={},
        loc={"self": FixtureNegativeDescriptors(), "arg1": "val"},
        local_var_types=None,
        mechanism="owner-class-attribute",
    )
    assert bound == {}, "Callable object stored on class must fail closed"


def test_negative_ambiguous_unknown_descriptor_fail_closed() -> None:
    """Negative control 12: Unknown non-function attribute fails closed."""
    walker = StaticWalker()
    call_node = ast.Call(
        func=ast.Attribute(
            value=ast.Name(id="self", ctx=ast.Load()),
            attr="unknown_desc",
            ctx=ast.Load(),
        ),
        args=[ast.Name(id="arg1", ctx=ast.Load())],
        keywords=[],
    )
    bound = walker._bind_call_site_locals(
        call_node,
        FixtureNegativeDescriptors.unknown_desc,
        g={},
        loc={"self": FixtureNegativeDescriptors(), "arg1": "val"},
        local_var_types=None,
        mechanism="owner-class-attribute",
    )
    assert bound == {}, "Unknown descriptor must fail closed"


def test_negative_no_double_prepend() -> None:
    """Negative control 13: Calling an unbound method directly with explicit receiver
    must not prepend a second receiver."""
    walker = StaticWalker()
    call_node = ast.Call(
        func=ast.Attribute(
            value=ast.Name(id="FixturePositiveBase", ctx=ast.Load()),
            attr="instance_two_arg",
            ctx=ast.Load(),
        ),
        args=[
            ast.Name(id="self", ctx=ast.Load()),
            ast.Constant(value="arg1"),
            ast.Name(id="helper", ctx=ast.Load()),
        ],
        keywords=[],
    )
    child_inst = FixturePositiveChild()
    helper_inst = FixtureHelper()
    bound = walker._bind_call_site_locals(
        call_node,
        FixturePositiveBase.instance_two_arg,
        g={"FixturePositiveBase": FixturePositiveBase},
        loc={"self": child_inst, "helper": helper_inst},
        local_var_types=None,
        mechanism="global-or-closure-attribute",
    )
    assert bound == {"self": child_inst, "helper": helper_inst}


def test_negative_unrelated_mechanisms_unchanged() -> None:
    """Negative control 14: Unrelated mechanisms (e.g. global-lookup) remain
    completely unchanged."""
    walker = StaticWalker()
    call_node = ast.Call(
        func=ast.Name(id="helper_func", ctx=ast.Load()),
        args=[ast.Name(id="param1", ctx=ast.Load())],
        keywords=[],
    )

    def dummy_func(p: object) -> None:
        pass

    bound = walker._bind_call_site_locals(
        call_node,
        dummy_func,
        g={"param1": FixtureHelper},
        loc={},
        local_var_types=None,
        mechanism="global-lookup",
    )
    assert bound == {"p": FixtureHelper}


def test_negative_local_var_type_inference_preserved() -> None:
    """Negative control 15: Existing local-variable-type-inference receiver
    prepending behavior is preserved."""
    walker = StaticWalker()
    call_node = ast.Call(
        func=ast.Attribute(
            value=ast.Name(id="receiver", ctx=ast.Load()),
            attr="instance_two_arg",
            ctx=ast.Load(),
        ),
        args=[
            ast.Name(id="arg1", ctx=ast.Load()),
            ast.Name(id="arg2", ctx=ast.Load()),
        ],
        keywords=[],
    )
    base_inst = FixturePositiveBase()
    helper_inst = FixtureHelper()
    bound = walker._bind_call_site_locals(
        call_node,
        FixturePositiveBase.instance_two_arg,
        g={},
        loc={"receiver": base_inst, "arg1": "first", "arg2": helper_inst},
        local_var_types={"receiver": FixturePositiveBase},
        mechanism="local-variable-type-inference",
    )
    assert bound == {"self": base_inst, "first_arg": "first", "helper": helper_inst}


# ==============================================================================
# Non-Execution Hostile Probes (All 8 Required Probes + Additional Controls)
# ==============================================================================

def test_hostile_probe_1_metaclass_getattribute() -> None:
    """Hostile Probe 1: Metaclass __getattribute__ override raising on any access
    must result in 0 arbitrary executions during safe attribute lookup."""
    attr = _safe_raw_class_attribute(
        HostileClassWithHostileMetaGetattribute, "target_method"
    )
    assert inspect.isfunction(attr)

    walker = StaticWalker()
    call_node = ast.Call(
        func=ast.Attribute(
            value=ast.Name(id="self", ctx=ast.Load()),
            attr="target_method",
            ctx=ast.Load(),
        ),
        args=[ast.Name(id="helper", ctx=ast.Load())],
        keywords=[],
    )
    helper = FixtureHelper()
    bound = walker._bind_call_site_locals(
        call_node,
        attr,
        g={},
        loc={
            "self": HostileClassWithHostileMetaGetattribute,
            "helper": helper,
        },
        local_var_types=None,
        mechanism="owner-class-attribute",
    )
    assert bound == {
        "self": HostileClassWithHostileMetaGetattribute,
        "helper": helper,
    }


def test_hostile_probe_2_metaclass_getattr() -> None:
    """Hostile Probe 2: Metaclass __getattr__ override raising on missing attributes
    must result in 0 arbitrary executions during safe attribute lookup."""
    attr = _safe_raw_class_attribute(
        HostileClassWithHostileMetaGetattr, "target_method"
    )
    assert inspect.isfunction(attr)
    missing = _safe_raw_class_attribute(
        HostileClassWithHostileMetaGetattr, "nonexistent_attr"
    )
    assert missing is None


def test_hostile_probe_3_module_getattribute() -> None:
    """Hostile Probe 3: Module with custom ModuleType.__getattribute__ raising on
    any access must result in 0 arbitrary executions during qualname resolution."""
    mod_name = "test_hostile_module_getattribute_pkg"
    hmod = HostileModuleGetattribute(mod_name)
    mod_dict = types.ModuleType.__dict__["__dict__"].__get__(hmod)
    mod_dict["TargetClass"] = HostileClassWithHostileMetaGetattribute
    sys.modules[mod_name] = hmod
    try:
        resolved = _safe_owner_class_from_qualname(
            "TargetClass.target_method.<locals>.<lambda>", mod_name
        )
        assert resolved is HostileClassWithHostileMetaGetattribute
    finally:
        sys.modules.pop(mod_name, None)


def test_hostile_probe_4_module_getattr() -> None:
    """Hostile Probe 4: Module with PEP 562 __getattr__ hook raising on missing
    names must result in 0 arbitrary executions during qualname resolution."""
    mod_name = "test_hostile_module_getattr_pkg"
    hmod = types.ModuleType(mod_name)
    mod_dict = types.ModuleType.__dict__["__dict__"].__get__(hmod)

    def hostile_getattr(name: str) -> object:
        raise HostileModuleGetattrExecuted(f"Module __getattr__ executed for {name}!")

    mod_dict["__getattr__"] = hostile_getattr
    mod_dict["ExistingClass"] = FixturePositiveBase
    sys.modules[mod_name] = hmod
    try:
        resolved = _safe_owner_class_from_qualname(
            "ExistingClass.instance_two_arg.<locals>.<lambda>", mod_name
        )
        assert resolved is FixturePositiveBase

        nonexistent = _safe_owner_class_from_qualname(
            "NonexistentClass.method.<locals>.<lambda>", mod_name
        )
        assert nonexistent is None
    finally:
        sys.modules.pop(mod_name, None)


def test_hostile_probe_5_property_getter() -> None:
    """Hostile Probe 5: Property getter raising HostilePropertyExecuted must
    not be executed during static inspection."""
    raw_attr = _safe_raw_class_attribute(FixtureHostileClass, "hostile_prop")
    assert isinstance(raw_attr, property)

    walker = StaticWalker()
    call_node = ast.Call(
        func=ast.Attribute(
            value=ast.Name(id="self", ctx=ast.Load()),
            attr="hostile_prop",
            ctx=ast.Load(),
        ),
        args=[],
        keywords=[],
    )
    bound = walker._bind_call_site_locals(
        call_node,
        raw_attr,
        g={},
        loc={"self": FixtureHostileClass()},
        local_var_types=None,
        mechanism="owner-class-attribute",
    )
    assert bound == {}


def test_hostile_probe_6_custom_descriptor_get() -> None:
    """Hostile Probe 6: Custom descriptor __get__ raising HostileDescriptorExecuted
    must not be executed during static inspection."""
    desc = type.__dict__["__dict__"].__get__(FixtureHostileClass)["hostile_desc"]
    assert isinstance(desc, HostileDescriptor)
    assert desc.exec_count == 0

    raw_attr = _safe_raw_class_attribute(FixtureHostileClass, "hostile_desc")
    assert raw_attr is desc
    assert desc.exec_count == 0

    walker = StaticWalker()
    call_node = ast.Call(
        func=ast.Attribute(
            value=ast.Name(id="self", ctx=ast.Load()),
            attr="hostile_desc",
            ctx=ast.Load(),
        ),
        args=[],
        keywords=[],
    )
    bound = walker._bind_call_site_locals(
        call_node,
        raw_attr,
        g={},
        loc={"self": FixtureHostileClass()},
        local_var_types=None,
        mechanism="owner-class-attribute",
    )
    assert bound == {}
    assert desc.exec_count == 0


def test_hostile_probe_7_callable_class_attribute() -> None:
    """Hostile Probe 7: Callable class attribute (instance of callable class)
    must not be executed and must fail closed (0 arbitrary executions)."""
    callable_obj = FixtureHostileClass.hostile_callable
    assert isinstance(callable_obj, HostileCallable)
    assert callable_obj.exec_count == 0

    raw_attr = _safe_raw_class_attribute(FixtureHostileClass, "hostile_callable")
    assert raw_attr is callable_obj
    assert callable_obj.exec_count == 0

    walker = StaticWalker()
    call_node = ast.Call(
        func=ast.Attribute(
            value=ast.Name(id="self", ctx=ast.Load()),
            attr="hostile_callable",
            ctx=ast.Load(),
        ),
        args=[],
        keywords=[],
    )
    bound = walker._bind_call_site_locals(
        call_node,
        raw_attr,
        g={},
        loc={"self": FixtureHostileClass()},
        local_var_types=None,
        mechanism="owner-class-attribute",
    )
    assert bound == {}
    assert callable_obj.exec_count == 0


def test_hostile_probe_8_bool_len_hooks() -> None:
    """Hostile Probe 8: Hostile classes and objects with __bool__ / __len__ hooks
    raising exceptions must not be executed during inspection or binding."""
    raw_attr = _safe_raw_class_attribute(
        HostileClassWithHostileBoolLen, "target_method"
    )
    assert inspect.isfunction(raw_attr)

    walker = StaticWalker()
    call_node = ast.Call(
        func=ast.Attribute(
            value=ast.Name(id="self", ctx=ast.Load()),
            attr="target_method",
            ctx=ast.Load(),
        ),
        args=[ast.Name(id="helper", ctx=ast.Load())],
        keywords=[],
    )
    helper = FixtureHelper()
    bound = walker._bind_call_site_locals(
        call_node,
        raw_attr,
        g={},
        loc={
            "self": HostileClassWithHostileBoolLen,
            "helper": helper,
        },
        local_var_types=None,
        mechanism="owner-class-attribute",
    )
    assert bound == {
        "self": HostileClassWithHostileBoolLen,
        "helper": helper,
    }


def test_hostile_additional_controls_instance_getattr_getattribute() -> None:
    """Additional Controls: Instance __getattr__ and __getattribute__ hooks must
    not be executed during static attribute resolution in _bind_call_site_locals."""
    walker = StaticWalker()
    call_node = ast.Call(
        func=ast.Attribute(
            value=ast.Name(id="self", ctx=ast.Load()),
            attr="nonexistent_attribute",
            ctx=ast.Load(),
        ),
        args=[],
        keywords=[],
    )

    def dummy_method(self: object) -> None:
        pass

    bound = walker._bind_call_site_locals(
        call_node,
        dummy_method,
        g={},
        loc={"self": FixtureHostileClass()},
        local_var_types=None,
        mechanism="owner-class-attribute",
    )
    assert bound == {}


# ==============================================================================
# Former Defect Reproductions
# ==============================================================================

def test_reproduce_former_defect_1_metaclass_getattr_static_vulnerability() -> None:
    """Defect 1 Reproduction: inspect.getattr_static triggers metaclass __getattribute__,
    whereas _safe_raw_class_attribute does not execute any arbitrary code."""
    # Proof of former vulnerability in inspect.getattr_static:
    with pytest.raises(HostileMetaGetattributeExecuted):
        inspect.getattr_static(HostileClassWithHostileMetaGetattribute, "target_method")

    # Proof of safe non-executing repair in _safe_raw_class_attribute:
    attr = _safe_raw_class_attribute(
        HostileClassWithHostileMetaGetattribute, "target_method"
    )
    assert inspect.isfunction(attr)


def test_reproduce_former_defect_2_module_dynamic_getattr_vulnerability() -> None:
    """Defect 2 Reproduction: getattr(mod, name) triggers module __getattr__ (PEP 562),
    whereas _safe_owner_class_from_qualname does not execute any arbitrary code."""
    mod_name = "test_defect_2_module_pkg"
    hmod = types.ModuleType(mod_name)
    mod_dict = types.ModuleType.__dict__["__dict__"].__get__(hmod)

    def hostile_pep562_getattr(name: str) -> object:
        raise HostileModuleGetattrExecuted(f"Dynamic module __getattr__ executed for {name}")

    mod_dict["__getattr__"] = hostile_pep562_getattr
    mod_dict["SafeClass"] = FixturePositiveBase
    sys.modules[mod_name] = hmod
    try:
        # Proof of former vulnerability in getattr(mod, "MissingClass", None):
        with pytest.raises(HostileModuleGetattrExecuted):
            getattr(hmod, "MissingClass", None)

        # Proof of safe non-executing repair in _safe_owner_class_from_qualname:
        resolved_safe = _safe_owner_class_from_qualname(
            "SafeClass.instance_two_arg.<locals>.<lambda>", mod_name
        )
        assert resolved_safe is FixturePositiveBase

        resolved_missing = _safe_owner_class_from_qualname(
            "MissingClass.method.<locals>.<lambda>", mod_name
        )
        assert resolved_missing is None
    finally:
        sys.modules.pop(mod_name, None)
