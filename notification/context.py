"""Notification context.

An immutable input carrying standardized outputs from across the running system —
monitoring, dashboard, optimization, and learning readings — plus the notification
parameters. Notification components never access infrastructure directly; they read
only from this context and the models it carries, and they never modify any
subject. Upstream frameworks are responsible for normalizing their outputs into
:class:`~notification.models.NotificationSource` readings; this framework only
requests delivery of them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from notification.models import NotificationParameters, NotificationSource

__all__ = ["NotificationContext"]


@dataclass(frozen=True, slots=True)
class NotificationContext:
    """Immutable input for producing notification requests.

    Attributes:
        notification_id: Identifier of the notification record to update.
        monitoring_sources: Monitoring notification readings to request.
        dashboard_sources: Dashboard notification readings to request.
        optimization_sources: Optimization notification readings to request.
        learning_sources: Learning notification readings to request.
        parameters: Deterministic notification parameters.
        correlation_id: Optional correlation id propagated to events.
        timestamp: When the context was assembled (UTC).
        metadata: Optional read-only extra context.
    """

    notification_id: str = "notification"
    monitoring_sources: tuple[NotificationSource, ...] = ()
    dashboard_sources: tuple[NotificationSource, ...] = ()
    optimization_sources: tuple[NotificationSource, ...] = ()
    learning_sources: tuple[NotificationSource, ...] = ()
    parameters: NotificationParameters = field(
        default_factory=NotificationParameters
    )
    correlation_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "monitoring_sources", tuple(self.monitoring_sources))
        object.__setattr__(self, "dashboard_sources", tuple(self.dashboard_sources))
        object.__setattr__(
            self, "optimization_sources", tuple(self.optimization_sources)
        )
        object.__setattr__(self, "learning_sources", tuple(self.learning_sources))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
