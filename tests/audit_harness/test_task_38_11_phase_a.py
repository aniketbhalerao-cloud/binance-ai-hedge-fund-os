"""Task 38.11 Phase A regression tests for provider-set resolution."""

from __future__ import annotations

from collections.abc import Callable

from audit_harness.trace import CallRecord, StaticWalker, _underlying
from core.container import ServiceContainer
from core.registry import ServiceRegistry


def _provider_a(_resolver: object) -> None:
    return None


def _provider_b(_resolver: object) -> None:
    return None


def _make_provider(value: object) -> Callable[[object], object]:
    def provider(_resolver: object) -> object:
        return value

    return provider


def _walker(
    providers: dict[int, Callable[..., object]], semantic_count: int
) -> StaticWalker:
    walker = StaticWalker(
        registration_providers=providers,
        registration_provider_semantic_count=semantic_count,
    )
    walker.instance_attribute_types[(ServiceContainer, "_registry")] = ServiceRegistry
    return walker


def _walk(walker: StaticWalker) -> None:
    walker.walk(
        ServiceContainer.resolve,
        "test:registration-provider-set",
        owner_class=ServiceContainer,
    )


def _aggregate_records(walker: StaticWalker) -> list[CallRecord]:
    return [
        record
        for record in walker.call_records
        if record.resolution_mechanism == "di-registration-provider-set"
    ]


def test_duplicate_provider_does_not_double_walk_or_inflate_records() -> None:
    providers: dict[int, Callable[..., object]] = {}
    registered_providers = (_provider_a, _provider_a)
    for provider in registered_providers:
        providers.setdefault(id(_underlying(provider)), provider)

    walker = _walker(providers, len(registered_providers))
    _walk(walker)
    records = _aggregate_records(walker)
    provider_id = id(_underlying(_provider_a))

    assert len(records) == 1
    assert records[0].verdict.category == "unresolved"
    assert "semantic_targets=2; walked_objects=1" in (
        records[0].verdict.rationale or ""
    )
    assert sum(fid == provider_id for fid, _key in walker.visited_funcs) == 1


def test_provider_replacement_and_mutation_are_checked_at_emit_time() -> None:
    providers: dict[int, Callable[..., object]] = {
        id(_underlying(_provider_a)): _provider_a
    }
    walker = _walker(providers, 1)
    providers[id(_underlying(_provider_b))] = _provider_b
    _walk(walker)
    mutated = _aggregate_records(walker)
    assert len(mutated) == 1
    assert mutated[0].verdict.category == "unresolved"
    assert "semantic_targets=1; walked_objects=2" in (
        mutated[0].verdict.rationale or ""
    )

    providers = {id(_underlying(_provider_a)): _provider_a}
    walker = _walker(providers, 1)
    providers[id(_underlying(_provider_a))] = _provider_b
    _walk(walker)
    replaced = _aggregate_records(walker)
    assert len(replaced) == 1
    assert replaced[0].verdict.category == "unresolved"


def test_sourceless_non_project_member_fails_closed() -> None:
    providers: dict[int, Callable[..., object]] = {id(_underlying(len)): len}
    walker = _walker(providers, 1)
    _walk(walker)
    records = _aggregate_records(walker)

    assert len(records) == 1
    assert records[0].verdict.category == "unresolved"
    rationale = records[0].verdict.rationale or ""
    assert "code_objects=0" in rationale
    assert "all_targets_resolved=false" in rationale


def test_same_code_different_closures_remain_distinct_and_are_both_walked() -> None:
    first = _make_provider(object())
    second = _make_provider(object())
    assert first.__code__ is second.__code__
    providers = {
        id(_underlying(first)): first,
        id(_underlying(second)): second,
    }
    walker = _walker(providers, 2)
    _walk(walker)
    records = _aggregate_records(walker)

    assert len(records) == 1
    assert records[0].verdict.category == "project_source_available"
    assert "walked_objects=2; symbol_identities=1; code_objects=1" in (
        records[0].verdict.rationale or ""
    )
    provider_ids = {id(_underlying(first)), id(_underlying(second))}
    visited_ids = {fid for fid, _key in walker.visited_funcs}
    assert provider_ids <= visited_ids
