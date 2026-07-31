"""Unit tests for the asynchronous Event Bus using fake subscribers.

Dispatch is awaited directly, so the tests are deterministic — no sleeps or
timing assertions are used.
"""

from __future__ import annotations

import unittest

from events.bus import EventBus
from events.events import Heartbeat, ServiceStarted, SystemEvent
from tests.support import FakeSubscriber


class EventBusTests(unittest.IsolatedAsyncioTestCase):
    async def test_subscriber_receives_published_event(self) -> None:
        bus = EventBus()
        subscriber = FakeSubscriber()
        bus.subscribe(ServiceStarted, subscriber.handle)

        event = ServiceStarted(component="market_data")
        await bus.publish(event)

        self.assertEqual(subscriber.received, [event])

    async def test_multiple_subscribers_all_receive_event(self) -> None:
        bus = EventBus()
        first, second = FakeSubscriber(), FakeSubscriber()
        bus.subscribe(ServiceStarted, first.handle)
        bus.subscribe(ServiceStarted, second.handle)

        event = ServiceStarted(component="strategy")
        await bus.publish(event)

        self.assertEqual(first.received, [event])
        self.assertEqual(second.received, [event])

    async def test_base_type_subscription_receives_subclass_events(self) -> None:
        bus = EventBus()
        subscriber = FakeSubscriber()
        bus.subscribe(SystemEvent, subscriber.handle)  # base type

        event = Heartbeat(component="scheduler", sequence=1)
        await bus.publish(event)

        self.assertEqual(subscriber.received, [event])

    async def test_unsubscribe_stops_delivery(self) -> None:
        bus = EventBus()
        subscriber = FakeSubscriber()
        subscription = bus.subscribe(ServiceStarted, subscriber.handle)

        subscription.unsubscribe()
        await bus.publish(ServiceStarted(component="risk"))

        self.assertEqual(subscriber.received, [])

    async def test_no_subscribers_is_a_noop(self) -> None:
        bus = EventBus()
        await bus.publish(ServiceStarted(component="none"))  # must not raise


if __name__ == "__main__":
    unittest.main()
