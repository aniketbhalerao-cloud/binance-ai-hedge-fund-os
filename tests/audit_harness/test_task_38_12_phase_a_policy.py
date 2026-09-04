"""Task 38.12 Phase A regression tests: the single exact identity
ADR-032's "Task 38.12 Phase 0" section authorizes (2026-09-05, Aniket
Bhalerao -- project owner/reviewer), ``builtins.str.join``, resolves via
``EXACT_IDENTITY_POLICY``, and every neighbouring ``.join`` identity that
same authorization explicitly declined to review stays out of it.

The pinning is deliberately two-sided, for the same reason Task 38.10
Phase A's policy tests are. A test that only proved ``str.join`` resolves
would pass equally well against a name-pattern or a textual ``".join"``
exemption; the excluded half -- ``os.path.join`` (``posixpath.join``) and
``bytes.join``, both named as out of scope by the authorization itself --
is what proves the table is still a set of individually reviewed exact
identities.

Nothing here executes any dangerous behaviour: the assertions classify
callables and read a live trace's verdicts, they never invoke them.
"""

from __future__ import annotations

import os.path

from audit_harness.identity import (
    EXACT_IDENTITY_POLICY,
    EXACT_IDENTITY_POLICY_VERSION,
    classify_callable,
    module_and_qualname,
)

#: The one identity authorized, exactly as the ADR spells it.
AUTHORIZED_KEY = "builtins.str.join"

#: Identities in the same textual ``.join`` family the authorization
#: explicitly did NOT review, with the reason each is a different
#: identity. Recorded here so a future reader cannot mistake the list for
#: an arbitrary denylist.
UNAUTHORIZED_JOINS: tuple[tuple[object, str, str, str], ...] = (
    (
        os.path.join,
        "posixpath",
        "join",
        "different module and qualname: a pure-Python path helper",
    ),
    (
        bytes.join,
        "builtins",
        "bytes.join",
        "different receiver type: bytes, not str",
    ),
    (
        bytearray.join,
        "builtins",
        "bytearray.join",
        "different receiver type: bytearray, not str",
    ),
)


def _classify_via_real_path(obj: object) -> object:
    """Classify a callable through the same ``module_and_qualname``
    derivation the walker itself uses, so these tests pin the real
    resolution path rather than a convenient approximation of it."""
    module, qualname = module_and_qualname(obj)
    return classify_callable(obj, module=module, qualname=qualname)


# -- Authorized: exactly one, resolving with its own rationale ---------


def test_policy_version_bumped_for_task_38_12_phase_a() -> None:
    """The table changed, so its version must have moved off Task 38.10's."""
    assert EXACT_IDENTITY_POLICY_VERSION == "2026-09-05.1"


def test_str_join_is_in_the_policy_table_with_its_own_rationale() -> None:
    assert AUTHORIZED_KEY in EXACT_IDENTITY_POLICY
    rationale = EXACT_IDENTITY_POLICY[AUTHORIZED_KEY]
    assert isinstance(rationale, str) and rationale.strip()


def test_str_join_rationale_records_the_iteration_caveat() -> None:
    """ADR-032 Task 38.12 Phase 0 item 4(a) requires the entry's own text
    to record -- not presume benign -- that ``str.join`` iterates its
    argument, so the argument's ``__iter__``/``__next__`` side effects run
    during the call. This is the single most load-bearing qualification in
    the authorization; if the rationale ever loses it, the entry must be
    re-reviewed rather than silently kept."""
    lowered = EXACT_IDENTITY_POLICY[AUTHORIZED_KEY].lower()
    assert "iterates its argument" in lowered
    assert "__iter__" in lowered
    assert "side effects" in lowered


def test_str_join_resolves_to_exact_identity() -> None:
    """``builtins.str.join`` resolves via `EXACT_IDENTITY_POLICY` through
    the real classification path -- never a name or pattern match."""
    verdict = _classify_via_real_path(str.join)
    assert verdict.category == "exact_identity_policy"
    assert verdict.rationale is not None and verdict.rationale.strip()


def test_str_join_identity_key_comes_from_the_objclass_fallback() -> None:
    """``str.join`` is a C-implemented ``method_descriptor`` carrying no
    ``__module__``; its key is reconstructed from ``__objclass__``. Pinned
    because the authorization names that path specifically -- if the
    derivation ever changed, the entry would stop matching silently."""
    assert not hasattr(str.join, "__module__")
    assert type(str.join).__name__ == "method_descriptor"
    assert str.join.__objclass__ is str
    assert module_and_qualname(str.join) == ("builtins", "str.join")


# -- Excluded: different identities, still not policy-accepted ---------


def test_unauthorized_join_identities_are_absent_from_the_policy_table() -> None:
    for _obj, module, qualname, _reason in UNAUTHORIZED_JOINS:
        assert f"{module}.{qualname}" not in EXACT_IDENTITY_POLICY


def test_unauthorized_join_identities_do_not_classify_exact_identity_policy() -> None:
    """Each excluded identity must fail closed through the real path. A
    wildcard, a name-pattern, or a textual ``".join"`` exemption would
    break this."""
    for obj, module, qualname, _reason in UNAUTHORIZED_JOINS:
        verdict = _classify_via_real_path(obj)
        assert verdict.category != "exact_identity_policy", (
            f"{module}.{qualname}",
            verdict.category,
        )


def test_unauthorized_join_identities_classify_unresolved() -> None:
    """Not merely "not policy-accepted": each excluded identity stays
    `unresolved` specifically, with no rationale attached. Measured on the
    live trace at Phase A, ``posixpath.join`` (3 calls) and
    ``builtins.bytes.join`` (1 call) remain unresolved residuals -- exactly
    as the authorization intended."""
    for obj, _module, _qualname, _reason in UNAUTHORIZED_JOINS:
        verdict = _classify_via_real_path(obj)
        assert verdict.category == "unresolved", verdict
        assert verdict.rationale is None


def test_str_join_is_the_only_join_identity_in_the_policy_table() -> None:
    """No broad name-based or textual ``.join`` matching was introduced:
    the table gained exactly one key whose qualname ends in ``.join``."""
    join_keys = {key for key in EXACT_IDENTITY_POLICY if key.endswith(".join")}
    assert join_keys == {AUTHORIZED_KEY}


# -- Scope: the table grew by exactly one, and by nothing else ---------


def test_policy_grew_by_exactly_one_key() -> None:
    """Task 38.10 Phase A's committed table held 86 entries; Task 38.12
    Phase A is authorized to add exactly one and nothing else."""
    assert len(EXACT_IDENTITY_POLICY) == 87


# -- The real residual this authorization targets ----------------------


def test_real_trace_str_join_sites_now_resolve() -> None:
    """The real residual sites this authorization targets -- the
    ``" -> ".join(...)`` circular-dependency message in
    ``core/container.py``, the ``", ".join(...)`` messages in
    ``core/logging.py``, and the ``config.settings``/``dotenv`` entrypoint
    chain -- now resolve on the live trace, while the identities the
    authorization excluded are untouched."""
    from audit_harness.trace import run_trace

    tr = run_trace()

    still_unresolved_join = [
        c
        for c in tr.calls
        if c.verdict.category == "unresolved"
        and c.verdict.module == "builtins"
        and c.verdict.qualname == "str.join"
    ]
    assert still_unresolved_join == []

    resolved_join = [
        c
        for c in tr.calls
        if c.verdict.category == "exact_identity_policy"
        and c.verdict.module == "builtins"
        and c.verdict.qualname == "str.join"
    ]
    assert resolved_join, "the authorized identity must appear on the live trace"

    # The excluded identities must not have been swept up: nothing may
    # resolve to them via the policy bucket.
    for module, qualname in (
        ("posixpath", "join"),
        ("builtins", "bytes.join"),
        ("builtins", "bytearray.join"),
    ):
        policy_accepted = [
            c
            for c in tr.calls
            if c.verdict.category == "exact_identity_policy"
            and c.verdict.module == module
            and c.verdict.qualname == qualname
        ]
        assert policy_accepted == [], (module, qualname)
