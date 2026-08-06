"""Notification Framework domain models.

Immutable, exchange-independent value objects. The rest of the application
consumes only these standardized models. Scores use :class:`~decimal.Decimal`;
timestamps are timezone-aware UTC. Every model is frozen — batches, requests, and
the running record are never mutated; each notified input produces a **new** record.

The framework only *requests*: requests carry delivery detail as immutable domain
objects and are never sent, and the framework never modifies a strategy, agent, or
portfolio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from notification.state import NotificationState

__all__ = [
    "NotificationResultStatus",
    "NotificationParameters",
    "NotificationSource",
    "Notification",
    "NotificationBatch",
    "NotificationRequest",
    "NotificationHistory",
    "NotificationRecord",
    "NotificationMetrics",
    "NotificationSnapshot",
    "NotificationResult",
]

_ZERO = Decimal("0")


class NotificationResultStatus(str, Enum):
    """Coarse outcome of notifying one input."""

    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class NotificationParameters:
    """Deterministic notification configuration.

    Attributes:
        priority_threshold: Priority at or above which a notification is delivered.
        max_notifications: Maximum number of notifications to build per input.
    """

    priority_threshold: Decimal = _ZERO
    max_notifications: int = 5


@dataclass(frozen=True, slots=True)
class NotificationSource:
    """A normalized notification datum feeding one notification."""

    name: str
    source: str
    category: str = "unknown"
    priority: Decimal = _ZERO
    samples: int = 0


@dataclass(frozen=True, slots=True)
class Notification:
    """A formatted notification within a batch (a domain object, never sent)."""

    source: NotificationSource
    deliver: bool = True
    channel: str = "general"
    detail: str = ""


@dataclass(frozen=True, slots=True)
class NotificationBatch:
    """An immutable batch: the collected sources and their formatted notifications."""

    sources: tuple[NotificationSource, ...] = ()
    notifications: tuple[Notification, ...] = ()


@dataclass(frozen=True, slots=True)
class NotificationRequest:
    """A deterministic notification request (an immutable object, never sent)."""

    subject: str
    source: str
    channel: str
    category: str = "unknown"
    priority: Decimal = _ZERO
    detail: str = ""


@dataclass(frozen=True, slots=True)
class NotificationHistory:
    """Append-only record of produced batches."""

    batches: tuple[NotificationBatch, ...] = ()

    def append(self, batch: NotificationBatch) -> NotificationHistory:
        """Return a new history with ``batch`` appended (never mutates)."""
        return NotificationHistory(self.batches + (batch,))


@dataclass(frozen=True, slots=True)
class NotificationRecord:
    """The durable, immutable running state of one notification session.

    The Registry owns the current ``NotificationRecord``; the Manager loads it,
    processes one input, and writes back a **new** ``NotificationRecord``.
    """

    id: str
    state: NotificationState
    history: NotificationHistory = field(default_factory=NotificationHistory)
    batch: NotificationBatch = field(default_factory=NotificationBatch)
    requests: tuple[NotificationRequest, ...] = ()
    notification_count: int = 0
    request_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class NotificationMetrics:
    """Derived metrics over a notification record."""

    total_notifications: int = 0
    total_requests: int = 0
    average_priority_score: Decimal = _ZERO
    highest_priority_notification: str = ""
    lowest_priority_notification: str = ""
    delivery_ratio: Decimal = _ZERO
    pending_requests_count: int = 0
    suppressed_requests_count: int = 0


@dataclass(frozen=True, slots=True)
class NotificationSnapshot:
    """A complete, immutable record of one notification update."""

    record: NotificationRecord
    metrics: NotificationMetrics
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class NotificationResult:
    """The immutable outcome of notifying one input."""

    status: NotificationResultStatus
    record: NotificationRecord | None = None
    snapshot: NotificationSnapshot | None = None
    batch: NotificationBatch | None = None
    requests: tuple[NotificationRequest, ...] = ()
    metrics: NotificationMetrics | None = None
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Return ``True`` when the input was notified successfully."""
        return self.status is NotificationResultStatus.SUCCESS
