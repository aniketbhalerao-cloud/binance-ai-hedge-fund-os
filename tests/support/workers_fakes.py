"""Helpers for Background Workers Framework tests.

Standalone support module (existing support files unchanged). Builds
deterministic worker contexts from normalized source readings. No network,
no sleeps, no randomness, and no model training.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from workers.context import WorkerContext
from workers.models import JobSource, WorkerParameters

__all__ = [
    "make_source",
    "make_context",
]


def make_source(
    name: str,
    priority: str,
    *,
    source: str = "monitoring",
    category: str = "immediate",
    samples: int = 5,
) -> JobSource:
    """Build a normalized source reading with a given priority."""
    return JobSource(
        name=name,
        source=source,
        category=category,
        priority=Decimal(priority),
        samples=samples,
    )


def make_context(
    *,
    worker_id: str = "workers-1",
    storage: Sequence[JobSource] | None = None,
    reporting: Sequence[JobSource] | None = None,
    notification: Sequence[JobSource] | None = None,
    monitoring: Sequence[JobSource] | None = None,
    scheduler: Sequence[JobSource] | None = None,
    parameters: WorkerParameters | None = None,
    cancel: bool = False,
) -> WorkerContext:
    """Build a deterministic worker context."""
    metadata = {"cancel": True} if cancel else {}
    return WorkerContext(
        worker_id=worker_id,
        storage_sources=tuple(storage) if storage is not None else (),
        reporting_sources=tuple(reporting) if reporting is not None else (),
        notification_sources=tuple(notification) if notification is not None else (),
        monitoring_sources=tuple(monitoring) if monitoring is not None
        else (make_source("cpu", "5"), make_source("mem", "-3")),
        scheduler_sources=tuple(scheduler) if scheduler is not None else (),
        parameters=parameters or WorkerParameters(),
        correlation_id="workers-corr",
        metadata=metadata,
    )
