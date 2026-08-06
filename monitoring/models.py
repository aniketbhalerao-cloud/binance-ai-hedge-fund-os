"""Monitoring Framework domain models.

Immutable, exchange-independent value objects. The rest of the application
consumes only these standardized models. Scores use :class:`~decimal.Decimal`;
timestamps are timezone-aware UTC. Every model is frozen — reports, alerts, and
the running record are never mutated; each observed input produces a **new**
record.

The framework only *observes*: alerts carry proposed severity and are never sent,
and the framework never modifies a strategy, agent, or portfolio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from monitoring.state import MonitoringState

__all__ = [
    "MonitoringResultStatus",
    "MonitoringParameters",
    "MonitoredComponent",
    "HealthCheck",
    "HealthReport",
    "Alert",
    "MonitoringHistory",
    "MonitoringRecord",
    "MonitoringMetrics",
    "MonitoringSnapshot",
    "MonitoringResult",
]

_ZERO = Decimal("0")


class MonitoringResultStatus(str, Enum):
    """Coarse outcome of observing one input."""

    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class MonitoringParameters:
    """Deterministic monitoring configuration.

    Attributes:
        health_threshold: Score at or above which a component is healthy.
        critical_threshold: Score below which a breach is critical (else warning).
        max_components: Maximum number of components to observe per input.
    """

    health_threshold: Decimal = _ZERO
    critical_threshold: Decimal = _ZERO
    max_components: int = 5


@dataclass(frozen=True, slots=True)
class MonitoredComponent:
    """A normalized health reading of one observed component."""

    name: str
    source: str
    status: str = "unknown"
    score: Decimal = _ZERO
    samples: int = 0


@dataclass(frozen=True, slots=True)
class HealthCheck:
    """The evaluated health of a single component (never acted upon)."""

    component: MonitoredComponent
    healthy: bool = True
    severity: str = "ok"
    detail: str = ""


@dataclass(frozen=True, slots=True)
class HealthReport:
    """An immutable report: the observed components and their health checks."""

    components: tuple[MonitoredComponent, ...] = ()
    checks: tuple[HealthCheck, ...] = ()


@dataclass(frozen=True, slots=True)
class Alert:
    """A deterministic alert (a proposed notification, never sent)."""

    subject: str
    source: str
    severity: str
    status: str = "unknown"
    score: Decimal = _ZERO
    detail: str = ""


@dataclass(frozen=True, slots=True)
class MonitoringHistory:
    """Append-only record of produced health reports."""

    reports: tuple[HealthReport, ...] = ()

    def append(self, report: HealthReport) -> MonitoringHistory:
        """Return a new history with ``report`` appended (never mutates)."""
        return MonitoringHistory(self.reports + (report,))


@dataclass(frozen=True, slots=True)
class MonitoringRecord:
    """The durable, immutable running state of one monitoring session.

    The Registry owns the current ``MonitoringRecord``; the Manager loads it,
    processes one input, and writes back a **new** ``MonitoringRecord``.
    """

    id: str
    state: MonitoringState
    history: MonitoringHistory = field(default_factory=MonitoringHistory)
    report: HealthReport = field(default_factory=HealthReport)
    alerts: tuple[Alert, ...] = ()
    check_count: int = 0
    alert_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class MonitoringMetrics:
    """Derived metrics over a monitoring record."""

    total_checks: int = 0
    total_alerts: int = 0
    average_health_score: Decimal = _ZERO
    best_component: str = ""
    worst_component: str = ""
    uptime_ratio: Decimal = _ZERO
    active_alerts_count: int = 0
    resolved_alerts_count: int = 0


@dataclass(frozen=True, slots=True)
class MonitoringSnapshot:
    """A complete, immutable record of one monitoring update."""

    record: MonitoringRecord
    metrics: MonitoringMetrics
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class MonitoringResult:
    """The immutable outcome of observing one input."""

    status: MonitoringResultStatus
    record: MonitoringRecord | None = None
    snapshot: MonitoringSnapshot | None = None
    report: HealthReport | None = None
    alerts: tuple[Alert, ...] = ()
    metrics: MonitoringMetrics | None = None
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Return ``True`` when the input was observed successfully."""
        return self.status is MonitoringResultStatus.SUCCESS
