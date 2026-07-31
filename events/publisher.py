"""Publish-only view over the event bus.

:class:`EventPublisher` wraps an :class:`~events.bus.EventBus` and exposes only
the ability to publish. Components that merely *emit* events (market-data
feeds, strategies, risk checks, …) can depend on this narrow surface instead of
the full bus, following the Interface Segregation Principle — they cannot
accidentally subscribe or clear handlers.
"""

from __future__ import annotations

from events.base import Event
from events.bus import EventBus

__all__ = ["EventPublisher"]


class EventPublisher:
    """A thin, publish-only facade over an :class:`EventBus`.

    Args:
        bus: The event bus events are published to.
    """

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    async def publish(self, event: Event) -> None:
        """Publish ``event`` to the underlying bus."""
        await self._bus.publish(event)
