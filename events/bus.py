"""In-memory asynchronous event bus.

:class:`EventBus` is a generic publish/subscribe hub built on :mod:`asyncio`
and the standard library only. It supports:

* subscribing one or many async handlers to an event type;
* type-hierarchy routing — a handler subscribed to a base type also receives
  every subclass event (subscribe to :class:`~events.base.Event` to see all);
* concurrent, asynchronous dispatch to all matching handlers; and
* isolation between handlers, so one failing subscriber never prevents the
  others from running.

The bus contains no trading, Binance, AI, or dashboard logic — it only moves
opaque :class:`~events.base.Event` objects from publishers to subscribers.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from threading import Lock

from events.base import Event, EventHandler, EventT
from events.subscriber import Subscription

__all__ = ["EventBus"]


class EventBus:
    """A generic, asyncio-based publish/subscribe event bus."""

    def __init__(self) -> None:
        # Handlers are keyed by the exact event type they subscribed to.
        self._handlers: dict[type[Event], list[EventHandler[Event]]] = defaultdict(
            list
        )
        # Guards mutation of ``_handlers`` so subscribe/unsubscribe/publish are
        # safe even if the bus is touched from multiple threads.
        self._lock = Lock()

    # -- subscription --------------------------------------------------------

    def subscribe(
        self, event_type: type[EventT], handler: EventHandler[EventT]
    ) -> Subscription:
        """Register ``handler`` to receive events of ``event_type``.

        A handler registered for a base type also receives events of any
        subtype (see :meth:`publish`).

        Args:
            event_type: The event class to listen for.
            handler: An async callable invoked with each matching event.

        Returns:
            A :class:`Subscription` that can cancel the registration.
        """
        generic_handler: EventHandler[Event] = handler  # type: ignore[assignment]
        with self._lock:
            self._handlers[event_type].append(generic_handler)

        def _cancel() -> None:
            with self._lock:
                handlers = self._handlers.get(event_type)
                if handlers and generic_handler in handlers:
                    handlers.remove(generic_handler)
                    if not handlers:
                        del self._handlers[event_type]

        return Subscription(
            event_type=event_type,
            handler=generic_handler,
            _unsubscribe=_cancel,
        )

    def subscribe_all(self, handler: EventHandler[Event]) -> Subscription:
        """Subscribe ``handler`` to *every* event (i.e. to :class:`Event`)."""
        return self.subscribe(Event, handler)

    # -- publishing ----------------------------------------------------------

    async def publish(self, event: Event) -> None:
        """Dispatch ``event`` to all matching handlers, concurrently.

        Handlers registered for the event's exact type and for any of its base
        types (up to and including :class:`Event`) are invoked. Exceptions
        raised by individual handlers are isolated and do not propagate or
        prevent other handlers from running.

        Args:
            event: The event instance to dispatch.
        """
        handlers = self._matching_handlers(type(event))
        if not handlers:
            return
        await asyncio.gather(
            *(handler(event) for handler in handlers),
            return_exceptions=True,
        )

    # -- introspection / lifecycle ------------------------------------------

    def handler_count(self, event_type: type[Event]) -> int:
        """Return the number of handlers registered for ``event_type`` exactly."""
        with self._lock:
            return len(self._handlers.get(event_type, ()))

    def clear(self) -> None:
        """Remove every registered handler."""
        with self._lock:
            self._handlers.clear()

    # -- internals -----------------------------------------------------------

    def _matching_handlers(
        self, event_type: type[Event]
    ) -> list[EventHandler[Event]]:
        """Return a snapshot of handlers for ``event_type`` and its bases."""
        matched: list[EventHandler[Event]] = []
        with self._lock:
            for klass in event_type.__mro__:
                if klass in self._handlers:
                    matched.extend(self._handlers[klass])
        return matched
