"""Task 38.8: characterization/regression tests for the implicit-
protocol-dispatch discovery gap (``docs/audits/task-38.5-risk-register.md``'s
**M-8**).

Originally Phase A.0-only (proving the pre-mechanism gap existed for
all 11 families named in `docs/prompts/task-38.8.md` §2). Phase A.1
(ADR-032 Option D, 2026-08-24) implemented production detection for
exactly 2 of those 11 families -- context managers and descriptors --
so this file now serves two roles side by side, for the *same* 36
independently isolated dispatch events, never collapsed into one:

* For the **2 mechanized families** (context managers, descriptors):
  this is now **regression protection**, not gap characterization --
  each case positively proves the mechanism *detects* the sentinel
  embedded in that dispatch event's own body, via identity
  (``verdict.category``/``module``/``qualname``), never a path
  substring or loose ``callee_text`` match.
* For the **remaining 9 unsupported families**: this remains
  unchanged **boundary characterization** -- each case still proves
  walking the trigger produces zero ``CallRecord`` referencing the
  embedded sentinel, exactly as it did before Phase A.1, proving the
  documented boundary has not silently eroded.

No case was deleted, skipped, or weakened to reach this state: the
same 36 fixtures, the same sentinel-integrity proof machinery, and the
same explicit case-count guard are all still here -- only the expected
outcome for the 8 now-mechanized cases (4 context-manager events, 4
descriptor events) was updated to match the production behavior this
task's own implementation added.

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
    *,
    expect_detected: bool,
) -> None:
    """Shared body for every dispatch-event test below -- one
    implementation, not one copy per test that could silently drift
    apart (the same discipline ``test_negative_controls.py`` already
    holds itself to for its own shared ``run_self_tests()`` call).

    ``expect_detected`` distinguishes the two roles this file now
    plays for the same 36 cases: ``True`` for the 8 cases belonging to
    the 2 families ADR-032 Option D mechanized (context managers,
    descriptors) -- regression protection, proving the mechanism
    positively detects the sentinel; ``False`` for the remaining 28
    cases (the 9 still-unsupported families) -- unchanged boundary
    characterization, proving the sentinel is still invisible."""
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
    if expect_detected:
        assert forbidden_open_records, (
            f"{site_label}: the mechanized family's own production detection "
            f"must discover the embedded sentinel via {trigger.__qualname__} "
            "-- a miss here is a real regression, not a characterization change"
        )
    else:
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
        expect_detected=False,
    )


def test_iteration_for_loop_next_only_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_for_loop,
        "task-38.8:iteration:for-loop-next-only",
        [(fx.ForbiddenNextOnly, "__next__")],
        expect_detected=False,
    )


def test_iteration_comprehension_next_only_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_list_comprehension,
        "task-38.8:iteration:comprehension-next-only",
        [(fx.ForbiddenNextOnly, "__next__")],
        expect_detected=False,
    )


# ---------------------------------------------------------------------
# 2. Starred unpacking -- __iter__ and __next__, isolated
# ---------------------------------------------------------------------


def test_starred_unpacking_iter_only_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_starred_unpacking_iter_only,
        "task-38.8:unpacking:iter-only",
        [(fx.ForbiddenUnpackIterOnly, "__iter__")],
        expect_detected=False,
    )


def test_starred_unpacking_next_only_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_starred_unpacking,
        "task-38.8:unpacking:next-only",
        [(fx.ForbiddenUnpackNextOnly, "__next__")],
        expect_detected=False,
    )


# ---------------------------------------------------------------------
# 3. Context managers -- __enter__ and __exit__, each isolated
# ---------------------------------------------------------------------


def test_sync_context_manager_enter_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_with_statement_enter_only,
        "task-38.8:context-manager:sync-enter",
        [(fx.ForbiddenEnterOnly, "__enter__")],
        expect_detected=True,
    )


def test_sync_context_manager_exit_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_with_statement,
        "task-38.8:context-manager:sync-exit",
        [(fx.ForbiddenExitOnly, "__exit__")],
        expect_detected=True,
    )


def test_async_context_manager_aenter_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_async_with_statement_enter_only,
        "task-38.8:context-manager:async-aenter",
        [(fx.ForbiddenAsyncEnterOnly, "__aenter__")],
        expect_detected=True,
    )


def test_async_context_manager_aexit_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_async_with_statement,
        "task-38.8:context-manager:async-aexit",
        [(fx.ForbiddenAsyncExitOnly, "__aexit__")],
        expect_detected=True,
    )


# ---------------------------------------------------------------------
# 4. Await -- __await__ (single stage)
# ---------------------------------------------------------------------


def test_await_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_await,
        "task-38.8:await:__await__",
        [(fx.ForbiddenAwaitable, "__await__")],
        expect_detected=False,
    )


# ---------------------------------------------------------------------
# 4b. Async iteration -- __aiter__ and __anext__, each isolated
# ---------------------------------------------------------------------


def test_async_iteration_aiter_only_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_async_for_aiter_only,
        "task-38.8:async-iteration:aiter-only",
        [(fx.ForbiddenAiterOnly, "__aiter__")],
        expect_detected=False,
    )


def test_async_iteration_anext_only_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_async_for,
        "task-38.8:async-iteration:anext-only",
        [(fx.ForbiddenAnextOnly, "__anext__")],
        expect_detected=False,
    )


# ---------------------------------------------------------------------
# 5. Properties and descriptors
# ---------------------------------------------------------------------


def test_property_get_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_property_get,
        "task-38.8:descriptor:property-get",
        [(fx.ForbiddenProperty, "value")],
        expect_detected=True,
    )


def test_descriptor_get_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_descriptor_get,
        "task-38.8:descriptor:raw-get",
        [(fx._ForbiddenGetDescriptor, "__get__")],  # noqa: SLF001
        expect_detected=True,
    )


def test_descriptor_set_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_descriptor_set,
        "task-38.8:descriptor:raw-set",
        [(fx._ForbiddenSetDescriptor, "__set__")],  # noqa: SLF001
        expect_detected=True,
    )


def test_descriptor_delete_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_descriptor_delete,
        "task-38.8:descriptor:raw-delete",
        [(fx._ForbiddenDeleteDescriptor, "__delete__")],  # noqa: SLF001
        expect_detected=True,
    )


# ---------------------------------------------------------------------
# 6. Equality, ordering, and arithmetic operators, including reflected
# ---------------------------------------------------------------------


def test_equality_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_equality,
        "task-38.8:operator:eq",
        [(fx.ForbiddenEq, "__eq__")],
        expect_detected=False,
    )


def test_ordering_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_less_than,
        "task-38.8:operator:lt",
        [(fx.ForbiddenLt, "__lt__")],
        expect_detected=False,
    )


def test_arithmetic_add_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_add,
        "task-38.8:operator:add",
        [(fx.ForbiddenAdd, "__add__")],
        expect_detected=False,
    )


def test_arithmetic_reflected_add_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_reflected_add,
        "task-38.8:operator:radd",
        [(fx.ForbiddenRadd, "__radd__")],
        expect_detected=False,
    )


# ---------------------------------------------------------------------
# 7. Truth testing -- __bool__ and the __len__ fallback
# ---------------------------------------------------------------------


def test_truth_bool_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_truth_bool,
        "task-38.8:truth:bool",
        [(fx.ForbiddenBool, "__bool__")],
        expect_detected=False,
    )


def test_truth_len_fallback_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_truth_len_fallback,
        "task-38.8:truth:len-fallback",
        [(fx.ForbiddenLenFallback, "__len__")],
        expect_detected=False,
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
        expect_detected=False,
    )


def test_membership_iteration_fallback_iter_only_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_membership_iteration_fallback_iter_only,
        "task-38.8:membership:iteration-fallback-iter-only",
        [(fx.ForbiddenMembershipIterOnly, "__iter__")],
        expect_detected=False,
    )


def test_membership_iteration_fallback_next_only_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_membership_iteration_fallback,
        "task-38.8:membership:iteration-fallback-next-only",
        [(fx.ForbiddenMembershipNextOnly, "__next__")],
        expect_detected=False,
    )


# ---------------------------------------------------------------------
# 9. Subscription and assignment/deletion
# ---------------------------------------------------------------------


def test_subscript_get_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_subscript_get,
        "task-38.8:subscription:getitem",
        [(fx.ForbiddenGetitem, "__getitem__")],
        expect_detected=False,
    )


def test_subscript_set_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_subscript_set,
        "task-38.8:subscription:setitem",
        [(fx.ForbiddenSetitem, "__setitem__")],
        expect_detected=False,
    )


def test_subscript_delete_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_subscript_delete,
        "task-38.8:subscription:delitem",
        [(fx.ForbiddenDelitem, "__delitem__")],
        expect_detected=False,
    )


# ---------------------------------------------------------------------
# 10. Hashing -- via set-literal, dict-key, and .add( insertion
# ---------------------------------------------------------------------


def test_hash_set_literal_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_hash_set_literal,
        "task-38.8:hashing:set-literal",
        [(fx.ForbiddenHashable, "__hash__")],
        expect_detected=False,
    )


def test_hash_dict_key_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_hash_dict_key,
        "task-38.8:hashing:dict-key",
        [(fx.ForbiddenHashable, "__hash__")],
        expect_detected=False,
    )


def test_hash_set_add_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_hash_set_add,
        "task-38.8:hashing:set-add",
        [(fx.ForbiddenHashable, "__hash__")],
        expect_detected=False,
    )


# ---------------------------------------------------------------------
# 11. Formatting -- __format__, with __str__/__repr__ fallback
# ---------------------------------------------------------------------


def test_format_fstring_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_fstring_format,
        "task-38.8:formatting:fstring",
        [(fx.ForbiddenFormat, "__format__")],
        expect_detected=False,
    )


def test_format_builtin_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_format_builtin,
        "task-38.8:formatting:format-builtin",
        [(fx.ForbiddenFormat, "__format__")],
        expect_detected=False,
    )


def test_format_dotformat_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_dotformat_builtin,
        "task-38.8:formatting:dotformat",
        [(fx.ForbiddenFormat, "__format__")],
        expect_detected=False,
    )


def test_format_str_fallback_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_str_builtin,
        "task-38.8:formatting:str-fallback",
        [(fx.ForbiddenStr, "__str__")],
        expect_detected=False,
    )


def test_format_repr_fallback_characterized() -> None:
    _assert_family_characterized(
        fx.trigger_repr_builtin,
        "task-38.8:formatting:repr-fallback",
        [(fx.ForbiddenRepr, "__repr__")],
        expect_detected=False,
    )


# ---------------------------------------------------------------------
# Summary -- all 11 families, every isolated dispatch event, one sweep
# ---------------------------------------------------------------------

_ALL_CASES: tuple[
    tuple[str, Callable[..., object], tuple[tuple[type, str], ...], bool], ...
] = (
    (
        "iteration:iter-only",
        fx.trigger_for_loop_iter_only,
        ((fx.ForbiddenIterOnly, "__iter__"),),
        False,
    ),
    (
        "iteration:for-loop-next-only",
        fx.trigger_for_loop,
        ((fx.ForbiddenNextOnly, "__next__"),),
        False,
    ),
    (
        "iteration:comprehension-next-only",
        fx.trigger_list_comprehension,
        ((fx.ForbiddenNextOnly, "__next__"),),
        False,
    ),
    (
        "unpacking:iter-only",
        fx.trigger_starred_unpacking_iter_only,
        ((fx.ForbiddenUnpackIterOnly, "__iter__"),),
        False,
    ),
    (
        "unpacking:next-only",
        fx.trigger_starred_unpacking,
        ((fx.ForbiddenUnpackNextOnly, "__next__"),),
        False,
    ),
    (
        "context-manager:sync-enter",
        fx.trigger_with_statement_enter_only,
        ((fx.ForbiddenEnterOnly, "__enter__"),),
        True,
    ),
    (
        "context-manager:sync-exit",
        fx.trigger_with_statement,
        ((fx.ForbiddenExitOnly, "__exit__"),),
        True,
    ),
    (
        "context-manager:async-aenter",
        fx.trigger_async_with_statement_enter_only,
        ((fx.ForbiddenAsyncEnterOnly, "__aenter__"),),
        True,
    ),
    (
        "context-manager:async-aexit",
        fx.trigger_async_with_statement,
        ((fx.ForbiddenAsyncExitOnly, "__aexit__"),),
        True,
    ),
    (
        "await:__await__",
        fx.trigger_await,
        ((fx.ForbiddenAwaitable, "__await__"),),
        False,
    ),
    (
        "async-iteration:aiter-only",
        fx.trigger_async_for_aiter_only,
        ((fx.ForbiddenAiterOnly, "__aiter__"),),
        False,
    ),
    (
        "async-iteration:anext-only",
        fx.trigger_async_for,
        ((fx.ForbiddenAnextOnly, "__anext__"),),
        False,
    ),
    (
        "descriptor:property-get",
        fx.trigger_property_get,
        ((fx.ForbiddenProperty, "value"),),
        True,
    ),
    (
        "descriptor:raw-get",
        fx.trigger_descriptor_get,
        ((fx._ForbiddenGetDescriptor, "__get__"),),  # noqa: SLF001
        True,
    ),
    (
        "descriptor:raw-set",
        fx.trigger_descriptor_set,
        ((fx._ForbiddenSetDescriptor, "__set__"),),  # noqa: SLF001
        True,
    ),
    (
        "descriptor:raw-delete",
        fx.trigger_descriptor_delete,
        ((fx._ForbiddenDeleteDescriptor, "__delete__"),),  # noqa: SLF001
        True,
    ),
    ("operator:eq", fx.trigger_equality, ((fx.ForbiddenEq, "__eq__"),), False),
    ("operator:lt", fx.trigger_less_than, ((fx.ForbiddenLt, "__lt__"),), False),
    ("operator:add", fx.trigger_add, ((fx.ForbiddenAdd, "__add__"),), False),
    (
        "operator:radd",
        fx.trigger_reflected_add,
        ((fx.ForbiddenRadd, "__radd__"),),
        False,
    ),
    ("truth:bool", fx.trigger_truth_bool, ((fx.ForbiddenBool, "__bool__"),), False),
    (
        "truth:len-fallback",
        fx.trigger_truth_len_fallback,
        ((fx.ForbiddenLenFallback, "__len__"),),
        False,
    ),
    (
        "membership:contains",
        fx.trigger_membership_contains,
        ((fx.ForbiddenContains, "__contains__"),),
        False,
    ),
    (
        "membership:iteration-fallback-iter-only",
        fx.trigger_membership_iteration_fallback_iter_only,
        ((fx.ForbiddenMembershipIterOnly, "__iter__"),),
        False,
    ),
    (
        "membership:iteration-fallback-next-only",
        fx.trigger_membership_iteration_fallback,
        ((fx.ForbiddenMembershipNextOnly, "__next__"),),
        False,
    ),
    (
        "subscription:getitem",
        fx.trigger_subscript_get,
        ((fx.ForbiddenGetitem, "__getitem__"),),
        False,
    ),
    (
        "subscription:setitem",
        fx.trigger_subscript_set,
        ((fx.ForbiddenSetitem, "__setitem__"),),
        False,
    ),
    (
        "subscription:delitem",
        fx.trigger_subscript_delete,
        ((fx.ForbiddenDelitem, "__delitem__"),),
        False,
    ),
    (
        "hashing:set-literal",
        fx.trigger_hash_set_literal,
        ((fx.ForbiddenHashable, "__hash__"),),
        False,
    ),
    (
        "hashing:dict-key",
        fx.trigger_hash_dict_key,
        ((fx.ForbiddenHashable, "__hash__"),),
        False,
    ),
    (
        "hashing:set-add",
        fx.trigger_hash_set_add,
        ((fx.ForbiddenHashable, "__hash__"),),
        False,
    ),
    (
        "formatting:fstring",
        fx.trigger_fstring_format,
        ((fx.ForbiddenFormat, "__format__"),),
        False,
    ),
    (
        "formatting:format-builtin",
        fx.trigger_format_builtin,
        ((fx.ForbiddenFormat, "__format__"),),
        False,
    ),
    (
        "formatting:dotformat",
        fx.trigger_dotformat_builtin,
        ((fx.ForbiddenFormat, "__format__"),),
        False,
    ),
    (
        "formatting:str-fallback",
        fx.trigger_str_builtin,
        ((fx.ForbiddenStr, "__str__"),),
        False,
    ),
    (
        "formatting:repr-fallback",
        fx.trigger_repr_builtin,
        ((fx.ForbiddenRepr, "__repr__"),),
        False,
    ),
)


def test_all_families_and_dispatch_events_characterized() -> None:
    """`docs/prompts/task-38.8.md` §3's own summary requirement: every
    family named in §2 -- and every independently-isolated dispatch
    event within it -- is walked. A single sweep over the same case
    list the individual tests above use, so a case can never be
    silently dropped from the "all" count without also failing to
    appear as its own named test.

    Split explicitly into two sub-sweeps, never merged into one
    "all clear" claim: the 8 mechanized (context-manager/descriptor)
    cases must each positively detect their sentinel; the remaining 28
    unmechanized cases must each still show zero detection -- the
    8+28 split itself is asserted, so a case silently moving between
    the two groups (e.g. a future change accidentally widening
    detection) fails loudly here."""
    assert len(_ALL_CASES) == 36, (
        "case count changed -- update this assertion deliberately, "
        "never silently, if a dispatch event was added or removed"
    )

    supported_cases = [c for c in _ALL_CASES if c[3]]
    unsupported_cases = [c for c in _ALL_CASES if not c[3]]
    assert len(supported_cases) == 8, (
        "expected exactly 8 mechanized (context-manager + descriptor) "
        "dispatch-event cases -- update deliberately if ADR-032's Option D "
        "scope ever changes"
    )
    assert len(unsupported_cases) == 28, (
        "expected exactly 28 still-unsupported dispatch-event cases "
        "(9 families' worth) -- update deliberately, never silently"
    )

    for site_label, trigger, sentinel_targets, expect_detected in supported_cases:
        _assert_family_characterized(
            trigger,
            f"task-38.8:{site_label}",
            sentinel_targets,
            expect_detected=expect_detected,
        )
    for site_label, trigger, sentinel_targets, expect_detected in unsupported_cases:
        _assert_family_characterized(
            trigger,
            f"task-38.8:{site_label}",
            sentinel_targets,
            expect_detected=expect_detected,
        )
