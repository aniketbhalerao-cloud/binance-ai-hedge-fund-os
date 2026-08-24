"""Task 38.8 Phase A.0: characterization fixtures for the implicit-
protocol-dispatch discovery gap (``docs/audits/task-38.5-risk-register.md``'s
**M-8**).

None of this module is imported by production code, registered as a
framework, or reachable from ``app.wiring``. Every fixture class below
embeds exactly one real forbidden identity (``open(...)``, a member of
``audit_harness.identity.FORBIDDEN_IDENTITIES``) inside the body of the
one dunder method that implements the **one** protocol dispatch event
under test -- every other dunder a given class defines is deliberately
inert (clean), so a sentinel embedded in one dispatch event is never
masked by a clean partner event living on the same class. Where a
protocol has two independently-dispatched stages (``__iter__`` then
``__next__``; ``__enter__`` then ``__exit__``; ``__aiter__`` then
``__anext__``; ``__aenter__`` then ``__aexit__``), each stage gets its
own dedicated class and trigger, isolating that one event.

**Precisely what is, and is not, executed by importing this module:**
importing this module *does* execute ordinary Python class- and
function-*definition* statements -- it creates the class objects and
function objects this module defines, exactly as importing any Python
module does. What is **never** executed is the *body* of any trigger
function, and the *body* of any sentinel-bearing dunder method: every
trigger below is walked *statically* (``StaticWalker.walk``), never
called, and no dunder method containing ``open(...)`` is ever invoked
by anything in this repository outside a characterization test's own
static walk.

A trigger function's own parameter is always the already-constructed
fixture instance, typed, never built inline -- so the trigger's own
body contains no constructor call that could be mistaken for the
protocol dispatch under test.

Where the triggering syntax itself performs an outer, explicit call
that the walker already discovers on its own (``format(obj, ...)``,
``str(obj)``, ``repr(obj)``, ``"{}".format(obj)``, ``some_set.add(obj)``),
that outer call is real, resolved, and expected to appear in
``call_records`` -- it is never the thing under test. What each
characterization test actually asserts is that no ``CallRecord``
anywhere in ``call_records`` resolves to the *embedded sentinel*
(``builtins.open``) -- the nested dispatch the outer call performs
internally, which carries no ``ast.Call`` node of its own.

Covers all 11 families named in ``docs/prompts/task-38.8.md`` §2, plus
every variant/fallback §2 names, with both dispatch stages isolated
independently wherever a protocol has two: iteration
(``__iter__``-only, ``__next__``-only via a ``for`` loop, ``__next__``-only
via a comprehension); starred unpacking (``__iter__``-only,
``__next__``-only); sync context managers (``__enter__``-only,
``__exit__``-only); async context managers (``__aenter__``-only,
``__aexit__``-only); ``await`` (``__await__``); async iteration
(``__aiter__``-only, ``__anext__``-only); descriptor
``__get__``/``__set__``/``__delete__`` (raw descriptor protocol and
``@property``); comparison/ordering/arithmetic including a reflected
form; ``__bool__`` and its ``__len__`` fallback; ``__contains__`` and
its iteration fallback (``__iter__``-only, ``__next__``-only);
subscription get/set/delete; hashing via set-literal, dict-key, and
``.add(`` insertion; formatting via f-string, ``format()``, ``str()``,
``repr()``, and ``"{}".format()``.
"""

from __future__ import annotations

_SENTINEL_PATH = "/dev/null/audit-harness-fixture-must-never-run"


# ---------------------------------------------------------------------
# 1. Iteration and comprehensions -- __iter__ and __next__, isolated
# ---------------------------------------------------------------------


class ForbiddenIterOnly:
    """Only ``__iter__`` carries the sentinel; ``__next__`` is clean --
    isolates the ``__iter__`` dispatch (what a ``for``/comprehension
    triggers to obtain an iterator in the first place) from the
    ``__next__`` dispatch a clean partner method could otherwise
    mask."""

    def __iter__(self) -> ForbiddenIterOnly:
        open(_SENTINEL_PATH)  # noqa: SIM115 - deliberately forbidden, never actually run
        return self

    def __next__(self) -> int:
        raise StopIteration


class ForbiddenNextOnly:
    """Only ``__next__`` carries the sentinel; ``__iter__`` is clean."""

    def __iter__(self) -> ForbiddenNextOnly:
        return self

    def __next__(self) -> int:
        open(_SENTINEL_PATH)  # noqa: SIM115
        raise StopIteration


def trigger_for_loop_iter_only(obj: ForbiddenIterOnly) -> None:
    for _ in obj:
        pass


def trigger_for_loop(obj: ForbiddenNextOnly) -> None:
    for _ in obj:
        pass


def trigger_list_comprehension(obj: ForbiddenNextOnly) -> list[int]:
    return [x for x in obj]


# ---------------------------------------------------------------------
# 2. Starred unpacking -- __iter__ and __next__, isolated, via a
# distinct AST shape from plain iteration (ast.Starred, not for/comp)
# ---------------------------------------------------------------------


class ForbiddenUnpackIterOnly:
    """A separate class from the iteration family above, so the
    starred-unpacking site is isolated from it; only ``__iter__``
    carries the sentinel."""

    def __iter__(self) -> ForbiddenUnpackIterOnly:
        open(_SENTINEL_PATH)  # noqa: SIM115
        return self

    def __next__(self) -> int:
        raise StopIteration


class ForbiddenUnpackNextOnly:
    """Only ``__next__`` carries the sentinel."""

    def __iter__(self) -> ForbiddenUnpackNextOnly:
        return self

    def __next__(self) -> int:
        open(_SENTINEL_PATH)  # noqa: SIM115
        raise StopIteration


def trigger_starred_unpacking_iter_only(
    obj: ForbiddenUnpackIterOnly,
) -> tuple[int, list[int]]:
    first, *rest = obj  # type: ignore[misc]
    return first, rest


def trigger_starred_unpacking(obj: ForbiddenUnpackNextOnly) -> tuple[int, list[int]]:
    first, *rest = obj  # type: ignore[misc]
    return first, rest


# ---------------------------------------------------------------------
# 3. Context managers -- __enter__ and __exit__, each isolated
# ---------------------------------------------------------------------


class ForbiddenEnterOnly:
    """Only ``__enter__`` carries the sentinel; ``__exit__`` is clean --
    isolates the ``__enter__`` dispatch event so a clean ``__exit__``
    cannot hide it."""

    def __enter__(self) -> ForbiddenEnterOnly:
        open(_SENTINEL_PATH)  # noqa: SIM115
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


class ForbiddenExitOnly:
    """Only ``__exit__`` carries the sentinel; ``__enter__`` is clean --
    proves ``__exit__`` specifically, not merely ``__enter__``, is
    invisible."""

    def __enter__(self) -> ForbiddenExitOnly:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        open(_SENTINEL_PATH)  # noqa: SIM115
        return False


def trigger_with_statement_enter_only(obj: ForbiddenEnterOnly) -> None:
    with obj:
        pass


def trigger_with_statement(obj: ForbiddenExitOnly) -> None:
    with obj:
        pass


# ---------------------------------------------------------------------
# 3b. Async context managers -- __aenter__ and __aexit__, each isolated
# ---------------------------------------------------------------------


class ForbiddenAsyncEnterOnly:
    """Async equivalent of :class:`ForbiddenEnterOnly` -- only
    ``__aenter__`` carries the sentinel; ``__aexit__`` is clean."""

    async def __aenter__(self) -> ForbiddenAsyncEnterOnly:
        open(_SENTINEL_PATH)  # noqa: SIM115
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


class ForbiddenAsyncExitOnly:
    """Async equivalent of :class:`ForbiddenExitOnly` -- only
    ``__aexit__`` carries the sentinel; ``__aenter__`` is clean."""

    async def __aenter__(self) -> ForbiddenAsyncExitOnly:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        open(_SENTINEL_PATH)  # noqa: SIM115
        return False


async def trigger_async_with_statement_enter_only(
    obj: ForbiddenAsyncEnterOnly,
) -> None:
    async with obj:
        pass


async def trigger_async_with_statement(obj: ForbiddenAsyncExitOnly) -> None:
    async with obj:
        pass


# ---------------------------------------------------------------------
# 4. Await -- __await__ (a single dispatch stage)
# ---------------------------------------------------------------------


class ForbiddenAwaitable:
    """``__await__`` is a generator function whose own body carries the
    sentinel -- calling it returns a generator (satisfying the iterator
    contract ``await`` requires) without this module ever running it."""

    def __await__(self):  # type: ignore[no-untyped-def]
        open(_SENTINEL_PATH)  # noqa: SIM115
        yield


async def trigger_await(obj: ForbiddenAwaitable) -> None:
    await obj  # type: ignore[misc]


# ---------------------------------------------------------------------
# 4b. Async iteration -- __aiter__ and __anext__, each isolated
# ---------------------------------------------------------------------


class ForbiddenAiterOnly:
    """Only ``__aiter__`` carries the sentinel; ``__anext__`` is
    clean."""

    def __aiter__(self) -> ForbiddenAiterOnly:
        open(_SENTINEL_PATH)  # noqa: SIM115
        return self

    async def __anext__(self) -> int:
        raise StopAsyncIteration


class ForbiddenAnextOnly:
    """Only ``__anext__`` carries the sentinel; ``__aiter__`` is
    clean."""

    def __aiter__(self) -> ForbiddenAnextOnly:
        return self

    async def __anext__(self) -> int:
        open(_SENTINEL_PATH)  # noqa: SIM115
        raise StopAsyncIteration


async def trigger_async_for_aiter_only(obj: ForbiddenAiterOnly) -> None:
    async for _ in obj:
        pass


async def trigger_async_for(obj: ForbiddenAnextOnly) -> None:
    async for _ in obj:
        pass


# ---------------------------------------------------------------------
# 5. Properties and descriptors -- __get__ / __set__ / __delete__
# ---------------------------------------------------------------------


class ForbiddenProperty:
    """M-8's own "sharpest instance": a bare ``ast.Attribute`` read
    invoking a ``@property`` getter -- not even an ``ast.Call`` node at
    all, only a bare attribute-load node."""

    @property
    def value(self) -> int:
        open(_SENTINEL_PATH)  # noqa: SIM115
        return 0


def trigger_property_get(obj: ForbiddenProperty) -> int:
    return obj.value


class _ForbiddenGetDescriptor:
    def __get__(self, instance: object, owner: type | None) -> int:
        open(_SENTINEL_PATH)  # noqa: SIM115
        return 0


class _ForbiddenSetDescriptor:
    def __set__(self, instance: object, value: object) -> None:
        open(_SENTINEL_PATH)  # noqa: SIM115


class _ForbiddenDeleteDescriptor:
    def __delete__(self, instance: object) -> None:
        open(_SENTINEL_PATH)  # noqa: SIM115


class HostGetDescriptor:
    """``Load`` context on ``attr`` dispatches to ``__get__``."""

    attr = _ForbiddenGetDescriptor()


class HostSetDescriptor:
    """``Store`` context on ``attr`` dispatches to ``__set__``."""

    attr = _ForbiddenSetDescriptor()


class HostDeleteDescriptor:
    """``Del`` context on ``attr`` dispatches to ``__delete__``."""

    attr = _ForbiddenDeleteDescriptor()


def trigger_descriptor_get(obj: HostGetDescriptor) -> int:
    return obj.attr


def trigger_descriptor_set(obj: HostSetDescriptor) -> None:
    obj.attr = 1


def trigger_descriptor_delete(obj: HostDeleteDescriptor) -> None:
    del obj.attr


# ---------------------------------------------------------------------
# 6. Equality, ordering, and arithmetic operators, including reflected
# ---------------------------------------------------------------------


class ForbiddenEq:
    def __eq__(self, other: object) -> bool:
        open(_SENTINEL_PATH)  # noqa: SIM115
        return False

    __hash__ = None  # type: ignore[assignment]


class ForbiddenLt:
    def __lt__(self, other: object) -> bool:
        open(_SENTINEL_PATH)  # noqa: SIM115
        return False


class ForbiddenAdd:
    def __add__(self, other: object) -> object:
        open(_SENTINEL_PATH)  # noqa: SIM115
        return self


class ForbiddenRadd:
    """Defines only ``__radd__`` (no ``__add__``) -- isolates the
    reflected-operator dispatch specifically."""

    def __radd__(self, other: object) -> object:
        open(_SENTINEL_PATH)  # noqa: SIM115
        return self


def trigger_equality(a: ForbiddenEq, b: object) -> bool:
    return a == b


def trigger_less_than(a: ForbiddenLt, b: object) -> bool:
    return a < b


def trigger_add(a: ForbiddenAdd, b: object) -> object:
    return a + b


def trigger_reflected_add(b: ForbiddenRadd) -> object:
    return 1 + b


# ---------------------------------------------------------------------
# 7. Truth testing -- __bool__, and the __len__ fallback
# ---------------------------------------------------------------------


class ForbiddenBool:
    def __bool__(self) -> bool:
        open(_SENTINEL_PATH)  # noqa: SIM115
        return True


class ForbiddenLenFallback:
    """No ``__bool__`` defined -- CPython's truth-testing protocol
    falls back to ``__len__``."""

    def __len__(self) -> int:
        open(_SENTINEL_PATH)  # noqa: SIM115
        return 0


def trigger_truth_bool(obj: ForbiddenBool) -> bool:
    if obj:
        return True
    return False


def trigger_truth_len_fallback(obj: ForbiddenLenFallback) -> bool:
    if obj:
        return True
    return False


# ---------------------------------------------------------------------
# 8. Membership, and its iteration fallback (__iter__/__next__,
# isolated) -- __contains__
# ---------------------------------------------------------------------


class ForbiddenContains:
    def __contains__(self, item: object) -> bool:
        open(_SENTINEL_PATH)  # noqa: SIM115
        return False


class ForbiddenMembershipIterOnly:
    """No ``__contains__`` defined -- CPython's membership test falls
    back to the iteration protocol; only ``__iter__`` carries the
    sentinel here."""

    def __iter__(self) -> ForbiddenMembershipIterOnly:
        open(_SENTINEL_PATH)  # noqa: SIM115
        return self

    def __next__(self) -> str:
        raise StopIteration


class ForbiddenMembershipNextOnly:
    """No ``__contains__`` defined -- membership falls back to
    iteration; only ``__next__`` carries the sentinel here."""

    def __iter__(self) -> ForbiddenMembershipNextOnly:
        return self

    def __next__(self) -> str:
        open(_SENTINEL_PATH)  # noqa: SIM115
        raise StopIteration


def trigger_membership_contains(obj: ForbiddenContains) -> bool:
    return "x" in obj


def trigger_membership_iteration_fallback_iter_only(
    obj: ForbiddenMembershipIterOnly,
) -> bool:
    return "x" in obj


def trigger_membership_iteration_fallback(
    obj: ForbiddenMembershipNextOnly,
) -> bool:
    return "x" in obj


# ---------------------------------------------------------------------
# 9. Subscription and assignment/deletion
# ---------------------------------------------------------------------


class ForbiddenGetitem:
    def __getitem__(self, key: object) -> int:
        open(_SENTINEL_PATH)  # noqa: SIM115
        return 0


class ForbiddenSetitem:
    def __setitem__(self, key: object, value: object) -> None:
        open(_SENTINEL_PATH)  # noqa: SIM115


class ForbiddenDelitem:
    def __delitem__(self, key: object) -> None:
        open(_SENTINEL_PATH)  # noqa: SIM115


def trigger_subscript_get(obj: ForbiddenGetitem) -> int:
    return obj[0]


def trigger_subscript_set(obj: ForbiddenSetitem) -> None:
    obj[0] = 1


def trigger_subscript_delete(obj: ForbiddenDelitem) -> None:
    del obj[0]


# ---------------------------------------------------------------------
# 10. Hashing -- __hash__, triggered by set/dict-key insertion
# ---------------------------------------------------------------------


class ForbiddenHashable:
    def __hash__(self) -> int:  # type: ignore[override]
        open(_SENTINEL_PATH)  # noqa: SIM115
        return 0


def trigger_hash_set_literal(obj: ForbiddenHashable) -> set[ForbiddenHashable]:
    return {obj}


def trigger_hash_dict_key(obj: ForbiddenHashable) -> dict[ForbiddenHashable, str]:
    return {obj: "value"}


def trigger_hash_set_add(obj: ForbiddenHashable) -> None:
    # ``set()`` here constructs an empty *container*, not ``obj`` --
    # the explicit, already-discovered ``.add(`` call is never the
    # thing under test; the nested ``obj.__hash__`` dispatch insertion
    # performs internally is.
    receiver: set[ForbiddenHashable] = set()
    receiver.add(obj)


# ---------------------------------------------------------------------
# 11. Formatting -- __format__, with __str__/__repr__ fallback
# ---------------------------------------------------------------------


class ForbiddenFormat:
    def __format__(self, format_spec: str) -> str:
        open(_SENTINEL_PATH)  # noqa: SIM115
        return ""


class ForbiddenStr:
    """No ``__format__`` override -- ``format()``/``str()`` fall back to
    ``__str__``."""

    def __str__(self) -> str:
        open(_SENTINEL_PATH)  # noqa: SIM115
        return ""


class ForbiddenRepr:
    """No ``__format__``/``__str__`` override -- ``repr()`` falls back to
    ``__repr__`` directly."""

    def __repr__(self) -> str:
        open(_SENTINEL_PATH)  # noqa: SIM115
        return ""


def trigger_fstring_format(obj: ForbiddenFormat) -> str:
    return f"{obj}"


def trigger_format_builtin(obj: ForbiddenFormat) -> str:
    return format(obj, "")


def trigger_dotformat_builtin(obj: ForbiddenFormat) -> str:
    return "{}".format(obj)  # noqa: UP032 - deliberate explicit outer call


def trigger_str_builtin(obj: ForbiddenStr) -> str:
    return str(obj)


def trigger_repr_builtin(obj: ForbiddenRepr) -> str:
    return repr(obj)
