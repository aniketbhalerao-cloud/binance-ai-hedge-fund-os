"""Task 38.6 Harness Requirement 7: negative-control fixtures.

Five deliberately unsafe shapes, one per named requirement-7 case. Not
imported by any production module, never registered with
``app.wiring``, never executed for real by anything except the harness
tests that prove each one is *detected*.
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FixtureWithForbiddenPostInit:
    """A ``__post_init__`` performing a forbidden operation (opens a
    real file). Requirement 7, case 1."""

    path: str

    def __post_init__(self) -> None:
        open(self.path)  # noqa: SIM115 - deliberately forbidden, never actually run


def fixture_unresolvable_call(mystery: object) -> object:
    """A call the harness's identity resolution genuinely cannot pin to
    a live object: ``mystery`` carries no annotation and is not a
    project-owned/known type, so its attribute access has no resolvable
    identity. Requirement 7, case 2."""
    return mystery.do_something_unverifiable()  # type: ignore[attr-defined]


_fixture_module_global: dict[str, int] = {}


def fixture_mutates_module_global_from_plain_function() -> None:
    """An ordinary (non-nested) function mutating a module-global dict
    via subscript assignment and a mutating method call. Requirement 7,
    case 3 -- exactly the shape M-7 gap 3 named as previously
    undetected."""
    _fixture_module_global["mutated"] = 1
    _fixture_module_global.update({"other": 2})


def fixture_calls_os_open_directly() -> None:
    """A direct ``os.open`` call -- the lower-level file-descriptor
    primitive M-7 gap 2 named as unpatched by the v5 runtime check.
    Requirement 7, case 4."""
    fd = os.open("/tmp/audit-harness-fixture-must-never-run", os.O_RDONLY)
    os.close(fd)


class FixtureDBClient:
    """Simulates a DB client's ``connect()`` -- routes through
    ``socket.create_connection`` (the primitive a TCP-based DB driver,
    e.g. psycopg/asyncpg, eventually reaches), so the runtime-denial
    patch on that primitive intercepts it, without this fixture ever
    completing a real connection. Requirement 7, case 5 (one of three)."""

    def connect(self) -> None:
        socket.create_connection(("127.0.0.1", 1), timeout=0.01)


class FixtureRedisClient:
    """Simulates a Redis client's ``connect()`` -- routes through the
    lower-level ``socket.socket()`` + ``.connect()`` two-step pattern
    real Redis clients typically use (distinct from
    ``FixtureDBClient``'s single-call ``create_connection`` shape), so
    the runtime-denial patch on the ``socket.socket`` *class itself*
    intercepts construction before any connection is even attempted.
    Requirement 7, case 5 (one of three)."""

    def connect(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", 1))


class FixtureExchangeAdapterClient:
    """Simulates an exchange-adapter connection -- a third, independent
    named client (distinct code path from the DB and Redis fixtures)
    routing through the same socket primitives a real
    ``exchange_adapters``/CCXT-backed connection would eventually reach.
    Requirement 7, case 5 (one of three)."""

    def connect(self) -> None:
        with socket.create_connection(("127.0.0.1", 1), timeout=0.01) as sock:
            sock.send(b"never reached")


# -- Task 38.7 category fixtures --------------------------------------
# This module (``tests.audit_harness.fixtures``) is itself outside
# ``audit_harness.identity.PROJECT_TOP_LEVEL_PACKAGES`` -- the same
# "non-project-owned" status real third-party code has -- so the two
# functions below double as a deterministic, cyclic, third-party-shaped
# call graph for Category A's termination requirement, with no real
# third-party dependency needed.


def fixture_cycle_a(n: int) -> int:
    """Calls :func:`fixture_cycle_b`, which calls back into this
    function -- a genuine cycle in non-project-owned source. Proves the
    fixed-point traversal (visited-function-identity dedup) terminates
    rather than looping forever."""
    if n <= 0:
        return 0
    return fixture_cycle_b(n - 1)


def fixture_cycle_b(n: int) -> int:
    if n <= 0:
        return 0
    return fixture_cycle_a(n - 1)


def fixture_multi_hop_chain() -> str:
    """A two-hop local-variable chain: ``x = f(); x.g().h()`` --
    Category B's transitive local-variable-type-inference shape. Second
    hop uses ``.lower()`` (not ``.upper()``) -- ``builtins.str.lower`` is
    an existing, already-authorized policy entry; ``builtins.str.upper``
    was explicitly deferred, not authorized, by ADR-032's Task 38.7
    Phase 0 decision (2026-08-22)."""
    text = fixture_returns_str()
    return text.strip().lower()


def fixture_returns_str() -> str:
    return "  value  "


def fixture_str_or_none_guarded(value: str | None) -> str:
    """The exact ``if value is None: return/raise`` guard shape Category
    C's flow-sensitive narrowing recognizes, on a *local* variable (not
    a bare parameter -- ``_real_param_types`` already unwraps parameter
    unions unconditionally, so a parameter alone would not exercise the
    new narrowing mechanism)."""
    local: str | None = value
    if local is None:
        raise ValueError("value is required")
    return local.strip().lower()


def fixture_str_or_none_unguarded(value: str | None) -> object:
    """The same union-typed local, but with **no** preceding
    ``is None`` guard -- proves narrowing is never assumed without
    evidence. Deliberately calls a method that only exists on ``str``,
    never on ``None``, at runtime this would raise on a ``None`` input;
    statically it must stay unresolved rather than being silently
    approved. Uses ``.lower()`` (not ``.upper()``) deliberately:
    ``builtins.str.lower`` *is* an authorized policy entry, so this
    negative control is discriminatory -- if narrowing were ever
    incorrectly assumed here without a preceding guard, the call would
    wrongly resolve to ``exact_identity_policy`` and the test would
    catch it. ``.upper()`` (unauthorized either way) could not tell
    correct non-narrowing apart from a merely-unauthorized identity."""
    local: str | None = value
    return local.lower()  # type: ignore[union-attr]


def fixture_subscript_chain() -> None:
    """``container[key].append(...)`` -- Category C's subscript-target
    chain, resolved from ``buckets``'s own ``dict[str, list[str]]``
    annotation, the same shape ``app.planner._plan``'s real
    ``dependents``/``deps_by_component`` locals use."""
    buckets: dict[str, list[str]] = {"k": []}
    buckets["k"].append("v")


# -- Termination-correctness repair: a chain deeper than the old,
# now-removed 10-hop cap -----------------------------------------------
#
# 12 straight-line hops (fixture_deep_chain_00 -> ... -> _11 -> the
# distinguishable leaf call), no cycle, no shared function reused at
# two depths -- proves a genuinely deep, non-cyclic chain is walked to
# its real end rather than being cut off at any fixed depth.


def fixture_deep_chain_00() -> str:
    return fixture_deep_chain_01()


def fixture_deep_chain_01() -> str:
    return fixture_deep_chain_02()


def fixture_deep_chain_02() -> str:
    return fixture_deep_chain_03()


def fixture_deep_chain_03() -> str:
    return fixture_deep_chain_04()


def fixture_deep_chain_04() -> str:
    return fixture_deep_chain_05()


def fixture_deep_chain_05() -> str:
    return fixture_deep_chain_06()


def fixture_deep_chain_06() -> str:
    return fixture_deep_chain_07()


def fixture_deep_chain_07() -> str:
    return fixture_deep_chain_08()


def fixture_deep_chain_08() -> str:
    return fixture_deep_chain_09()


def fixture_deep_chain_09() -> str:
    return fixture_deep_chain_10()


def fixture_deep_chain_10() -> str:
    return fixture_deep_chain_11()


def fixture_deep_chain_11() -> str:
    # .lower() (not .upper()) -- see fixture_multi_hop_chain's docstring.
    return "deep-chain-leaf-reached".lower()


# -- Local callable-alias resolution (Task 38.7) -------------------------
#
# `_len = len; _len(value)` / `emit = values.append; emit(value)` -- the
# exact shape `sre_parse.py`/`sre_compile.py` use throughout (`_len =
# len`, `emit = code.append`), reachable statically without executing
# anything: a plain local Name written exactly once, unconditionally, as
# a direct statement of the function's own body, whose RHS is a Name or
# single-level Attribute the walker already resolves through its
# existing global/closure/local-variable-type-inference mechanisms.


def fixture_local_callable_alias_direct(value: str) -> int:
    """Positive: a bare builtin bound to a plain local name, then called
    through that alias."""
    _len = len
    return _len(value)


def fixture_local_callable_alias_typed_method(value: str) -> None:
    """Positive: a bound method of a locally-typed container, aliased to
    a plain local name -- the exact `emit = code.append` shape."""
    values: list[str] = []
    emit = values.append
    emit(value)


def fixture_local_callable_alias_call_before_assignment(value: str) -> int:
    """Negative: the call textually precedes its own alias assignment --
    the mechanism does no control-flow analysis, only definite
    program-order assignment-before-use, so this must stay unresolved."""
    result = _alias(value)  # type: ignore[operator]  # noqa: F821
    _alias = len
    return result


def fixture_local_callable_alias_conditional_branch(value: str, flag: bool) -> int:
    """Negative: the assignment exists only inside an `if` branch, never
    unconditionally in the function's own direct body -- must not be
    treated as dominating the later call."""
    if flag:
        _alias = len
    return _alias(value)  # type: ignore[operator, possibly-undefined]  # noqa: F821


def fixture_local_callable_alias_reassigned(value: str) -> int:
    """Negative: a second write (reassignment) to the same name anywhere
    in the function scope disqualifies it entirely, regardless of which
    write the call would actually observe at runtime."""
    _alias = len
    _alias = str  # noqa: F811
    return _alias(value)  # type: ignore[operator]


def fixture_local_callable_alias_deleted(value: str) -> int:
    """Negative: a `del` of the name anywhere in the function scope is
    itself a disqualifying second write, even though the name is
    reassigned afterward."""
    _alias = len
    del _alias
    _alias = len  # noqa: F811
    return _alias(value)  # type: ignore[operator]


def fixture_local_callable_alias_unknown_rhs(value: object) -> int:
    """Negative: the RHS name does not resolve to anything at all (not a
    closure var, not a global, not a builtin) -- never accepted."""
    _alias = _totally_unknown_name_never_defined_anywhere  # type: ignore[name-defined]  # noqa: F821
    return _alias(value)  # type: ignore[operator]


_fixture_non_callable_marker: str = "not callable"


def fixture_local_callable_alias_non_callable_rhs(value: object) -> int:
    """Negative: the RHS resolves to a real, known object that is not
    itself callable -- never accepted as an alias."""
    _alias = _fixture_non_callable_marker
    return _alias(value)  # type: ignore[operator]


def fixture_local_callable_alias_leak_check_defines_alias(value: str) -> int:
    """One half of the no-leakage pair: this function defines `_alias`
    locally and calls it."""
    _alias = len
    return _alias(value)


def fixture_local_callable_alias_leak_check_no_alias_here(value: str) -> int:
    """The other half: a completely separate function that never defines
    `_alias` at all and calls it anyway -- a fresh walk of this function
    must never see the other function's alias table."""
    return _alias(value)  # type: ignore[name-defined]  # noqa: F821


# -- Call-site parameter-type propagation (Task 38.7) ---------------------
#
# `re._parser.parse -> _parse_sub -> _parse`'s exact real shape: a local
# whose type `_collect_local_var_types` already infers (`source =
# Tokenizer(str)`) is passed by bare Name into a callee whose own
# parameter then accesses an attribute on it -- `_bind_call_site_locals`
# must propagate that already-known type into the callee's `forced_locals`
# so `param.method()` inside the callee resolves.


class FixturePropagationTarget:
    def marker_method(self) -> str:
        return "reached"


class FixturePropagationTargetA:
    def marker_method(self) -> str:
        return "A"


class FixturePropagationTargetB:
    def marker_method(self) -> str:
        return "B"


def fixture_param_propagation_single_hop() -> None:
    """Positive: a locally-inferred type, passed as a direct Name
    argument to a plain callee -- the callee's own parameter must
    receive that type."""
    value = FixturePropagationTarget()
    fixture_param_propagation_callee_hop1(value)


def fixture_param_propagation_callee_hop1(item: object) -> None:
    item.marker_method()  # type: ignore[attr-defined]


def fixture_param_propagation_three_hop_a() -> None:
    """Positive: the same propagation must continue across a second
    hop (`_b -> _c`) with no additional mechanism beyond the one fix at
    the first hop -- `forced_locals` merged into the callee's own `loc`
    is what the *existing* `_bind_call_site_locals` already checks."""
    value = FixturePropagationTarget()
    fixture_param_propagation_three_hop_b(value)


def fixture_param_propagation_three_hop_b(item: object) -> None:
    fixture_param_propagation_three_hop_c(item)


def fixture_param_propagation_three_hop_c(item: object) -> None:
    item.marker_method()  # type: ignore[attr-defined]


def fixture_param_propagation_caller_a() -> None:
    """One half of the specialization-isolation pair: passes a
    `FixturePropagationTargetA` instance to the shared callee."""
    value = FixturePropagationTargetA()
    fixture_param_propagation_shared_callee(value)


def fixture_param_propagation_caller_b() -> None:
    """The other half: passes a `FixturePropagationTargetB` instance to
    the *same* shared callee -- each caller's own walk must specialize
    independently, never merging the two types into one result."""
    value = FixturePropagationTargetB()
    fixture_param_propagation_shared_callee(value)


def fixture_param_propagation_shared_callee(item: object) -> None:
    item.marker_method()  # type: ignore[attr-defined]


def fixture_param_propagation_nonname_argument() -> None:
    """Negative: the argument is a Call expression, not a bare Name --
    `_bind_call_site_locals` only ever matches `isinstance(value_node,
    ast.Name)`, so nothing propagates and the callee's attribute call
    stays unresolved."""
    fixture_param_propagation_callee_hop1(FixturePropagationTarget())


def fixture_param_propagation_untyped_local(mystery: object) -> None:
    """Negative: `value = mystery` is a plain Name-to-Name assignment,
    never a Call -- `_collect_local_var_types` never infers a type for
    `value`, so there is nothing in `local_var_types` to propagate and
    the callee's attribute call stays unresolved."""
    value = mystery
    fixture_param_propagation_callee_hop1(value)


# -- Implicit method-receiver binding (Task 38.7) --------------------------
#
# `state.checklookbehindgroup(gid, source)`'s exact real shape: an
# ordinary instance method reached via `local-variable-type-inference`
# (the receiver is a locally-typed value, not a live instance) resolves
# to the UNBOUND function -- its own first parameter is a receiver slot
# the AST call's explicit arguments never fill, silently shifting every
# later argument one position early unless the receiver is prepended.


class FixtureReceiverBindingHelper:
    def marker_method(self) -> str:
        return "reached"


class FixtureReceiverBindingTarget:
    def method_with_extra_arg(self, unused_first: object, helper: object) -> None:
        helper.marker_method()  # type: ignore[attr-defined]


class FixtureReceiverBindingBase:
    def method_with_extra_arg(self, unused_first: object, helper: object) -> None:
        helper.marker_method()  # type: ignore[attr-defined]


class FixtureReceiverBindingChild(FixtureReceiverBindingBase):
    pass


class FixtureReceiverBindingWithStatic:
    @staticmethod
    def static_method_with_arg(helper: object) -> None:
        helper.marker_method()  # type: ignore[attr-defined]


class FixtureReceiverBindingWithClassmethod:
    @classmethod
    def classmethod_with_arg(cls, helper: object) -> None:
        helper.marker_method()  # type: ignore[attr-defined]


def fixture_receiver_binding_two_arg_positive() -> None:
    """Positive: an ordinary instance method, resolved via
    `local-variable-type-inference`, called with two explicit args --
    the second (`helper`) must be correctly bound (not shifted into the
    receiver slot) and remain usable inside the callee's own body."""
    value = FixtureReceiverBindingTarget()
    helper = FixtureReceiverBindingHelper()
    value.method_with_extra_arg(1, helper)


def fixture_receiver_binding_inherited_positive() -> None:
    """Positive: the same shape, but the method is inherited from a
    base class -- `inspect.getattr_static` on the subclass must still
    correctly classify it as a plain function."""
    value = FixtureReceiverBindingChild()
    helper = FixtureReceiverBindingHelper()
    value.method_with_extra_arg(1, helper)


def fixture_receiver_binding_staticmethod_unchanged() -> None:
    """Negative: a `staticmethod` reached via `local-variable-type-inference`
    on its owning locally-typed value -- no receiver needed at all;
    `inspect.getattr_static` returns the raw `staticmethod` wrapper
    (never a plain `function`), so nothing is prepended."""
    value = FixtureReceiverBindingWithStatic()
    helper = FixtureReceiverBindingHelper()
    value.static_method_with_arg(helper)


def fixture_receiver_binding_classmethod_unchanged() -> None:
    """Negative: a `classmethod` reached the same way -- `getattr`
    already returns a bound method (`cls` filled in); `getattr_static`
    returns the raw `classmethod` wrapper (never a plain `function`),
    so nothing is prepended."""
    value = FixtureReceiverBindingWithClassmethod()
    helper = FixtureReceiverBindingHelper()
    value.classmethod_with_arg(helper)


def fixture_receiver_binding_c_descriptor_unchanged() -> None:
    """Negative: a C-implemented method (`list.append`) reached via
    `local-variable-type-inference` -- `inspect.getattr_static(list,
    "append")` is a `method_descriptor`, never a plain `function`, so
    the receiver-prepend fix never applies; behavior is exactly the
    same (unfixed) shape as before this change, never guessed."""
    value: list[object] = []
    marker = "x"
    value.append(marker)
