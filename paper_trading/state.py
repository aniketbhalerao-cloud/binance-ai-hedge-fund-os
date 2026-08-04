"""Paper trading session lifecycle states.

Pure data: the finite session states plus the legal transition table. No feed,
broker, or metrics logic here — those live in the dedicated components. A live
paper-trading session advances through these states as the manager processes
live market updates.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["SessionState", "can_transition", "VALID_TRANSITIONS"]


class SessionState(str, Enum):
    """Lifecycle state of a paper-trading session."""

    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


#: Allowed transitions. ``RUNNING`` re-enters itself as each live update is
#: processed, and may pause, complete, cancel, or fail.
VALID_TRANSITIONS: dict[SessionState, frozenset[SessionState]] = {
    SessionState.CREATED: frozenset(
        {SessionState.RUNNING, SessionState.CANCELLED}
    ),
    SessionState.RUNNING: frozenset(
        {
            SessionState.RUNNING,
            SessionState.PAUSED,
            SessionState.COMPLETED,
            SessionState.CANCELLED,
            SessionState.FAILED,
        }
    ),
    SessionState.PAUSED: frozenset(
        {
            SessionState.RUNNING,
            SessionState.CANCELLED,
            SessionState.FAILED,
        }
    ),
    SessionState.COMPLETED: frozenset(),
    SessionState.CANCELLED: frozenset(),
    SessionState.FAILED: frozenset(),
}


def can_transition(source: SessionState, target: SessionState) -> bool:
    """Return ``True`` if moving from ``source`` to ``target`` is permitted."""
    if source == target and target is SessionState.RUNNING:
        return True
    return target in VALID_TRANSITIONS.get(source, frozenset())
