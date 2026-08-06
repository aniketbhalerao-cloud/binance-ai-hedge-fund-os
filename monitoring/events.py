"""Monitoring Framework events.

Each inherits the existing :class:`events.base.Event` and is immutable. The
framework publishes **only** these — never strategy, agent, learning, optimization,
or any other framework's events. Events are published only after a consistent
record update (or an isolated failure).
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event

__all__ = [
    "MonitoringEvent",
    "MonitoringStarted",
    "HealthReportCreated",
    "HealthEvaluated",
    "AlertsGenerated",
    "MonitoringSnapshotCreated",
    "MonitoringMetricsUpdated",
    "MonitoringCompleted",
    "MonitoringCancelled",
    "MonitoringErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class MonitoringEvent(Event):
    """Base class for all monitoring events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class MonitoringStarted(MonitoringEvent):
    """A monitoring update was requested for a record."""

    monitoring_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class HealthReportCreated(MonitoringEvent):
    """A health report was created."""

    monitoring_id: str
    checks: int


@dataclass(frozen=True, slots=True, kw_only=True)
class HealthEvaluated(MonitoringEvent):
    """The health report was scored and resolved."""

    monitoring_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class AlertsGenerated(MonitoringEvent):
    """Alerts were generated (proposed, not sent)."""

    monitoring_id: str
    count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class MonitoringSnapshotCreated(MonitoringEvent):
    """A monitoring snapshot was created."""

    monitoring_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class MonitoringMetricsUpdated(MonitoringEvent):
    """Monitoring metrics were recomputed."""

    monitoring_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class MonitoringCompleted(MonitoringEvent):
    """A monitoring update completed successfully."""

    monitoring_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class MonitoringCancelled(MonitoringEvent):
    """A monitoring session was cancelled."""

    monitoring_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class MonitoringErrorOccurred(MonitoringEvent):
    """A monitoring update failed and was isolated by the manager."""

    monitoring_id: str
    message: str
