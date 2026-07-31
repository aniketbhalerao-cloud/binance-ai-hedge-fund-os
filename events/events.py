"""Generic, infrastructure-level event definitions.

These are domain-agnostic events that any component may emit or observe — they
carry no trading, exchange, AI, or dashboard semantics. Concrete domain events
(market data, signals, orders, …) belong in their own modules and simply
subclass :class:`~events.base.Event`; they are intentionally *not* defined here
to keep the event system generic.

All events are immutable and inherit ``event_id`` / ``timestamp`` metadata from
:class:`~events.base.Event`.
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event

__all__ = [
    "SystemEvent",
    "ServiceStarted",
    "ServiceStopped",
    "Heartbeat",
    "ErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class SystemEvent(Event):
    """Base for lifecycle/system events emitted by a named component.

    Attributes:
        component: Name of the component that emitted the event.
    """

    component: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ServiceStarted(SystemEvent):
    """Emitted when a component has started."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ServiceStopped(SystemEvent):
    """Emitted when a component has stopped."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Heartbeat(SystemEvent):
    """Periodic liveness signal from a component.

    Attributes:
        sequence: Monotonically increasing heartbeat counter.
    """

    sequence: int = 0


@dataclass(frozen=True, slots=True, kw_only=True)
class ErrorOccurred(Event):
    """A generic error notification.

    Attributes:
        message: Human-readable description of the error.
        source: Optional name of the component where the error originated.
    """

    message: str
    source: str | None = None
