"""Scheduler Framework events.

Each inherits the existing :class:`events.base.Event` and is immutable. The
framework publishes **only** these — never storage, reporting, notification,
monitoring, optimization, or any other framework's events. Events are
published only after a consistent record update (or an isolated failure).
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event

__all__ = [
    "SchedulerEvent",
    "SchedulerStarted",
    "ScheduleCollected",
    "SchedulePlanned",
    "RequestsDispatched",
    "SchedulerSnapshotCreated",
    "SchedulerMetricsUpdated",
    "SchedulerCompleted",
    "SchedulerCancelled",
    "SchedulerErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class SchedulerEvent(Event):
    """Base class for all scheduler events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class SchedulerStarted(SchedulerEvent):
    """A scheduler update was requested for a record."""

    scheduler_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ScheduleCollected(SchedulerEvent):
    """A schedule batch was collected."""

    scheduler_id: str
    entries: int


@dataclass(frozen=True, slots=True, kw_only=True)
class SchedulePlanned(SchedulerEvent):
    """The schedule batch's entries were planned."""

    scheduler_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RequestsDispatched(SchedulerEvent):
    """Schedule requests were generated (domain objects, never executed)."""

    scheduler_id: str
    count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class SchedulerSnapshotCreated(SchedulerEvent):
    """A scheduler snapshot was created."""

    scheduler_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SchedulerMetricsUpdated(SchedulerEvent):
    """Scheduler metrics were recomputed."""

    scheduler_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SchedulerCompleted(SchedulerEvent):
    """A scheduler update completed successfully."""

    scheduler_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SchedulerCancelled(SchedulerEvent):
    """A scheduler session was cancelled."""

    scheduler_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SchedulerErrorOccurred(SchedulerEvent):
    """A scheduler update failed and was isolated by the manager."""

    scheduler_id: str
    message: str
