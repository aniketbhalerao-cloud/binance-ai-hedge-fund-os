"""Model Gateway registry.

:class:`InMemoryModelGatewayRegistry` is a thread-safe store that **owns the
running model gateway records**, keyed by id. It never creates records
(creation is the manager's job) — it only registers (insert or replace),
looks up, lists, and clears them. Mutable state is guarded by a
:class:`threading.Lock`. It never persists a record to a file or database.
"""

from __future__ import annotations

from threading import Lock

from model_gateway.exceptions import RegistryError
from model_gateway.models import ModelInvocationRecord

__all__ = ["InMemoryModelGatewayRegistry"]


class InMemoryModelGatewayRegistry:
    """A thread-safe registry that owns model gateway records, keyed by id."""

    def __init__(self) -> None:
        self._records: dict[str, ModelInvocationRecord] = {}
        self._lock = Lock()

    def register(self, record: ModelInvocationRecord) -> None:
        """Store ``record`` (insert or replace)."""
        with self._lock:
            self._records[record.id] = record

    def unregister(self, record_id: str) -> None:
        """Remove ``record_id`` if present."""
        with self._lock:
            self._records.pop(record_id, None)

    def get(self, record_id: str) -> ModelInvocationRecord:
        """Return the record for ``record_id``.

        Raises:
            RegistryError: If it is not registered.
        """
        with self._lock:
            record = self._records.get(record_id)
        if record is None:
            raise RegistryError(f"model gateway record {record_id!r} not found")
        return record

    def exists(self, record_id: str) -> bool:
        """Return ``True`` if ``record_id`` is registered."""
        with self._lock:
            return record_id in self._records

    def list(self) -> list[ModelInvocationRecord]:
        """Return all registered records."""
        with self._lock:
            return list(self._records.values())

    def clear(self) -> None:
        """Remove all registered records."""
        with self._lock:
            self._records.clear()
