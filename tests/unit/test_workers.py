"""Unit tests for the Background Workers Framework (stdlib unittest, deterministic)."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from decimal import Decimal

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.workers_fakes import make_context, make_source
from workers import (
    Collector,
    DefaultCollector,
    DefaultDispatcher,
    DefaultPlanner,
    DefaultWorkerEngine,
    DefaultWorkerManager,
    DefaultWorkerMetrics,
    Dispatcher,
    InMemoryWorkerRegistry,
    Planner,
    WorkerCancelled,
    WorkerCompleted,
    WorkerEngine,
    WorkerError,
    WorkerEvent,
    WorkerManager,
    WorkerParameters,
    WorkerRegistry,
    WorkerResultStatus,
    register_workers,
)
from workers.events import WorkerErrorOccurred
from workers.exceptions import CollectionError, RegistryError
from workers.models import (
    JobBatch,
    JobEntry,
    JobSource,
    WorkerRecord,
)
from workers.state import VALID_TRANSITIONS, WorkerState, can_transition

_ZERO = Decimal("0")
_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def _manager(bus: EventBus, **overrides: object) -> DefaultWorkerManager:
    return DefaultWorkerManager(
        bus,
        InMemoryWorkerRegistry(),
        overrides.get("collector", DefaultCollector()),  # type: ignore[arg-type]
        DefaultPlanner(),
        DefaultDispatcher(),
        DefaultWorkerMetrics(),
        logger=FakeLoggerFactory(),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# State & models
# ---------------------------------------------------------------------------
class StateModelTests(unittest.TestCase):
    def test_transitions(self) -> None:
        self.assertTrue(
            can_transition(WorkerState.CREATED, WorkerState.COLLECTING)
        )
        self.assertTrue(
            can_transition(WorkerState.QUEUED, WorkerState.QUEUED)
        )
        self.assertEqual(
            VALID_TRANSITIONS[WorkerState.COMPLETED], frozenset()
        )

    def test_history_append_immutable(self) -> None:
        from workers.models import WorkerHistory

        history = WorkerHistory()
        new = history.append(JobBatch())
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
                parameters=WorkerParameters(max_items=3),
            )
        )
        self.assertEqual(len(batch.sources), 3)


# ---------------------------------------------------------------------------
# Planner & Dispatcher
# ---------------------------------------------------------------------------
class PlannerDispatcherTests(unittest.TestCase):
    def _batch(self) -> JobBatch:
        s_ok = JobSource(
            name="cpu", source="monitoring", priority=Decimal("5")
        )
        s_bad = JobSource(
            name="mem", source="monitoring", priority=Decimal("-3")
        )
        return JobBatch(
            sources=(s_ok, s_bad),
            entries=(
                JobEntry(source=s_ok),
                JobEntry(source=s_bad),
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
        s_hi = JobSource(
            name="cpu", source="monitoring", priority=Decimal("5")
        )
        s_lo = JobSource(
            name="mem", source="monitoring", priority=Decimal("-3")
        )
        batch = JobBatch(
            sources=(s_hi, s_lo),
            entries=(
                JobEntry(source=s_hi, dispatch=True),
                JobEntry(source=s_lo, dispatch=False),
            ),
        )
        from workers.models import WorkerRequest

        record = WorkerRecord(
            id="w1", state=WorkerState.QUEUED, batch=batch,
            requests=(
                WorkerRequest(
                    subject="cpu", source="monitoring", queue="immediate"
                ),
            ),
            job_count=2, request_count=1,
        )
        metrics = DefaultWorkerMetrics().calculate(record)
        self.assertEqual(metrics.highest_priority_job, "cpu")
        self.assertEqual(metrics.lowest_priority_job, "mem")
        self.assertEqual(metrics.pending_requests_count, 1)
        self.assertEqual(metrics.suppressed_requests_count, 1)
        self.assertEqual(metrics.dispatch_ratio, Decimal("0.5"))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = InMemoryWorkerRegistry()
        self.record = WorkerRecord(id="w1", state=WorkerState.COLLECTING)

    def test_register_and_get(self) -> None:
        self.registry.register(self.record)
        self.assertTrue(self.registry.exists("w1"))
        self.assertEqual(self.registry.get("w1"), self.record)
        self.assertEqual(self.registry.list(), [self.record])

    def test_get_missing_raises(self) -> None:
        with self.assertRaises(RegistryError):
            self.registry.get("nope")

    def test_unregister_and_clear(self) -> None:
        self.registry.register(self.record)
        self.registry.unregister("w1")
        self.assertFalse(self.registry.exists("w1"))
        self.registry.register(self.record)
        self.registry.clear()
        self.assertEqual(self.registry.list(), [])


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------
class ManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_enqueues_and_accumulates(self) -> None:
        bus = EventBus()
        completed = FakeSubscriber()
        bus.subscribe(WorkerCompleted, completed.handle)
        manager = _manager(bus)

        first = await manager.enqueue(make_context(worker_id="w1"))
        second = await manager.enqueue(make_context(worker_id="w1"))

        self.assertEqual(second.status, WorkerResultStatus.SUCCESS)
        assert second.record is not None and second.metrics is not None
        self.assertEqual(second.record.job_count, 4)  # 2 per input
        self.assertTrue(second.requests)  # cpu dispatchable
        self.assertEqual(second.metrics.suppressed_requests_count, 1)  # mem suppressed
        self.assertEqual(len(completed.received), 2)
        self.assertEqual(first.metrics.total_requests, 1)  # type: ignore[union-attr]

    async def test_cancellation(self) -> None:
        bus = EventBus()
        cancelled = FakeSubscriber()
        bus.subscribe(WorkerCancelled, cancelled.handle)
        manager = _manager(bus)
        result = await manager.enqueue(make_context(worker_id="w1", cancel=True))
        self.assertEqual(result.status, WorkerResultStatus.CANCELLED)
        self.assertEqual(len(cancelled.received), 1)

    async def test_terminal_rejected(self) -> None:
        manager = _manager(EventBus())
        await manager.enqueue(make_context(worker_id="w1", cancel=True))
        result = await manager.enqueue(make_context(worker_id="w1"))
        self.assertEqual(result.status, WorkerResultStatus.FAILED)

    async def test_error_isolated(self) -> None:
        class _Boom:
            def collect(self, context: object) -> object:
                raise CollectionError("boom")

        bus = EventBus()
        errors = FakeSubscriber()
        bus.subscribe(WorkerErrorOccurred, errors.handle)
        manager = _manager(bus, collector=_Boom())
        result = await manager.enqueue(make_context(worker_id="w1"))
        self.assertEqual(result.status, WorkerResultStatus.FAILED)
        self.assertEqual(len(errors.received), 1)

    async def test_events_published(self) -> None:
        bus = EventBus()
        allev = FakeSubscriber()
        bus.subscribe(WorkerEvent, allev.handle)
        manager = _manager(bus)
        await manager.enqueue(make_context(worker_id="w1"))
        names = [type(e).__name__ for e in allev.received]
        self.assertEqual(names[0], "WorkerStarted")
        self.assertIn("JobsCollected", names)
        self.assertIn("RequestsDispatched", names)
        self.assertIn("WorkerCompleted", names)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_engine_delegates(self) -> None:
        engine = DefaultWorkerEngine(
            _manager(EventBus()), logger=FakeLoggerFactory()  # type: ignore[arg-type]
        )
        await engine.start()
        result = await engine.enqueue(make_context(worker_id="w1"))
        await engine.stop()
        self.assertEqual(result.status, WorkerResultStatus.SUCCESS)


# ---------------------------------------------------------------------------
# Dependency Injection
# ---------------------------------------------------------------------------
class RegistrationTests(unittest.TestCase):
    def test_registers_and_binds(self) -> None:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_workers(container)
        self.assertTrue(container.has(EventBus))
        self.assertIsInstance(
            container.resolve(WorkerEngine), DefaultWorkerEngine
        )
        self.assertIsInstance(
            container.resolve(WorkerManager), DefaultWorkerManager
        )
        self.assertIsInstance(container.resolve(Collector), DefaultCollector)
        self.assertIsInstance(container.resolve(Planner), DefaultPlanner)
        self.assertIsInstance(
            container.resolve(Dispatcher), DefaultDispatcher
        )
        self.assertIsInstance(
            container.resolve(WorkerRegistry), InMemoryWorkerRegistry
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class ExceptionTests(unittest.TestCase):
    def test_hierarchy(self) -> None:
        for exc in (CollectionError, RegistryError):
            self.assertTrue(issubclass(exc, WorkerError))


if __name__ == "__main__":
    unittest.main()
