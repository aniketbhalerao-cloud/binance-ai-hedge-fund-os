"""Storage Framework events.

Each inherits the existing :class:`events.base.Event` and is immutable. The
framework publishes **only** these — never reporting, notification, dashboard,
monitoring, performance, or any other framework's events. Events are published
only after a consistent record update (or an isolated failure).
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event

__all__ = [
    "StorageEvent",
    "StorageStarted",
    "StorageCollected",
    "StorageSerialized",
    "RequestsPlanned",
    "StorageSnapshotCreated",
    "StorageMetricsUpdated",
    "StorageCompleted",
    "StorageCancelled",
    "StorageErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class StorageEvent(Event):
    """Base class for all storage events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class StorageStarted(StorageEvent):
    """A storage update was requested for a record."""

    storage_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class StorageCollected(StorageEvent):
    """A storage batch was collected."""

    storage_id: str
    items: int


@dataclass(frozen=True, slots=True, kw_only=True)
class StorageSerialized(StorageEvent):
    """The storage batch's items were serialized."""

    storage_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RequestsPlanned(StorageEvent):
    """Storage requests were generated (domain objects, never persisted)."""

    storage_id: str
    count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class StorageSnapshotCreated(StorageEvent):
    """A storage snapshot was created."""

    storage_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class StorageMetricsUpdated(StorageEvent):
    """Storage metrics were recomputed."""

    storage_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class StorageCompleted(StorageEvent):
    """A storage update completed successfully."""

    storage_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class StorageCancelled(StorageEvent):
    """A storage session was cancelled."""

    storage_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class StorageErrorOccurred(StorageEvent):
    """A storage update failed and was isolated by the manager."""

    storage_id: str
    message: str
