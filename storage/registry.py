"""Storage registry.

:class:`InMemoryStorageRegistry` is a thread-safe store that **owns the running
storage records**, keyed by id. It never creates records (creation is the
manager's job) — it only registers (insert or replace), looks up, lists, and
clears them. Mutable state is guarded by a :class:`threading.Lock`.
"""

from __future__ import annotations

from threading import Lock

from storage.exceptions import RegistryError
from storage.models import StorageRecord

__all__ = ["InMemoryStorageRegistry"]


class InMemoryStorageRegistry:
    """A thread-safe registry that owns storage records, keyed by id."""

    def __init__(self) -> None:
        self._records: dict[str, StorageRecord] = {}
        self._lock = Lock()

    def register(self, record: StorageRecord) -> None:
        """Store ``record`` (insert or replace)."""
        with self._lock:
            self._records[record.id] = record

    def unregister(self, record_id: str) -> None:
        """Remove ``record_id`` if present."""
        with self._lock:
            self._records.pop(record_id, None)

    def get(self, record_id: str) -> StorageRecord:
        """Return the record for ``record_id``.

        Raises:
            RegistryError: If it is not registered.
        """
        with self._lock:
            record = self._records.get(record_id)
        if record is None:
            raise RegistryError(f"storage record {record_id!r} not found")
        return record

    def exists(self, record_id: str) -> bool:
        """Return ``True`` if ``record_id`` is registered."""
        with self._lock:
            return record_id in self._records

    def list(self) -> list[StorageRecord]:
        """Return all registered records."""
        with self._lock:
            return list(self._records.values())

    def clear(self) -> None:
        """Remove all registered records."""
        with self._lock:
            self._records.clear()
