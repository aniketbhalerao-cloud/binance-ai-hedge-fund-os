"""Background Workers Framework exceptions.

Definitions only. Internal failures are translated into these so no
implementation detail escapes; the manager always returns a
:class:`~workers.models.WorkerResult`.
"""

from __future__ import annotations

__all__ = [
    "WorkerError",
    "CollectionError",
    "PlanningError",
    "DispatchError",
    "MetricsError",
    "RegistryError",
    "WorkerCancelledError",
]


class WorkerError(Exception):
    """Base class for all Background Workers Framework errors."""


class CollectionError(WorkerError):
    """Raised when building a job batch fails."""


class PlanningError(WorkerError):
    """Raised when planning job entries fails."""


class DispatchError(WorkerError):
    """Raised when worker request generation fails."""


class MetricsError(WorkerError):
    """Raised when a metrics calculation fails."""


class RegistryError(WorkerError):
    """Raised when a registry operation fails."""


class WorkerCancelledError(WorkerError):
    """Raised internally to unwind a worker session that was cancelled."""
