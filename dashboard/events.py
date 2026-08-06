"""Dashboard Framework events.

Each inherits the existing :class:`events.base.Event` and is immutable. The
framework publishes **only** these — never strategy, agent, optimization,
monitoring, or any other framework's events. Events are published only after a
consistent record update (or an isolated failure).
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event

__all__ = [
    "DashboardEvent",
    "DashboardStarted",
    "DashboardViewCreated",
    "DashboardComposed",
    "WidgetsGenerated",
    "DashboardSnapshotCreated",
    "DashboardMetricsUpdated",
    "DashboardCompleted",
    "DashboardCancelled",
    "DashboardErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class DashboardEvent(Event):
    """Base class for all dashboard events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class DashboardStarted(DashboardEvent):
    """A dashboard update was requested for a record."""

    dashboard_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class DashboardViewCreated(DashboardEvent):
    """A dashboard view was created."""

    dashboard_id: str
    panels: int


@dataclass(frozen=True, slots=True, kw_only=True)
class DashboardComposed(DashboardEvent):
    """The dashboard view was arranged and resolved."""

    dashboard_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class WidgetsGenerated(DashboardEvent):
    """Widgets were generated (view models, not rendered to a display)."""

    dashboard_id: str
    count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class DashboardSnapshotCreated(DashboardEvent):
    """A dashboard snapshot was created."""

    dashboard_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class DashboardMetricsUpdated(DashboardEvent):
    """Dashboard metrics were recomputed."""

    dashboard_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class DashboardCompleted(DashboardEvent):
    """A dashboard update completed successfully."""

    dashboard_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class DashboardCancelled(DashboardEvent):
    """A dashboard session was cancelled."""

    dashboard_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class DashboardErrorOccurred(DashboardEvent):
    """A dashboard update failed and was isolated by the manager."""

    dashboard_id: str
    message: str
