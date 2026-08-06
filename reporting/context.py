"""Reporting context.

An immutable input carrying standardized outputs from across the running system
— dashboard, notification, monitoring, performance analytics, and learning
readings — plus the reporting parameters. Reporting components never access
infrastructure directly; they read only from this context and the models it
carries, and they never modify any subject. Upstream frameworks are responsible
for normalizing their outputs into :class:`~reporting.models.ReportingSource`
readings; this framework only builds and exports immutable report objects from
them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from reporting.models import ReportingParameters, ReportingSource

__all__ = ["ReportingContext"]


@dataclass(frozen=True, slots=True)
class ReportingContext:
    """Immutable input for producing report objects.

    Attributes:
        reporting_id: Identifier of the reporting record to update.
        dashboard_sources: Dashboard reporting readings to build from.
        notification_sources: Notification reporting readings to build from.
        monitoring_sources: Monitoring reporting readings to build from.
        performance_sources: Performance analytics reporting readings to build from.
        learning_sources: Learning reporting readings to build from.
        parameters: Deterministic reporting parameters.
        correlation_id: Optional correlation id propagated to events.
        timestamp: When the context was assembled (UTC).
        metadata: Optional read-only extra context.
    """

    reporting_id: str = "reporting"
    dashboard_sources: tuple[ReportingSource, ...] = ()
    notification_sources: tuple[ReportingSource, ...] = ()
    monitoring_sources: tuple[ReportingSource, ...] = ()
    performance_sources: tuple[ReportingSource, ...] = ()
    learning_sources: tuple[ReportingSource, ...] = ()
    parameters: ReportingParameters = field(default_factory=ReportingParameters)
    correlation_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "dashboard_sources", tuple(self.dashboard_sources))
        object.__setattr__(
            self, "notification_sources", tuple(self.notification_sources)
        )
        object.__setattr__(self, "monitoring_sources", tuple(self.monitoring_sources))
        object.__setattr__(
            self, "performance_sources", tuple(self.performance_sources)
        )
        object.__setattr__(self, "learning_sources", tuple(self.learning_sources))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
