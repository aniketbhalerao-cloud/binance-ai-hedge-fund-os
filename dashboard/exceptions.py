"""Dashboard Framework exceptions.

Definitions only. Internal failures are translated into these so no
implementation detail escapes; the manager always returns a
:class:`~dashboard.models.DashboardResult`.
"""

from __future__ import annotations

__all__ = [
    "DashboardError",
    "AggregationError",
    "CompositionError",
    "WidgetError",
    "MetricsError",
    "RegistryError",
    "DashboardCancelledError",
]


class DashboardError(Exception):
    """Base class for all Dashboard Framework errors."""


class AggregationError(DashboardError):
    """Raised when building a dashboard view fails."""


class CompositionError(DashboardError):
    """Raised when composing a dashboard view fails."""


class WidgetError(DashboardError):
    """Raised when widget generation fails."""


class MetricsError(DashboardError):
    """Raised when a metrics calculation fails."""


class RegistryError(DashboardError):
    """Raised when a registry operation fails."""


class DashboardCancelledError(DashboardError):
    """Raised internally to unwind a dashboard session that was cancelled."""
