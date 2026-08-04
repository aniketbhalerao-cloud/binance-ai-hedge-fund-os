"""Learning registry.

:class:`InMemoryLearningRegistry` is a thread-safe store that **owns the running
learning records**, keyed by id. It never creates records (creation is the
manager's job) — it only registers (insert or replace), looks up, lists, and
clears them. The manager loads the current record, processes one outcome, and
writes back a new immutable record. Mutable state is guarded by a
:class:`threading.Lock`.
"""

from __future__ import annotations

from threading import Lock

from learning.exceptions import RegistryError
from learning.models import LearningRecord

__all__ = ["InMemoryLearningRegistry"]


class InMemoryLearningRegistry:
    """A thread-safe registry that owns learning records, keyed by id."""

    def __init__(self) -> None:
        self._records: dict[str, LearningRecord] = {}
        self._lock = Lock()

    def register(self, record: LearningRecord) -> None:
        """Store ``record`` (insert or replace)."""
        with self._lock:
            self._records[record.id] = record

    def unregister(self, record_id: str) -> None:
        """Remove ``record_id`` if present."""
        with self._lock:
            self._records.pop(record_id, None)

    def get(self, record_id: str) -> LearningRecord:
        """Return the record for ``record_id``.

        Raises:
            RegistryError: If it is not registered.
        """
        with self._lock:
            record = self._records.get(record_id)
        if record is None:
            raise RegistryError(f"learning record {record_id!r} not found")
        return record

    def exists(self, record_id: str) -> bool:
        """Return ``True`` if ``record_id`` is registered."""
        with self._lock:
            return record_id in self._records

    def list(self) -> list[LearningRecord]:
        """Return all registered records."""
        with self._lock:
            return list(self._records.values())

    def clear(self) -> None:
        """Remove all registered records."""
        with self._lock:
            self._records.clear()
