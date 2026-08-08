"""Scheduler Framework domain models.

Immutable, exchange-independent value objects. The rest of the application
consumes only these standardized models. Scores use :class:`~decimal.Decimal`;
timestamps are timezone-aware UTC. Every model is frozen — batches, schedule
requests, and the running record are never mutated; each scheduled input
produces a **new** record.

The framework only *plans and dispatches domain objects*: ``ScheduleRequest``
carries cadence detail as an immutable domain object and is never executed,
run, or triggered anywhere, and the framework never modifies a strategy,
agent, or portfolio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from scheduler.state import SchedulerState

__all__ = [
    "SchedulerResultStatus",
    "SUPPORTED_SCHEDULE_CADENCES",
    "SchedulerParameters",
    "ScheduleSource",
    "ScheduleEntry",
    "ScheduleBatch",
    "ScheduleRequest",
    "SchedulerHistory",
    "SchedulerRecord",
    "SchedulerMetrics",
    "SchedulerSnapshot",
    "SchedulerResult",
]

_ZERO = Decimal("0")

#: The schedule cadences the framework recognizes and can route (domain only).
SUPPORTED_SCHEDULE_CADENCES: frozenset[str] = frozenset(
    {"once", "interval", "cron", "daily", "weekly", "monthly"}
)


class SchedulerResultStatus(str, Enum):
    """Coarse outcome of scheduling one input."""

    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class SchedulerParameters:
    """Deterministic scheduler configuration.

    Attributes:
        priority_threshold: Priority at or above which an entry is dispatched.
        max_items: Maximum number of entries to plan per input.
    """

    priority_threshold: Decimal = _ZERO
    max_items: int = 5


@dataclass(frozen=True, slots=True)
class ScheduleSource:
    """A normalized schedule datum feeding one entry."""

    name: str
    source: str
    category: str = "unknown"
    priority: Decimal = _ZERO
    samples: int = 0


@dataclass(frozen=True, slots=True)
class ScheduleEntry:
    """A planned entry within a batch (an immutable domain object, never run)."""

    source: ScheduleSource
    dispatch: bool = True
    cadence: str = "once"
    detail: str = ""


@dataclass(frozen=True, slots=True)
class ScheduleBatch:
    """An immutable batch: the collected sources and their planned entries."""

    sources: tuple[ScheduleSource, ...] = ()
    entries: tuple[ScheduleEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class ScheduleRequest:
    """A deterministic schedule request (an immutable object, never executed)."""

    subject: str
    source: str
    cadence: str
    category: str = "unknown"
    priority: Decimal = _ZERO
    detail: str = ""


@dataclass(frozen=True, slots=True)
class SchedulerHistory:
    """Append-only record of produced batches."""

    batches: tuple[ScheduleBatch, ...] = ()

    def append(self, batch: ScheduleBatch) -> SchedulerHistory:
        """Return a new history with ``batch`` appended (never mutates)."""
        return SchedulerHistory(self.batches + (batch,))


@dataclass(frozen=True, slots=True)
class SchedulerRecord:
    """The durable, immutable running state of one scheduler session.

    The Registry owns the current ``SchedulerRecord``; the Manager loads it,
    processes one input, and writes back a **new** ``SchedulerRecord``.
    """

    id: str
    state: SchedulerState
    history: SchedulerHistory = field(default_factory=SchedulerHistory)
    batch: ScheduleBatch = field(default_factory=ScheduleBatch)
    requests: tuple[ScheduleRequest, ...] = ()
    entry_count: int = 0
    request_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SchedulerMetrics:
    """Derived metrics over a scheduler record."""

    total_entries: int = 0
    total_requests: int = 0
    average_schedule_score: Decimal = _ZERO
    highest_priority_entry: str = ""
    lowest_priority_entry: str = ""
    dispatch_ratio: Decimal = _ZERO
    pending_requests_count: int = 0
    suppressed_requests_count: int = 0


@dataclass(frozen=True, slots=True)
class SchedulerSnapshot:
    """A complete, immutable record of one scheduler update."""

    record: SchedulerRecord
    metrics: SchedulerMetrics
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class SchedulerResult:
    """The immutable outcome of scheduling one input."""

    status: SchedulerResultStatus
    record: SchedulerRecord | None = None
    snapshot: SchedulerSnapshot | None = None
    batch: ScheduleBatch | None = None
    requests: tuple[ScheduleRequest, ...] = ()
    metrics: SchedulerMetrics | None = None
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Return ``True`` when the input was scheduled successfully."""
        return self.status is SchedulerResultStatus.SUCCESS
