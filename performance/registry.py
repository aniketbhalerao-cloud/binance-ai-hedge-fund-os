"""Performance registry.

:class:`InMemoryPerformanceRegistry` is a thread-safe store of performance
snapshots, keyed by snapshot id. It never creates snapshots (creation is the
manager's job) — it only registers, looks up, lists, and clears them. Mutable
state is guarded by a :class:`threading.Lock`. Registering a duplicate id raises
:class:`~performance.exceptions.DuplicatePerformanceError`.
"""

from __future__ import annotations

from threading import Lock

from performance.exceptions import (
    DuplicatePerformanceError,
    PerformanceNotFoundError,
)
from performance.models import PerformanceSnapshot

__all__ = ["InMemoryPerformanceRegistry"]


class InMemoryPerformanceRegistry:
    """A thread-safe registry of performance snapshots, keyed by id."""

    def __init__(self) -> None:
        self._snapshots: dict[str, PerformanceSnapshot] = {}
        self._lock = Lock()

    def register(self, snapshot: PerformanceSnapshot) -> None:
        """Store ``snapshot``.

        Raises:
            DuplicatePerformanceError: If the snapshot id already exists.
        """
        sid = snapshot.identifier.id
        with self._lock:
            if sid in self._snapshots:
                raise DuplicatePerformanceError(f"snapshot {sid!r} already registered")
            self._snapshots[sid] = snapshot

    def unregister(self, snapshot_id: str) -> None:
        """Remove ``snapshot_id`` if present."""
        with self._lock:
            self._snapshots.pop(snapshot_id, None)

    def get(self, snapshot_id: str) -> PerformanceSnapshot:
        """Return the snapshot for ``snapshot_id``.

        Raises:
            PerformanceNotFoundError: If it is not registered.
        """
        with self._lock:
            snapshot = self._snapshots.get(snapshot_id)
        if snapshot is None:
            raise PerformanceNotFoundError(f"snapshot {snapshot_id!r} not found")
        return snapshot

    def exists(self, snapshot_id: str) -> bool:
        """Return ``True`` if ``snapshot_id`` is registered."""
        with self._lock:
            return snapshot_id in self._snapshots

    def list(self) -> list[PerformanceSnapshot]:
        """Return all registered snapshots."""
        with self._lock:
            return list(self._snapshots.values())

    def clear(self) -> None:
        """Remove all registered snapshots."""
        with self._lock:
            self._snapshots.clear()
