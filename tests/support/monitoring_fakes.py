"""Helpers for Monitoring Framework tests.

Standalone support module (existing support files unchanged). Builds deterministic
monitoring contexts from normalized component readings. No network, no sleeps, no
randomness, and no model training.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from monitoring.context import MonitoringContext
from monitoring.models import MonitoredComponent, MonitoringParameters

__all__ = [
    "make_component",
    "make_context",
]


def make_component(
    name: str,
    score: str,
    *,
    source: str = "strategy",
    status: str = "up",
    samples: int = 5,
) -> MonitoredComponent:
    """Build a normalized component reading with a given score."""
    return MonitoredComponent(
        name=name, source=source, status=status, score=Decimal(score), samples=samples
    )


def make_context(
    *,
    monitoring_id: str = "mon-1",
    strategy: Sequence[MonitoredComponent] | None = None,
    agents: Sequence[MonitoredComponent] | None = None,
    performance: Sequence[MonitoredComponent] | None = None,
    optimization: Sequence[MonitoredComponent] | None = None,
    parameters: MonitoringParameters | None = None,
    cancel: bool = False,
) -> MonitoringContext:
    """Build a deterministic monitoring context."""
    metadata = {"cancel": True} if cancel else {}
    return MonitoringContext(
        monitoring_id=monitoring_id,
        strategy_signals=tuple(strategy) if strategy is not None
        else (make_component("ema", "5"), make_component("rsi", "-3")),
        agent_signals=tuple(agents) if agents is not None else (),
        performance_metrics=tuple(performance) if performance is not None else (),
        optimization_signals=tuple(optimization) if optimization is not None else (),
        parameters=parameters or MonitoringParameters(),
        correlation_id="mon-corr",
        metadata=metadata,
    )
