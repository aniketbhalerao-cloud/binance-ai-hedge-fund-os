"""Worker context.

An immutable input carrying standardized outputs from across the running
system — storage requests, report objects, notification requests, monitoring
reports, and schedule requests — plus the worker parameters. Worker
components never access infrastructure directly; they read only from this
context and the models it carries, and they never modify any subject.
Upstream frameworks are responsible for normalizing their outputs into
:class:`~workers.models.JobSource` readings; this framework only plans and
dispatches immutable worker requests from them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from workers.models import JobSource, WorkerParameters

__all__ = ["WorkerContext"]


@dataclass(frozen=True, slots=True)
class WorkerContext:
    """Immutable input for producing worker requests.

    Attributes:
        worker_id: Identifier of the worker record to update.
        storage_sources: Storage job readings to plan.
        reporting_sources: Reporting job readings to plan.
        notification_sources: Notification job readings to plan.
        monitoring_sources: Monitoring job readings to plan.
        scheduler_sources: Scheduler job readings to plan.
        parameters: Deterministic worker parameters.
        correlation_id: Optional correlation id propagated to events.
        timestamp: When the context was assembled (UTC).
        metadata: Optional read-only extra context.
    """

    worker_id: str = "workers"
    storage_sources: tuple[JobSource, ...] = ()
    reporting_sources: tuple[JobSource, ...] = ()
    notification_sources: tuple[JobSource, ...] = ()
    monitoring_sources: tuple[JobSource, ...] = ()
    scheduler_sources: tuple[JobSource, ...] = ()
    parameters: WorkerParameters = field(default_factory=WorkerParameters)
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
        object.__setattr__(self, "scheduler_sources", tuple(self.scheduler_sources))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
