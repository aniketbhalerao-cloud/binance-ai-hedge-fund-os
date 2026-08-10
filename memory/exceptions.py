"""Memory Framework exceptions.

Definitions only. Internal failures are translated into these so no
implementation detail escapes; the manager always returns a
:class:`~memory.models.MemoryResult`.
"""

from __future__ import annotations

__all__ = [
    "MemoryError",
    "CollectionError",
    "PlanningError",
    "DispatchError",
    "MetricsError",
    "RegistryError",
    "MemoryCancelledError",
]


class MemoryError(Exception):
    """Base class for all Memory Framework errors."""


class CollectionError(MemoryError):
    """Raised when building a memory batch fails."""


class PlanningError(MemoryError):
    """Raised when planning memory entries fails."""


class DispatchError(MemoryError):
    """Raised when memory request generation fails."""


class MetricsError(MemoryError):
    """Raised when a metrics calculation fails."""


class RegistryError(MemoryError):
    """Raised when a registry operation fails."""


class MemoryCancelledError(MemoryError):
    """Raised internally to unwind a memory session that was cancelled."""
