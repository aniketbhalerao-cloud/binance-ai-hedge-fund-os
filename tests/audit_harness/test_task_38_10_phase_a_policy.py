"""Task 38.10 Phase A regression tests: the nine exact callable-SLOT
identities ADR-032's "Task 38.10 Phase 0" section authorizes (2026-09-02,
Aniket Bhalerao -- project owner/reviewer) resolve via
``EXACT_IDENTITY_POLICY``, and every identity that same authorization
explicitly deferred, rejected, or declined to authorize stays out of it.

The pinning is deliberately two-sided. A test that only proved the nine
resolve would pass equally well against a wildcard or a family-level
exemption; the deferred half is what proves the table is still a set of
individually reviewed exact identities. Each deferred case below is
chosen for a *different* reason for exclusion, so a single over-broad
rule cannot satisfy them all at once.

Nothing here executes any dangerous behaviour: the assertions classify
callables, they never invoke them.
"""

from __future__ import annotations

import _thread
import collections
import functools
import io
import itertools
import weakref

from audit_harness.identity import (
    EXACT_IDENTITY_POLICY,
    IdentityVerdict,
    classify_callable,
    defining_module_of_method,
    is_namedtuple_generated_new,
    module_and_qualname,
)

# -- The two authorization sets, verbatim from ADR-032 Task 38.10 Phase 0 --

#: The exact nine slots authorized. Order matches the ADR's own list.
AUTHORIZED_SLOTS: tuple[tuple[type, str, str], ...] = (
    (_thread.RLock, "__new__", "_thread.RLock.__new__"),
    (AssertionError, "__new__", "builtins.AssertionError.__new__"),
    (AssertionError, "__init__", "builtins.AssertionError.__init__"),
    (AttributeError, "__init__", "builtins.AttributeError.__init__"),
    (NotImplementedError, "__new__", "builtins.NotImplementedError.__new__"),
    (NotImplementedError, "__init__", "builtins.NotImplementedError.__init__"),
    (OverflowError, "__new__", "builtins.OverflowError.__new__"),
    (OverflowError, "__init__", "builtins.OverflowError.__init__"),
    (functools.partial, "__new__", "functools.partial.__new__"),
)

#: Every identity the same authorization explicitly did NOT authorize,
#: with the reason it was excluded -- the reason is asserted nowhere but
#: recorded here so a future reader cannot mistake the list for an
#: arbitrary denylist.
DEFERRED_SLOTS: tuple[tuple[type, str, str, str], ...] = (
    # (a) construction-time numeric coercion (__int__/__index__/__trunc__)
    (int, "__new__", "builtins.int.__new__", "callback: numeric coercion"),
    (range, "__new__", "builtins.range.__new__", "callback: __index__"),
    # (b) construction-time __bytes__/__index__/__iter__/__buffer__
    (bytes, "__new__", "builtins.bytes.__new__", "callback: bytes conversion"),
    (bytearray, "__init__", "builtins.bytearray.__init__", "callback: buffer/iter"),
    (memoryview, "__new__", "builtins.memoryview.__new__", "callback: PEP 688"),
    # (c) construction-time iteration / mapping-protocol dispatch
    (collections.deque, "__init__", "collections.deque.__init__", "callback: __iter__"),
    (
        collections.OrderedDict,
        "__init__",
        "collections.OrderedDict.__init__",
        "callback: keys()/__getitem__",
    ),
    (itertools.islice, "__new__", "itertools.islice.__new__", "callback: iter()"),
    (map, "__new__", "builtins.map.__new__", "callback: iter()"),
    (SyntaxError, "__init__", "builtins.SyntaxError.__init__", "callback: __iter__"),
    (
        _thread._ExceptHookArgs,
        "__new__",
        "_thread._ExceptHookArgs.__new__",
        "callback: sequence consumption",
    ),
    # (d) deferred, GC-timed arbitrary user callable
    (
        weakref.ReferenceType,
        "__new__",
        "weakref.ReferenceType.__new__",
        "callback: deferred GC callback",
    ),
    (
        weakref.ReferenceType,
        "__init__",
        "weakref.ReferenceType.__init__",
        "callback: deferred GC callback",
    ),
    # (e) no callback, but deferred for its own recorded reason
    (
        OSError,
        "__new__",
        "builtins.OSError.__new__",
        "deeper review: errno->subclass type substitution",
    ),
    (type, "__init__", "builtins.type.__init__", "deeper review: no node benefit"),
    # (f) rejected outright -- arbitrary class-creation hooks
    (type, "__new__", "builtins.type.__new__", "rejected: metaclass/__set_name__"),
    # (g) evidence-safe but deliberately NOT authorized (resolves no node
    #     while its sibling slot stays deferred)
    (OSError, "__init__", "builtins.OSError.__init__", "safe but no node benefit"),
    (bytearray, "__new__", "builtins.bytearray.__new__", "safe but no node benefit"),
    (
        collections.deque,
        "__new__",
        "collections.deque.__new__",
        "safe but no node benefit",
    ),
    # (h) Family E -- I/O types, deferred since Phase 0.1
    (io.StringIO, "__init__", "_io.StringIO.__init__", "Family E: I/O type"),
    (io.StringIO, "__new__", "_io.StringIO.__new__", "Family E: I/O type"),
    (io.TextIOWrapper, "__init__", "_io.TextIOWrapper.__init__", "Family E: I/O type"),
)

#: The type objects whose slots are authorized. The authorization is
#: slot-only; calling the type runs both slots plus whatever the type's
#: own construction protocol dispatches, so none of these may be in the
#: table.
UNAUTHORIZED_TYPES: tuple[type, ...] = (
    _thread.RLock,
    AssertionError,
    AttributeError,
    NotImplementedError,
    OverflowError,
    functools.partial,
)


def _classify_slot(cls: type, slot_name: str) -> IdentityVerdict:
    """Classify one constructor slot exactly the way
    ``StaticWalker.classify_nodes``' own ``classify_ctor`` does, so this
    test pins the real resolution path rather than a convenient
    approximation of it."""
    method = getattr(cls, slot_name)
    is_nt_new = slot_name == "__new__" and is_namedtuple_generated_new(cls, method)
    return classify_callable(
        method,
        module=defining_module_of_method(cls, method),
        qualname=(
            getattr(method, "__qualname__", None) or module_and_qualname(method)[1]
        ),
        is_namedtuple_generated=is_nt_new,
    )


# -- Authorized: exactly nine, each resolving with a real rationale -----


def test_policy_version_bumped_for_task_38_10_phase_a() -> None:
    """The table changed, so its version must have moved off Task 38.7's."""
    from audit_harness.identity import EXACT_IDENTITY_POLICY_VERSION

    assert EXACT_IDENTITY_POLICY_VERSION == "2026-09-02.1"


def test_nine_authorized_slots_are_in_the_policy_table() -> None:
    """Each authorized key is present with its own nonempty rationale."""
    for _cls, _slot, key in AUTHORIZED_SLOTS:
        assert key in EXACT_IDENTITY_POLICY, key
        rationale = EXACT_IDENTITY_POLICY[key]
        assert isinstance(rationale, str) and rationale.strip(), key


def test_nine_authorized_slots_classify_exact_identity_policy() -> None:
    """Each authorized slot resolves through the real ``classify_ctor``
    path, not merely by being a dict key."""
    for cls, slot, key in AUTHORIZED_SLOTS:
        verdict = _classify_slot(cls, slot)
        assert verdict.category == "exact_identity_policy", (key, verdict.category)
        assert verdict.rationale is not None and verdict.rationale.strip(), key


def test_each_authorized_rationale_is_individually_written() -> None:
    """No generic rationale copied across the nine -- the authorization
    requires an identity-specific operational boundary for each."""
    rationales = [EXACT_IDENTITY_POLICY[key] for _c, _s, key in AUTHORIZED_SLOTS]
    assert len(set(rationales)) == len(rationales)


def test_partial_rationale_states_the_store_not_invoke_boundary() -> None:
    """`functools.partial.__new__`'s entry must say, in its own text,
    that it stores rather than invokes the wrapped callable and does not
    authorize the later invocation -- the single most load-bearing
    qualification in this authorization."""
    rationale = EXACT_IDENTITY_POLICY["functools.partial.__new__"]
    lowered = rationale.lower()
    assert "stores" in lowered
    assert "does not invoke" in lowered
    assert "does not authorize the later invocation" in lowered


def test_partial_deferred_invocation_still_fails_closed() -> None:
    """The stored callable's later invocation is a separate explicit
    call that must stay `unresolved`; if this ever flips, the
    `functools.partial.__new__` entry must be re-reviewed."""
    bound = functools.partial(len, [1])
    module, qualname = module_and_qualname(bound)
    assert classify_callable(bound, module=module, qualname=qualname).category == (
        "unresolved"
    )
    assert (
        classify_callable(
            functools.partial.__call__,
            module="functools",
            qualname="partial.__call__",
        ).category
        == "unresolved"
    )


# -- Deferred / rejected: absent, and still not policy-accepted --------


def test_deferred_and_rejected_slots_are_absent_from_the_policy_table() -> None:
    for _cls, _slot, key, _reason in DEFERRED_SLOTS:
        assert key not in EXACT_IDENTITY_POLICY, key


def test_deferred_and_rejected_slots_do_not_classify_exact_identity_policy() -> None:
    """Each excluded slot must fail closed through the real path -- a
    wildcard, name-pattern, or family-level exemption would break this."""
    for cls, slot, key, _reason in DEFERRED_SLOTS:
        verdict = _classify_slot(cls, slot)
        assert verdict.category != "exact_identity_policy", (key, verdict.category)


def test_representative_exclusions_classify_unresolved() -> None:
    """The seven representatives named by Task 38.10 Phase A, one per
    distinct reason for exclusion, each still classify `unresolved`."""
    representatives = (
        (int, "__new__", "builtins.int.__new__"),
        (SyntaxError, "__init__", "builtins.SyntaxError.__init__"),
        (type, "__new__", "builtins.type.__new__"),
        (weakref.ReferenceType, "__new__", "weakref.ReferenceType.__new__"),
        (io.TextIOWrapper, "__init__", "_io.TextIOWrapper.__init__"),
        (bytearray, "__new__", "builtins.bytearray.__new__"),
        (collections.deque, "__new__", "collections.deque.__new__"),
    )
    for cls, slot, key in representatives:
        verdict = _classify_slot(cls, slot)
        assert verdict.category == "unresolved", (key, verdict.category)
        assert verdict.rationale is None, key


# -- Slot-only: the corresponding type identities stay out -------------


def test_authorized_types_themselves_are_not_policy_accepted() -> None:
    """The authorization covers slots only. No corresponding type object
    may be in the table or classify `exact_identity_policy`."""
    for cls in UNAUTHORIZED_TYPES:
        module, qualname = module_and_qualname(cls)
        key = f"{module}.{qualname}"
        assert key not in EXACT_IDENTITY_POLICY, key
        verdict = classify_callable(cls, module=module, qualname=qualname)
        assert verdict.category != "exact_identity_policy", (key, verdict.category)


def test_exception_and_lock_type_identities_remain_unresolved() -> None:
    """The five C-implemented type identities among them stay
    `unresolved` specifically (``functools.partial`` is excluded here:
    it resolves as `project_source_available` through the pure-Python
    `functools` fallback, which is a pre-existing, separate disposition
    this authorization neither relies on nor changes)."""
    for cls in (
        _thread.RLock,
        AssertionError,
        AttributeError,
        NotImplementedError,
        OverflowError,
    ):
        module, qualname = module_and_qualname(cls)
        verdict = classify_callable(cls, module=module, qualname=qualname)
        assert verdict.category == "unresolved", (f"{module}.{qualname}", verdict)


# -- Scope: the table grew by exactly nine, and by nothing else --------


def test_policy_grew_by_exactly_the_nine_authorized_keys() -> None:
    """Task 38.7's committed table held 77 entries; Task 38.10 Phase A
    is authorized to add exactly nine and nothing else."""
    assert len(EXACT_IDENTITY_POLICY) == 77 + len(AUTHORIZED_SLOTS)


def test_no_policy_key_is_a_wildcard_or_pattern() -> None:
    """Every key stays a fully-qualified exact identity -- the property
    the whole three-bucket scheme rests on."""
    for key in EXACT_IDENTITY_POLICY:
        assert key and "*" not in key and "?" not in key and " " not in key
