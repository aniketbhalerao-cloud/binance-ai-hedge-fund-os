"""Unit tests for the Notification Framework (stdlib unittest, deterministic)."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from decimal import Decimal

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from notification import (
    Collector,
    DefaultCollector,
    DefaultDispatcher,
    DefaultFormatter,
    DefaultNotificationEngine,
    DefaultNotificationManager,
    DefaultNotificationMetrics,
    Dispatcher,
    Formatter,
    InMemoryNotificationRegistry,
    NotificationCancelled,
    NotificationCompleted,
    NotificationEngine,
    NotificationError,
    NotificationEvent,
    NotificationManager,
    NotificationParameters,
    NotificationRegistry,
    NotificationResultStatus,
    register_notification,
)
from notification.events import NotificationErrorOccurred
from notification.exceptions import CollectionError, RegistryError
from notification.models import (
    Notification,
    NotificationBatch,
    NotificationRecord,
    NotificationSource,
)
from notification.state import VALID_TRANSITIONS, NotificationState, can_transition
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.notification_fakes import make_context, make_source

_ZERO = Decimal("0")
_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def _manager(bus: EventBus, **overrides: object) -> DefaultNotificationManager:
    return DefaultNotificationManager(
        bus,
        InMemoryNotificationRegistry(),
        overrides.get("collector", DefaultCollector()),  # type: ignore[arg-type]
        DefaultFormatter(),
        DefaultDispatcher(),
        DefaultNotificationMetrics(),
        logger=FakeLoggerFactory(),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# State & models
# ---------------------------------------------------------------------------
class StateModelTests(unittest.TestCase):
    def test_transitions(self) -> None:
        self.assertTrue(
            can_transition(NotificationState.CREATED, NotificationState.COLLECTING)
        )
        self.assertTrue(
            can_transition(NotificationState.FORMATTED, NotificationState.FORMATTED)
        )
        self.assertEqual(
            VALID_TRANSITIONS[NotificationState.COMPLETED], frozenset()
        )

    def test_history_append_immutable(self) -> None:
        from notification.models import NotificationHistory

        history = NotificationHistory()
        new = history.append(NotificationBatch())
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
        self.assertEqual(len(batch.notifications), 2)

    def test_max_notifications_caps(self) -> None:
        monitoring = tuple(make_source(f"s{i}", str(i)) for i in range(10))
        batch = self.collector.collect(
            make_context(
                monitoring=monitoring,
                parameters=NotificationParameters(max_notifications=3),
            )
        )
        self.assertEqual(len(batch.sources), 3)


# ---------------------------------------------------------------------------
# Formatter & Dispatcher
# ---------------------------------------------------------------------------
class FormatterDispatcherTests(unittest.TestCase):
    def _batch(self) -> NotificationBatch:
        s_ok = NotificationSource(
            name="cpu", source="monitoring", priority=Decimal("5")
        )
        s_bad = NotificationSource(
            name="mem", source="monitoring", priority=Decimal("-3")
        )
        return NotificationBatch(
            sources=(s_ok, s_bad),
            notifications=(
                Notification(source=s_ok),
                Notification(source=s_bad),
            ),
        )

    def test_formatter_resolves_delivery(self) -> None:
        formatted = DefaultFormatter().format(self._batch(), make_context())
        deliver = {n.source.name: n.deliver for n in formatted.notifications}
        self.assertTrue(deliver["cpu"])
        self.assertFalse(deliver["mem"])

    def test_dispatcher_only_for_deliverable(self) -> None:
        formatted = DefaultFormatter().format(self._batch(), make_context())
        requests = DefaultDispatcher().dispatch(formatted, make_context())
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].subject, "cpu")
        self.assertEqual(requests[0].channel, "monitoring")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
class MetricsTests(unittest.TestCase):
    def test_highest_lowest_delivery_and_suppressed(self) -> None:
        s_hi = NotificationSource(
            name="cpu", source="monitoring", priority=Decimal("5")
        )
        s_lo = NotificationSource(
            name="mem", source="monitoring", priority=Decimal("-3")
        )
        batch = NotificationBatch(
            sources=(s_hi, s_lo),
            notifications=(
                Notification(source=s_hi, deliver=True),
                Notification(source=s_lo, deliver=False),
            ),
        )
        from notification.models import NotificationRequest

        record = NotificationRecord(
            id="n1", state=NotificationState.FORMATTED, batch=batch,
            requests=(
                NotificationRequest(
                    subject="cpu", source="monitoring", channel="monitoring"
                ),
            ),
            notification_count=2, request_count=1,
        )
        metrics = DefaultNotificationMetrics().calculate(record)
        self.assertEqual(metrics.highest_priority_notification, "cpu")
        self.assertEqual(metrics.lowest_priority_notification, "mem")
        self.assertEqual(metrics.pending_requests_count, 1)
        self.assertEqual(metrics.suppressed_requests_count, 1)
        self.assertEqual(metrics.delivery_ratio, Decimal("0.5"))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = InMemoryNotificationRegistry()
        self.record = NotificationRecord(id="n1", state=NotificationState.COLLECTING)

    def test_register_and_get(self) -> None:
        self.registry.register(self.record)
        self.assertTrue(self.registry.exists("n1"))
        self.assertEqual(self.registry.get("n1"), self.record)
        self.assertEqual(self.registry.list(), [self.record])

    def test_get_missing_raises(self) -> None:
        with self.assertRaises(RegistryError):
            self.registry.get("nope")

    def test_unregister_and_clear(self) -> None:
        self.registry.register(self.record)
        self.registry.unregister("n1")
        self.assertFalse(self.registry.exists("n1"))
        self.registry.register(self.record)
        self.registry.clear()
        self.assertEqual(self.registry.list(), [])


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------
class ManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_notifies_and_accumulates(self) -> None:
        bus = EventBus()
        completed = FakeSubscriber()
        bus.subscribe(NotificationCompleted, completed.handle)
        manager = _manager(bus)

        first = await manager.notify(make_context(notification_id="n1"))
        second = await manager.notify(make_context(notification_id="n1"))

        self.assertEqual(second.status, NotificationResultStatus.SUCCESS)
        assert second.record is not None and second.metrics is not None
        self.assertEqual(second.record.notification_count, 4)  # 2 per input
        self.assertTrue(second.requests)  # cpu deliverable
        self.assertEqual(second.metrics.suppressed_requests_count, 1)  # mem suppressed
        self.assertEqual(len(completed.received), 2)
        self.assertEqual(first.metrics.total_requests, 1)  # type: ignore[union-attr]

    async def test_cancellation(self) -> None:
        bus = EventBus()
        cancelled = FakeSubscriber()
        bus.subscribe(NotificationCancelled, cancelled.handle)
        manager = _manager(bus)
        result = await manager.notify(make_context(notification_id="n1", cancel=True))
        self.assertEqual(result.status, NotificationResultStatus.CANCELLED)
        self.assertEqual(len(cancelled.received), 1)

    async def test_terminal_rejected(self) -> None:
        manager = _manager(EventBus())
        await manager.notify(make_context(notification_id="n1", cancel=True))
        result = await manager.notify(make_context(notification_id="n1"))
        self.assertEqual(result.status, NotificationResultStatus.FAILED)

    async def test_error_isolated(self) -> None:
        class _Boom:
            def collect(self, context: object) -> object:
                raise CollectionError("boom")

        bus = EventBus()
        errors = FakeSubscriber()
        bus.subscribe(NotificationErrorOccurred, errors.handle)
        manager = _manager(bus, collector=_Boom())
        result = await manager.notify(make_context(notification_id="n1"))
        self.assertEqual(result.status, NotificationResultStatus.FAILED)
        self.assertEqual(len(errors.received), 1)

    async def test_events_published(self) -> None:
        bus = EventBus()
        allev = FakeSubscriber()
        bus.subscribe(NotificationEvent, allev.handle)
        manager = _manager(bus)
        await manager.notify(make_context(notification_id="n1"))
        names = [type(e).__name__ for e in allev.received]
        self.assertEqual(names[0], "NotificationStarted")
        self.assertIn("NotificationCollected", names)
        self.assertIn("RequestsGenerated", names)
        self.assertIn("NotificationCompleted", names)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_engine_delegates(self) -> None:
        engine = DefaultNotificationEngine(
            _manager(EventBus()), logger=FakeLoggerFactory()  # type: ignore[arg-type]
        )
        await engine.start()
        result = await engine.notify(make_context(notification_id="n1"))
        await engine.stop()
        self.assertEqual(result.status, NotificationResultStatus.SUCCESS)


# ---------------------------------------------------------------------------
# Dependency Injection
# ---------------------------------------------------------------------------
class RegistrationTests(unittest.TestCase):
    def test_registers_and_binds(self) -> None:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_notification(container)
        self.assertTrue(container.has(EventBus))
        self.assertIsInstance(
            container.resolve(NotificationEngine), DefaultNotificationEngine
        )
        self.assertIsInstance(
            container.resolve(NotificationManager), DefaultNotificationManager
        )
        self.assertIsInstance(container.resolve(Collector), DefaultCollector)
        self.assertIsInstance(container.resolve(Formatter), DefaultFormatter)
        self.assertIsInstance(container.resolve(Dispatcher), DefaultDispatcher)
        self.assertIsInstance(
            container.resolve(NotificationRegistry), InMemoryNotificationRegistry
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class ExceptionTests(unittest.TestCase):
    def test_hierarchy(self) -> None:
        for exc in (CollectionError, RegistryError):
            self.assertTrue(issubclass(exc, NotificationError))


if __name__ == "__main__":
    unittest.main()
