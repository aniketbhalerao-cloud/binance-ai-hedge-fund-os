"""Memory record lifecycle states.

Pure data: the finite states a memory record passes through plus the legal
transition table. No collection, planning, or dispatch logic here — those
live in the dedicated components.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["MemoryState", "can_transition", "VALID_TRANSITIONS"]


class MemoryState(str, Enum):
    """Lifecycle state of a memory record."""

    CREATED = "created"
    COLLECTING = "collecting"
    PLANNED = "planned"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


#: Allowed transitions. ``COLLECTING`` and ``PLANNED`` re-enter as more inputs
#: are remembered; a record may complete, cancel, or fail.
VALID_TRANSITIONS: dict[MemoryState, frozenset[MemoryState]] = {
    MemoryState.CREATED: frozenset(
        {MemoryState.COLLECTING, MemoryState.CANCELLED}
    ),
    MemoryState.COLLECTING: frozenset(
        {
            MemoryState.COLLECTING,
            MemoryState.PLANNED,
            MemoryState.COMPLETED,
            MemoryState.CANCELLED,
            MemoryState.FAILED,
        }
    ),
    MemoryState.PLANNED: frozenset(
        {
            MemoryState.COLLECTING,
            MemoryState.PLANNED,
            MemoryState.COMPLETED,
            MemoryState.CANCELLED,
            MemoryState.FAILED,
        }
    ),
    MemoryState.COMPLETED: frozenset(),
    MemoryState.CANCELLED: frozenset(),
    MemoryState.FAILED: frozenset(),
}

_REENTRANT: frozenset[MemoryState] = frozenset(
    {MemoryState.COLLECTING, MemoryState.PLANNED}
)


def can_transition(source: MemoryState, target: MemoryState) -> bool:
    """Return ``True`` if moving from ``source`` to ``target`` is permitted."""
    if source == target and target in _REENTRANT:
        return True
    return target in VALID_TRANSITIONS.get(source, frozenset())
