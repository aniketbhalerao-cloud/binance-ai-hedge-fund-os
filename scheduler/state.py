"""Scheduler record lifecycle states.

Pure data: the finite states a scheduler record passes through plus the legal
transition table. No collection, planning, or dispatch logic here — those
live in the dedicated components.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["SchedulerState", "can_transition", "VALID_TRANSITIONS"]


class SchedulerState(str, Enum):
    """Lifecycle state of a scheduler record."""

    CREATED = "created"
    COLLECTING = "collecting"
    PLANNED = "planned"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


#: Allowed transitions. ``COLLECTING`` and ``PLANNED`` re-enter as more inputs
#: are scheduled; a record may complete, cancel, or fail.
VALID_TRANSITIONS: dict[SchedulerState, frozenset[SchedulerState]] = {
    SchedulerState.CREATED: frozenset(
        {SchedulerState.COLLECTING, SchedulerState.CANCELLED}
    ),
    SchedulerState.COLLECTING: frozenset(
        {
            SchedulerState.COLLECTING,
            SchedulerState.PLANNED,
            SchedulerState.COMPLETED,
            SchedulerState.CANCELLED,
            SchedulerState.FAILED,
        }
    ),
    SchedulerState.PLANNED: frozenset(
        {
            SchedulerState.COLLECTING,
            SchedulerState.PLANNED,
            SchedulerState.COMPLETED,
            SchedulerState.CANCELLED,
            SchedulerState.FAILED,
        }
    ),
    SchedulerState.COMPLETED: frozenset(),
    SchedulerState.CANCELLED: frozenset(),
    SchedulerState.FAILED: frozenset(),
}

_REENTRANT: frozenset[SchedulerState] = frozenset(
    {SchedulerState.COLLECTING, SchedulerState.PLANNED}
)


def can_transition(source: SchedulerState, target: SchedulerState) -> bool:
    """Return ``True`` if moving from ``source`` to ``target`` is permitted."""
    if source == target and target in _REENTRANT:
        return True
    return target in VALID_TRANSITIONS.get(source, frozenset())
