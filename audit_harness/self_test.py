"""Harness Requirement 7 + item-5 of the implementation instructions:
run the five negative controls programmatically and report exactly
which were detected. ``run_audit.run_full_audit`` calls this *before*
trusting any other part of the run -- a missed negative control means
``self_test_failed`` is set and the run must never claim a clean gate.

The same detection logic backs
``tests/audit_harness/test_negative_controls.py`` (each pytest there
asserts on the corresponding entry here), so there is exactly one
implementation of "does the harness catch this," not two that could
silently drift apart.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass

from audit_harness.module_state import scan_module
from audit_harness.runtime_denial import ForbiddenOperationError, _apply_patches
from audit_harness.trace import StaticWalker
from tests.audit_harness.fixtures import negative_controls as fx


@dataclass(frozen=True, slots=True)
class NegativeControlResult:
    name: str
    detected: bool
    detail: str


def _check_forbidden_post_init() -> NegativeControlResult:
    walker = StaticWalker()
    walker.walk(
        fx.FixtureWithForbiddenPostInit.__post_init__,
        "self-test:__post_init__",
        owner_class=fx.FixtureWithForbiddenPostInit,
    )
    hit = any(
        c.callee_text == "open" and c.verdict.category == "forbidden"
        for c in walker.call_records
    )
    return NegativeControlResult(
        "forbidden_post_init", hit, "open(self.path) inside a fixture __post_init__"
    )


def _check_unresolvable_call() -> NegativeControlResult:
    walker = StaticWalker()
    walker.walk(fx.fixture_unresolvable_call, "self-test:unresolvable_call")
    matching = [
        c for c in walker.call_records if "do_something_unverifiable" in c.callee_text
    ]
    hit = bool(matching) and all(c.verdict.category == "unresolved" for c in matching)
    return NegativeControlResult(
        "unresolvable_call_reported", hit, "mystery.do_something_unverifiable()"
    )


def _check_module_global_mutation() -> NegativeControlResult:
    source = inspect.getsource(fx)
    candidates = scan_module(
        "tests/audit_harness/fixtures/negative_controls.py", source
    )
    if candidates is None:
        return NegativeControlResult(
            "module_global_mutation_from_plain_function",
            False,
            "fixture failed to parse",
        )
    hit = any(
        c.kind
        in (
            "module_global_mutated_via_method_call",
            "module_global_subscript_assignment",
        )
        and "_fixture_module_global" in c.detail
        for c in candidates
    )
    return NegativeControlResult(
        "module_global_mutation_from_plain_function",
        hit,
        "_fixture_module_global mutated in a plain function",
    )


def _check_direct_os_open() -> NegativeControlResult:
    walker = StaticWalker()
    walker.walk(fx.fixture_calls_os_open_directly, "self-test:os_open")
    hit = any(
        c.callee_text == "os.open" and c.verdict.category == "forbidden"
        for c in walker.call_records
    )
    return NegativeControlResult(
        "direct_os_open_call", hit, "os.open(...) called directly"
    )


def _check_connecting_client_intercepted() -> NegativeControlResult:
    """Case 5 exercises three NAMED, independent fake clients -- DB,
    Redis, and exchange-adapter -- and passes only if all three connect
    attempts are intercepted before any of them completes a real
    connection. One intercepted client does not stand in for the other
    two: a patch that happens to cover only one connection shape (e.g.
    ``socket.create_connection`` but not the ``socket.socket()`` class
    construction path) must be caught here, not silently accepted."""
    named_clients: tuple[tuple[str, object], ...] = (
        ("db", fx.FixtureDBClient()),
        ("redis", fx.FixtureRedisClient()),
        ("exchange_adapter", fx.FixtureExchangeAdapterClient()),
    )
    with _apply_patches() as applied:
        if not any(p.category == "network" for p in applied):
            return NegativeControlResult(
                "db_redis_exchange_connection_intercepted",
                False,
                "no network primitive was patched",
            )
        intercepted: list[str] = []
        not_intercepted: list[str] = []
        for name, client in named_clients:
            try:
                client.connect()  # type: ignore[attr-defined]
            except ForbiddenOperationError:
                intercepted.append(name)
            else:
                not_intercepted.append(name)

    if not_intercepted:
        return NegativeControlResult(
            "db_redis_exchange_connection_intercepted",
            False,
            f"not intercepted: {not_intercepted}; intercepted: {intercepted}",
        )
    return NegativeControlResult(
        "db_redis_exchange_connection_intercepted",
        True,
        f"all three fake clients intercepted before any connection: {intercepted}",
    )


def run_self_tests() -> tuple[NegativeControlResult, ...]:
    return (
        _check_forbidden_post_init(),
        _check_unresolvable_call(),
        _check_module_global_mutation(),
        _check_direct_os_open(),
        _check_connecting_client_intercepted(),
    )
