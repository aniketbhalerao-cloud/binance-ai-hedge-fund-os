"""Helpers for Dashboard Framework tests.

Standalone support module (existing support files unchanged). Builds deterministic
dashboard contexts from normalized source readings. No network, no sleeps, no
randomness, and no model training.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from dashboard.context import DashboardContext
from dashboard.models import DashboardParameters, DashboardSource

__all__ = [
    "make_source",
    "make_context",
]


def make_source(
    name: str,
    score: str,
    *,
    source: str = "strategy",
    label: str = "ok",
    samples: int = 5,
) -> DashboardSource:
    """Build a normalized source reading with a given score."""
    return DashboardSource(
        name=name, source=source, label=label, score=Decimal(score), samples=samples
    )


def make_context(
    *,
    dashboard_id: str = "dash-1",
    strategy: Sequence[DashboardSource] | None = None,
    performance: Sequence[DashboardSource] | None = None,
    optimization: Sequence[DashboardSource] | None = None,
    monitoring: Sequence[DashboardSource] | None = None,
    parameters: DashboardParameters | None = None,
    cancel: bool = False,
) -> DashboardContext:
    """Build a deterministic dashboard context."""
    metadata = {"cancel": True} if cancel else {}
    return DashboardContext(
        dashboard_id=dashboard_id,
        strategy_sources=tuple(strategy) if strategy is not None
        else (make_source("ema", "5"), make_source("rsi", "-3")),
        performance_sources=tuple(performance) if performance is not None else (),
        optimization_sources=tuple(optimization) if optimization is not None else (),
        monitoring_sources=tuple(monitoring) if monitoring is not None else (),
        parameters=parameters or DashboardParameters(),
        correlation_id="dash-corr",
        metadata=metadata,
    )
