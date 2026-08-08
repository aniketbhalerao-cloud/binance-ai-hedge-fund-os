"""Scheduler context.

An immutable input carrying standardized outputs from across the running
system — storage requests, report objects, notification requests, monitoring
reports, and optimization plans — plus the scheduler parameters. Scheduler
components never access infrastructure directly; they read only from this
context and the models it carries, and they never modify any subject.
Upstream frameworks are responsible for normalizing their outputs into
:class:`~scheduler.models.ScheduleSource` readings; this framework only plans
and dispatches immutable schedule requests from them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from scheduler.models import SchedulerParameters, ScheduleSource

__all__ = ["SchedulerContext"]


@dataclass(frozen=True, slots=True)
class SchedulerContext:
    """Immutable input for producing schedule requests.

    Attributes:
        scheduler_id: Identifier of the scheduler record to update.
        storage_sources: Storage schedule readings to plan.
        reporting_sources: Reporting schedule readings to plan.
        notification_sources: Notification schedule readings to plan.
        monitoring_sources: Monitoring schedule readings to plan.
        optimization_sources: Optimization schedule readings to plan.
        parameters: Deterministic scheduler parameters.
        correlation_id: Optional correlation id propagated to events.
        timestamp: When the context was assembled (UTC).
        metadata: Optional read-only extra context.
    """

    scheduler_id: str = "scheduler"
    storage_sources: tuple[ScheduleSource, ...] = ()
    reporting_sources: tuple[ScheduleSource, ...] = ()
    notification_sources: tuple[ScheduleSource, ...] = ()
    monitoring_sources: tuple[ScheduleSource, ...] = ()
    optimization_sources: tuple[ScheduleSource, ...] = ()
    parameters: SchedulerParameters = field(default_factory=SchedulerParameters)
    correlation_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "storage_sources", tuple(self.storage_sources))
        object.__setattr__(self, "reporting_sources", tuple(self.reporting_sources))
        object.__setattr__(
            self, "notification_sources", tuple(self.notification_sources)
        )
        object.__setattr__(self, "monitoring_sources", tuple(self.monitoring_sources))
        object.__setattr__(
            self, "optimization_sources", tuple(self.optimization_sources)
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
