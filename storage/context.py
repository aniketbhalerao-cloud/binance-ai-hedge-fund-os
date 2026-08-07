"""Storage context.

An immutable input carrying standardized outputs from across the running system
— reporting, notification, dashboard, monitoring, and performance analytics
readings — plus the storage parameters. Storage components never access
infrastructure directly; they read only from this context and the models it
carries, and they never modify any subject. Upstream frameworks are responsible
for normalizing their outputs into :class:`~storage.models.StorageSource`
readings; this framework only serializes and plans immutable storage requests
from them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from storage.models import StorageParameters, StorageSource

__all__ = ["StorageContext"]


@dataclass(frozen=True, slots=True)
class StorageContext:
    """Immutable input for producing storage requests.

    Attributes:
        storage_id: Identifier of the storage record to update.
        reporting_sources: Reporting storage readings to serialize.
        notification_sources: Notification storage readings to serialize.
        dashboard_sources: Dashboard storage readings to serialize.
        monitoring_sources: Monitoring storage readings to serialize.
        performance_sources: Performance analytics storage readings to serialize.
        parameters: Deterministic storage parameters.
        correlation_id: Optional correlation id propagated to events.
        timestamp: When the context was assembled (UTC).
        metadata: Optional read-only extra context.
    """

    storage_id: str = "storage"
    reporting_sources: tuple[StorageSource, ...] = ()
    notification_sources: tuple[StorageSource, ...] = ()
    dashboard_sources: tuple[StorageSource, ...] = ()
    monitoring_sources: tuple[StorageSource, ...] = ()
    performance_sources: tuple[StorageSource, ...] = ()
    parameters: StorageParameters = field(default_factory=StorageParameters)
    correlation_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "reporting_sources", tuple(self.reporting_sources))
        object.__setattr__(
            self, "notification_sources", tuple(self.notification_sources)
        )
        object.__setattr__(self, "dashboard_sources", tuple(self.dashboard_sources))
        object.__setattr__(self, "monitoring_sources", tuple(self.monitoring_sources))
        object.__setattr__(
            self, "performance_sources", tuple(self.performance_sources)
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
