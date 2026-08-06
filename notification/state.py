"""Notification record lifecycle states.

Pure data: the finite states a notification record passes through plus the legal
transition table. No collection, formatting, or dispatch logic here — those live in
the dedicated components.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["NotificationState", "can_transition", "VALID_TRANSITIONS"]


class NotificationState(str, Enum):
    """Lifecycle state of a notification record."""

    CREATED = "created"
    COLLECTING = "collecting"
    FORMATTED = "formatted"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


#: Allowed transitions. ``COLLECTING`` and ``FORMATTED`` re-enter as more inputs are
#: notified; a record may complete, cancel, or fail.
VALID_TRANSITIONS: dict[NotificationState, frozenset[NotificationState]] = {
    NotificationState.CREATED: frozenset(
        {NotificationState.COLLECTING, NotificationState.CANCELLED}
    ),
    NotificationState.COLLECTING: frozenset(
        {
            NotificationState.COLLECTING,
            NotificationState.FORMATTED,
            NotificationState.COMPLETED,
            NotificationState.CANCELLED,
            NotificationState.FAILED,
        }
    ),
    NotificationState.FORMATTED: frozenset(
        {
            NotificationState.COLLECTING,
            NotificationState.FORMATTED,
            NotificationState.COMPLETED,
            NotificationState.CANCELLED,
            NotificationState.FAILED,
        }
    ),
    NotificationState.COMPLETED: frozenset(),
    NotificationState.CANCELLED: frozenset(),
    NotificationState.FAILED: frozenset(),
}

_REENTRANT: frozenset[NotificationState] = frozenset(
    {NotificationState.COLLECTING, NotificationState.FORMATTED}
)


def can_transition(source: NotificationState, target: NotificationState) -> bool:
    """Return ``True`` if moving from ``source`` to ``target`` is permitted."""
    if source == target and target in _REENTRANT:
        return True
    return target in VALID_TRANSITIONS.get(source, frozenset())
