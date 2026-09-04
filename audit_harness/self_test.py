"""Harness Requirement 7 + Task 38.11 Phase A:
run the ten negative controls programmatically and report exactly
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
from collections.abc import Callable
from dataclasses import dataclass

from audit_harness.module_state import scan_module
from audit_harness.runtime_denial import ForbiddenOperationError, _apply_patches
from audit_harness.trace import CallRecord, StaticWalker, _underlying
from core.container import ServiceContainer
from core.registry import ServiceRegistry
from tests.audit_harness.fixtures import implicit_dispatch as implicit_fx
from tests.audit_harness.fixtures import negative_controls as fx


@dataclass(frozen=True, slots=True)
class NegativeControlResult:
    name: str
    detected: bool
    detail: str


def _resolved_registration_provider(_resolver: object) -> None:
    return None


def _walk_registration_provider_set(
    providers: dict[int, Callable[..., object]] | None,
    semantic_count: int | None,
) -> StaticWalker:
    walker = StaticWalker(
        registration_providers=providers,
        registration_provider_semantic_count=semantic_count,
    )
    walker.instance_attribute_types[(ServiceContainer, "_registry")] = ServiceRegistry
    walker.walk(
        ServiceContainer.resolve,
        "self-test:registration-provider-set",
        owner_class=ServiceContainer,
    )
    return walker


def _registration_provider_set_records(walker: StaticWalker) -> list[CallRecord]:
    return [
        record
        for record in walker.call_records
        if record.resolution_mechanism == "di-registration-provider-set"
    ]


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


def _check_implicit_context_manager_dispatch_detected() -> NegativeControlResult:
    """Task 38.8 Phase A.1 (§8's "Negative-control results", mirroring
    the existing shape): the same production mechanism `run_audit`
    itself relies on must still detect the sentinel embedded in
    ``__enter__`` via ordinary ``with`` syntax, using the frozen Phase
    A.0 fixture -- one implementation, not a second detector that could
    silently drift from the one `tests/audit_harness/
    test_task_38_8_phase_a1_mechanism.py` already exercises via pytest."""
    walker = StaticWalker()
    walker.walk(
        implicit_fx.trigger_with_statement_enter_only,
        "self-test:implicit-context-manager",
    )
    hit = any(
        c.callee_text == "open" and c.verdict.category == "forbidden"
        for c in walker.call_records
    )
    return NegativeControlResult(
        "implicit_context_manager_dispatch_detected",
        hit,
        "open(...) inside ForbiddenEnterOnly.__enter__, triggered via `with obj:`",
    )


def _check_implicit_descriptor_dispatch_detected() -> NegativeControlResult:
    """The descriptor-family counterpart -- M-8's own "sharpest
    instance" (a bare attribute read with zero ``ast.Call`` node),
    using the frozen Phase A.0 ``@property`` fixture."""
    walker = StaticWalker()
    walker.walk(
        implicit_fx.trigger_property_get, "self-test:implicit-descriptor"
    )
    hit = any(
        c.callee_text == "open" and c.verdict.category == "forbidden"
        for c in walker.call_records
    )
    return NegativeControlResult(
        "implicit_descriptor_dispatch_detected",
        hit,
        "open(...) inside ForbiddenProperty.value's fget, triggered via a bare "
        "attribute read",
    )


def _check_incomplete_registration_provider_set() -> NegativeControlResult:
    provider = _resolved_registration_provider
    walker = _walk_registration_provider_set(
        {id(_underlying(provider)): provider}, 2
    )
    records = _registration_provider_set_records(walker)
    hit = len(records) == 1 and records[0].verdict.category == "unresolved"
    return NegativeControlResult(
        "incomplete_registration_provider_set_fails_closed",
        hit,
        "one walked provider for two semantic registration targets",
    )


def _check_unresolved_registration_provider_set_member() -> NegativeControlResult:
    providers = (_resolved_registration_provider, print)
    walker = _walk_registration_provider_set(
        {id(_underlying(provider)): provider for provider in providers},
        len(providers),
    )
    records = _registration_provider_set_records(walker)
    hit = len(records) == 1 and records[0].verdict.category == "unresolved"
    return NegativeControlResult(
        "unresolved_registration_provider_set_member_fails_closed",
        hit,
        "one unresolved member makes the aggregate unresolved",
    )


def _check_empty_or_unavailable_registration_provider_set() -> NegativeControlResult:
    empty_records = _registration_provider_set_records(
        _walk_registration_provider_set({}, 0)
    )
    unavailable_records = _registration_provider_set_records(
        _walk_registration_provider_set(None, None)
    )
    hit = all(
        len(records) == 1 and records[0].verdict.category == "unresolved"
        for records in (empty_records, unavailable_records)
    )
    return NegativeControlResult(
        "empty_or_unavailable_registration_provider_set_fails_closed",
        hit,
        "empty enumeration and unavailable provenance both remain unresolved",
    )


def run_self_tests() -> tuple[NegativeControlResult, ...]:
    return (
        _check_forbidden_post_init(),
        _check_unresolvable_call(),
        _check_module_global_mutation(),
        _check_direct_os_open(),
        _check_connecting_client_intercepted(),
        _check_implicit_context_manager_dispatch_detected(),
        _check_implicit_descriptor_dispatch_detected(),
        _check_incomplete_registration_provider_set(),
        _check_unresolved_registration_provider_set_member(),
        _check_empty_or_unavailable_registration_provider_set(),
    )
