"""Monitoring context.

An immutable input carrying standardized health signals from across the running
system — strategy, agent, performance, and optimization readings — plus the
monitoring parameters. Monitoring components never access infrastructure directly;
they read only from this context and the models it carries, and they never modify
any subject. Upstream frameworks are responsible for normalizing their outputs into
:class:`~monitoring.models.MonitoredComponent` readings; this framework only
observes them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from monitoring.models import MonitoredComponent, MonitoringParameters

__all__ = ["MonitoringContext"]


@dataclass(frozen=True, slots=True)
class MonitoringContext:
    """Immutable input for observing system health.

    Attributes:
        monitoring_id: Identifier of the monitoring record to update.
        strategy_signals: Strategy component readings to observe.
        agent_signals: Agent (decision) component readings to observe.
        performance_metrics: Performance component readings to observe.
        optimization_signals: Optimization component readings to observe.
        parameters: Deterministic monitoring parameters.
        correlation_id: Optional correlation id propagated to events.
        timestamp: When the context was assembled (UTC).
        metadata: Optional read-only extra context.
    """

    monitoring_id: str = "monitoring"
    strategy_signals: tuple[MonitoredComponent, ...] = ()
    agent_signals: tuple[MonitoredComponent, ...] = ()
    performance_metrics: tuple[MonitoredComponent, ...] = ()
    optimization_signals: tuple[MonitoredComponent, ...] = ()
    parameters: MonitoringParameters = field(default_factory=MonitoringParameters)
    correlation_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "strategy_signals", tuple(self.strategy_signals))
        object.__setattr__(self, "agent_signals", tuple(self.agent_signals))
        object.__setattr__(self, "performance_metrics", tuple(self.performance_metrics))
        object.__setattr__(
            self, "optimization_signals", tuple(self.optimization_signals)
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
