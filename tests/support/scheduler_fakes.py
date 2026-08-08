"""Helpers for Scheduler Framework tests.

Standalone support module (existing support files unchanged). Builds
deterministic scheduler contexts from normalized source readings. No network,
no sleeps, no randomness, and no model training.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from scheduler.context import SchedulerContext
from scheduler.models import SchedulerParameters, ScheduleSource

__all__ = [
    "make_source",
    "make_context",
]


def make_source(
    name: str,
    priority: str,
    *,
    source: str = "monitoring",
    category: str = "once",
    samples: int = 5,
) -> ScheduleSource:
    """Build a normalized source reading with a given priority."""
    return ScheduleSource(
        name=name,
        source=source,
        category=category,
        priority=Decimal(priority),
        samples=samples,
    )


def make_context(
    *,
    scheduler_id: str = "sched-1",
    storage: Sequence[ScheduleSource] | None = None,
    reporting: Sequence[ScheduleSource] | None = None,
    notification: Sequence[ScheduleSource] | None = None,
    monitoring: Sequence[ScheduleSource] | None = None,
    optimization: Sequence[ScheduleSource] | None = None,
    parameters: SchedulerParameters | None = None,
    cancel: bool = False,
) -> SchedulerContext:
    """Build a deterministic scheduler context."""
    metadata = {"cancel": True} if cancel else {}
    return SchedulerContext(
        scheduler_id=scheduler_id,
        storage_sources=tuple(storage) if storage is not None else (),
        reporting_sources=tuple(reporting) if reporting is not None else (),
        notification_sources=tuple(notification) if notification is not None else (),
        monitoring_sources=tuple(monitoring) if monitoring is not None
        else (make_source("cpu", "5"), make_source("mem", "-3")),
        optimization_sources=tuple(optimization) if optimization is not None else (),
        parameters=parameters or SchedulerParameters(),
        correlation_id="sched-corr",
        metadata=metadata,
    )
