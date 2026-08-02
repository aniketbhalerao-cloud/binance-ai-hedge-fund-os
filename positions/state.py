"""Position lifecycle states.

Pure data: the finite position states plus the legal transition table. No
tracking, calculation, or valuation logic here.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["PositionState", "can_transition", "VALID_TRANSITIONS"]


class PositionState(str, Enum):
    """Lifecycle state of a position."""

    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_CLOSED = "partially_closed"
    CLOSED = "closed"
    CANCELLED = "cancelled"


#: Allowed transitions. ``OPEN`` / ``PARTIALLY_CLOSED`` may re-enter themselves as
#: more fills arrive.
VALID_TRANSITIONS: dict[PositionState, frozenset[PositionState]] = {
    PositionState.PENDING: frozenset(
        {PositionState.OPEN, PositionState.CANCELLED}
    ),
    PositionState.OPEN: frozenset(
        {
            PositionState.OPEN,
            PositionState.PARTIALLY_CLOSED,
            PositionState.CLOSED,
        }
    ),
    PositionState.PARTIALLY_CLOSED: frozenset(
        {
            PositionState.PARTIALLY_CLOSED,
            PositionState.OPEN,
            PositionState.CLOSED,
        }
    ),
    PositionState.CLOSED: frozenset(),
    PositionState.CANCELLED: frozenset(),
}


def can_transition(source: PositionState, target: PositionState) -> bool:
    """Return ``True`` if moving from ``source`` to ``target`` is permitted."""
    if source == target and target in (PositionState.OPEN, PositionState.PARTIALLY_CLOSED):
        return True
    return target in VALID_TRANSITIONS.get(source, frozenset())
