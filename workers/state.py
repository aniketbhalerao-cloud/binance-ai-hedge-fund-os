"""Worker record lifecycle states.

Pure data: the finite states a worker record passes through plus the legal
transition table. No collection, planning, or dispatch logic here — those
live in the dedicated components.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["WorkerState", "can_transition", "VALID_TRANSITIONS"]


class WorkerState(str, Enum):
    """Lifecycle state of a worker record."""

    CREATED = "created"
    COLLECTING = "collecting"
    QUEUED = "queued"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


#: Allowed transitions. ``COLLECTING`` and ``QUEUED`` re-enter as more inputs
#: are enqueued; a record may complete, cancel, or fail.
VALID_TRANSITIONS: dict[WorkerState, frozenset[WorkerState]] = {
    WorkerState.CREATED: frozenset(
        {WorkerState.COLLECTING, WorkerState.CANCELLED}
    ),
    WorkerState.COLLECTING: frozenset(
        {
            WorkerState.COLLECTING,
            WorkerState.QUEUED,
            WorkerState.COMPLETED,
            WorkerState.CANCELLED,
            WorkerState.FAILED,
        }
    ),
    WorkerState.QUEUED: frozenset(
        {
            WorkerState.COLLECTING,
            WorkerState.QUEUED,
            WorkerState.COMPLETED,
            WorkerState.CANCELLED,
            WorkerState.FAILED,
        }
    ),
    WorkerState.COMPLETED: frozenset(),
    WorkerState.CANCELLED: frozenset(),
    WorkerState.FAILED: frozenset(),
}

_REENTRANT: frozenset[WorkerState] = frozenset(
    {WorkerState.COLLECTING, WorkerState.QUEUED}
)


def can_transition(source: WorkerState, target: WorkerState) -> bool:
    """Return ``True`` if moving from ``source`` to ``target`` is permitted."""
    if source == target and target in _REENTRANT:
        return True
    return target in VALID_TRANSITIONS.get(source, frozenset())
