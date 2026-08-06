"""Reporting Framework events.

Each inherits the existing :class:`events.base.Event` and is immutable. The
framework publishes **only** these — never dashboard, notification, monitoring,
performance, learning, or any other framework's events. Events are published
only after a consistent record update (or an isolated failure).
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event

__all__ = [
    "ReportingEvent",
    "ReportingStarted",
    "ReportingCollected",
    "ReportBuilt",
    "ReportsExported",
    "ReportingSnapshotCreated",
    "ReportingMetricsUpdated",
    "ReportingCompleted",
    "ReportingCancelled",
    "ReportingErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class ReportingEvent(Event):
    """Base class for all reporting events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ReportingStarted(ReportingEvent):
    """A reporting update was requested for a record."""

    reporting_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ReportingCollected(ReportingEvent):
    """A reporting batch was collected."""

    reporting_id: str
    reports: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ReportBuilt(ReportingEvent):
    """The reporting batch's report objects were built."""

    reporting_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ReportsExported(ReportingEvent):
    """Export requests were generated (domain objects, never written or sent)."""

    reporting_id: str
    count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ReportingSnapshotCreated(ReportingEvent):
    """A reporting snapshot was created."""

    reporting_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ReportingMetricsUpdated(ReportingEvent):
    """Reporting metrics were recomputed."""

    reporting_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ReportingCompleted(ReportingEvent):
    """A reporting update completed successfully."""

    reporting_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ReportingCancelled(ReportingEvent):
    """A reporting session was cancelled."""

    reporting_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ReportingErrorOccurred(ReportingEvent):
    """A reporting update failed and was isolated by the manager."""

    reporting_id: str
    message: str
