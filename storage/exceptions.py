"""Storage Framework exceptions.

Definitions only. Internal failures are translated into these so no
implementation detail escapes; the manager always returns a
:class:`~storage.models.StorageResult`.
"""

from __future__ import annotations

__all__ = [
    "StorageError",
    "CollectionError",
    "SerializationError",
    "PersistenceError",
    "MetricsError",
    "RegistryError",
    "StorageCancelledError",
]


class StorageError(Exception):
    """Base class for all Storage Framework errors."""


class CollectionError(StorageError):
    """Raised when building a storage batch fails."""


class SerializationError(StorageError):
    """Raised when serializing storage items fails."""


class PersistenceError(StorageError):
    """Raised when storage request generation fails."""


class MetricsError(StorageError):
    """Raised when a metrics calculation fails."""


class RegistryError(StorageError):
    """Raised when a registry operation fails."""


class StorageCancelledError(StorageError):
    """Raised internally to unwind a storage session that was cancelled."""
