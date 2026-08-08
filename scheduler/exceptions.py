"""Scheduler Framework exceptions.

Definitions only. Internal failures are translated into these so no
implementation detail escapes; the manager always returns a
:class:`~scheduler.models.SchedulerResult`.
"""

from __future__ import annotations

__all__ = [
    "SchedulerError",
    "CollectionError",
    "PlanningError",
    "DispatchError",
    "MetricsError",
    "RegistryError",
    "SchedulerCancelledError",
]


class SchedulerError(Exception):
    """Base class for all Scheduler Framework errors."""


class CollectionError(SchedulerError):
    """Raised when building a schedule batch fails."""


class PlanningError(SchedulerError):
    """Raised when planning schedule entries fails."""


class DispatchError(SchedulerError):
    """Raised when schedule request generation fails."""


class MetricsError(SchedulerError):
    """Raised when a metrics calculation fails."""


class RegistryError(SchedulerError):
    """Raised when a registry operation fails."""


class SchedulerCancelledError(SchedulerError):
    """Raised internally to unwind a scheduler session that was cancelled."""
