"""Reporting record lifecycle states.

Pure data: the finite states a reporting record passes through plus the legal
transition table. No collection, building, or export logic here — those live in
the dedicated components.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["ReportingState", "can_transition", "VALID_TRANSITIONS"]


class ReportingState(str, Enum):
    """Lifecycle state of a reporting record."""

    CREATED = "created"
    COLLECTING = "collecting"
    BUILT = "built"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


#: Allowed transitions. ``COLLECTING`` and ``BUILT`` re-enter as more inputs are
#: reported; a record may complete, cancel, or fail.
VALID_TRANSITIONS: dict[ReportingState, frozenset[ReportingState]] = {
    ReportingState.CREATED: frozenset(
        {ReportingState.COLLECTING, ReportingState.CANCELLED}
    ),
    ReportingState.COLLECTING: frozenset(
        {
            ReportingState.COLLECTING,
            ReportingState.BUILT,
            ReportingState.COMPLETED,
            ReportingState.CANCELLED,
            ReportingState.FAILED,
        }
    ),
    ReportingState.BUILT: frozenset(
        {
            ReportingState.COLLECTING,
            ReportingState.BUILT,
            ReportingState.COMPLETED,
            ReportingState.CANCELLED,
            ReportingState.FAILED,
        }
    ),
    ReportingState.COMPLETED: frozenset(),
    ReportingState.CANCELLED: frozenset(),
    ReportingState.FAILED: frozenset(),
}

_REENTRANT: frozenset[ReportingState] = frozenset(
    {ReportingState.COLLECTING, ReportingState.BUILT}
)


def can_transition(source: ReportingState, target: ReportingState) -> bool:
    """Return ``True`` if moving from ``source`` to ``target`` is permitted."""
    if source == target and target in _REENTRANT:
        return True
    return target in VALID_TRANSITIONS.get(source, frozenset())
