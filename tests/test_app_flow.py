"""Integration tests for the Application Bootstrap & Dry-Run Runtime
Composition Framework — dry-run only. No network, no sleeps, no
randomness, no model training, and no live framework/engine start
anywhere.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import itertools
import multiprocessing
import socket
import threading
import unittest
from datetime import timedelta
from unittest.mock import patch

import app.bootstrap as bootstrap_module
import app.exceptions as exceptions_module
import app.main as main_module
import app.models as models_module
import app.planner as planner_module
import app.preflight as preflight_module
from app import bootstrap, preflight, wiring
from app.models import BootstrapResultStatus
from core.container import ServiceContainer
from tests.app_fakes import CANONICAL_UTC, make_component, make_context, make_manifest

#: The 24 completed framework package names, plus ``trading`` (excluded
#: from ``COMPONENT_REGISTRARS`` but still off-limits to import directly).
#: An executable ``import`` of any of these outside ``app/wiring.py`` (as
#: opposed to a docstring *mention*) is a boundary violation.
_FORBIDDEN_MODULES = wiring.KNOWN_COMPONENT_IDS | {"trading"}

#: Every real ``register_<framework>`` identifier — may only ever appear as
#: executable code inside ``app/wiring.py``.
_FORBIDDEN_IDENTIFIERS = {f"register_{cid}" for cid in wiring.KNOWN_COMPONENT_IDS}

_NON_WIRING_MODULES = (
    models_module,
    exceptions_module,
    planner_module,
    preflight_module,
    bootstrap_module,
    main_module,
)


def _collect_identifiers(tree: ast.AST) -> tuple[set[str], set[str]]:
    """Return ``(imported_top_level_modules, referenced_names)`` from ``tree``.

    Only *executable* references count: a docstring is a string ``Constant``
    node — never a ``Name``/``Attribute`` node — so it is naturally excluded
    without any special-casing.
    """
    modules: set[str] = set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return modules, names


def _raising_registrar(container: object) -> None:
    raise RuntimeError("registration boom (test fixture)")


class ImportBoundaryTests(unittest.TestCase):
    def test_only_wiring_imports_frameworks_directly(self) -> None:
        for module in _NON_WIRING_MODULES:
            tree = ast.parse(inspect.getsource(module))
            modules, names = _collect_identifiers(tree)
            self.assertTrue(
                _FORBIDDEN_MODULES.isdisjoint(modules),
                f"{module.__name__} imports a framework module directly",
            )
            self.assertTrue(
                _FORBIDDEN_IDENTIFIERS.isdisjoint(names),
                f"{module.__name__} references a registrar directly",
            )

    def test_wiring_module_is_the_documented_exception(self) -> None:
        import app.wiring as wiring_module

        tree = ast.parse(inspect.getsource(wiring_module))
        modules, names = _collect_identifiers(tree)
        self.assertFalse(_FORBIDDEN_MODULES.isdisjoint(modules))
        self.assertFalse(_FORBIDDEN_IDENTIFIERS.isdisjoint(names))

    def test_ast_boundary_check_ignores_docstring_mentions(self) -> None:
        source = (
            '"""Mentions register_agents() and workflows only in prose, '
            'never as real code."""\n'
            "from __future__ import annotations\n"
            "x = 1\n"
        )
        modules, names = _collect_identifiers(ast.parse(source))
        self.assertTrue(_FORBIDDEN_MODULES.isdisjoint(modules))
        self.assertTrue(_FORBIDDEN_IDENTIFIERS.isdisjoint(names))


class NoContainerParameterTests(unittest.TestCase):
    """No function in this task accepts a container instance as a
    parameter anywhere — provable structurally from each signature."""

    def test_run_dry_run_bootstrap_only_container_parameter_is_the_factory(
        self,
    ) -> None:
        sig = inspect.signature(bootstrap.run_dry_run_bootstrap)
        self.assertEqual(set(sig.parameters), {"context", "container_factory"})
        annotation = str(sig.parameters["container_factory"].annotation)
        self.assertIn("Callable", annotation)

    def test_main_only_container_parameter_is_the_factory(self) -> None:
        sig = inspect.signature(main_module.main)
        self.assertEqual(set(sig.parameters), {"argv", "container_factory", "clock"})
        annotation = str(sig.parameters["container_factory"].annotation)
        self.assertIn("Callable", annotation)

    def test_preflight_run_accepts_a_resolver_callable_not_a_container(self) -> None:
        import collections.abc

        import app.preflight as preflight_module

        sig = inspect.signature(preflight_module.run)
        self.assertEqual(list(sig.parameters), ["plan", "resolve"])
        annotation = str(sig.parameters["resolve"].annotation)
        self.assertEqual(annotation, "ServiceResolver")
        self.assertNotIn("Container", annotation)
        # ``ServiceResolver`` itself is a plain ``Callable`` alias — never
        # ``Container`` or anything with registration capability.
        self.assertIs(
            getattr(preflight_module.ServiceResolver, "__origin__", None),
            collections.abc.Callable,
        )


class EndToEndTests(unittest.TestCase):
    def test_default_manifest_registers_all_24_into_the_candidate_container(
        self,
    ) -> None:
        captured: list[ServiceContainer] = []

        def capturing_factory() -> ServiceContainer:
            container = ServiceContainer()
            captured.append(container)
            return container

        context = make_context(manifest=wiring.build_default_manifest())
        result = bootstrap.run_dry_run_bootstrap(
            context, container_factory=capturing_factory
        )

        self.assertEqual(result.status, BootstrapResultStatus.SUCCESS)
        self.assertEqual(len(captured), 1)
        container = captured[0]
        for service_type in wiring.SAFE_SERVICE_KEYS.values():
            self.assertTrue(container.has(service_type))
        self.assertNotIn("trading", wiring.KNOWN_COMPONENT_IDS)

        assert result.preflight_report is not None
        assert result.runtime_snapshot is not None
        self.assertEqual(result.preflight_report.total_checks, 24)
        self.assertEqual(result.preflight_report.passed_checks, 24)
        self.assertEqual(result.preflight_report.failed_checks, 0)
        self.assertEqual(
            set(result.runtime_snapshot.registered_component_ids),
            wiring.KNOWN_COMPONENT_IDS,
        )
        self.assertEqual(len(result.runtime_snapshot.registered_component_ids), 24)

    def test_end_to_end_pipeline_produces_all_four_artifacts(self) -> None:
        manifest = make_manifest(
            [make_component("workflows", "1"), make_component("scheduler", "0")]
        )
        context = make_context(manifest=manifest)
        result = bootstrap.run_dry_run_bootstrap(
            context, container_factory=ServiceContainer
        )

        self.assertEqual(result.status, BootstrapResultStatus.SUCCESS)
        assert result.plan is not None
        assert result.preflight_report is not None
        assert result.runtime_snapshot is not None
        assert result.lifecycle_plan is not None
        self.assertEqual(
            [entry.component_id for entry in result.plan.entries],
            ["workflows", "scheduler"],
        )
        self.assertEqual(
            result.lifecycle_plan.start_order, ("workflows", "scheduler")
        )
        self.assertEqual(
            result.lifecycle_plan.stop_order, ("scheduler", "workflows")
        )


class FactoryCallCountContractTests(unittest.TestCase):
    @staticmethod
    def _spy() -> tuple[object, list[ServiceContainer]]:
        calls: list[ServiceContainer] = []

        def factory() -> ServiceContainer:
            container = ServiceContainer()
            calls.append(container)
            return container

        return factory, calls

    def test_zero_calls_when_planning_fails(self) -> None:
        factory, calls = self._spy()
        context = make_context(
            manifest=make_manifest([make_component("not-a-real-framework")])
        )
        result = bootstrap.run_dry_run_bootstrap(context, container_factory=factory)
        self.assertEqual(result.status, BootstrapResultStatus.FAILED)
        self.assertEqual(len(calls), 0)

    def test_zero_calls_when_static_service_key_validation_fails(self) -> None:
        factory, calls = self._spy()
        context = make_context(
            manifest=make_manifest(
                [make_component("workflows", required_service_keys=("nope",))]
            )
        )
        result = bootstrap.run_dry_run_bootstrap(context, container_factory=factory)
        self.assertEqual(result.status, BootstrapResultStatus.FAILED)
        self.assertEqual(len(calls), 0)

    def test_exactly_one_call_on_success(self) -> None:
        factory, calls = self._spy()
        context = make_context(manifest=make_manifest([make_component("workflows")]))
        result = bootstrap.run_dry_run_bootstrap(context, container_factory=factory)
        self.assertEqual(result.status, BootstrapResultStatus.SUCCESS)
        self.assertEqual(len(calls), 1)

    def test_exactly_one_call_even_when_registration_later_fails(self) -> None:
        factory, calls = self._spy()
        patched = dict(wiring.COMPONENT_REGISTRARS)
        patched["workflows"] = _raising_registrar
        with patch.object(wiring, "COMPONENT_REGISTRARS", patched):
            context = make_context(
                manifest=make_manifest([make_component("workflows")])
            )
            result = bootstrap.run_dry_run_bootstrap(
                context, container_factory=factory
            )
        self.assertEqual(result.status, BootstrapResultStatus.FAILED)
        self.assertEqual(len(calls), 1)

    def test_exactly_one_call_even_when_preflight_run_later_fails(self) -> None:
        factory, calls = self._spy()
        context = make_context(manifest=make_manifest([make_component("workflows")]))
        with patch.object(preflight, "run", side_effect=RuntimeError("boom")):
            result = bootstrap.run_dry_run_bootstrap(
                context, container_factory=factory
            )
        self.assertEqual(result.status, BootstrapResultStatus.FAILED)
        self.assertIsNone(result.runtime_snapshot)
        self.assertEqual(len(calls), 1)


class FailureLeavesZeroAcceptedStateTests(unittest.TestCase):
    def test_failing_registration_leaves_zero_accepted_state(self) -> None:
        calls: list[ServiceContainer] = []

        def spy_factory() -> ServiceContainer:
            container = ServiceContainer()
            calls.append(container)
            return container

        patched = dict(wiring.COMPONENT_REGISTRARS)
        patched["workflows"] = _raising_registrar
        with patch.object(wiring, "COMPONENT_REGISTRARS", patched):
            context = make_context(
                manifest=make_manifest([make_component("workflows")])
            )
            result = bootstrap.run_dry_run_bootstrap(
                context, container_factory=spy_factory
            )

        self.assertEqual(result.status, BootstrapResultStatus.FAILED)
        self.assertIsNone(result.runtime_snapshot)
        self.assertIsNone(result.plan)
        self.assertEqual(len(calls), 1)

    def test_failing_preflight_run_leaves_zero_accepted_state(self) -> None:
        calls: list[ServiceContainer] = []

        def spy_factory() -> ServiceContainer:
            container = ServiceContainer()
            calls.append(container)
            return container

        context = make_context(manifest=make_manifest([make_component("workflows")]))
        with patch.object(preflight, "run", side_effect=RuntimeError("boom")):
            result = bootstrap.run_dry_run_bootstrap(
                context, container_factory=spy_factory
            )

        self.assertEqual(result.status, BootstrapResultStatus.FAILED)
        self.assertIsNone(result.runtime_snapshot)
        self.assertEqual(len(calls), 1)


class CompliantFactoryFreshnessAndNonRetentionTests(unittest.TestCase):
    def test_each_call_returns_a_distinct_container_never_retained(self) -> None:
        created: list[ServiceContainer] = []

        def compliant_factory() -> ServiceContainer:
            container = ServiceContainer()
            created.append(container)
            return container

        context = make_context(manifest=wiring.build_default_manifest())
        results = [
            bootstrap.run_dry_run_bootstrap(
                context, container_factory=compliant_factory
            )
            for _ in range(3)
        ]

        self.assertEqual(len(created), 3)
        for a, b in itertools.combinations(created, 2):
            self.assertIsNot(a, b)

        for result, container in zip(results, created, strict=True):
            self.assertEqual(result.status, BootstrapResultStatus.SUCCESS)
            for artifact in (
                result,
                result.plan,
                result.preflight_report,
                result.runtime_snapshot,
                result.lifecycle_plan,
            ):
                if artifact is None:
                    continue
                for field in dataclasses.fields(artifact):
                    self.assertIsNot(getattr(artifact, field.name), container)


class DefenceInDepthTests(unittest.TestCase):
    def test_dry_run_never_touches_network_thread_or_process_apis(self) -> None:
        """``socket.socket``, ``threading.Thread.start``, and
        ``multiprocessing.Process.start`` are monkeypatched to raise; a full
        default dry-run bootstrap must still complete successfully without
        tripping any of them. No DB/Redis client library is a project
        dependency yet (see ``pyproject.toml``), so there is no such
        constructor in this codebase to patch."""

        def _boom(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("must not be called during a dry-run bootstrap")

        context = make_context(manifest=wiring.build_default_manifest())
        with (
            patch.object(socket, "socket", new=_boom),
            patch.object(threading.Thread, "start", new=_boom),
            patch.object(multiprocessing.Process, "start", new=_boom),
        ):
            result = bootstrap.run_dry_run_bootstrap(
                context, container_factory=ServiceContainer
            )

        self.assertEqual(result.status, BootstrapResultStatus.SUCCESS)

    def test_main_end_to_end_never_touches_network_thread_or_process_apis(
        self,
    ) -> None:
        def _boom(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("must not be called during a dry-run bootstrap")

        with (
            patch.object(socket, "socket", new=_boom),
            patch.object(threading.Thread, "start", new=_boom),
            patch.object(multiprocessing.Process, "start", new=_boom),
        ):
            exit_code = main_module.main(
                container_factory=ServiceContainer, clock=lambda: CANONICAL_UTC
            )

        self.assertEqual(exit_code, 0)


class MainEntrypointTests(unittest.TestCase):
    def test_returns_0_on_success_and_1_on_failure(self) -> None:
        success_code = main_module.main(
            container_factory=ServiceContainer, clock=lambda: CANONICAL_UTC
        )
        self.assertEqual(success_code, 0)

        bad_manifest = make_manifest([make_component("not-a-real-framework")])
        with patch.object(wiring, "build_default_manifest", return_value=bad_manifest):
            failure_code = main_module.main(
                container_factory=ServiceContainer, clock=lambda: CANONICAL_UTC
            )
        self.assertEqual(failure_code, 1)

    def test_never_starts_live_mode_or_a_framework_engine(self) -> None:
        # No framework's Engine exposes a way to be started from app/'s
        # public surface at all — main() never resolves or references an
        # Engine type, only a fresh container built and discarded inside
        # run_dry_run_bootstrap. Structurally confirmed by
        # ImportBoundaryTests; this asserts the observable outcome.
        exit_code = main_module.main(
            container_factory=ServiceContainer, clock=lambda: CANONICAL_UTC
        )
        self.assertEqual(exit_code, 0)

    def test_default_clock_produces_canonical_utc(self) -> None:
        now = main_module._utc_now()
        self.assertIsNotNone(now.tzinfo)
        self.assertEqual(now.utcoffset(), timedelta(0))

    def test_default_manifest_resolves_24_of_24_and_exits_0(self) -> None:
        """The real default composition: all 24 known components register
        and every declared service key resolves — no partial/failed
        preflight checks, matching ``docs/prompts/task-38.md``'s intent
        that a dry run prove the *whole* graph would wire."""
        captured: list[ServiceContainer] = []

        def capturing_factory() -> ServiceContainer:
            container = ServiceContainer()
            captured.append(container)
            return container

        exit_code = main_module.main(
            container_factory=capturing_factory, clock=lambda: CANONICAL_UTC
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(captured), 1)
        for service_type in wiring.SAFE_SERVICE_KEYS.values():
            self.assertTrue(captured[0].has(service_type))


class InjectedResolutionFailureTests(unittest.TestCase):
    """A resolution failure inside preflight is a bootstrap failure: no
    artifact, ``FAILED`` status, and (through ``main()``) exit code 1."""

    def _patched_safe_keys(self) -> dict[str, type]:
        class _NeverRegistered:
            def __init__(self) -> None:
                pass

        patched = dict(wiring.SAFE_SERVICE_KEYS)
        patched["test.unresolvable.key"] = _NeverRegistered
        return patched

    def test_bootstrap_level_failure_leaves_zero_artifacts(self) -> None:
        calls: list[ServiceContainer] = []

        def spy_factory() -> ServiceContainer:
            container = ServiceContainer()
            calls.append(container)
            return container

        with patch.object(wiring, "SAFE_SERVICE_KEYS", self._patched_safe_keys()):
            context = make_context(
                manifest=make_manifest(
                    [
                        make_component(
                            "workflows",
                            required_service_keys=("test.unresolvable.key",),
                        )
                    ]
                )
            )
            result = bootstrap.run_dry_run_bootstrap(
                context, container_factory=spy_factory
            )

        self.assertEqual(result.status, BootstrapResultStatus.FAILED)
        self.assertIsNone(result.plan)
        self.assertIsNone(result.preflight_report)
        self.assertIsNone(result.runtime_snapshot)
        self.assertIsNone(result.lifecycle_plan)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(len(calls), 1)

    def test_main_level_failure_returns_exit_code_1(self) -> None:
        bad_manifest = make_manifest(
            [
                make_component(
                    "workflows", required_service_keys=("test.unresolvable.key",)
                )
            ]
        )
        with (
            patch.object(wiring, "SAFE_SERVICE_KEYS", self._patched_safe_keys()),
            patch.object(wiring, "build_default_manifest", return_value=bad_manifest),
        ):
            exit_code = main_module.main(
                container_factory=ServiceContainer, clock=lambda: CANONICAL_UTC
            )
        self.assertEqual(exit_code, 1)


class FactoryExceptionTests(unittest.TestCase):
    def test_container_factory_exception_yields_safe_failed_result(self) -> None:
        marker = "SECRET-MARKER-factory-boom-9f3a1c"

        def raising_factory() -> ServiceContainer:
            raise RuntimeError(marker)

        context = make_context(manifest=make_manifest([make_component("workflows")]))
        result = bootstrap.run_dry_run_bootstrap(
            context, container_factory=raising_factory
        )

        self.assertEqual(result.status, BootstrapResultStatus.FAILED)
        self.assertIsNone(result.plan)
        self.assertIsNone(result.preflight_report)
        self.assertIsNone(result.runtime_snapshot)
        self.assertIsNone(result.lifecycle_plan)
        self.assertEqual(len(result.errors), 1)
        for message in result.errors:
            self.assertNotIn(marker, message)
            self.assertNotIn("RuntimeError", message)


class SettingsAndConfigurationExceptionTests(unittest.TestCase):
    def test_main_returns_1_when_get_settings_raises(self) -> None:
        with patch.object(
            main_module, "get_settings", side_effect=RuntimeError("boom")
        ):
            exit_code = main_module.main(
                container_factory=ServiceContainer, clock=lambda: CANONICAL_UTC
            )
        self.assertEqual(exit_code, 1)

    def test_main_returns_1_when_configuration_view_building_raises(self) -> None:
        with patch.object(
            wiring, "build_configuration_view", side_effect=RuntimeError("boom")
        ):
            exit_code = main_module.main(
                container_factory=ServiceContainer, clock=lambda: CANONICAL_UTC
            )
        self.assertEqual(exit_code, 1)

    def test_main_returns_1_when_context_construction_raises(self) -> None:
        # An out-of-range clock value (naive datetime) makes
        # ``BootstrapContext.__post_init__`` raise ``ConfigurationError``.
        exit_code = main_module.main(
            container_factory=ServiceContainer,
            clock=lambda: CANONICAL_UTC.replace(tzinfo=None),
        )
        self.assertEqual(exit_code, 1)


class NoSecretMarkerLeakTests(unittest.TestCase):
    """Errors must never echo caller-supplied manifest values, however
    sensitive-looking."""

    def test_marker_absent_from_unknown_component_id_failure(self) -> None:
        marker = "SECRET-MARKER-component-7d2e"
        context = make_context(manifest=make_manifest([make_component(marker)]))
        result = bootstrap.run_dry_run_bootstrap(
            context, container_factory=ServiceContainer
        )
        self.assertEqual(result.status, BootstrapResultStatus.FAILED)
        for message in result.errors:
            self.assertNotIn(marker, message)

    def test_marker_absent_from_unknown_service_key_failure(self) -> None:
        marker = "SECRET-MARKER-service-key-4c1b"
        context = make_context(
            manifest=make_manifest(
                [make_component("workflows", required_service_keys=(marker,))]
            )
        )
        result = bootstrap.run_dry_run_bootstrap(
            context, container_factory=ServiceContainer
        )
        self.assertEqual(result.status, BootstrapResultStatus.FAILED)
        for message in result.errors:
            self.assertNotIn(marker, message)

    def test_marker_absent_from_dependency_and_self_dependency_failures(self) -> None:
        from tests.app_fakes import make_dependency

        marker = "SECRET-MARKER-dep-a91f"
        for manifest in (
            make_manifest(
                [make_component("workflows")],
                [make_dependency("workflows", marker)],
            ),
            make_manifest(
                [make_component("workflows")],
                [make_dependency("workflows", "workflows")],
            ),
        ):
            context = make_context(manifest=manifest)
            result = bootstrap.run_dry_run_bootstrap(
                context, container_factory=ServiceContainer
            )
            self.assertEqual(result.status, BootstrapResultStatus.FAILED)
            for message in result.errors:
                self.assertNotIn(marker, message)


class DryRunMarketDataProviderStatelessnessTests(unittest.TestCase):
    """``_DryRunMarketDataProvider`` must be genuinely stateless: no
    attribute can be stored on it at all, so ``on_data()`` can never leak a
    bound service callback across bootstrap runs or create shared mutable
    state."""

    def test_on_data_retains_no_callback_or_state(self) -> None:
        provider = wiring._DryRunMarketDataProvider()

        # __slots__ = () means the instance has no __dict__ — nothing can
        # ever be stored on it, by this class or by any caller.
        self.assertEqual(provider.__slots__, ())
        self.assertFalse(hasattr(provider, "__dict__"))

        received: list[object] = []

        def handler(payload: object) -> None:
            received.append(payload)

        provider.on_data(handler)

        # The handler was accepted, then discarded: it was never retained
        # (no such attribute can even exist) and never invoked.
        with self.assertRaises(AttributeError):
            getattr(provider, "_handler")  # noqa: B009
        self.assertEqual(received, [])

    def test_repeated_on_data_calls_leave_no_trace_between_them(self) -> None:
        provider = wiring._DryRunMarketDataProvider()
        first_calls: list[object] = []
        second_calls: list[object] = []

        provider.on_data(lambda payload: first_calls.append(payload))
        provider.on_data(lambda payload: second_calls.append(payload))

        # Neither handler was ever stored or invoked — a second ``on_data``
        # call cannot observe, replace, or be affected by the first.
        self.assertEqual(first_calls, [])
        self.assertEqual(second_calls, [])
        self.assertFalse(hasattr(provider, "__dict__"))

    def test_shared_module_instance_is_the_same_stateless_class(self) -> None:
        self.assertIsInstance(
            wiring._DRY_RUN_MARKET_DATA_PROVIDER, wiring._DryRunMarketDataProvider
        )
        self.assertFalse(hasattr(wiring._DRY_RUN_MARKET_DATA_PROVIDER, "__dict__"))


class TwoIndependentDefaultRunsBothSucceedTests(unittest.TestCase):
    def test_two_independent_default_runs_both_resolve_24_of_24(self) -> None:
        for _ in range(2):
            context = make_context(manifest=wiring.build_default_manifest())
            result = bootstrap.run_dry_run_bootstrap(
                context, container_factory=ServiceContainer
            )

            self.assertEqual(result.status, BootstrapResultStatus.SUCCESS)
            assert result.preflight_report is not None
            assert result.runtime_snapshot is not None
            self.assertEqual(result.preflight_report.total_checks, 24)
            self.assertEqual(result.preflight_report.passed_checks, 24)
            self.assertEqual(result.preflight_report.failed_checks, 0)
            self.assertEqual(
                len(result.runtime_snapshot.registered_component_ids), 24
            )


if __name__ == "__main__":
    unittest.main()
