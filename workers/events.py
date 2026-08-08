"""Background Workers Framework events.

Each inherits the existing :class:`events.base.Event` and is immutable. The
framework publishes **only** these — never storage, reporting, notification,
monitoring, scheduler, or any other framework's events. Events are published
only after a consistent record update (or an isolated failure).
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event

__all__ = [
    "WorkerEvent",
    "WorkerStarted",
    "JobsCollected",
    "JobsQueued",
    "RequestsDispatched",
    "WorkerSnapshotCreated",
    "WorkerMetricsUpdated",
    "WorkerCompleted",
    "WorkerCancelled",
    "WorkerErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkerEvent(Event):
    """Base class for all worker events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkerStarted(WorkerEvent):
    """A worker update was requested for a record."""

    worker_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class JobsCollected(WorkerEvent):
    """A job batch was collected."""

    worker_id: str
    jobs: int


@dataclass(frozen=True, slots=True, kw_only=True)
class JobsQueued(WorkerEvent):
    """The job batch's entries were planned."""

    worker_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RequestsDispatched(WorkerEvent):
    """Worker requests were generated (domain objects, never executed)."""

    worker_id: str
    count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkerSnapshotCreated(WorkerEvent):
    """A worker snapshot was created."""

    worker_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkerMetricsUpdated(WorkerEvent):
    """Worker metrics were recomputed."""

    worker_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkerCompleted(WorkerEvent):
    """A worker update completed successfully."""

    worker_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkerCancelled(WorkerEvent):
    """A worker session was cancelled."""

    worker_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkerErrorOccurred(WorkerEvent):
    """A worker update failed and was isolated by the manager."""

    worker_id: str
    message: str
