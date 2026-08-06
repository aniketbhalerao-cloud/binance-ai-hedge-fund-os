"""Helpers for Notification Framework tests.

Standalone support module (existing support files unchanged). Builds deterministic
notification contexts from normalized source readings. No network, no sleeps, no
randomness, and no model training.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from notification.context import NotificationContext
from notification.models import NotificationParameters, NotificationSource

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
) -> NotificationSource:
    """Build a normalized source reading with a given priority."""
    return NotificationSource(
        name=name,
        source=source,
        category=category,
        priority=Decimal(priority),
        samples=samples,
    )


def make_context(
    *,
    notification_id: str = "notif-1",
    monitoring: Sequence[NotificationSource] | None = None,
    dashboard: Sequence[NotificationSource] | None = None,
    optimization: Sequence[NotificationSource] | None = None,
    learning: Sequence[NotificationSource] | None = None,
    parameters: NotificationParameters | None = None,
    cancel: bool = False,
) -> NotificationContext:
    """Build a deterministic notification context."""
    metadata = {"cancel": True} if cancel else {}
    return NotificationContext(
        notification_id=notification_id,
        monitoring_sources=tuple(monitoring) if monitoring is not None
        else (make_source("cpu", "5"), make_source("mem", "-3")),
        dashboard_sources=tuple(dashboard) if dashboard is not None else (),
        optimization_sources=tuple(optimization) if optimization is not None else (),
        learning_sources=tuple(learning) if learning is not None else (),
        parameters=parameters or NotificationParameters(),
        correlation_id="notif-corr",
        metadata=metadata,
    )
