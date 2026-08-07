"""Unit tests for the Storage Framework (stdlib unittest, deterministic)."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from decimal import Decimal

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from storage import (
    Collector,
    DefaultCollector,
    DefaultPersistencePlanner,
    DefaultSerializer,
    DefaultStorageEngine,
    DefaultStorageManager,
    DefaultStorageMetrics,
    InMemoryStorageRegistry,
    PersistencePlanner,
    Serializer,
    StorageCancelled,
    StorageCompleted,
    StorageEngine,
    StorageError,
    StorageEvent,
    StorageManager,
    StorageParameters,
    StorageRegistry,
    StorageResultStatus,
    register_storage,
)
from storage.events import StorageErrorOccurred
from storage.exceptions import CollectionError, RegistryError
from storage.models import StorageBatch, StorageItem, StorageRecord, StorageSource
from storage.state import VALID_TRANSITIONS, StorageState, can_transition
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.storage_fakes import make_context, make_source

_ZERO = Decimal("0")
_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def _manager(bus: EventBus, **overrides: object) -> DefaultStorageManager:
    return DefaultStorageManager(
        bus,
        InMemoryStorageRegistry(),
        overrides.get("collector", DefaultCollector()),  # type: ignore[arg-type]
        DefaultSerializer(),
        DefaultPersistencePlanner(),
        DefaultStorageMetrics(),
        logger=FakeLoggerFactory(),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# State & models
# ---------------------------------------------------------------------------
class StateModelTests(unittest.TestCase):
    def test_transitions(self) -> None:
        self.assertTrue(
            can_transition(StorageState.CREATED, StorageState.COLLECTING)
        )
        self.assertTrue(
            can_transition(StorageState.SERIALIZED, StorageState.SERIALIZED)
        )
        self.assertEqual(
            VALID_TRANSITIONS[StorageState.COMPLETED], frozenset()
        )

    def test_history_append_immutable(self) -> None:
        from storage.models import StorageHistory

        history = StorageHistory()
        new = history.append(StorageBatch())
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
        self.assertEqual(len(batch.items), 2)

    def test_max_items_caps(self) -> None:
        monitoring = tuple(make_source(f"s{i}", str(i)) for i in range(10))
        batch = self.collector.collect(
            make_context(
                monitoring=monitoring,
                parameters=StorageParameters(max_items=3),
            )
        )
        self.assertEqual(len(batch.sources), 3)


# ---------------------------------------------------------------------------
# Serializer & PersistencePlanner
# ---------------------------------------------------------------------------
class SerializerPlannerTests(unittest.TestCase):
    def _batch(self) -> StorageBatch:
        s_ok = StorageSource(
            name="cpu", source="monitoring", priority=Decimal("5")
        )
        s_bad = StorageSource(
            name="mem", source="monitoring", priority=Decimal("-3")
        )
        return StorageBatch(
            sources=(s_ok, s_bad),
            items=(
                StorageItem(source=s_ok),
                StorageItem(source=s_bad),
            ),
        )

    def test_serializer_resolves_persistence(self) -> None:
        serialized = DefaultSerializer().serialize(self._batch(), make_context())
        persist = {i.source.name: i.persist for i in serialized.items}
        self.assertTrue(persist["cpu"])
        self.assertFalse(persist["mem"])

    def test_planner_only_for_persistable(self) -> None:
        serialized = DefaultSerializer().serialize(self._batch(), make_context())
        requests = DefaultPersistencePlanner().plan(serialized, make_context())
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].subject, "cpu")
        self.assertEqual(requests[0].source, "monitoring")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
class MetricsTests(unittest.TestCase):
    def test_highest_lowest_persistence_and_suppressed(self) -> None:
        s_hi = StorageSource(
            name="cpu", source="monitoring", priority=Decimal("5")
        )
        s_lo = StorageSource(
            name="mem", source="monitoring", priority=Decimal("-3")
        )
        batch = StorageBatch(
            sources=(s_hi, s_lo),
            items=(
                StorageItem(source=s_hi, persist=True),
                StorageItem(source=s_lo, persist=False),
            ),
        )
        from storage.models import StorageRequest

        record = StorageRecord(
            id="s1", state=StorageState.SERIALIZED, batch=batch,
            requests=(
                StorageRequest(
                    subject="cpu", source="monitoring", target="database"
                ),
            ),
            item_count=2, request_count=1,
        )
        metrics = DefaultStorageMetrics().calculate(record)
        self.assertEqual(metrics.highest_priority_item, "cpu")
        self.assertEqual(metrics.lowest_priority_item, "mem")
        self.assertEqual(metrics.pending_requests_count, 1)
        self.assertEqual(metrics.suppressed_requests_count, 1)
        self.assertEqual(metrics.persistence_ratio, Decimal("0.5"))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = InMemoryStorageRegistry()
        self.record = StorageRecord(id="s1", state=StorageState.COLLECTING)

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
    async def test_stores_and_accumulates(self) -> None:
        bus = EventBus()
        completed = FakeSubscriber()
        bus.subscribe(StorageCompleted, completed.handle)
        manager = _manager(bus)

        first = await manager.store(make_context(storage_id="s1"))
        second = await manager.store(make_context(storage_id="s1"))

        self.assertEqual(second.status, StorageResultStatus.SUCCESS)
        assert second.record is not None and second.metrics is not None
        self.assertEqual(second.record.item_count, 4)  # 2 per input
        self.assertTrue(second.requests)  # cpu persistable
        self.assertEqual(second.metrics.suppressed_requests_count, 1)  # mem suppressed
        self.assertEqual(len(completed.received), 2)
        self.assertEqual(first.metrics.total_requests, 1)  # type: ignore[union-attr]

    async def test_cancellation(self) -> None:
        bus = EventBus()
        cancelled = FakeSubscriber()
        bus.subscribe(StorageCancelled, cancelled.handle)
        manager = _manager(bus)
        result = await manager.store(make_context(storage_id="s1", cancel=True))
        self.assertEqual(result.status, StorageResultStatus.CANCELLED)
        self.assertEqual(len(cancelled.received), 1)

    async def test_terminal_rejected(self) -> None:
        manager = _manager(EventBus())
        await manager.store(make_context(storage_id="s1", cancel=True))
        result = await manager.store(make_context(storage_id="s1"))
        self.assertEqual(result.status, StorageResultStatus.FAILED)

    async def test_error_isolated(self) -> None:
        class _Boom:
            def collect(self, context: object) -> object:
                raise CollectionError("boom")

        bus = EventBus()
        errors = FakeSubscriber()
        bus.subscribe(StorageErrorOccurred, errors.handle)
        manager = _manager(bus, collector=_Boom())
        result = await manager.store(make_context(storage_id="s1"))
        self.assertEqual(result.status, StorageResultStatus.FAILED)
        self.assertEqual(len(errors.received), 1)

    async def test_events_published(self) -> None:
        bus = EventBus()
        allev = FakeSubscriber()
        bus.subscribe(StorageEvent, allev.handle)
        manager = _manager(bus)
        await manager.store(make_context(storage_id="s1"))
        names = [type(e).__name__ for e in allev.received]
        self.assertEqual(names[0], "StorageStarted")
        self.assertIn("StorageCollected", names)
        self.assertIn("RequestsPlanned", names)
        self.assertIn("StorageCompleted", names)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_engine_delegates(self) -> None:
        engine = DefaultStorageEngine(
            _manager(EventBus()), logger=FakeLoggerFactory()  # type: ignore[arg-type]
        )
        await engine.start()
        result = await engine.store(make_context(storage_id="s1"))
        await engine.stop()
        self.assertEqual(result.status, StorageResultStatus.SUCCESS)


# ---------------------------------------------------------------------------
# Dependency Injection
# ---------------------------------------------------------------------------
class RegistrationTests(unittest.TestCase):
    def test_registers_and_binds(self) -> None:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_storage(container)
        self.assertTrue(container.has(EventBus))
        self.assertIsInstance(
            container.resolve(StorageEngine), DefaultStorageEngine
        )
        self.assertIsInstance(
            container.resolve(StorageManager), DefaultStorageManager
        )
        self.assertIsInstance(container.resolve(Collector), DefaultCollector)
        self.assertIsInstance(container.resolve(Serializer), DefaultSerializer)
        self.assertIsInstance(
            container.resolve(PersistencePlanner), DefaultPersistencePlanner
        )
        self.assertIsInstance(
            container.resolve(StorageRegistry), InMemoryStorageRegistry
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class ExceptionTests(unittest.TestCase):
    def test_hierarchy(self) -> None:
        for exc in (CollectionError, RegistryError):
            self.assertTrue(issubclass(exc, StorageError))


if __name__ == "__main__":
    unittest.main()
