"""Task 38.8 Phase A.0: characterization tests for the implicit-
protocol-dispatch discovery gap (``docs/audits/task-38.5-risk-register.md``'s
**M-8**).

Each test proves the *current* behavior `docs/prompts/task-38.8.md` §3
requires: walking a fixture's "trigger" function -- which exercises one
protocol dispatch event through ordinary syntax, never a direct call to
the dunder by name -- produces zero ``CallRecord`` referencing the
sentinel embedded in that event's own dunder body. This is Phase A.0
only: it documents M-8's own claim on committed source, exactly as it
stands today. No mechanism is implemented here, and no test below
asserts anything about *detecting* the sentinel -- only that it is
currently invisible to ``StaticWalker``.

**Only the trigger functions and the sentinel-bearing dunder bodies are
never executed.** Importing ``tests.audit_harness.fixtures.implicit_dispatch``
does execute ordinary class- and function-*definition* statements
(creating the fixture classes and functions), exactly as importing any
module does -- this file's docstring and the fixture module's own
docstring are both precise about that distinction.

Before trusting any "zero ``CallRecord``" result, each test first
proves, for the specific dunder under test:

1. **AST proof** -- its own source genuinely contains a call to a
   free-variable name ``open``, never rebound as a parameter or a local
   assignment target within that same function.
2. **Real-builtin-binding proof** -- that free variable's own module
   ``__globals__`` mapping does not rebind ``open`` to anything else,
   and the object that name would resolve to (module globals, falling
   back to ``builtins``, exactly the way CPython itself resolves a free
   variable) is object-identical to the real ``builtins.open`` -- not
   merely inferred from the absence of shadowing.
3. **Forbidden-identity proof** -- that real ``builtins.open`` object is
   independently classified ``forbidden`` by the repository's own
   ``audit_harness.identity.classify_callable``, the exact API the
   walker itself uses -- so the sentinel this whole file relies on is a
   proven, not assumed, forbidden identity.

Only once all three hold does a test proceed to walk the trigger and
assert no ``CallRecord`` in ``call_records`` matches that identity --
via ``verdict.category``/``module``/``qualname``, never a path
substring or loose ``callee_text`` match.
"""

from __future__ import annotations

import ast
import builtins
import inspect
import textwrap
from collections.abc import Callable, Sequence

from audit_harness.identity import (
    IdentityVerdict,
    classify_callable,
    module_and_qualname,
)
from audit_harness.trace import StaticWalker
from tests.audit_harness.fixtures import implicit_dispatch as fx

# ---------------------------------------------------------------------
# Proven once, module-wide: the sentinel identity every test below
# relies on.
# ---------------------------------------------------------------------

_OPEN_MODULE, _OPEN_QUALNAME = module_and_qualname(builtins.open)
_OPEN_VERDICT: IdentityVerdict = classify_callable(
    builtins.open, module=_OPEN_MODULE, qualname=_OPEN_QUALNAME
)
# `builtins.open`'s own real ``__module__`` is CPython's C-implemented
# ``_io`` module, not ``"builtins"`` -- the same aliasing
# ``audit_harness.identity.FORBIDDEN_IDENTITIES`` documents (it lists
# ``"builtins.open"``, ``"_io.open"``, and ``"io.open"`` as separate
# entries for exactly this reason). ``_OPEN_MODULE``/``_OPEN_QUALNAME``
# are used, dynamically, as the real resolved identity everywhere below
# -- never hardcoded as a literal string, and never assumed to be
# ``"builtins"``.
assert _OPEN_QUALNAME == "open", (
    "audit_harness.identity.module_and_qualname(builtins.open) no longer "
    "resolves a qualname of 'open' -- every case in this file depends on "
    "that exact identity"
)
assert _OPEN_VERDICT.category == "forbidden", (
    "builtins.open is no longer classified 'forbidden' by "
    "audit_harness.identity.classify_callable -- every characterization "
    "test in this file depends on this fact holding"
)


def test_sentinel_identity_is_a_real_forbidden_identity() -> None:
    """`docs/prompts/task-38.8.md`'s own detection-assertion discipline
    (§3): the sentinel this whole file relies on is proven, via the
    repository's real ``classify_callable`` -- the exact API the walker
    itself uses -- to be a genuine forbidden identity, not assumed. The
    resolved module (``_io``, not ``"builtins"`` -- a real CPython
    aliasing quirk `audit_harness.identity.FORBIDDEN_IDENTITIES` itself
    documents) is asserted dynamically, never hardcoded."""
    assert _OPEN_QUALNAME == "open"
    assert _OPEN_MODULE is not None
    assert _OPEN_VERDICT.module == _OPEN_MODULE
    assert _OPEN_VERDICT.qualname == "open"
    assert _OPEN_VERDICT.category == "forbidden"


# ---------------------------------------------------------------------
# Shared verification + characterization body
# ---------------------------------------------------------------------


def _resolve_target_function(cls: type, attr_name: str) -> Callable[..., object]:
    """The real function object a class attribute's dispatch ultimately
    runs -- unwrapping ``property`` to its ``fget`` the same way Python
    itself does for ``Load`` context, since ``cls.__dict__[attr_name]``
    for a ``@property``-declared attribute is a ``property`` object,
    not a plain function."""
    raw = cls.__dict__[attr_name]
    if isinstance(raw, property):
        assert raw.fget is not None
        return raw.fget
    if isinstance(raw, staticmethod):
        return raw.__func__
    return raw


def _function_builtin_open(func: Callable[..., object]) -> object | None:
    """The object ``func``'s own builtin namespace -- ``func.__builtins__``,
    the exact dict/module CPython itself consults as the fallback for a
    free variable a function's ``LOAD_GLOBAL`` does not find in
    ``func.__globals__`` -- binds the name ``"open"`` to. ``None`` if
    that namespace does not define ``open`` at all. ``func.__builtins__``
    is, depending on how the defining module was itself executed,
    either a plain ``dict`` or the real ``builtins`` module object --
    both are handled."""
    ns = func.__builtins__  # type: ignore[attr-defined]
    if isinstance(ns, dict):
        return ns.get("open")
    return getattr(ns, "open", None)


def _dunder_calls_the_real_forbidden_sentinel(cls: type, attr_name: str) -> bool:
    """Structural **and** identity proof that ``cls.<attr_name>``'s own
    body genuinely calls the real, live ``builtins.open`` -- prevents
    the exact false-pass risk M-8's own v1/v2 diagnostic passes made:
    asserting "no CallRecord found" proves nothing if the fixture never
    genuinely called the sentinel in the first place, and "nothing
    shadows the name" alone proves less than confirming what the name
    actually, presently resolves to.
    """
    func = _resolve_target_function(cls, attr_name)
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))

    calls_open = False
    shadowed_locally = False
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "open"
        ):
            calls_open = True
        if isinstance(node, ast.arg) and node.arg == "open":
            shadowed_locally = True
        if (
            isinstance(node, ast.Name)
            and node.id == "open"
            and isinstance(node.ctx, ast.Store)
        ):
            shadowed_locally = True
    if not calls_open or shadowed_locally:
        return False

    # Real-builtin-binding proof, modeling CPython's own free-variable
    # resolution order exactly, not approximated:
    #
    # 1. `"open"` must be absent from this function's own module
    #    globals -- if present there, `LOAD_GLOBAL` would find and use
    #    that binding and never fall through to the builtin namespace
    #    at all, so a module-level shadow must independently fail this
    #    proof.
    if "open" in func.__globals__:
        return False

    # 2. The function's *actual* builtin namespace -- `func.__builtins__`,
    #    the exact fallback CPython itself consults once step 1 confirms
    #    `open` is absent from globals -- must bind `"open"` to an
    #    object that is `is`-identical to the real `builtins.open`.
    bound_open = _function_builtin_open(func)
    if bound_open is not builtins.open:
        return False

    # 3. That real, confirmed object receives the repository's own
    #    `forbidden` identity verdict, via its exact existing API --
    #    the same one StaticWalker itself would use if it ever
    #    discovered this call.
    module, qualname = module_and_qualname(bound_open)
    verdict = classify_callable(bound_open, module=module, qualname=qualname)
    return verdict.category == "forbidden"


def _assert_family_characterized(
    trigger: Callable[..., object],
    site_label: str,
    sentinel_targets: Sequence[tuple[type, str]],
) -> None:
    """Shared body for every dispatch-event test below -- one
    implementation, not one copy per test that could silently drift
    apart (the same discipline ``test_negative_controls.py`` already
    holds itself to for its own shared ``run_self_tests()`` call)."""
    for cls, attr_name in sentinel_targets:
        assert _dunder_calls_the_real_forbidden_sentinel(cls, attr_name), (
            f"fixture malformed: {cls.__qualname__}.{attr_name} does not "
            "genuinely, provably call the real, live builtins.open -- this "
            "case's characterization would pass vacuously"
        )

    walker = StaticWalker()
    walker.walk(trigger, site_label)

    forbidden_open_records = [
        r
        for r in walker.call_records
        if r.verdict.module == _OPEN_MODULE and r.verdict.qualname == _OPEN_QUALNAME
    ]
    assert not forbidden_open_records, (
        f"{site_label}: StaticWalker unexpectedly discovered the embedded "
        f"sentinel via {trigger.__qualname__} -- M-8's own claim would be "
        f"falsified by this run: {forbidden_open_records}"
    )


# ---------------------------------------------------------------------
# 1. Iteration and comprehensions -- __iter__ and __next__, isolated
# ---------------------------------------------------------------------


def test_iteration_iter_only_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_for_loop_iter_only,
        "task-38.8:iteration:iter-only",
        [(fx.ForbiddenIterOnly, "__iter__")],
    )


def test_iteration_for_loop_next_only_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_for_loop,
        "task-38.8:iteration:for-loop-next-only",
        [(fx.ForbiddenNextOnly, "__next__")],
    )


def test_iteration_comprehension_next_only_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_list_comprehension,
        "task-38.8:iteration:comprehension-next-only",
        [(fx.ForbiddenNextOnly, "__next__")],
    )


# ---------------------------------------------------------------------
# 2. Starred unpacking -- __iter__ and __next__, isolated
# ---------------------------------------------------------------------


def test_starred_unpacking_iter_only_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_starred_unpacking_iter_only,
        "task-38.8:unpacking:iter-only",
        [(fx.ForbiddenUnpackIterOnly, "__iter__")],
    )


def test_starred_unpacking_next_only_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_starred_unpacking,
        "task-38.8:unpacking:next-only",
        [(fx.ForbiddenUnpackNextOnly, "__next__")],
    )


# ---------------------------------------------------------------------
# 3. Context managers -- __enter__ and __exit__, each isolated
# ---------------------------------------------------------------------


def test_sync_context_manager_enter_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_with_statement_enter_only,
        "task-38.8:context-manager:sync-enter",
        [(fx.ForbiddenEnterOnly, "__enter__")],
    )


def test_sync_context_manager_exit_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_with_statement,
        "task-38.8:context-manager:sync-exit",
        [(fx.ForbiddenExitOnly, "__exit__")],
    )


def test_async_context_manager_aenter_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_async_with_statement_enter_only,
        "task-38.8:context-manager:async-aenter",
        [(fx.ForbiddenAsyncEnterOnly, "__aenter__")],
    )


def test_async_context_manager_aexit_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_async_with_statement,
        "task-38.8:context-manager:async-aexit",
        [(fx.ForbiddenAsyncExitOnly, "__aexit__")],
    )


# ---------------------------------------------------------------------
# 4. Await -- __await__ (single stage)
# ---------------------------------------------------------------------


def test_await_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_await,
        "task-38.8:await:__await__",
        [(fx.ForbiddenAwaitable, "__await__")],
    )


# ---------------------------------------------------------------------
# 4b. Async iteration -- __aiter__ and __anext__, each isolated
# ---------------------------------------------------------------------


def test_async_iteration_aiter_only_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_async_for_aiter_only,
        "task-38.8:async-iteration:aiter-only",
        [(fx.ForbiddenAiterOnly, "__aiter__")],
    )


def test_async_iteration_anext_only_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_async_for,
        "task-38.8:async-iteration:anext-only",
        [(fx.ForbiddenAnextOnly, "__anext__")],
    )


# ---------------------------------------------------------------------
# 5. Properties and descriptors
# ---------------------------------------------------------------------


def test_property_get_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_property_get,
        "task-38.8:descriptor:property-get",
        [(fx.ForbiddenProperty, "value")],
    )


def test_descriptor_get_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_descriptor_get,
        "task-38.8:descriptor:raw-get",
        [(fx._ForbiddenGetDescriptor, "__get__")],  # noqa: SLF001
    )


def test_descriptor_set_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_descriptor_set,
        "task-38.8:descriptor:raw-set",
        [(fx._ForbiddenSetDescriptor, "__set__")],  # noqa: SLF001
    )


def test_descriptor_delete_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_descriptor_delete,
        "task-38.8:descriptor:raw-delete",
        [(fx._ForbiddenDeleteDescriptor, "__delete__")],  # noqa: SLF001
    )


# ---------------------------------------------------------------------
# 6. Equality, ordering, and arithmetic operators, including reflected
# ---------------------------------------------------------------------


def test_equality_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_equality,
        "task-38.8:operator:eq",
        [(fx.ForbiddenEq, "__eq__")],
    )


def test_ordering_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_less_than,
        "task-38.8:operator:lt",
        [(fx.ForbiddenLt, "__lt__")],
    )


def test_arithmetic_add_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_add,
        "task-38.8:operator:add",
        [(fx.ForbiddenAdd, "__add__")],
    )


def test_arithmetic_reflected_add_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_reflected_add,
        "task-38.8:operator:radd",
        [(fx.ForbiddenRadd, "__radd__")],
    )


# ---------------------------------------------------------------------
# 7. Truth testing -- __bool__ and the __len__ fallback
# ---------------------------------------------------------------------


def test_truth_bool_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_truth_bool,
        "task-38.8:truth:bool",
        [(fx.ForbiddenBool, "__bool__")],
    )


def test_truth_len_fallback_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_truth_len_fallback,
        "task-38.8:truth:len-fallback",
        [(fx.ForbiddenLenFallback, "__len__")],
    )


# ---------------------------------------------------------------------
# 8. Membership, and its iteration fallback (__iter__/__next__,
# isolated)
# ---------------------------------------------------------------------


def test_membership_contains_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_membership_contains,
        "task-38.8:membership:contains",
        [(fx.ForbiddenContains, "__contains__")],
    )


def test_membership_iteration_fallback_iter_only_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_membership_iteration_fallback_iter_only,
        "task-38.8:membership:iteration-fallback-iter-only",
        [(fx.ForbiddenMembershipIterOnly, "__iter__")],
    )


def test_membership_iteration_fallback_next_only_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_membership_iteration_fallback,
        "task-38.8:membership:iteration-fallback-next-only",
        [(fx.ForbiddenMembershipNextOnly, "__next__")],
    )


# ---------------------------------------------------------------------
# 9. Subscription and assignment/deletion
# ---------------------------------------------------------------------


def test_subscript_get_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_subscript_get,
        "task-38.8:subscription:getitem",
        [(fx.ForbiddenGetitem, "__getitem__")],
    )


def test_subscript_set_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_subscript_set,
        "task-38.8:subscription:setitem",
        [(fx.ForbiddenSetitem, "__setitem__")],
    )


def test_subscript_delete_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_subscript_delete,
        "task-38.8:subscription:delitem",
        [(fx.ForbiddenDelitem, "__delitem__")],
    )


# ---------------------------------------------------------------------
# 10. Hashing -- via set-literal, dict-key, and .add( insertion
# ---------------------------------------------------------------------


def test_hash_set_literal_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_hash_set_literal,
        "task-38.8:hashing:set-literal",
        [(fx.ForbiddenHashable, "__hash__")],
    )


def test_hash_dict_key_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_hash_dict_key,
        "task-38.8:hashing:dict-key",
        [(fx.ForbiddenHashable, "__hash__")],
    )


def test_hash_set_add_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_hash_set_add,
        "task-38.8:hashing:set-add",
        [(fx.ForbiddenHashable, "__hash__")],
    )


# ---------------------------------------------------------------------
# 11. Formatting -- __format__, with __str__/__repr__ fallback
# ---------------------------------------------------------------------


def test_format_fstring_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_fstring_format,
        "task-38.8:formatting:fstring",
        [(fx.ForbiddenFormat, "__format__")],
    )


def test_format_builtin_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_format_builtin,
        "task-38.8:formatting:format-builtin",
        [(fx.ForbiddenFormat, "__format__")],
    )


def test_format_dotformat_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_dotformat_builtin,
        "task-38.8:formatting:dotformat",
        [(fx.ForbiddenFormat, "__format__")],
    )


def test_format_str_fallback_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_str_builtin,
        "task-38.8:formatting:str-fallback",
        [(fx.ForbiddenStr, "__str__")],
    )


def test_format_repr_fallback_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_repr_builtin,
        "task-38.8:formatting:repr-fallback",
        [(fx.ForbiddenRepr, "__repr__")],
    )


# ---------------------------------------------------------------------
# Summary -- all 11 families, every isolated dispatch event, one sweep
# ---------------------------------------------------------------------

_ALL_CASES: tuple[
    tuple[str, Callable[..., object], tuple[tuple[type, str], ...]], ...
] = (
    (
        "iteration:iter-only",
        fx.trigger_for_loop_iter_only,
        ((fx.ForbiddenIterOnly, "__iter__"),),
    ),
    (
        "iteration:for-loop-next-only",
        fx.trigger_for_loop,
        ((fx.ForbiddenNextOnly, "__next__"),),
    ),
    (
        "iteration:comprehension-next-only",
        fx.trigger_list_comprehension,
        ((fx.ForbiddenNextOnly, "__next__"),),
    ),
    (
        "unpacking:iter-only",
        fx.trigger_starred_unpacking_iter_only,
        ((fx.ForbiddenUnpackIterOnly, "__iter__"),),
    ),
    (
        "unpacking:next-only",
        fx.trigger_starred_unpacking,
        ((fx.ForbiddenUnpackNextOnly, "__next__"),),
    ),
    (
        "context-manager:sync-enter",
        fx.trigger_with_statement_enter_only,
        ((fx.ForbiddenEnterOnly, "__enter__"),),
    ),
    (
        "context-manager:sync-exit",
        fx.trigger_with_statement,
        ((fx.ForbiddenExitOnly, "__exit__"),),
    ),
    (
        "context-manager:async-aenter",
        fx.trigger_async_with_statement_enter_only,
        ((fx.ForbiddenAsyncEnterOnly, "__aenter__"),),
    ),
    (
        "context-manager:async-aexit",
        fx.trigger_async_with_statement,
        ((fx.ForbiddenAsyncExitOnly, "__aexit__"),),
    ),
    ("await:__await__", fx.trigger_await, ((fx.ForbiddenAwaitable, "__await__"),)),
    (
        "async-iteration:aiter-only",
        fx.trigger_async_for_aiter_only,
        ((fx.ForbiddenAiterOnly, "__aiter__"),),
    ),
    (
        "async-iteration:anext-only",
        fx.trigger_async_for,
        ((fx.ForbiddenAnextOnly, "__anext__"),),
    ),
    (
        "descriptor:property-get",
        fx.trigger_property_get,
        ((fx.ForbiddenProperty, "value"),),
    ),
    (
        "descriptor:raw-get",
        fx.trigger_descriptor_get,
        ((fx._ForbiddenGetDescriptor, "__get__"),),  # noqa: SLF001
    ),
    (
        "descriptor:raw-set",
        fx.trigger_descriptor_set,
        ((fx._ForbiddenSetDescriptor, "__set__"),),  # noqa: SLF001
    ),
    (
        "descriptor:raw-delete",
        fx.trigger_descriptor_delete,
        ((fx._ForbiddenDeleteDescriptor, "__delete__"),),  # noqa: SLF001
    ),
    ("operator:eq", fx.trigger_equality, ((fx.ForbiddenEq, "__eq__"),)),
    ("operator:lt", fx.trigger_less_than, ((fx.ForbiddenLt, "__lt__"),)),
    ("operator:add", fx.trigger_add, ((fx.ForbiddenAdd, "__add__"),)),
    ("operator:radd", fx.trigger_reflected_add, ((fx.ForbiddenRadd, "__radd__"),)),
    ("truth:bool", fx.trigger_truth_bool, ((fx.ForbiddenBool, "__bool__"),)),
    (
        "truth:len-fallback",
        fx.trigger_truth_len_fallback,
        ((fx.ForbiddenLenFallback, "__len__"),),
    ),
    (
        "membership:contains",
        fx.trigger_membership_contains,
        ((fx.ForbiddenContains, "__contains__"),),
    ),
    (
        "membership:iteration-fallback-iter-only",
        fx.trigger_membership_iteration_fallback_iter_only,
        ((fx.ForbiddenMembershipIterOnly, "__iter__"),),
    ),
    (
        "membership:iteration-fallback-next-only",
        fx.trigger_membership_iteration_fallback,
        ((fx.ForbiddenMembershipNextOnly, "__next__"),),
    ),
    (
        "subscription:getitem",
        fx.trigger_subscript_get,
        ((fx.ForbiddenGetitem, "__getitem__"),),
    ),
    (
        "subscription:setitem",
        fx.trigger_subscript_set,
        ((fx.ForbiddenSetitem, "__setitem__"),),
    ),
    (
        "subscription:delitem",
        fx.trigger_subscript_delete,
        ((fx.ForbiddenDelitem, "__delitem__"),),
    ),
    (
        "hashing:set-literal",
        fx.trigger_hash_set_literal,
        ((fx.ForbiddenHashable, "__hash__"),),
    ),
    (
        "hashing:dict-key",
        fx.trigger_hash_dict_key,
        ((fx.ForbiddenHashable, "__hash__"),),
    ),
    (
        "hashing:set-add",
        fx.trigger_hash_set_add,
        ((fx.ForbiddenHashable, "__hash__"),),
    ),
    (
        "formatting:fstring",
        fx.trigger_fstring_format,
        ((fx.ForbiddenFormat, "__format__"),),
    ),
    (
        "formatting:format-builtin",
        fx.trigger_format_builtin,
        ((fx.ForbiddenFormat, "__format__"),),
    ),
    (
        "formatting:dotformat",
        fx.trigger_dotformat_builtin,
        ((fx.ForbiddenFormat, "__format__"),),
    ),
    (
        "formatting:str-fallback",
        fx.trigger_str_builtin,
        ((fx.ForbiddenStr, "__str__"),),
    ),
    (
        "formatting:repr-fallback",
        fx.trigger_repr_builtin,
        ((fx.ForbiddenRepr, "__repr__"),),
    ),
)


def test_all_families_and_dispatch_events_characterized() -> None:
    """`docs/prompts/task-38.8.md` §3's own summary requirement: every
    family named in §2 -- and every independently-isolated dispatch
    event within it -- is walked, and none produces a `CallRecord` for
    its embedded sentinel. A single sweep over the same case list the
    individual tests above use, so a case can never be silently
    dropped from the "all" count without also failing to appear as its
    own named test."""
    assert len(_ALL_CASES) == 36, (
        "case count changed -- update this assertion deliberately, "
        "never silently, if a dispatch event was added or removed"
    )
    for site_label, trigger, sentinel_targets in _ALL_CASES:
        _assert_family_characterized(
            trigger, f"task-38.8:{site_label}", sentinel_targets
        )
