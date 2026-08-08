"""Background Workers Framework domain models.

Immutable, exchange-independent value objects. The rest of the application
consumes only these standardized models. Scores use :class:`~decimal.Decimal`;
timestamps are timezone-aware UTC. Every model is frozen — batches, worker
requests, and the running record are never mutated; each enqueued input
produces a **new** record.

The framework only *plans and dispatches domain objects*: ``WorkerRequest``
carries queue detail as an immutable domain object and is never executed,
run, or triggered anywhere, and the framework never modifies a strategy,
agent, or portfolio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from workers.state import WorkerState

__all__ = [
    "WorkerResultStatus",
    "SUPPORTED_WORKER_QUEUES",
    "WorkerParameters",
    "JobSource",
    "JobEntry",
    "JobBatch",
    "WorkerRequest",
    "WorkerHistory",
    "WorkerRecord",
    "WorkerMetrics",
    "WorkerSnapshot",
    "WorkerResult",
]

_ZERO = Decimal("0")

#: The worker queues the framework recognizes and can route (domain only).
SUPPORTED_WORKER_QUEUES: frozenset[str] = frozenset(
    {"immediate", "delayed", "scheduled", "retry", "priority", "batch"}
)


class WorkerResultStatus(str, Enum):
    """Coarse outcome of enqueuing one input."""

    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class WorkerParameters:
    """Deterministic worker configuration.

    Attributes:
        priority_threshold: Priority at or above which a job is dispatched.
        max_items: Maximum number of jobs to plan per input.
    """

    priority_threshold: Decimal = _ZERO
    max_items: int = 5


@dataclass(frozen=True, slots=True)
class JobSource:
    """A normalized job datum feeding one entry."""

    name: str
    source: str
    category: str = "unknown"
    priority: Decimal = _ZERO
    samples: int = 0


@dataclass(frozen=True, slots=True)
class JobEntry:
    """A planned entry within a batch (an immutable domain object, never run)."""

    source: JobSource
    dispatch: bool = True
    queue: str = "immediate"
    detail: str = ""


@dataclass(frozen=True, slots=True)
class JobBatch:
    """An immutable batch: the collected sources and their planned entries."""

    sources: tuple[JobSource, ...] = ()
    entries: tuple[JobEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkerRequest:
    """A deterministic worker request (an immutable object, never executed)."""

    subject: str
    source: str
    queue: str
    category: str = "unknown"
    priority: Decimal = _ZERO
    detail: str = ""


@dataclass(frozen=True, slots=True)
class WorkerHistory:
    """Append-only record of produced batches."""

    batches: tuple[JobBatch, ...] = ()

    def append(self, batch: JobBatch) -> WorkerHistory:
        """Return a new history with ``batch`` appended (never mutates)."""
        return WorkerHistory(self.batches + (batch,))


@dataclass(frozen=True, slots=True)
class WorkerRecord:
    """The durable, immutable running state of one worker session.

    The Registry owns the current ``WorkerRecord``; the Manager loads it,
    processes one input, and writes back a **new** ``WorkerRecord``.
    """

    id: str
    state: WorkerState
    history: WorkerHistory = field(default_factory=WorkerHistory)
    batch: JobBatch = field(default_factory=JobBatch)
    requests: tuple[WorkerRequest, ...] = ()
    job_count: int = 0
    request_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkerMetrics:
    """Derived metrics over a worker record."""

    total_jobs: int = 0
    total_requests: int = 0
    average_job_score: Decimal = _ZERO
    highest_priority_job: str = ""
    lowest_priority_job: str = ""
    dispatch_ratio: Decimal = _ZERO
    pending_requests_count: int = 0
    suppressed_requests_count: int = 0


@dataclass(frozen=True, slots=True)
class WorkerSnapshot:
    """A complete, immutable record of one worker update."""

    record: WorkerRecord
    metrics: WorkerMetrics
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class WorkerResult:
    """The immutable outcome of enqueuing one input."""

    status: WorkerResultStatus
    record: WorkerRecord | None = None
    snapshot: WorkerSnapshot | None = None
    batch: JobBatch | None = None
    requests: tuple[WorkerRequest, ...] = ()
    metrics: WorkerMetrics | None = None
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Return ``True`` when the input was enqueued successfully."""
        return self.status is WorkerResultStatus.SUCCESS
