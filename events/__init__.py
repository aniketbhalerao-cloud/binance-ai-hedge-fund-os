"""Asynchronous, event-driven communication layer.

This package provides a generic publish/subscribe :class:`EventBus` built on
:mod:`asyncio` and the standard library only. Components communicate by
publishing and subscribing to :class:`Event` objects rather than calling each
other directly, keeping the system loosely coupled.

Public API:
    * :class:`Event` — immutable base event with ``event_id`` / ``timestamp``.
    * :class:`EventBus` — the publish/subscribe hub.
    * :class:`EventPublisher` — a publish-only facade over a bus.
    * :class:`Subscriber` / :class:`Subscription` — subscription primitives.
    * Generic system events (:class:`ServiceStarted`, :class:`Heartbeat`, …).
"""

from __future__ import annotations

from events.base import Event, EventHandler, EventT
from events.bus import EventBus
from events.events import (
    ErrorOccurred,
    Heartbeat,
    ServiceStarted,
    ServiceStopped,
    SystemEvent,
)
from events.publisher import EventPublisher
from events.subscriber import Subscriber, Subscription

__all__ = [
    "Event",
    "EventHandler",
    "EventT",
    "EventBus",
    "EventPublisher",
    "Subscriber",
    "Subscription",
    "SystemEvent",
    "ServiceStarted",
    "ServiceStopped",
    "Heartbeat",
    "ErrorOccurred",
]
