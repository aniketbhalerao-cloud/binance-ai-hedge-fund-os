"""Task 38.6 Harness Requirement 7: negative-control tests.

Each test asserts the harness *detects* one deliberately unsafe fixture
shape, via the exact same detection logic ``audit_harness.self_test``
uses before every real audit run -- one implementation, not two that
could silently drift apart. A fixture that goes undetected here is a
harness bug, not a passing test.
"""

from __future__ import annotations

from audit_harness.self_test import run_self_tests


def test_all_ten_negative_controls_are_detected() -> None:
    """5 original + 2 implicit-dispatch + 3 provider-set controls."""
    results = run_self_tests()
    assert len(results) == 10
    undetected = [r for r in results if not r.detected]
    assert not undetected, (
        f"negative controls not detected: {[(r.name, r.detail) for r in undetected]}"
    )


def test_forbidden_post_init_is_detected() -> None:
    result = next(r for r in run_self_tests() if r.name == "forbidden_post_init")
    assert result.detected


def test_unresolvable_call_is_reported_unresolved_not_dropped() -> None:
    result = next(r for r in run_self_tests() if r.name == "unresolvable_call_reported")
    assert result.detected


def test_module_global_mutation_from_plain_function_is_detected() -> None:
    result = next(
        r
        for r in run_self_tests()
        if r.name == "module_global_mutation_from_plain_function"
    )
    assert result.detected


def test_direct_os_open_call_is_classified_forbidden() -> None:
    result = next(r for r in run_self_tests() if r.name == "direct_os_open_call")
    assert result.detected


def test_connecting_client_is_intercepted_before_any_real_connection() -> None:
    result = next(
        r
        for r in run_self_tests()
        if r.name == "db_redis_exchange_connection_intercepted"
    )
    assert result.detected


def test_implicit_context_manager_dispatch_is_detected() -> None:
    result = next(
        r
        for r in run_self_tests()
        if r.name == "implicit_context_manager_dispatch_detected"
    )
    assert result.detected


def test_implicit_descriptor_dispatch_is_detected() -> None:
    result = next(
        r
        for r in run_self_tests()
        if r.name == "implicit_descriptor_dispatch_detected"
    )
    assert result.detected


def test_incomplete_registration_provider_set_fails_closed() -> None:
    result = next(
        r
        for r in run_self_tests()
        if r.name == "incomplete_registration_provider_set_fails_closed"
    )
    assert result.detected


def test_unresolved_registration_provider_set_member_fails_closed() -> None:
    result = next(
        r
        for r in run_self_tests()
        if r.name == "unresolved_registration_provider_set_member_fails_closed"
    )
    assert result.detected


def test_empty_or_unavailable_registration_provider_set_fails_closed() -> None:
    result = next(
        r
        for r in run_self_tests()
        if r.name == "empty_or_unavailable_registration_provider_set_fails_closed"
    )
    assert result.detected
