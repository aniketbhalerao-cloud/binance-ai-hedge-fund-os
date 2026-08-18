"""Unit tests for the Application Bootstrap & Dry-Run Runtime Composition
Framework (stdlib unittest)."""

from __future__ import annotations

import dataclasses
import unittest
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from decimal import Decimal
from types import MappingProxyType
from unittest.mock import patch

from app import bootstrap, planner, preflight, wiring
from app.exceptions import ConfigurationError, PlanningError, PreflightError
from app.models import (
    BootstrapPlan,
    BootstrapPlanEntry,
    BootstrapResultStatus,
    ComponentManifest,
    ComponentSpec,
    LifecyclePlan,
    PreflightEntry,
    PreflightReport,
)
from config.settings import BinanceSettings, SecuritySettings, Settings
from core.container import ServiceContainer
from tests.app_fakes import make_component, make_context, make_dependency, make_manifest

#: A ``Settings``-field-name fragment blocklist mirroring
#: ``app.wiring._SENSITIVE_NAME_FRAGMENTS`` — kept as a literal copy here so
#: this test does not depend on that module's private constant.
_SENSITIVE_FRAGMENTS = (
    "key", "secret", "token", "credential", "password", "url", "dsn",
)


class ModelTests(unittest.TestCase):
    def test_component_spec_is_frozen_decimal_and_immutable_metadata(self) -> None:
        spec = ComponentSpec(
            component_id="workflows", priority=Decimal("5"), metadata={"a": 1}
        )
        self.assertIsInstance(spec.priority, Decimal)
        self.assertIsInstance(spec.metadata, MappingProxyType)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            spec.priority = Decimal("1")  # type: ignore[misc]

    def test_preflight_report_derives_counts_once_from_entries(self) -> None:
        report = PreflightReport(
            entries=(
                PreflightEntry("a", "a.key", True),
                PreflightEntry("b", "b.key", False),
            )
        )
        self.assertEqual(report.total_checks, 2)
        self.assertEqual(report.passed_checks, 1)
        self.assertEqual(report.failed_checks, 1)

    def test_bootstrap_plan_entry_normalizes_mutable_lists_to_tuples(self) -> None:
        entry = BootstrapPlanEntry(
            position=0,
            component_id="workflows",
            required_service_keys=["a.key", "b.key"],  # type: ignore[arg-type]
            dependencies=["scheduler"],  # type: ignore[arg-type]
        )
        self.assertIsInstance(entry.required_service_keys, tuple)
        self.assertIsInstance(entry.dependencies, tuple)
        self.assertEqual(entry.required_service_keys, ("a.key", "b.key"))
        self.assertEqual(entry.dependencies, ("scheduler",))

    def test_bootstrap_plan_normalizes_mutable_entries_list_to_tuple(self) -> None:
        entry = BootstrapPlanEntry(position=0, component_id="workflows")
        plan_ = BootstrapPlan(entries=[entry])  # type: ignore[arg-type]
        self.assertIsInstance(plan_.entries, tuple)
        self.assertEqual(plan_.entries, (entry,))

    def test_lifecycle_plan_normalizes_lists_and_accepts_exact_reverse(self) -> None:
        plan_ = LifecyclePlan(
            start_order=["a", "b"],  # type: ignore[arg-type]
            stop_order=["b", "a"],  # type: ignore[arg-type]
        )
        self.assertIsInstance(plan_.start_order, tuple)
        self.assertIsInstance(plan_.stop_order, tuple)
        self.assertEqual(plan_.start_order, ("a", "b"))
        self.assertEqual(plan_.stop_order, ("b", "a"))

    def test_lifecycle_plan_rejects_non_reversed_stop_order(self) -> None:
        with self.assertRaises(ConfigurationError):
            LifecyclePlan(start_order=("a", "b", "c"), stop_order=("a", "b", "c"))

    def test_lifecycle_plan_rejects_stop_order_of_different_length(self) -> None:
        with self.assertRaises(ConfigurationError):
            LifecyclePlan(start_order=("a", "b"), stop_order=("b",))


class BootstrapContextTimestampTests(unittest.TestCase):
    def test_accepts_canonical_utc(self) -> None:
        make_context(requested_at=datetime(2024, 1, 1, tzinfo=UTC))  # no raise

    def test_rejects_naive_datetime(self) -> None:
        with self.assertRaises(ConfigurationError):
            make_context(requested_at=datetime(2024, 1, 1))

    def test_rejects_tzinfo_with_none_utcoffset(self) -> None:
        class _BrokenTzinfo(tzinfo):
            def utcoffset(self, dt: datetime | None) -> timedelta | None:
                return None

            def dst(self, dt: datetime | None) -> timedelta | None:
                return None

            def tzname(self, dt: datetime | None) -> str | None:
                return "broken"

        with self.assertRaises(ConfigurationError):
            make_context(requested_at=datetime(2024, 1, 1, tzinfo=_BrokenTzinfo()))

    def test_rejects_non_zero_offset(self) -> None:
        ist = timezone(timedelta(hours=5, minutes=30))
        with self.assertRaises(ConfigurationError):
            make_context(requested_at=datetime(2024, 1, 1, tzinfo=ist))


class PlannerTests(unittest.TestCase):
    def test_unknown_component_id_rejected(self) -> None:
        manifest = make_manifest([make_component("not-a-real-framework")])
        with self.assertRaises(PlanningError):
            planner.plan(manifest)

    def test_duplicate_component_identifier_rejected(self) -> None:
        manifest = make_manifest(
            [make_component("workflows"), make_component("workflows")]
        )
        with self.assertRaises(PlanningError):
            planner.plan(manifest)

    def test_missing_dependency_rejected(self) -> None:
        manifest = make_manifest(
            [make_component("workflows")],
            [make_dependency("workflows", "does-not-exist")],
        )
        with self.assertRaises(PlanningError):
            planner.plan(manifest)

    def test_self_dependency_rejected(self) -> None:
        manifest = make_manifest(
            [make_component("workflows")],
            [make_dependency("workflows", "workflows")],
        )
        with self.assertRaises(PlanningError):
            planner.plan(manifest)

    def test_cyclic_dependency_rejected(self) -> None:
        manifest = make_manifest(
            [make_component("workflows"), make_component("scheduler")],
            [
                make_dependency("workflows", "scheduler"),
                make_dependency("scheduler", "workflows"),
            ],
        )
        with self.assertRaises(PlanningError):
            planner.plan(manifest)

    def test_priority_ordering_and_lexical_tie_break(self) -> None:
        manifest = make_manifest(
            [
                make_component("workflows", "1"),
                make_component("agents", "5"),
                make_component("scheduler", "1"),
            ]
        )
        result = planner.plan(manifest)
        self.assertEqual(
            [entry.component_id for entry in result.entries],
            ["agents", "scheduler", "workflows"],
        )

    def test_topological_ordering_respects_dependencies_over_priority(self) -> None:
        manifest = make_manifest(
            [make_component("workflows", "0"), make_component("scheduler", "9")],
            [make_dependency("scheduler", "workflows")],
        )
        result = planner.plan(manifest)
        self.assertEqual(
            [entry.component_id for entry in result.entries],
            ["workflows", "scheduler"],
        )

    def test_dependency_canonicalization_is_order_independent(self) -> None:
        components = [
            make_component("workflows"),
            make_component("scheduler"),
            make_component("workers"),
        ]
        plan_a = planner.plan(
            make_manifest(
                components,
                [
                    make_dependency("workers", "scheduler"),
                    make_dependency("workers", "workflows"),
                ],
            )
        )
        plan_b = planner.plan(
            make_manifest(
                components,
                [
                    make_dependency("workers", "workflows"),
                    make_dependency("workers", "scheduler"),
                ],
            )
        )
        self.assertEqual(plan_a, plan_b)

    def test_component_insertion_order_independence(self) -> None:
        components_a = [make_component("agents", "1"), make_component("workflows", "1")]
        components_b = list(reversed(components_a))
        self.assertEqual(
            planner.plan(make_manifest(components_a)),
            planner.plan(make_manifest(components_b)),
        )


class PreflightTests(unittest.TestCase):
    def test_unknown_service_key_rejected_before_any_resolution(self) -> None:
        entry = BootstrapPlanEntry(
            position=0,
            component_id="workflows",
            required_service_keys=("totally.unknown.key",),
        )
        bad_plan = BootstrapPlan(entries=(entry,))
        with self.assertRaises(PreflightError):
            preflight.validate_service_keys(bad_plan)

    def test_successful_and_failed_resolution_recorded_correctly(self) -> None:
        class _FakeGoodService:
            def __init__(self) -> None:
                pass

        class _FakeBadService:
            def __init__(self) -> None:
                pass

        with patch.object(
            wiring,
            "SAFE_SERVICE_KEYS",
            {"good.key": _FakeGoodService, "bad.key": _FakeBadService},
        ):
            container = ServiceContainer()
            container.register_class(_FakeGoodService)
            # _FakeBadService is intentionally left unregistered.
            entry = BootstrapPlanEntry(
                position=0,
                component_id="fixture",
                required_service_keys=("good.key", "bad.key"),
            )
            plan_ = BootstrapPlan(entries=(entry,))
            report = preflight.run(plan_, container.resolve)

        self.assertEqual(report.total_checks, 2)
        self.assertEqual(report.passed_checks, 1)
        self.assertEqual(report.failed_checks, 1)
        by_key = {entry.service_key: entry for entry in report.entries}
        self.assertTrue(by_key["good.key"].resolved)
        self.assertFalse(by_key["bad.key"].resolved)
        # Detail is always safe/generic, never a raw exception.
        self.assertNotIn("Traceback", by_key["bad.key"].detail)


class BootstrapOrchestrationTests(unittest.TestCase):
    def test_unknown_component_id_rejected_before_any_container_is_created(
        self,
    ) -> None:
        calls: list[ServiceContainer] = []

        def spy_factory() -> ServiceContainer:
            container = ServiceContainer()
            calls.append(container)
            return container

        context = make_context(
            manifest=make_manifest([make_component("not-a-real-framework")])
        )
        result = bootstrap.run_dry_run_bootstrap(context, container_factory=spy_factory)

        self.assertEqual(result.status, BootstrapResultStatus.FAILED)
        self.assertIsNone(result.runtime_snapshot)
        self.assertEqual(len(calls), 0)

    def test_lifecycle_plan_stop_order_is_exact_reverse_of_start_order(self) -> None:
        manifest = make_manifest(
            [make_component("workflows", "1"), make_component("scheduler", "0")]
        )
        context = make_context(manifest=manifest)
        result = bootstrap.run_dry_run_bootstrap(
            context, container_factory=ServiceContainer
        )

        self.assertEqual(result.status, BootstrapResultStatus.SUCCESS)
        assert result.lifecycle_plan is not None
        self.assertEqual(
            result.lifecycle_plan.stop_order,
            tuple(reversed(result.lifecycle_plan.start_order)),
        )


class DeterminismTests(unittest.TestCase):
    def test_repeated_runs_produce_field_for_field_equal_artifacts(self) -> None:
        context = make_context(manifest=wiring.build_default_manifest())

        result_a = bootstrap.run_dry_run_bootstrap(
            context, container_factory=ServiceContainer
        )
        result_b = bootstrap.run_dry_run_bootstrap(
            context, container_factory=ServiceContainer
        )

        self.assertEqual(result_a.status, result_b.status)
        self.assertEqual(result_a.plan, result_b.plan)
        self.assertEqual(result_a.preflight_report, result_b.preflight_report)
        self.assertEqual(result_a.runtime_snapshot, result_b.runtime_snapshot)
        self.assertEqual(result_a.lifecycle_plan, result_b.lifecycle_plan)


class ConfigurationViewRedactionTests(unittest.TestCase):
    def test_only_allowlisted_fields_present_no_sensitive_names_or_values(
        self,
    ) -> None:
        secret_marker = "REALISTIC-LOOKING-SECRET-VALUE-0001"
        settings = Settings(
            binance=BinanceSettings(
                api_key=f"AKIA-{secret_marker}",
                api_secret=f"sk-{secret_marker}",
            ),
            security=SecuritySettings(
                secret_key=f"signing-{secret_marker}-000000",
                api_token=f"token-{secret_marker}-000000",
            ),
        )

        view = wiring.build_configuration_view(settings)

        field_names = {f.name for f in dataclasses.fields(view)}
        for name in field_names:
            lowered = name.lower()
            self.assertFalse(
                any(fragment in lowered for fragment in _SENSITIVE_FRAGMENTS),
                f"ConfigurationView must not expose field {name!r}",
            )

        for name in field_names:
            value = getattr(view, name)
            if isinstance(value, str):
                self.assertNotIn(secret_marker, value)

    def test_rejects_copying_a_sensitive_field_defence_in_depth(self) -> None:
        with self.assertRaises(ConfigurationError):
            wiring._safe("binance.api_key", "should-never-be-copied")


class WiringManifestTests(unittest.TestCase):
    def test_default_manifest_declares_all_known_ids_with_zero_dependencies(
        self,
    ) -> None:
        manifest: ComponentManifest = wiring.build_default_manifest()
        ids = {component.component_id for component in manifest.components}
        self.assertEqual(ids, wiring.KNOWN_COMPONENT_IDS)
        self.assertEqual(manifest.dependencies, ())
        self.assertNotIn("trading", ids)


if __name__ == "__main__":
    unittest.main()
