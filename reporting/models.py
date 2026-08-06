"""Reporting Framework domain models.

Immutable, exchange-independent value objects. The rest of the application
consumes only these standardized models. Scores use :class:`~decimal.Decimal`;
timestamps are timezone-aware UTC. Every model is frozen — batches, export
requests, and the running record are never mutated; each reported input produces
a **new** record.

The framework only *builds and exports domain objects*: ``ExportRequest``
carries export detail as an immutable domain object and is never saved, written
to a file, or sent anywhere, and the framework never modifies a strategy, agent,
or portfolio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from reporting.state import ReportingState

__all__ = [
    "ReportingResultStatus",
    "SUPPORTED_REPORT_TYPES",
    "ReportingParameters",
    "ReportingSource",
    "Report",
    "ReportingBatch",
    "ExportRequest",
    "ReportingHistory",
    "ReportingRecord",
    "ReportingMetrics",
    "ReportingSnapshot",
    "ReportingResult",
]

_ZERO = Decimal("0")

#: The report types the framework recognizes and can route.
SUPPORTED_REPORT_TYPES: frozenset[str] = frozenset(
    {"daily", "weekly", "monthly", "performance", "portfolio", "risk"}
)


class ReportingResultStatus(str, Enum):
    """Coarse outcome of reporting one input."""

    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class ReportingParameters:
    """Deterministic reporting configuration.

    Attributes:
        priority_threshold: Priority at or above which a report is built.
        max_reports: Maximum number of reports to build per input.
    """

    priority_threshold: Decimal = _ZERO
    max_reports: int = 5


@dataclass(frozen=True, slots=True)
class ReportingSource:
    """A normalized reporting datum feeding one report."""

    name: str
    source: str
    category: str = "unknown"
    priority: Decimal = _ZERO
    samples: int = 0


@dataclass(frozen=True, slots=True)
class Report:
    """A built report within a batch (an immutable domain object, never saved)."""

    source: ReportingSource
    include: bool = True
    report_type: str = "daily"
    detail: str = ""


@dataclass(frozen=True, slots=True)
class ReportingBatch:
    """An immutable batch: the collected sources and their built reports."""

    sources: tuple[ReportingSource, ...] = ()
    reports: tuple[Report, ...] = ()


@dataclass(frozen=True, slots=True)
class ExportRequest:
    """A deterministic export request (an immutable object, never written or sent)."""

    subject: str
    source: str
    report_type: str
    category: str = "unknown"
    priority: Decimal = _ZERO
    detail: str = ""


@dataclass(frozen=True, slots=True)
class ReportingHistory:
    """Append-only record of produced batches."""

    batches: tuple[ReportingBatch, ...] = ()

    def append(self, batch: ReportingBatch) -> ReportingHistory:
        """Return a new history with ``batch`` appended (never mutates)."""
        return ReportingHistory(self.batches + (batch,))


@dataclass(frozen=True, slots=True)
class ReportingRecord:
    """The durable, immutable running state of one reporting session.

    The Registry owns the current ``ReportingRecord``; the Manager loads it,
    processes one input, and writes back a **new** ``ReportingRecord``.
    """

    id: str
    state: ReportingState
    history: ReportingHistory = field(default_factory=ReportingHistory)
    batch: ReportingBatch = field(default_factory=ReportingBatch)
    exports: tuple[ExportRequest, ...] = ()
    report_count: int = 0
    export_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ReportingMetrics:
    """Derived metrics over a reporting record."""

    total_reports: int = 0
    total_exports: int = 0
    average_report_score: Decimal = _ZERO
    highest_priority_report: str = ""
    lowest_priority_report: str = ""
    export_ratio: Decimal = _ZERO
    pending_reports_count: int = 0
    suppressed_reports_count: int = 0


@dataclass(frozen=True, slots=True)
class ReportingSnapshot:
    """A complete, immutable record of one reporting update."""

    record: ReportingRecord
    metrics: ReportingMetrics
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class ReportingResult:
    """The immutable outcome of reporting one input."""

    status: ReportingResultStatus
    record: ReportingRecord | None = None
    snapshot: ReportingSnapshot | None = None
    batch: ReportingBatch | None = None
    exports: tuple[ExportRequest, ...] = ()
    metrics: ReportingMetrics | None = None
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Return ``True`` when the input was reported successfully."""
        return self.status is ReportingResultStatus.SUCCESS
