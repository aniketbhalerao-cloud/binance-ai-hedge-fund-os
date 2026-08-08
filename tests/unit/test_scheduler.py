"""Unit tests for the Scheduler Framework (stdlib unittest, deterministic)."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from decimal import Decimal

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from scheduler import (
    Collector,
    DefaultCollector,
    DefaultDispatcher,
    DefaultPlanner,
    DefaultSchedulerEngine,
    DefaultSchedulerManager,
    DefaultSchedulerMetrics,
    Dispatcher,
    InMemorySchedulerRegistry,
    Planner,
    SchedulerCancelled,
    SchedulerCompleted,
    SchedulerEngine,
    SchedulerError,
    SchedulerEvent,
    SchedulerManager,
    SchedulerParameters,
    SchedulerRegistry,
    SchedulerResultStatus,
    register_scheduler,
)
from scheduler.events import SchedulerErrorOccurred
from scheduler.exceptions import CollectionError, RegistryError
from scheduler.models import (
    ScheduleBatch,
    ScheduleEntry,
    SchedulerRecord,
    ScheduleSource,
)
from scheduler.state import VALID_TRANSITIONS, SchedulerState, can_transition
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.scheduler_fakes import make_context, make_source

_ZERO = Decimal("0")
_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def _manager(bus: EventBus, **overrides: object) -> DefaultSchedulerManager:
    return DefaultSchedulerManager(
        bus,
        InMemorySchedulerRegistry(),
        overrides.get("collector", DefaultCollector()),  # type: ignore[arg-type]
        DefaultPlanner(),
        DefaultDispatcher(),
        DefaultSchedulerMetrics(),
        logger=FakeLoggerFactory(),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# State & models
# ---------------------------------------------------------------------------
class StateModelTests(unittest.TestCase):
    def test_transitions(self) -> None:
        self.assertTrue(
            can_transition(SchedulerState.CREATED, SchedulerState.COLLECTING)
        )
        self.assertTrue(
            can_transition(SchedulerState.PLANNED, SchedulerState.PLANNED)
        )
        self.assertEqual(
            VALID_TRANSITIONS[SchedulerState.COMPLETED], frozenset()
        )

    def test_history_append_immutable(self) -> None:
        from scheduler.models import SchedulerHistory

        history = SchedulerHistory()
        new = history.append(ScheduleBatch())
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
                reporting=(make_source("daily", "9", source="reporting"),),
            )
        )
        self.assertEqual(batch.sources[0].name, "daily")  # highest priority first
        self.assertEqual(len(batch.entries), 2)

    def test_max_items_caps(self) -> None:
        monitoring = tuple(make_source(f"s{i}", str(i)) for i in range(10))
        batch = self.collector.collect(
            make_context(
                monitoring=monitoring,
                parameters=SchedulerParameters(max_items=3),
            )
        )
        self.assertEqual(len(batch.sources), 3)


# ---------------------------------------------------------------------------
# Planner & Dispatcher
# ---------------------------------------------------------------------------
class PlannerDispatcherTests(unittest.TestCase):
    def _batch(self) -> ScheduleBatch:
        s_ok = ScheduleSource(
            name="cpu", source="monitoring", priority=Decimal("5")
        )
        s_bad = ScheduleSource(
            name="mem", source="monitoring", priority=Decimal("-3")
        )
        return ScheduleBatch(
            sources=(s_ok, s_bad),
            entries=(
                ScheduleEntry(source=s_ok),
                ScheduleEntry(source=s_bad),
            ),
        )

    def test_planner_resolves_dispatch(self) -> None:
        planned = DefaultPlanner().plan(self._batch(), make_context())
        dispatch = {e.source.name: e.dispatch for e in planned.entries}
        self.assertTrue(dispatch["cpu"])
        self.assertFalse(dispatch["mem"])

    def test_dispatcher_only_for_dispatchable(self) -> None:
        planned = DefaultPlanner().plan(self._batch(), make_context())
        requests = DefaultDispatcher().dispatch(planned, make_context())
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].subject, "cpu")
        self.assertEqual(requests[0].source, "monitoring")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
class MetricsTests(unittest.TestCase):
    def test_highest_lowest_dispatch_and_suppressed(self) -> None:
        s_hi = ScheduleSource(
            name="cpu", source="monitoring", priority=Decimal("5")
        )
        s_lo = ScheduleSource(
            name="mem", source="monitoring", priority=Decimal("-3")
        )
        batch = ScheduleBatch(
            sources=(s_hi, s_lo),
            entries=(
                ScheduleEntry(source=s_hi, dispatch=True),
                ScheduleEntry(source=s_lo, dispatch=False),
            ),
        )
        from scheduler.models import ScheduleRequest

        record = SchedulerRecord(
            id="s1", state=SchedulerState.PLANNED, batch=batch,
            requests=(
                ScheduleRequest(
                    subject="cpu", source="monitoring", cadence="once"
                ),
            ),
            entry_count=2, request_count=1,
        )
        metrics = DefaultSchedulerMetrics().calculate(record)
        self.assertEqual(metrics.highest_priority_entry, "cpu")
        self.assertEqual(metrics.lowest_priority_entry, "mem")
        self.assertEqual(metrics.pending_requests_count, 1)
        self.assertEqual(metrics.suppressed_requests_count, 1)
        self.assertEqual(metrics.dispatch_ratio, Decimal("0.5"))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = InMemorySchedulerRegistry()
        self.record = SchedulerRecord(id="s1", state=SchedulerState.COLLECTING)

    def test_register_and_get(self) -> None:
        self.registry.register(self.record)
        self.assertTrue(self.registry.exists("s1"))
        self.assertEqual(self.registry.get("s1"), self.record)
        self.assertEqual(self.registry.list(), [self.record])

    def test_get_missing_raises(self) -> None:
        with self.assertRaises(RegistryError):
            self.registry.get("nope")

    def test_unregister_and_clear(self) -> None:
        self.registry.register(self.record)
        self.registry.unregister("s1")
        self.assertFalse(self.registry.exists("s1"))
        self.registry.register(self.record)
        self.registry.clear()
        self.assertEqual(self.registry.list(), [])


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------
class ManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_schedules_and_accumulates(self) -> None:
        bus = EventBus()
        completed = FakeSubscriber()
        bus.subscribe(SchedulerCompleted, completed.handle)
        manager = _manager(bus)

        first = await manager.schedule(make_context(scheduler_id="s1"))
        second = await manager.schedule(make_context(scheduler_id="s1"))

        self.assertEqual(second.status, SchedulerResultStatus.SUCCESS)
        assert second.record is not None and second.metrics is not None
        self.assertEqual(second.record.entry_count, 4)  # 2 per input
        self.assertTrue(second.requests)  # cpu dispatchable
        self.assertEqual(second.metrics.suppressed_requests_count, 1)  # mem suppressed
        self.assertEqual(len(completed.received), 2)
        self.assertEqual(first.metrics.total_requests, 1)  # type: ignore[union-attr]

    async def test_cancellation(self) -> None:
        bus = EventBus()
        cancelled = FakeSubscriber()
        bus.subscribe(SchedulerCancelled, cancelled.handle)
        manager = _manager(bus)
        result = await manager.schedule(make_context(scheduler_id="s1", cancel=True))
        self.assertEqual(result.status, SchedulerResultStatus.CANCELLED)
        self.assertEqual(len(cancelled.received), 1)

    async def test_terminal_rejected(self) -> None:
        manager = _manager(EventBus())
        await manager.schedule(make_context(scheduler_id="s1", cancel=True))
        result = await manager.schedule(make_context(scheduler_id="s1"))
        self.assertEqual(result.status, SchedulerResultStatus.FAILED)

    async def test_error_isolated(self) -> None:
        class _Boom:
            def collect(self, context: object) -> object:
                raise CollectionError("boom")

        bus = EventBus()
        errors = FakeSubscriber()
        bus.subscribe(SchedulerErrorOccurred, errors.handle)
        manager = _manager(bus, collector=_Boom())
        result = await manager.schedule(make_context(scheduler_id="s1"))
        self.assertEqual(result.status, SchedulerResultStatus.FAILED)
        self.assertEqual(len(errors.received), 1)

    async def test_events_published(self) -> None:
        bus = EventBus()
        allev = FakeSubscriber()
        bus.subscribe(SchedulerEvent, allev.handle)
        manager = _manager(bus)
        await manager.schedule(make_context(scheduler_id="s1"))
        names = [type(e).__name__ for e in allev.received]
        self.assertEqual(names[0], "SchedulerStarted")
        self.assertIn("ScheduleCollected", names)
        self.assertIn("RequestsDispatched", names)
        self.assertIn("SchedulerCompleted", names)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_engine_delegates(self) -> None:
        engine = DefaultSchedulerEngine(
            _manager(EventBus()), logger=FakeLoggerFactory()  # type: ignore[arg-type]
        )
        await engine.start()
        result = await engine.schedule(make_context(scheduler_id="s1"))
        await engine.stop()
        self.assertEqual(result.status, SchedulerResultStatus.SUCCESS)


# ---------------------------------------------------------------------------
# Dependency Injection
# ---------------------------------------------------------------------------
class RegistrationTests(unittest.TestCase):
    def test_registers_and_binds(self) -> None:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_scheduler(container)
        self.assertTrue(container.has(EventBus))
        self.assertIsInstance(
            container.resolve(SchedulerEngine), DefaultSchedulerEngine
        )
        self.assertIsInstance(
            container.resolve(SchedulerManager), DefaultSchedulerManager
        )
        self.assertIsInstance(container.resolve(Collector), DefaultCollector)
        self.assertIsInstance(container.resolve(Planner), DefaultPlanner)
        self.assertIsInstance(
            container.resolve(Dispatcher), DefaultDispatcher
        )
        self.assertIsInstance(
            container.resolve(SchedulerRegistry), InMemorySchedulerRegistry
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class ExceptionTests(unittest.TestCase):
    def test_hierarchy(self) -> None:
        for exc in (CollectionError, RegistryError):
            self.assertTrue(issubclass(exc, SchedulerError))


if __name__ == "__main__":
    unittest.main()
