"""Position registry.

:class:`InMemoryPositionRegistry` is a thread-safe store of positions and their
histories, keyed by id. It never creates positions (creation is the manager's/DI's
job) — it only registers, looks up, lists, and removes them.
"""

from __future__ import annotations

from threading import Lock

from positions.exceptions import PositionNotFoundError
from positions.models import Position, PositionHistory

__all__ = ["InMemoryPositionRegistry"]


class InMemoryPositionRegistry:
    """A thread-safe registry of positions + histories, keyed by id."""

    def __init__(self) -> None:
        self._positions: dict[str, Position] = {}
        self._histories: dict[str, PositionHistory] = {}
        self._lock = Lock()

    def register(self, position: Position, history: PositionHistory) -> None:
        """Store ``position`` and its ``history`` (insert or replace)."""
        with self._lock:
            self._positions[position.id] = position
            self._histories[position.id] = history

    def exists(self, position_id: str) -> bool:
        """Return ``True`` if ``position_id`` is registered."""
        with self._lock:
            return position_id in self._positions

    def get(self, position_id: str) -> Position:
        """Return the position for ``position_id``.

        Raises:
            PositionNotFoundError: If it is not registered.
        """
        with self._lock:
            position = self._positions.get(position_id)
        if position is None:
            raise PositionNotFoundError(f"position {position_id!r} not found")
        return position

    def history(self, position_id: str) -> PositionHistory:
        """Return the history for ``position_id`` (empty if none yet)."""
        with self._lock:
            return self._histories.get(
                position_id, PositionHistory(position_id)
            )

    def list(self) -> list[Position]:
        """Return all registered positions."""
        with self._lock:
            return list(self._positions.values())

    def remove(self, position_id: str) -> None:
        """Remove ``position_id`` (position + history) if present."""
        with self._lock:
            self._positions.pop(position_id, None)
            self._histories.pop(position_id, None)
