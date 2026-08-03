"""Backtest registry.

:class:`InMemoryBacktestRegistry` is a thread-safe store of backtest snapshots,
keyed by backtest id. It never creates snapshots (creation is the manager's job)
— it only registers, looks up, lists, and clears them. Mutable state is guarded
by a :class:`threading.Lock`.
"""

from __future__ import annotations

from threading import Lock

from backtesting.exceptions import RegistryError
from backtesting.models import BacktestSnapshot

__all__ = ["InMemoryBacktestRegistry"]


class InMemoryBacktestRegistry:
    """A thread-safe registry of backtest snapshots, keyed by id."""

    def __init__(self) -> None:
        self._snapshots: dict[str, BacktestSnapshot] = {}
        self._lock = Lock()

    def register(self, snapshot: BacktestSnapshot) -> None:
        """Store ``snapshot`` (insert or replace)."""
        with self._lock:
            self._snapshots[snapshot.backtest.id] = snapshot

    def unregister(self, backtest_id: str) -> None:
        """Remove ``backtest_id`` if present."""
        with self._lock:
            self._snapshots.pop(backtest_id, None)

    def get(self, backtest_id: str) -> BacktestSnapshot:
        """Return the snapshot for ``backtest_id``.

        Raises:
            RegistryError: If it is not registered.
        """
        with self._lock:
            snapshot = self._snapshots.get(backtest_id)
        if snapshot is None:
            raise RegistryError(f"backtest {backtest_id!r} not found")
        return snapshot

    def exists(self, backtest_id: str) -> bool:
        """Return ``True`` if ``backtest_id`` is registered."""
        with self._lock:
            return backtest_id in self._snapshots

    def list(self) -> list[BacktestSnapshot]:
        """Return all registered snapshots."""
        with self._lock:
            return list(self._snapshots.values())

    def clear(self) -> None:
        """Remove all registered snapshots."""
        with self._lock:
            self._snapshots.clear()
