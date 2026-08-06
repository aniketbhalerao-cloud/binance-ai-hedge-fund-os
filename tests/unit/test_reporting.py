"""Unit tests for the Reporting Framework (stdlib unittest, deterministic)."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from decimal import Decimal

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from reporting import (
    Builder,
    Collector,
    DefaultBuilder,
    DefaultCollector,
    DefaultExporter,
    DefaultReportingEngine,
    DefaultReportingManager,
    DefaultReportingMetrics,
    Exporter,
    InMemoryReportingRegistry,
    ReportingCancelled,
    ReportingCompleted,
    ReportingEngine,
    ReportingError,
    ReportingEvent,
    ReportingManager,
    ReportingParameters,
    ReportingRegistry,
    ReportingResultStatus,
    register_reporting,
)
from reporting.events import ReportingErrorOccurred
from reporting.exceptions import CollectionError, RegistryError
from reporting.models import Report, ReportingBatch, ReportingRecord, ReportingSource
from reporting.state import VALID_TRANSITIONS, ReportingState, can_transition
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.reporting_fakes import make_context, make_source

_ZERO = Decimal("0")
_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def _manager(bus: EventBus, **overrides: object) -> DefaultReportingManager:
    return DefaultReportingManager(
        bus,
        InMemoryReportingRegistry(),
        overrides.get("collector", DefaultCollector()),  # type: ignore[arg-type]
        DefaultBuilder(),
        DefaultExporter(),
        DefaultReportingMetrics(),
        logger=FakeLoggerFactory(),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# State & models
# ---------------------------------------------------------------------------
class StateModelTests(unittest.TestCase):
    def test_transitions(self) -> None:
        self.assertTrue(
            can_transition(ReportingState.CREATED, ReportingState.COLLECTING)
        )
        self.assertTrue(
            can_transition(ReportingState.BUILT, ReportingState.BUILT)
        )
        self.assertEqual(
            VALID_TRANSITIONS[ReportingState.COMPLETED], frozenset()
        )

    def test_history_append_immutable(self) -> None:
        from reporting.models import ReportingHistory

        history = ReportingHistory()
        new = history.append(ReportingBatch())
        self.assertEqual(len(history.batches), 0)
        self.assertEqual(len(new.batches), 1)


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------
class CollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.collector = DefaultCollector()

    def test_collects_highest_priority_first_across_sources(self) -> None:
        batch = self.collector.collect(
            make_context(
                monitoring=(make_source("cpu", "5"),),
                learning=(make_source("drift", "9", source="learning"),),
            )
        )
        self.assertEqual(batch.sources[0].name, "drift")  # highest priority first
        self.assertEqual(len(batch.reports), 2)

    def test_max_reports_caps(self) -> None:
        monitoring = tuple(make_source(f"s{i}", str(i)) for i in range(10))
        batch = self.collector.collect(
            make_context(
                monitoring=monitoring,
                parameters=ReportingParameters(max_reports=3),
            )
        )
        self.assertEqual(len(batch.sources), 3)


# ---------------------------------------------------------------------------
# Builder & Exporter
# ---------------------------------------------------------------------------
class BuilderExporterTests(unittest.TestCase):
    def _batch(self) -> ReportingBatch:
        s_ok = ReportingSource(
            name="cpu", source="monitoring", priority=Decimal("5")
        )
        s_bad = ReportingSource(
            name="mem", source="monitoring", priority=Decimal("-3")
        )
        return ReportingBatch(
            sources=(s_ok, s_bad),
            reports=(
                Report(source=s_ok),
                Report(source=s_bad),
            ),
        )

    def test_builder_resolves_inclusion(self) -> None:
        built = DefaultBuilder().build(self._batch(), make_context())
        include = {r.source.name: r.include for r in built.reports}
        self.assertTrue(include["cpu"])
        self.assertFalse(include["mem"])

    def test_exporter_only_for_included(self) -> None:
        built = DefaultBuilder().build(self._batch(), make_context())
        exports = DefaultExporter().export(built, make_context())
        self.assertEqual(len(exports), 1)
        self.assertEqual(exports[0].subject, "cpu")
        self.assertEqual(exports[0].source, "monitoring")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
class MetricsTests(unittest.TestCase):
    def test_highest_lowest_export_and_suppressed(self) -> None:
        s_hi = ReportingSource(
            name="cpu", source="monitoring", priority=Decimal("5")
        )
        s_lo = ReportingSource(
            name="mem", source="monitoring", priority=Decimal("-3")
        )
        batch = ReportingBatch(
            sources=(s_hi, s_lo),
            reports=(
                Report(source=s_hi, include=True),
                Report(source=s_lo, include=False),
            ),
        )
        from reporting.models import ExportRequest

        record = ReportingRecord(
            id="r1", state=ReportingState.BUILT, batch=batch,
            exports=(
                ExportRequest(
                    subject="cpu", source="monitoring", report_type="daily"
                ),
            ),
            report_count=2, export_count=1,
        )
        metrics = DefaultReportingMetrics().calculate(record)
        self.assertEqual(metrics.highest_priority_report, "cpu")
        self.assertEqual(metrics.lowest_priority_report, "mem")
        self.assertEqual(metrics.pending_reports_count, 1)
        self.assertEqual(metrics.suppressed_reports_count, 1)
        self.assertEqual(metrics.export_ratio, Decimal("0.5"))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = InMemoryReportingRegistry()
        self.record = ReportingRecord(id="r1", state=ReportingState.COLLECTING)

    def test_register_and_get(self) -> None:
        self.registry.register(self.record)
        self.assertTrue(self.registry.exists("r1"))
        self.assertEqual(self.registry.get("r1"), self.record)
        self.assertEqual(self.registry.list(), [self.record])

    def test_get_missing_raises(self) -> None:
        with self.assertRaises(RegistryError):
            self.registry.get("nope")

    def test_unregister_and_clear(self) -> None:
        self.registry.register(self.record)
        self.registry.unregister("r1")
        self.assertFalse(self.registry.exists("r1"))
        self.registry.register(self.record)
        self.registry.clear()
        self.assertEqual(self.registry.list(), [])


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------
class ManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_reports_and_accumulates(self) -> None:
        bus = EventBus()
        completed = FakeSubscriber()
        bus.subscribe(ReportingCompleted, completed.handle)
        manager = _manager(bus)

        first = await manager.report(make_context(reporting_id="r1"))
        second = await manager.report(make_context(reporting_id="r1"))

        self.assertEqual(second.status, ReportingResultStatus.SUCCESS)
        assert second.record is not None and second.metrics is not None
        self.assertEqual(second.record.report_count, 4)  # 2 per input
        self.assertTrue(second.exports)  # cpu included
        self.assertEqual(second.metrics.suppressed_reports_count, 1)  # mem suppressed
        self.assertEqual(len(completed.received), 2)
        self.assertEqual(first.metrics.total_exports, 1)  # type: ignore[union-attr]

    async def test_cancellation(self) -> None:
        bus = EventBus()
        cancelled = FakeSubscriber()
        bus.subscribe(ReportingCancelled, cancelled.handle)
        manager = _manager(bus)
        result = await manager.report(make_context(reporting_id="r1", cancel=True))
        self.assertEqual(result.status, ReportingResultStatus.CANCELLED)
        self.assertEqual(len(cancelled.received), 1)

    async def test_terminal_rejected(self) -> None:
        manager = _manager(EventBus())
        await manager.report(make_context(reporting_id="r1", cancel=True))
        result = await manager.report(make_context(reporting_id="r1"))
        self.assertEqual(result.status, ReportingResultStatus.FAILED)

    async def test_error_isolated(self) -> None:
        class _Boom:
            def collect(self, context: object) -> object:
                raise CollectionError("boom")

        bus = EventBus()
        errors = FakeSubscriber()
        bus.subscribe(ReportingErrorOccurred, errors.handle)
        manager = _manager(bus, collector=_Boom())
        result = await manager.report(make_context(reporting_id="r1"))
        self.assertEqual(result.status, ReportingResultStatus.FAILED)
        self.assertEqual(len(errors.received), 1)

    async def test_events_published(self) -> None:
        bus = EventBus()
        allev = FakeSubscriber()
        bus.subscribe(ReportingEvent, allev.handle)
        manager = _manager(bus)
        await manager.report(make_context(reporting_id="r1"))
        names = [type(e).__name__ for e in allev.received]
        self.assertEqual(names[0], "ReportingStarted")
        self.assertIn("ReportingCollected", names)
        self.assertIn("ReportsExported", names)
        self.assertIn("ReportingCompleted", names)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_engine_delegates(self) -> None:
        engine = DefaultReportingEngine(
            _manager(EventBus()), logger=FakeLoggerFactory()  # type: ignore[arg-type]
        )
        await engine.start()
        result = await engine.report(make_context(reporting_id="r1"))
        await engine.stop()
        self.assertEqual(result.status, ReportingResultStatus.SUCCESS)


# ---------------------------------------------------------------------------
# Dependency Injection
# ---------------------------------------------------------------------------
class RegistrationTests(unittest.TestCase):
    def test_registers_and_binds(self) -> None:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_reporting(container)
        self.assertTrue(container.has(EventBus))
        self.assertIsInstance(
            container.resolve(ReportingEngine), DefaultReportingEngine
        )
        self.assertIsInstance(
            container.resolve(ReportingManager), DefaultReportingManager
        )
        self.assertIsInstance(container.resolve(Collector), DefaultCollector)
        self.assertIsInstance(container.resolve(Builder), DefaultBuilder)
        self.assertIsInstance(container.resolve(Exporter), DefaultExporter)
        self.assertIsInstance(
            container.resolve(ReportingRegistry), InMemoryReportingRegistry
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class ExceptionTests(unittest.TestCase):
    def test_hierarchy(self) -> None:
        for exc in (CollectionError, RegistryError):
            self.assertTrue(issubclass(exc, ReportingError))


if __name__ == "__main__":
    unittest.main()
