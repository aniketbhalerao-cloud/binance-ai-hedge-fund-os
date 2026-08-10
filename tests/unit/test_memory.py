"""Unit tests for the Memory Framework (stdlib unittest, deterministic)."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from decimal import Decimal

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from memory import (
    Collector,
    DefaultCollector,
    DefaultDispatcher,
    DefaultMemoryEngine,
    DefaultMemoryManager,
    DefaultMemoryMetrics,
    DefaultPlanner,
    Dispatcher,
    InMemoryMemoryRegistry,
    MemoryCancelled,
    MemoryCompleted,
    MemoryEngine,
    MemoryError,
    MemoryEvent,
    MemoryManager,
    MemoryParameters,
    MemoryRegistry,
    MemoryResultStatus,
    Planner,
    register_memory,
)
from memory.events import MemoryErrorOccurred
from memory.exceptions import CollectionError, RegistryError
from memory.models import (
    MemoryBatch,
    MemoryEntry,
    MemoryRecord,
    MemorySource,
)
from memory.state import VALID_TRANSITIONS, MemoryState, can_transition
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.memory_fakes import make_context, make_source

_ZERO = Decimal("0")
_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def _manager(bus: EventBus, **overrides: object) -> DefaultMemoryManager:
    return DefaultMemoryManager(
        bus,
        InMemoryMemoryRegistry(),
        overrides.get("collector", DefaultCollector()),  # type: ignore[arg-type]
        DefaultPlanner(),
        DefaultDispatcher(),
        DefaultMemoryMetrics(),
        logger=FakeLoggerFactory(),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# State & models
# ---------------------------------------------------------------------------
class StateModelTests(unittest.TestCase):
    def test_transitions(self) -> None:
        self.assertTrue(
            can_transition(MemoryState.CREATED, MemoryState.COLLECTING)
        )
        self.assertTrue(
            can_transition(MemoryState.PLANNED, MemoryState.PLANNED)
        )
        self.assertEqual(
            VALID_TRANSITIONS[MemoryState.COMPLETED], frozenset()
        )

    def test_history_append_immutable(self) -> None:
        from memory.models import MemoryHistory

        history = MemoryHistory()
        new = history.append(MemoryBatch())
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
                learning=(make_source("cpu", "5"),),
                reporting=(make_source("daily", "9", source="reporting"),),
            )
        )
        self.assertEqual(batch.sources[0].name, "daily")  # highest priority first
        self.assertEqual(len(batch.entries), 2)

    def test_max_items_caps(self) -> None:
        learning = tuple(make_source(f"s{i}", str(i)) for i in range(10))
        batch = self.collector.collect(
            make_context(
                learning=learning,
                parameters=MemoryParameters(max_items=3),
            )
        )
        self.assertEqual(len(batch.sources), 3)


# ---------------------------------------------------------------------------
# Planner & Dispatcher
# ---------------------------------------------------------------------------
class PlannerDispatcherTests(unittest.TestCase):
    def _batch(self) -> MemoryBatch:
        s_ok = MemorySource(
            name="cpu", source="learning", priority=Decimal("5")
        )
        s_bad = MemorySource(
            name="mem", source="learning", priority=Decimal("-3")
        )
        return MemoryBatch(
            sources=(s_ok, s_bad),
            entries=(
                MemoryEntry(source=s_ok),
                MemoryEntry(source=s_bad),
            ),
        )

    def test_planner_resolves_commit(self) -> None:
        planned = DefaultPlanner().plan(self._batch(), make_context())
        commit = {e.source.name: e.commit for e in planned.entries}
        self.assertTrue(commit["cpu"])
        self.assertFalse(commit["mem"])

    def test_dispatcher_only_for_committable(self) -> None:
        planned = DefaultPlanner().plan(self._batch(), make_context())
        requests = DefaultDispatcher().dispatch(planned, make_context())
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].subject, "cpu")
        self.assertEqual(requests[0].source, "learning")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
class MetricsTests(unittest.TestCase):
    def test_highest_lowest_commit_and_suppressed(self) -> None:
        s_hi = MemorySource(
            name="cpu", source="learning", priority=Decimal("5")
        )
        s_lo = MemorySource(
            name="mem", source="learning", priority=Decimal("-3")
        )
        batch = MemoryBatch(
            sources=(s_hi, s_lo),
            entries=(
                MemoryEntry(source=s_hi, commit=True),
                MemoryEntry(source=s_lo, commit=False),
            ),
        )
        from memory.models import MemoryRequest

        record = MemoryRecord(
            id="m1", state=MemoryState.PLANNED, batch=batch,
            requests=(
                MemoryRequest(
                    subject="cpu", source="learning", scope="working"
                ),
            ),
            entry_count=2, request_count=1,
        )
        metrics = DefaultMemoryMetrics().calculate(record)
        self.assertEqual(metrics.highest_priority_entry, "cpu")
        self.assertEqual(metrics.lowest_priority_entry, "mem")
        self.assertEqual(metrics.pending_requests_count, 1)
        self.assertEqual(metrics.suppressed_requests_count, 1)
        self.assertEqual(metrics.commit_ratio, Decimal("0.5"))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = InMemoryMemoryRegistry()
        self.record = MemoryRecord(id="m1", state=MemoryState.COLLECTING)

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
    async def test_remembers_and_accumulates(self) -> None:
        bus = EventBus()
        completed = FakeSubscriber()
        bus.subscribe(MemoryCompleted, completed.handle)
        manager = _manager(bus)

        first = await manager.remember(make_context(memory_id="m1"))
        second = await manager.remember(make_context(memory_id="m1"))

        self.assertEqual(second.status, MemoryResultStatus.SUCCESS)
        assert second.record is not None and second.metrics is not None
        self.assertEqual(second.record.entry_count, 4)  # 2 per input
        self.assertTrue(second.requests)  # cpu committable
        self.assertEqual(second.metrics.suppressed_requests_count, 1)  # mem suppressed
        self.assertEqual(len(completed.received), 2)
        self.assertEqual(first.metrics.total_requests, 1)  # type: ignore[union-attr]

    async def test_cancellation(self) -> None:
        bus = EventBus()
        cancelled = FakeSubscriber()
        bus.subscribe(MemoryCancelled, cancelled.handle)
        manager = _manager(bus)
        result = await manager.remember(make_context(memory_id="m1", cancel=True))
        self.assertEqual(result.status, MemoryResultStatus.CANCELLED)
        self.assertEqual(len(cancelled.received), 1)

    async def test_terminal_rejected(self) -> None:
        manager = _manager(EventBus())
        await manager.remember(make_context(memory_id="m1", cancel=True))
        result = await manager.remember(make_context(memory_id="m1"))
        self.assertEqual(result.status, MemoryResultStatus.FAILED)

    async def test_error_isolated(self) -> None:
        class _Boom:
            def collect(self, context: object) -> object:
                raise CollectionError("boom")

        bus = EventBus()
        errors = FakeSubscriber()
        bus.subscribe(MemoryErrorOccurred, errors.handle)
        manager = _manager(bus, collector=_Boom())
        result = await manager.remember(make_context(memory_id="m1"))
        self.assertEqual(result.status, MemoryResultStatus.FAILED)
        self.assertEqual(len(errors.received), 1)

    async def test_events_published(self) -> None:
        bus = EventBus()
        allev = FakeSubscriber()
        bus.subscribe(MemoryEvent, allev.handle)
        manager = _manager(bus)
        await manager.remember(make_context(memory_id="m1"))
        names = [type(e).__name__ for e in allev.received]
        self.assertEqual(names[0], "MemoryStarted")
        self.assertIn("EntriesCollected", names)
        self.assertIn("RequestsDispatched", names)
        self.assertIn("MemoryCompleted", names)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_engine_delegates(self) -> None:
        engine = DefaultMemoryEngine(
            _manager(EventBus()), logger=FakeLoggerFactory()  # type: ignore[arg-type]
        )
        await engine.start()
        result = await engine.remember(make_context(memory_id="m1"))
        await engine.stop()
        self.assertEqual(result.status, MemoryResultStatus.SUCCESS)


# ---------------------------------------------------------------------------
# Dependency Injection
# ---------------------------------------------------------------------------
class RegistrationTests(unittest.TestCase):
    def test_registers_and_binds(self) -> None:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_memory(container)
        self.assertTrue(container.has(EventBus))
        self.assertIsInstance(
            container.resolve(MemoryEngine), DefaultMemoryEngine
        )
        self.assertIsInstance(
            container.resolve(MemoryManager), DefaultMemoryManager
        )
        self.assertIsInstance(container.resolve(Collector), DefaultCollector)
        self.assertIsInstance(container.resolve(Planner), DefaultPlanner)
        self.assertIsInstance(
            container.resolve(Dispatcher), DefaultDispatcher
        )
        self.assertIsInstance(
            container.resolve(MemoryRegistry), InMemoryMemoryRegistry
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class ExceptionTests(unittest.TestCase):
    def test_hierarchy(self) -> None:
        for exc in (CollectionError, RegistryError):
            self.assertTrue(issubclass(exc, MemoryError))


if __name__ == "__main__":
    unittest.main()
