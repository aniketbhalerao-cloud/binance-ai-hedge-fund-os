"""Dashboard context.

An immutable input carrying standardized outputs from across the running system —
strategy, performance, optimization, and monitoring readings — plus the dashboard
parameters. Dashboard components never access infrastructure directly; they read
only from this context and the models it carries, and they never modify any
subject. Upstream frameworks are responsible for normalizing their outputs into
:class:`~dashboard.models.DashboardSource` readings; this framework only presents
them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from dashboard.models import DashboardParameters, DashboardSource

__all__ = ["DashboardContext"]


@dataclass(frozen=True, slots=True)
class DashboardContext:
    """Immutable input for rendering a dashboard.

    Attributes:
        dashboard_id: Identifier of the dashboard record to update.
        strategy_sources: Strategy display readings to render.
        performance_sources: Performance display readings to render.
        optimization_sources: Optimization display readings to render.
        monitoring_sources: Monitoring display readings to render.
        parameters: Deterministic dashboard parameters.
        correlation_id: Optional correlation id propagated to events.
        timestamp: When the context was assembled (UTC).
        metadata: Optional read-only extra context.
    """

    dashboard_id: str = "dashboard"
    strategy_sources: tuple[DashboardSource, ...] = ()
    performance_sources: tuple[DashboardSource, ...] = ()
    optimization_sources: tuple[DashboardSource, ...] = ()
    monitoring_sources: tuple[DashboardSource, ...] = ()
    parameters: DashboardParameters = field(default_factory=DashboardParameters)
    correlation_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "strategy_sources", tuple(self.strategy_sources))
        object.__setattr__(
            self, "performance_sources", tuple(self.performance_sources)
        )
        object.__setattr__(
            self, "optimization_sources", tuple(self.optimization_sources)
        )
        object.__setattr__(self, "monitoring_sources", tuple(self.monitoring_sources))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
