"""Tests for Task 38.14 Phase A: owner-class-attribute binder repair.

Verifies:
1. Positive controls: plain Python instance functions resolved via
   owner-class-attribute correctly receive implicit receiver prepending,
   preventing argument left-shift.
2. Negative controls: staticmethods, classmethods, properties, custom
   descriptors, C method descriptors, callable attributes, ambiguous descriptors,
   double prepends, and unrelated mechanisms remain unchanged (fail-closed).
3. Non-execution controls: static inspection uses getattr_static and never
   invokes property getters, descriptor __get__ methods, __getattr__, or
   __getattribute__ hooks.
"""

import ast
import inspect
import types
import pytest

from audit_harness.trace import StaticWalker, _owner_class_from_qualname


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
    # Non-function attribute behaving unexpectedly
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


# --- Fixtures / Test classes for Non-Execution Controls ---

class HostilePropertyExecuted(Exception):
    pass


class HostileDescriptorExecuted(Exception):
    pass


class HostileGetattrExecuted(Exception):
    pass


class HostileGetattributeExecuted(Exception):
    pass


class HostileDescriptor:
    def __get__(self, instance: object, owner: type | None = None) -> object:
        raise HostileDescriptorExecuted("Hostile descriptor __get__ was executed!")


class FixtureHostileClass:
    hostile_desc = HostileDescriptor()

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
    bound = walker._bind_call_site_locals(
        call_node,
        getattr(FixtureNegativeDescriptors, "my_property"),
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
    # Explicit call: Base.instance_two_arg(self, "arg1", helper)
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
    # Target obtained via global lookup of FixturePositiveBase.instance_two_arg
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
# Non-Execution Controls
# ==============================================================================

def test_non_execution_hostile_property_getter() -> None:
    """Non-execution control 16: Hostile property getter is not executed
    during _bind_call_site_locals classification."""
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
    # Target obtained via inspect.getattr_static or class dict to avoid triggering getter
    target = inspect.getattr_static(FixtureHostileClass, "hostile_prop")
    # Must not raise HostilePropertyExecuted
    bound = walker._bind_call_site_locals(
        call_node,
        target,
        g={},
        loc={"self": FixtureHostileClass()},
        local_var_types=None,
        mechanism="owner-class-attribute",
    )
    assert bound == {}


def test_non_execution_hostile_descriptor_get() -> None:
    """Non-execution control 17: Hostile descriptor __get__ is not executed
    during _bind_call_site_locals classification."""
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
    target = inspect.getattr_static(FixtureHostileClass, "hostile_desc")
    # Must not raise HostileDescriptorExecuted
    bound = walker._bind_call_site_locals(
        call_node,
        target,
        g={},
        loc={"self": FixtureHostileClass()},
        local_var_types=None,
        mechanism="owner-class-attribute",
    )
    assert bound == {}


def test_non_execution_hostile_getattr_hook() -> None:
    """Non-execution control 18: Hostile __getattr__ and __getattribute__ hooks
    are not executed during static attribute resolution in _bind_call_site_locals."""
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

    # Must not raise HostileGetattrExecuted or HostileGetattributeExecuted
    bound = walker._bind_call_site_locals(
        call_node,
        dummy_method,
        g={},
        loc={"self": FixtureHostileClass()},
        local_var_types=None,
        mechanism="owner-class-attribute",
    )
    # Since attribute nonexistent_attribute is not found, no receiver is prepended,
    # and dummy_method expecting 'self' binds nothing.
    assert bound == {}
