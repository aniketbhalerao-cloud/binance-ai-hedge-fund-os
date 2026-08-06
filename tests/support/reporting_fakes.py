"""Helpers for Reporting Framework tests.

Standalone support module (existing support files unchanged). Builds
deterministic reporting contexts from normalized source readings. No network,
no sleeps, no randomness, and no model training.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from reporting.context import ReportingContext
from reporting.models import ReportingParameters, ReportingSource

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
) -> ReportingSource:
    """Build a normalized source reading with a given priority."""
    return ReportingSource(
        name=name,
        source=source,
        category=category,
        priority=Decimal(priority),
        samples=samples,
    )


def make_context(
    *,
    reporting_id: str = "report-1",
    dashboard: Sequence[ReportingSource] | None = None,
    notification: Sequence[ReportingSource] | None = None,
    monitoring: Sequence[ReportingSource] | None = None,
    performance: Sequence[ReportingSource] | None = None,
    learning: Sequence[ReportingSource] | None = None,
    parameters: ReportingParameters | None = None,
    cancel: bool = False,
) -> ReportingContext:
    """Build a deterministic reporting context."""
    metadata = {"cancel": True} if cancel else {}
    return ReportingContext(
        reporting_id=reporting_id,
        dashboard_sources=tuple(dashboard) if dashboard is not None else (),
        notification_sources=tuple(notification) if notification is not None else (),
        monitoring_sources=tuple(monitoring) if monitoring is not None
        else (make_source("cpu", "5"), make_source("mem", "-3")),
        performance_sources=tuple(performance) if performance is not None else (),
        learning_sources=tuple(learning) if learning is not None else (),
        parameters=parameters or ReportingParameters(),
        correlation_id="report-corr",
        metadata=metadata,
    )
