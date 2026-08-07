"""Helpers for Storage Framework tests.

Standalone support module (existing support files unchanged). Builds
deterministic storage contexts from normalized source readings. No network,
no sleeps, no randomness, and no model training.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from storage.context import StorageContext
from storage.models import StorageParameters, StorageSource

__all__ = [
    "make_source",
    "make_context",
]


def make_source(
    name: str,
    priority: str,
    *,
    source: str = "monitoring",
    category: str = "info",
    samples: int = 5,
) -> StorageSource:
    """Build a normalized source reading with a given priority."""
    return StorageSource(
        name=name,
        source=source,
        category=category,
        priority=Decimal(priority),
        samples=samples,
    )


def make_context(
    *,
    storage_id: str = "store-1",
    reporting: Sequence[StorageSource] | None = None,
    notification: Sequence[StorageSource] | None = None,
    dashboard: Sequence[StorageSource] | None = None,
    monitoring: Sequence[StorageSource] | None = None,
    performance: Sequence[StorageSource] | None = None,
    parameters: StorageParameters | None = None,
    cancel: bool = False,
) -> StorageContext:
    """Build a deterministic storage context."""
    metadata = {"cancel": True} if cancel else {}
    return StorageContext(
        storage_id=storage_id,
        reporting_sources=tuple(reporting) if reporting is not None else (),
        notification_sources=tuple(notification) if notification is not None else (),
        dashboard_sources=tuple(dashboard) if dashboard is not None else (),
        monitoring_sources=tuple(monitoring) if monitoring is not None
        else (make_source("cpu", "5"), make_source("mem", "-3")),
        performance_sources=tuple(performance) if performance is not None else (),
        parameters=parameters or StorageParameters(),
        correlation_id="store-corr",
        metadata=metadata,
    )
