"""Unit tests for the Monitoring Framework (stdlib unittest, deterministic)."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from decimal import Decimal

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from monitoring import (
    AlertGenerator,
    Collector,
    DefaultAlerts,
    DefaultDiagnostics,
    DefaultHealth,
    DefaultMonitoringEngine,
    DefaultMonitoringManager,
    DefaultMonitoringMetrics,
    Evaluator,
    InMemoryMonitoringRegistry,
    MonitoringCancelled,
    MonitoringCompleted,
    MonitoringEngine,
    MonitoringError,
    MonitoringEvent,
    MonitoringManager,
    MonitoringParameters,
    MonitoringRegistry,
    MonitoringResultStatus,
    register_monitoring,
)
from monitoring.events import MonitoringErrorOccurred
from monitoring.exceptions import CollectionError, RegistryError
from monitoring.models import (
    HealthCheck,
    HealthReport,
    MonitoredComponent,
    MonitoringRecord,
)
from monitoring.state import VALID_TRANSITIONS, MonitoringState, can_transition
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.monitoring_fakes import make_component, make_context

_ZERO = Decimal("0")
_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def _manager(bus: EventBus, **overrides: object) -> DefaultMonitoringManager:
    return DefaultMonitoringManager(
        bus,
        InMemoryMonitoringRegistry(),
        overrides.get("collector", DefaultHealth()),  # type: ignore[arg-type]
        DefaultDiagnostics(),
        DefaultAlerts(),
        DefaultMonitoringMetrics(),
        logger=FakeLoggerFactory(),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# State & models
# ---------------------------------------------------------------------------
class StateModelTests(unittest.TestCase):
    def test_transitions(self) -> None:
        self.assertTrue(
            can_transition(MonitoringState.CREATED, MonitoringState.COLLECTING)
        )
        self.assertTrue(
            can_transition(MonitoringState.EVALUATED, MonitoringState.EVALUATED)
        )
        self.assertEqual(VALID_TRANSITIONS[MonitoringState.COMPLETED], frozenset())

    def test_history_append_immutable(self) -> None:
        from monitoring.models import MonitoringHistory

        history = MonitoringHistory()
        new = history.append(HealthReport())
        self.assertEqual(len(history.reports), 0)
        self.assertEqual(len(new.reports), 1)


# ---------------------------------------------------------------------------
# Health collector
# ---------------------------------------------------------------------------
class HealthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.health = DefaultHealth()

    def test_collects_worst_first_across_sources(self) -> None:
        report = self.health.collect(
            make_context(
                strategy=(make_component("ema", "5"),),
                agents=(make_component("ceo", "-3", source="agent"),),
            )
        )
        self.assertEqual(report.components[0].name, "ceo")  # worst first
        self.assertEqual(len(report.checks), 2)

    def test_max_components_caps(self) -> None:
        strategy = tuple(make_component(f"s{i}", str(i)) for i in range(10))
        report = self.health.collect(
            make_context(
                strategy=strategy, parameters=MonitoringParameters(max_components=3)
            )
        )
        self.assertEqual(len(report.components), 3)


# ---------------------------------------------------------------------------
# Diagnostics & Alerts
# ---------------------------------------------------------------------------
class DiagnosticsAlertTests(unittest.TestCase):
    def _report(self) -> HealthReport:
        c_ok = MonitoredComponent(name="ema", source="strategy", score=Decimal("5"))
        c_bad = MonitoredComponent(name="rsi", source="strategy", score=Decimal("-3"))
        return HealthReport(
            components=(c_ok, c_bad),
            checks=(HealthCheck(component=c_ok), HealthCheck(component=c_bad)),
        )

    def test_diagnostics_flags_breaches(self) -> None:
        evaluated = DefaultDiagnostics().evaluate(self._report(), make_context())
        verdicts = {c.component.name: c.healthy for c in evaluated.checks}
        self.assertTrue(verdicts["ema"])
        self.assertFalse(verdicts["rsi"])

    def test_alerts_only_for_unhealthy(self) -> None:
        evaluated = DefaultDiagnostics().evaluate(self._report(), make_context())
        alerts = DefaultAlerts().generate(evaluated, make_context())
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].subject, "rsi")
        self.assertEqual(alerts[0].severity, "critical")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
class MetricsTests(unittest.TestCase):
    def test_best_worst_uptime_and_never_resolved(self) -> None:
        c_best = MonitoredComponent(name="ema", source="strategy", score=Decimal("5"))
        c_worst = MonitoredComponent(
            name="rsi", source="strategy", score=Decimal("-3")
        )
        report = HealthReport(
            components=(c_best, c_worst),
            checks=(
                HealthCheck(component=c_best, healthy=True, severity="ok"),
                HealthCheck(component=c_worst, healthy=False, severity="critical"),
            ),
        )
        from monitoring.models import Alert

        record = MonitoringRecord(
            id="m1", state=MonitoringState.EVALUATED, report=report,
            alerts=(
                Alert(subject="rsi", source="strategy", severity="critical"),
            ),
            check_count=2, alert_count=1,
        )
        metrics = DefaultMonitoringMetrics().calculate(record)
        self.assertEqual(metrics.best_component, "ema")
        self.assertEqual(metrics.worst_component, "rsi")
        self.assertEqual(metrics.resolved_alerts_count, 0)  # never resolved
        self.assertEqual(metrics.active_alerts_count, 1)
        self.assertEqual(metrics.uptime_ratio, Decimal("0.5"))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = InMemoryMonitoringRegistry()
        self.record = MonitoringRecord(id="m1", state=MonitoringState.COLLECTING)

    def test_register_and_get(self) -> None:
        self.registry.register(self.record)
        self.assertTrue(self.registry.exists("m1"))
        self.assertEqual(self.registry.get("m1"), self.record)
        self.assertEqual(self.registry.list(), [self.record])

    def test_get_missing_raises(self) -> None:
        with self.assertRaises(RegistryError):
            self.registry.get("nope")

    def test_unregister_and_clear(self) -> None:
        self.registry.register(self.record)
        self.registry.unregister("m1")
        self.assertFalse(self.registry.exists("m1"))
        self.registry.register(self.record)
        self.registry.clear()
        self.assertEqual(self.registry.list(), [])


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------
class ManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_observes_and_accumulates(self) -> None:
        bus = EventBus()
        completed = FakeSubscriber()
        bus.subscribe(MonitoringCompleted, completed.handle)
        manager = _manager(bus)

        first = await manager.monitor(make_context(monitoring_id="m1"))
        second = await manager.monitor(make_context(monitoring_id="m1"))

        self.assertEqual(second.status, MonitoringResultStatus.SUCCESS)
        assert second.record is not None and second.metrics is not None
        self.assertEqual(second.record.check_count, 4)  # 2 checks per input
        self.assertTrue(second.alerts)  # rsi breaches
        self.assertEqual(second.metrics.resolved_alerts_count, 0)
        self.assertEqual(len(completed.received), 2)
        self.assertEqual(first.metrics.total_alerts, 1)  # type: ignore[union-attr]

    async def test_cancellation(self) -> None:
        bus = EventBus()
        cancelled = FakeSubscriber()
        bus.subscribe(MonitoringCancelled, cancelled.handle)
        manager = _manager(bus)
        result = await manager.monitor(make_context(monitoring_id="m1", cancel=True))
        self.assertEqual(result.status, MonitoringResultStatus.CANCELLED)
        self.assertEqual(len(cancelled.received), 1)

    async def test_terminal_rejected(self) -> None:
        manager = _manager(EventBus())
        await manager.monitor(make_context(monitoring_id="m1", cancel=True))
        result = await manager.monitor(make_context(monitoring_id="m1"))
        self.assertEqual(result.status, MonitoringResultStatus.FAILED)

    async def test_error_isolated(self) -> None:
        class _Boom:
            def collect(self, context: object) -> object:
                raise CollectionError("boom")

        bus = EventBus()
        errors = FakeSubscriber()
        bus.subscribe(MonitoringErrorOccurred, errors.handle)
        manager = _manager(bus, collector=_Boom())
        result = await manager.monitor(make_context(monitoring_id="m1"))
        self.assertEqual(result.status, MonitoringResultStatus.FAILED)
        self.assertEqual(len(errors.received), 1)

    async def test_events_published(self) -> None:
        bus = EventBus()
        allev = FakeSubscriber()
        bus.subscribe(MonitoringEvent, allev.handle)
        manager = _manager(bus)
        await manager.monitor(make_context(monitoring_id="m1"))
        names = [type(e).__name__ for e in allev.received]
        self.assertEqual(names[0], "MonitoringStarted")
        self.assertIn("HealthReportCreated", names)
        self.assertIn("AlertsGenerated", names)
        self.assertIn("MonitoringCompleted", names)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_engine_delegates(self) -> None:
        engine = DefaultMonitoringEngine(
            _manager(EventBus()), logger=FakeLoggerFactory()  # type: ignore[arg-type]
        )
        await engine.start()
        result = await engine.monitor(make_context(monitoring_id="m1"))
        await engine.stop()
        self.assertEqual(result.status, MonitoringResultStatus.SUCCESS)


# ---------------------------------------------------------------------------
# Dependency Injection
# ---------------------------------------------------------------------------
class RegistrationTests(unittest.TestCase):
    def test_registers_and_binds(self) -> None:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_monitoring(container)
        self.assertTrue(container.has(EventBus))
        self.assertIsInstance(
            container.resolve(MonitoringEngine), DefaultMonitoringEngine
        )
        self.assertIsInstance(
            container.resolve(MonitoringManager), DefaultMonitoringManager
        )
        self.assertIsInstance(container.resolve(Collector), DefaultHealth)
        self.assertIsInstance(container.resolve(Evaluator), DefaultDiagnostics)
        self.assertIsInstance(container.resolve(AlertGenerator), DefaultAlerts)
        self.assertIsInstance(
            container.resolve(MonitoringRegistry), InMemoryMonitoringRegistry
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class ExceptionTests(unittest.TestCase):
    def test_hierarchy(self) -> None:
        for exc in (CollectionError, RegistryError):
            self.assertTrue(issubclass(exc, MonitoringError))


if __name__ == "__main__":
    unittest.main()
