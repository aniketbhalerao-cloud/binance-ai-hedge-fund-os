"""Task 38.8 Phase A.1: additional fixtures for the mechanized
context-manager/descriptor dispatch mechanism (ADR-032 Option D).

``tests/audit_harness/fixtures/implicit_dispatch.py`` (Phase A.0) is
frozen evidence of the pre-mechanism boundary and is never edited or
extended for Phase A.1 purposes. These few fixtures cover exactly the
shapes Phase A.0 deliberately did not need: an unresolved (untyped)
receiver for each of the two mechanized families, and a context
manager constructed inline in its own triggering ``with`` statement --
proving the mechanism's new per-site records coexist correctly with
the existing, already-tested explicit-call resolution for that same
constructor call.

Same non-execution discipline as Phase A.0: only ordinary class/
function *definition* statements are ever executed by importing this
module; no trigger body and no dunder body is ever invoked.
"""

from __future__ import annotations

_SENTINEL_PATH = "/dev/null/audit-harness-fixture-must-never-run"


# ---------------------------------------------------------------------
# Unresolved receiver -- fail-closed, for each of the two families
# ---------------------------------------------------------------------


def trigger_context_manager_unresolved_receiver(obj) -> None:  # type: ignore[no-untyped-def]
    """``obj`` carries no type annotation at all -- the walker's own
    type-inference chain cannot soundly pin a receiver type, so this
    must produce an explicit ``unresolved`` implicit-dispatch record
    for both ``__enter__`` and ``__exit__``, never a default-safe skip."""
    with obj:
        pass


def trigger_descriptor_get_unresolved_receiver(obj):  # type: ignore[no-untyped-def]
    """Same fail-closed shape for the descriptor family: an untyped
    ``obj.attr`` read whose receiver type cannot be soundly resolved."""
    return obj.attr


# ---------------------------------------------------------------------
# Inline construction -- the context manager's own constructor call is
# a distinct, already-discovered explicit ast.Call, never the implicit
# dispatch mechanism's concern.
# ---------------------------------------------------------------------


class CleanContextManager:
    """No sentinel anywhere -- both dunders are inert; used only to
    prove the constructor call and the two dispatch events are all
    independently, correctly recorded side by side."""

    def __enter__(self) -> CleanContextManager:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


def trigger_with_inline_construction() -> None:
    with CleanContextManager():
        pass


# ---------------------------------------------------------------------
# Hostile non-execution fixtures -- each of these raises the moment its
# own dunder is actually *invoked* (not merely looked up). A passing
# test that walks a trigger below without that exception propagating
# is direct proof the resolution path never executes the hook it is
# only supposed to statically identify (item 3).
# ---------------------------------------------------------------------


class _HostileInstanceDescriptor:
    """A data descriptor (defines all three dunders) whose every method
    raises immediately if actually called, and additionally embeds the
    real forbidden sentinel in its own body -- so a passing walk must
    both (a) never raise (proving no accidental real invocation) and
    (b) still discover the sentinel via ordinary static source parsing
    (proving detection survives even though the walker never runs the
    method it is reading)."""

    def __get__(self, instance: object, owner: type | None) -> int:
        open(_SENTINEL_PATH)  # noqa: SIM115
        raise RuntimeError(
            "HOSTILE FIXTURE: __get__ was actually invoked during static "
            "analysis"
        )

    def __set__(self, instance: object, value: object) -> None:
        open(_SENTINEL_PATH)  # noqa: SIM115
        raise RuntimeError(
            "HOSTILE FIXTURE: __set__ was actually invoked during static "
            "analysis"
        )

    def __delete__(self, instance: object) -> None:
        open(_SENTINEL_PATH)  # noqa: SIM115
        raise RuntimeError(
            "HOSTILE FIXTURE: __delete__ was actually invoked during "
            "static analysis"
        )


class HostileInstanceHost:
    attr = _HostileInstanceDescriptor()


def trigger_hostile_instance_get(obj: HostileInstanceHost) -> int:
    return obj.attr


def trigger_hostile_instance_set(obj: HostileInstanceHost) -> None:
    obj.attr = 1


def trigger_hostile_instance_delete(obj: HostileInstanceHost) -> None:
    del obj.attr


class _HostileMetaclass(type):
    """A metaclass-level *data* descriptor -- `HostileClassLevelHost.attr`
    dispatches through this, per `type.__getattribute__`'s own priority
    rule, never through anything on `HostileClassLevelHost` itself."""

    attr = _HostileInstanceDescriptor()


class HostileClassLevelHost(metaclass=_HostileMetaclass):
    """No instance is ever constructed -- the trigger below accesses
    `HostileClassLevelHost.attr` directly, on the class object itself,
    exercising the class-receiver resolution path (item 4)."""


def trigger_hostile_class_level_get() -> int:
    return HostileClassLevelHost.attr


# ---------------------------------------------------------------------
# Class-level descriptor access (item 4): C.attr must never be silently
# excluded merely for being a class.
# ---------------------------------------------------------------------


class _CleanMetaclassDataDescriptor:
    def __get__(self, instance: object, owner: type | None) -> int:
        return 0

    def __set__(self, instance: object, value: object) -> None:
        pass


class _ForbiddenMetaclassDataDescriptor:
    """Only the metaclass-level descriptor's own __get__ carries the
    sentinel -- isolates the metaclass-priority path from the ordinary
    class-body path."""

    def __get__(self, instance: object, owner: type | None) -> int:
        open(_SENTINEL_PATH)  # noqa: SIM115
        return 0

    def __set__(self, instance: object, value: object) -> None:
        pass


class ForbiddenMetaclass(type):
    attr = _ForbiddenMetaclassDataDescriptor()


class HostViaForbiddenMetaclass(metaclass=ForbiddenMetaclass):
    """No `attr` of its own -- resolution must fall through to (and
    detect) the metaclass's own data descriptor."""


def trigger_class_level_metaclass_descriptor_get() -> int:
    return HostViaForbiddenMetaclass.attr


class _ForbiddenClassBodyDescriptor:
    """A plain (non-data) descriptor assigned directly in a class body
    -- accessed via the class itself, not an instance, so this is the
    class-receiver's own-MRO path, not the metaclass path."""

    def __get__(self, instance: object, owner: type | None) -> int:
        open(_SENTINEL_PATH)  # noqa: SIM115
        return 0


class HostClassBodyDescriptor:
    attr = _ForbiddenClassBodyDescriptor()


def trigger_class_level_own_mro_descriptor_get() -> int:
    return HostClassBodyDescriptor.attr


# ---------------------------------------------------------------------
# Non-data descriptor ambiguity on instance Load (item 4): an instance's
# own __dict__ could shadow it -- must be reported unresolved/ambiguous,
# never resolved-safe, regardless of what the descriptor's body itself
# contains.
# ---------------------------------------------------------------------


class _CleanNonDataDescriptor:
    """Only __get__ -- a non-data descriptor. No sentinel anywhere;
    used to prove the *ambiguous* classification is reported purely
    from the shape (get-only, no __set__/__delete__), never inferred
    from whether the body happens to be forbidden."""

    def __get__(self, instance: object, owner: type | None) -> int:
        return 0


class HostCleanNonDataDescriptor:
    attr = _CleanNonDataDescriptor()


def trigger_clean_non_data_descriptor_get(obj: HostCleanNonDataDescriptor) -> int:
    return obj.attr


# ---------------------------------------------------------------------
# A property missing fset/fdel (item 4): assignment/deletion still
# reaches property's own descriptor operation and raises -- never
# silently treated as "no dispatch occurs".
# ---------------------------------------------------------------------


class ReadOnlyProperty:
    @property
    def value(self) -> int:
        return 0
    # No .setter/.deleter defined -- fset and fdel are both None.


def trigger_readonly_property_set(obj: ReadOnlyProperty) -> None:
    obj.value = 1  # type: ignore[misc]


def trigger_readonly_property_delete(obj: ReadOnlyProperty) -> None:
    del obj.value  # type: ignore[misc]


# ---------------------------------------------------------------------
# Augmented assignment (item 5): obj.attr += value performs both a
# __get__ (read the current value) and a __set__ (store the result) --
# independently isolated sentinels so one stage cannot mask the other.
# ---------------------------------------------------------------------


class _AugGetForbiddenDescriptor:
    def __get__(self, instance: object, owner: type | None) -> int:
        open(_SENTINEL_PATH)  # noqa: SIM115
        return 0

    def __set__(self, instance: object, value: object) -> None:
        pass


class _AugSetForbiddenDescriptor:
    def __get__(self, instance: object, owner: type | None) -> int:
        return 0

    def __set__(self, instance: object, value: object) -> None:
        open(_SENTINEL_PATH)  # noqa: SIM115


class HostAugGetForbidden:
    attr = _AugGetForbiddenDescriptor()


class HostAugSetForbidden:
    attr = _AugSetForbiddenDescriptor()


def trigger_augassign_get_forbidden(obj: HostAugGetForbidden) -> None:
    obj.attr += 1


def trigger_augassign_set_forbidden(obj: HostAugSetForbidden) -> None:
    obj.attr += 1


# ---------------------------------------------------------------------
# Multi-item context managers (item 6): with a, b: -- every enter/exit
# event represented exactly once, enter in program order, exit in
# reverse order (matching real interpreter cleanup semantics).
# ---------------------------------------------------------------------


class TrackedCleanContextManagerA:
    def __enter__(self) -> TrackedCleanContextManagerA:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


class TrackedCleanContextManagerB:
    def __enter__(self) -> TrackedCleanContextManagerB:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


def trigger_multi_item_with(
    a: TrackedCleanContextManagerA, b: TrackedCleanContextManagerB
) -> None:
    with a, b:
        pass


class TrackedAsyncContextManagerA:
    async def __aenter__(self) -> TrackedAsyncContextManagerA:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


class TrackedAsyncContextManagerB:
    async def __aenter__(self) -> TrackedAsyncContextManagerB:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


async def trigger_multi_item_async_with(
    a: TrackedAsyncContextManagerA, b: TrackedAsyncContextManagerB
) -> None:
    async with a, b:
        pass


# ---------------------------------------------------------------------
# Ordinary, non-descriptor attribute access (§8/§11): a resolved
# receiver and attribute whose value's own type implements none of the
# three dunders -- the `resolved_non_descriptor_exclusion` case,
# excluded from the resolved/unresolved partition entirely.
# ---------------------------------------------------------------------


class HostPlainAttribute:
    value: int = 5  # a plain class-level int -- no __get__/__set__/__delete__


def trigger_plain_attribute_get(obj: HostPlainAttribute) -> int:
    return obj.value


# ---------------------------------------------------------------------
# Explicit-path duplicate (§8/§11): the same target reached both via
# implicit dispatch and via an ordinary, already-discovered ast.Call
# elsewhere in the same trace -- never miscounted as newly-covered by
# the implicit-dispatch mechanism.
# ---------------------------------------------------------------------


class ExplicitlyDuplicatedContextManager:
    def __enter__(self) -> ExplicitlyDuplicatedContextManager:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


def trigger_with_and_explicit_enter_duplicate(
    obj: ExplicitlyDuplicatedContextManager,
) -> None:
    with obj:
        pass
    obj.__enter__()  # the same __enter__, also reached via an ordinary explicit call


# =======================================================================
# Correction pass: legacy-metric contamination, syntax-site/candidate
# ownership, context-manager missing-method semantics, class-level
# store/delete, Call.func/chained-receiver blind spots, attribute-access
# overrides, and context-manager target binding.
# =======================================================================


# ---------------------------------------------------------------------
# Item 3: a statically-known-missing context-manager protocol method is
# a fail-closed unresolved dispatch, never the descriptor-only
# `resolved_non_descriptor_exclusion` counter.
# ---------------------------------------------------------------------


class MissingEnter:
    """No ``__enter__`` at all -- ``with`` requires it."""

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


def trigger_missing_enter(obj: MissingEnter) -> None:
    with obj:  # type: ignore[attr-defined]
        pass


class MissingExit:
    def __enter__(self) -> MissingExit:
        return self


def trigger_missing_exit(obj: MissingExit) -> None:
    with obj:  # type: ignore[attr-defined]
        pass


class MissingAenter:
    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


async def trigger_missing_aenter(obj: MissingAenter) -> None:
    async with obj:  # type: ignore[attr-defined]
        pass


class MissingAexit:
    async def __aenter__(self) -> MissingAexit:
        return self


async def trigger_missing_aexit(obj: MissingAexit) -> None:
    async with obj:  # type: ignore[attr-defined]
        pass


# ---------------------------------------------------------------------
# Item 4: class-level store/delete semantics. `C.attr = value` / `del
# C.attr` go through the metaclass's own data-descriptor lookup only --
# a descriptor merely stored in `C.__dict__` is never consulted for
# these two operations (it is overwritten/deleted directly, exactly
# like a plain value would be). Each hostile method raises the instant
# it is actually invoked -- a passing walk (no exception) is direct
# proof the wrong path was never dispatched into.
# ---------------------------------------------------------------------


class _ClassBodyDataDescriptor:
    """A genuine data descriptor (``__set__``/``__delete__`` both
    defined) -- but stored directly in a class body, not on a
    metaclass. Real ``type.__setattr__``/``__delattr__`` never consult
    it."""

    def __get__(self, instance: object, owner: type | None) -> int:
        return 0

    def __set__(self, instance: object, value: object) -> None:
        open(_SENTINEL_PATH)  # noqa: SIM115
        raise RuntimeError(
            "HOSTILE FIXTURE: a class-body descriptor's __set__ must never "
            "be invoked by C.attr = value"
        )

    def __delete__(self, instance: object) -> None:
        open(_SENTINEL_PATH)  # noqa: SIM115
        raise RuntimeError(
            "HOSTILE FIXTURE: a class-body descriptor's __delete__ must "
            "never be invoked by del C.attr"
        )


class HostClassBodyDataDescriptor:
    attr = _ClassBodyDataDescriptor()


def trigger_class_level_set_never_calls_class_body_descriptor() -> None:
    HostClassBodyDataDescriptor.attr = 1


def trigger_class_level_delete_never_calls_class_body_descriptor() -> None:
    del HostClassBodyDataDescriptor.attr


class _InterceptingMetaclassDataDescriptor:
    def __get__(self, instance: object, owner: type | None) -> int:
        return 0

    def __set__(self, instance: object, value: object) -> None:
        open(_SENTINEL_PATH)  # noqa: SIM115
        raise RuntimeError(
            "HOSTILE FIXTURE: __set__ was actually invoked during static "
            "analysis"
        )

    def __delete__(self, instance: object) -> None:
        open(_SENTINEL_PATH)  # noqa: SIM115
        raise RuntimeError(
            "HOSTILE FIXTURE: __delete__ was actually invoked during "
            "static analysis"
        )


class InterceptingMetaclass(type):
    attr = _InterceptingMetaclassDataDescriptor()


class HostInterceptingMetaclass(metaclass=InterceptingMetaclass):
    """No ``attr`` of its own -- class-level assignment/deletion must
    dispatch through the metaclass's own data descriptor instead."""


def trigger_class_level_set_via_metaclass_data_descriptor() -> None:
    HostInterceptingMetaclass.attr = 1


def trigger_class_level_delete_via_metaclass_data_descriptor() -> None:
    del HostInterceptingMetaclass.attr


# ---------------------------------------------------------------------
# Item 5: descriptor dispatch via ast.Call.func, and chained (non-Name)
# receivers -- neither silently omitted.
# ---------------------------------------------------------------------


def _clean_returned_callable() -> int:
    return 0


class _CallableReturningDataDescriptor:
    """A *data* descriptor (defines ``__set__`` too, so ``__get__`` is
    never ambiguous) -- its own ``__get__`` carries the sentinel,
    isolating the descriptor-access event from whatever the outer call
    goes on to do with the object ``__get__`` returns.

    The sentinel is guarded by ``instance is not None`` -- never
    reached when this same class is accessed via the class object
    itself (``instance=None``, exactly what the *pre-existing*,
    out-of-scope ``parameter-annotation-substitution`` explicit-call
    mechanism's own ``hasattr``/``getattr`` probe does, harmlessly, as
    a side effect of resolving the outer call's own target). This
    walker's own static discovery mechanism under test walks the
    function body unconditionally -- via source parsing, never
    execution -- so it still finds the guarded sentinel regardless of
    this branch; only real, live execution ever skips it."""

    def __get__(self, instance: object, owner: type | None) -> object:
        if instance is not None:
            open(_SENTINEL_PATH)  # noqa: SIM115
        return _clean_returned_callable

    def __set__(self, instance: object, value: object) -> None:
        pass


class HostCallableReturningDescriptor:
    descriptor_returning_callable = _CallableReturningDataDescriptor()


def trigger_descriptor_returning_callable_used_as_call_func(
    obj: HostCallableReturningDescriptor,
) -> object:
    return obj.descriptor_returning_callable()


class HostOrdinaryMethod:
    def method(self) -> int:
        return 0


def trigger_ordinary_bound_method_call(obj: HostOrdinaryMethod) -> int:
    """``obj.method`` is a non-data descriptor (a plain function) --
    per item 4's own existing discipline for a bare Load, an instance's
    own ``__dict__`` could shadow it, so this must now report
    ``ambiguous``/``unresolved`` too when the attribute happens to be
    called immediately, exactly as it already does for a bare read."""
    return obj.method()


class ChainChild:
    attr: int = 0


class ChainHost:
    def __init__(self) -> None:
        self.child = ChainChild()


def trigger_chained_descriptor_read(host: ChainHost) -> int:
    return host.child.attr


def trigger_chained_descriptor_write(host: ChainHost) -> None:
    host.child.attr = 1


def trigger_chained_descriptor_delete(host: ChainHost) -> None:
    del host.child.attr


# ---------------------------------------------------------------------
# Item 6: attribute-access overrides -- a class (or its metaclass)
# overriding the base attribute-access machinery makes the ordinary
# descriptor-lookup algorithm unproven; must degrade to
# ambiguous/unresolved, never resolved-safe. Each override raises the
# instant it is actually invoked -- proving the walker's own override
# *detection* never executes it.
# ---------------------------------------------------------------------


class HostCustomGetattribute:
    attr: int = 0

    def __getattribute__(self, name: str) -> object:
        raise RuntimeError(
            "HOSTILE FIXTURE: __getattribute__ was actually invoked during "
            "static analysis"
        )


def trigger_custom_getattribute_get(obj: HostCustomGetattribute) -> object:
    return obj.attr


class HostCustomSetattr:
    def __setattr__(self, name: str, value: object) -> None:
        raise RuntimeError(
            "HOSTILE FIXTURE: __setattr__ was actually invoked during "
            "static analysis"
        )


def trigger_custom_setattr_set(obj: HostCustomSetattr) -> None:
    obj.attr = 1


class HostCustomDelattr:
    def __delattr__(self, name: str) -> None:
        raise RuntimeError(
            "HOSTILE FIXTURE: __delattr__ was actually invoked during "
            "static analysis"
        )


def trigger_custom_delattr_delete(obj: HostCustomDelattr) -> None:
    del obj.attr


class _MetaGetattribute(type):
    def __getattribute__(cls, name: str) -> object:
        raise RuntimeError(
            "HOSTILE FIXTURE: metaclass __getattribute__ was actually "
            "invoked during static analysis"
        )


class HostMetaGetattribute(metaclass=_MetaGetattribute):
    attr: int = 0


def trigger_meta_getattribute_class_get() -> object:
    return HostMetaGetattribute.attr


class _MetaSetattr(type):
    def __setattr__(cls, name: str, value: object) -> None:
        raise RuntimeError(
            "HOSTILE FIXTURE: metaclass __setattr__ was actually invoked "
            "during static analysis"
        )


class HostMetaSetattr(metaclass=_MetaSetattr):
    attr: int = 0


def trigger_meta_setattr_class_set() -> None:
    HostMetaSetattr.attr = 1


class _MetaDelattr(type):
    def __delattr__(cls, name: str) -> None:
        raise RuntimeError(
            "HOSTILE FIXTURE: metaclass __delattr__ was actually invoked "
            "during static analysis"
        )


class HostMetaDelattr(metaclass=_MetaDelattr):
    attr: int = 0


def trigger_meta_delattr_class_delete() -> None:
    del HostMetaDelattr.attr


# ---------------------------------------------------------------------
# Item 7: context-manager special-method binding -- a
# staticmethod/classmethod/descriptor-backed __enter__ must never be
# misclassified as its own wrapper object.
# ---------------------------------------------------------------------


def _static_enter_impl(cm: object) -> object:
    return cm


class StaticmethodContextManager:
    __enter__ = staticmethod(_static_enter_impl)

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


def trigger_staticmethod_enter(obj: StaticmethodContextManager) -> None:
    with obj:
        pass


class ClassmethodContextManager:
    @classmethod
    def __enter__(cls) -> type[ClassmethodContextManager]:
        return cls

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


def trigger_classmethod_enter(obj: ClassmethodContextManager) -> None:
    with obj:
        pass


class _DescriptorBackedEnter:
    def __get__(self, instance: object, owner: type | None) -> object:
        raise RuntimeError(
            "HOSTILE FIXTURE: __get__ was actually invoked to bind "
            "a descriptor-backed __enter__"
        )


class DescriptorBackedContextManager:
    __enter__ = _DescriptorBackedEnter()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


def trigger_descriptor_backed_enter(obj: DescriptorBackedContextManager) -> None:
    with obj:
        pass
