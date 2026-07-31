"""Base event type and shared event typing.

Every event flowing through the bus derives from :class:`Event`, an immutable
dataclass that carries generic metadata (a unique ``event_id`` and a UTC
``timestamp``). The base is deliberately domain-agnostic: it knows nothing about
trading, market data, or any concrete component — those define their own
subclasses.

Fields are keyword-only so subclasses can add their own required fields without
running into dataclass default-ordering constraints.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TypeVar

__all__ = ["Event", "EventT", "EventHandler"]


@dataclass(frozen=True, slots=True, kw_only=True)
class Event:
    """Immutable base class for all events.

    Attributes:
        event_id: Unique identifier for this event instance (UUID4 hex).
        timestamp: Creation time, timezone-aware UTC.
    """

    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def name(self) -> str:
        """Return the event's type name (useful for routing and logs)."""
        return type(self).__name__


#: A type variable bound to :class:`Event`, used for generic, type-safe
#: subscription and handler signatures.
EventT = TypeVar("EventT", bound=Event)

#: An asynchronous handler that consumes an event of type ``EventT``.
EventHandler = Callable[[EventT], Awaitable[None]]
