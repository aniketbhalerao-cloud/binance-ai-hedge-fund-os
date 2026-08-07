"""Storage record lifecycle states.

Pure data: the finite states a storage record passes through plus the legal
transition table. No collection, serialization, or persistence-planning logic
here — those live in the dedicated components.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["StorageState", "can_transition", "VALID_TRANSITIONS"]


class StorageState(str, Enum):
    """Lifecycle state of a storage record."""

    CREATED = "created"
    COLLECTING = "collecting"
    SERIALIZED = "serialized"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


#: Allowed transitions. ``COLLECTING`` and ``SERIALIZED`` re-enter as more inputs
#: are stored; a record may complete, cancel, or fail.
VALID_TRANSITIONS: dict[StorageState, frozenset[StorageState]] = {
    StorageState.CREATED: frozenset(
        {StorageState.COLLECTING, StorageState.CANCELLED}
    ),
    StorageState.COLLECTING: frozenset(
        {
            StorageState.COLLECTING,
            StorageState.SERIALIZED,
            StorageState.COMPLETED,
            StorageState.CANCELLED,
            StorageState.FAILED,
        }
    ),
    StorageState.SERIALIZED: frozenset(
        {
            StorageState.COLLECTING,
            StorageState.SERIALIZED,
            StorageState.COMPLETED,
            StorageState.CANCELLED,
            StorageState.FAILED,
        }
    ),
    StorageState.COMPLETED: frozenset(),
    StorageState.CANCELLED: frozenset(),
    StorageState.FAILED: frozenset(),
}

_REENTRANT: frozenset[StorageState] = frozenset(
    {StorageState.COLLECTING, StorageState.SERIALIZED}
)


def can_transition(source: StorageState, target: StorageState) -> bool:
    """Return ``True`` if moving from ``source`` to ``target`` is permitted."""
    if source == target and target in _REENTRANT:
        return True
    return target in VALID_TRANSITIONS.get(source, frozenset())
