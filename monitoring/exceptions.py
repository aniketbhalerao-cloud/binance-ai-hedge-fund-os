"""Monitoring Framework exceptions.

Definitions only. Internal failures are translated into these so no
implementation detail escapes; the manager always returns a
:class:`~monitoring.models.MonitoringResult`.
"""

from __future__ import annotations

__all__ = [
    "MonitoringError",
    "CollectionError",
    "EvaluationError",
    "AlertError",
    "MetricsError",
    "RegistryError",
    "MonitoringCancelledError",
]


class MonitoringError(Exception):
    """Base class for all Monitoring Framework errors."""


class CollectionError(MonitoringError):
    """Raised when building a health report fails."""


class EvaluationError(MonitoringError):
    """Raised when evaluating a health report fails."""


class AlertError(MonitoringError):
    """Raised when alert generation fails."""


class MetricsError(MonitoringError):
    """Raised when a metrics calculation fails."""


class RegistryError(MonitoringError):
    """Raised when a registry operation fails."""


class MonitoringCancelledError(MonitoringError):
    """Raised internally to unwind a monitoring session that was cancelled."""
