"""Subscription primitives for the event bus.

This module defines:

* :class:`Subscriber` — an optional abstract base for class-based handlers; and
* :class:`Subscription` — a handle returned when subscribing, used to cancel the
  subscription later.

Neither type depends on the concrete :class:`~events.bus.EventBus`; the bus
supplies an ``unsubscribe`` callback when it creates a :class:`Subscription`,
which keeps this module free of import cycles.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field

from events.base import Event, EventHandler

__all__ = ["Subscriber", "Subscription"]


class Subscriber(ABC):
    """Optional base class for object-oriented event handlers.

    Implementations override :meth:`handle`; the bound method can then be passed
    to :meth:`~events.bus.EventBus.subscribe`. Using this base is not required —
    any async callable works as a handler.
    """

    @abstractmethod
    async def handle(self, event: Event) -> None:
        """Handle a received ``event``."""


@dataclass(slots=True)
class Subscription:
    """A cancellable handle to a registered handler.

    Attributes:
        event_type: The event type this subscription listens for.
        handler: The async callable invoked when a matching event is published.

    A subscription is created by the bus, which injects the ``_unsubscribe``
    callback used by :meth:`unsubscribe`.
    """

    event_type: type[Event]
    handler: EventHandler[Event]
    _unsubscribe: Callable[[], None]
    _active: bool = field(default=True, repr=False)

    @property
    def active(self) -> bool:
        """Return ``True`` while the subscription is still registered."""
        return self._active

    def unsubscribe(self) -> None:
        """Cancel the subscription. Idempotent — safe to call more than once."""
        if self._active:
            self._active = False
            self._unsubscribe()
