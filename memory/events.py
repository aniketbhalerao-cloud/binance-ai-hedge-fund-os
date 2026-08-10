"""Memory Framework events.

Each inherits the existing :class:`events.base.Event` and is immutable. The
framework publishes **only** these — never agents, learning, reporting,
storage, or any other framework's events. Events are published only after a
consistent record update (or an isolated failure).
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event

__all__ = [
    "MemoryEvent",
    "MemoryStarted",
    "EntriesCollected",
    "EntriesPlanned",
    "RequestsDispatched",
    "MemorySnapshotCreated",
    "MemoryMetricsUpdated",
    "MemoryCompleted",
    "MemoryCancelled",
    "MemoryErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class MemoryEvent(Event):
    """Base class for all memory events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class MemoryStarted(MemoryEvent):
    """A memory update was requested for a record."""

    memory_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class EntriesCollected(MemoryEvent):
    """A memory batch was collected."""

    memory_id: str
    entries: int


@dataclass(frozen=True, slots=True, kw_only=True)
class EntriesPlanned(MemoryEvent):
    """The memory batch's entries were planned."""

    memory_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RequestsDispatched(MemoryEvent):
    """Memory requests were generated (domain objects, never persisted)."""

    memory_id: str
    count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class MemorySnapshotCreated(MemoryEvent):
    """A memory snapshot was created."""

    memory_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class MemoryMetricsUpdated(MemoryEvent):
    """Memory metrics were recomputed."""

    memory_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class MemoryCompleted(MemoryEvent):
    """A memory update completed successfully."""

    memory_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class MemoryCancelled(MemoryEvent):
    """A memory session was cancelled."""

    memory_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class MemoryErrorOccurred(MemoryEvent):
    """A memory update failed and was isolated by the manager."""

    memory_id: str
    message: str
