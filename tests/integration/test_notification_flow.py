"""Integration tests for the Notification Framework via the DI container.

Wires the notification engine into a container and runs the notify-loop input by
input over normalized source readings. The Registry owns the running record across
calls. No network, no sleeps, no randomness, no model training, and nothing is ever
sent.
"""

from __future__ import annotations

import unittest

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from notification import (
    DefaultNotificationEngine,
    NotificationCompleted,
    NotificationRegistry,
    NotificationResultStatus,
    register_notification,
)
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.notification_fakes import make_context, make_source


class NotificationIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _container(self) -> ServiceContainer:
        c = ServiceContainer()
        c.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_notification(c)
        return c

    async def test_notify_loop_produces_requests(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultNotificationEngine)
        registry = c.resolve(NotificationRegistry)
        bus = c.resolve(EventBus)
        done = FakeSubscriber()
        bus.subscribe(NotificationCompleted, done.handle)

        result = await engine.notify(make_context(notification_id="n1"))

        self.assertEqual(result.status, NotificationResultStatus.SUCCESS)
        assert result.metrics is not None
        self.assertTrue(result.requests)
        self.assertEqual(result.metrics.highest_priority_notification, "cpu")
        self.assertEqual(result.metrics.lowest_priority_notification, "mem")
        self.assertEqual(registry.get("n1").notification_count, 2)
        self.assertEqual(len(done.received), 1)

    async def test_record_accumulates_across_inputs(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultNotificationEngine)
        registry = c.resolve(NotificationRegistry)
        await engine.notify(make_context(notification_id="n1"))
        await engine.notify(
            make_context(notification_id="n1", monitoring=(make_source("disk", "2"),))
        )
        self.assertEqual(registry.get("n1").notification_count, 3)

    async def test_sessions_isolated(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultNotificationEngine)
        registry = c.resolve(NotificationRegistry)
        await engine.notify(make_context(notification_id="a"))
        await engine.notify(make_context(notification_id="b"))
        self.assertEqual(len(registry.list()), 2)


if __name__ == "__main__":
    unittest.main()
