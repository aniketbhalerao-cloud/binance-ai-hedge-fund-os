"""Notification Framework events.

Each inherits the existing :class:`events.base.Event` and is immutable. The
framework publishes **only** these — never monitoring, dashboard, optimization,
learning, or any other framework's events. Events are published only after a
consistent record update (or an isolated failure).
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event

__all__ = [
    "NotificationEvent",
    "NotificationStarted",
    "NotificationCollected",
    "NotificationFormatted",
    "RequestsGenerated",
    "NotificationSnapshotCreated",
    "NotificationMetricsUpdated",
    "NotificationCompleted",
    "NotificationCancelled",
    "NotificationErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class NotificationEvent(Event):
    """Base class for all notification events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class NotificationStarted(NotificationEvent):
    """A notification update was requested for a record."""

    notification_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class NotificationCollected(NotificationEvent):
    """A notification batch was collected."""

    notification_id: str
    notifications: int


@dataclass(frozen=True, slots=True, kw_only=True)
class NotificationFormatted(NotificationEvent):
    """The notification batch was arranged and resolved."""

    notification_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RequestsGenerated(NotificationEvent):
    """Notification requests were generated (domain objects, not sent)."""

    notification_id: str
    count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class NotificationSnapshotCreated(NotificationEvent):
    """A notification snapshot was created."""

    notification_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class NotificationMetricsUpdated(NotificationEvent):
    """Notification metrics were recomputed."""

    notification_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class NotificationCompleted(NotificationEvent):
    """A notification update completed successfully."""

    notification_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class NotificationCancelled(NotificationEvent):
    """A notification session was cancelled."""

    notification_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class NotificationErrorOccurred(NotificationEvent):
    """A notification update failed and was isolated by the manager."""

    notification_id: str
    message: str
