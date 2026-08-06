"""Dashboard record lifecycle states.

Pure data: the finite states a dashboard record passes through plus the legal
transition table. No aggregation, composition, or widget logic here — those live
in the dedicated components.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["DashboardState", "can_transition", "VALID_TRANSITIONS"]


class DashboardState(str, Enum):
    """Lifecycle state of a dashboard record."""

    CREATED = "created"
    AGGREGATING = "aggregating"
    COMPOSED = "composed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


#: Allowed transitions. ``AGGREGATING`` and ``COMPOSED`` re-enter as more inputs are
#: rendered; a record may complete, cancel, or fail.
VALID_TRANSITIONS: dict[DashboardState, frozenset[DashboardState]] = {
    DashboardState.CREATED: frozenset(
        {DashboardState.AGGREGATING, DashboardState.CANCELLED}
    ),
    DashboardState.AGGREGATING: frozenset(
        {
            DashboardState.AGGREGATING,
            DashboardState.COMPOSED,
            DashboardState.COMPLETED,
            DashboardState.CANCELLED,
            DashboardState.FAILED,
        }
    ),
    DashboardState.COMPOSED: frozenset(
        {
            DashboardState.AGGREGATING,
            DashboardState.COMPOSED,
            DashboardState.COMPLETED,
            DashboardState.CANCELLED,
            DashboardState.FAILED,
        }
    ),
    DashboardState.COMPLETED: frozenset(),
    DashboardState.CANCELLED: frozenset(),
    DashboardState.FAILED: frozenset(),
}

_REENTRANT: frozenset[DashboardState] = frozenset(
    {DashboardState.AGGREGATING, DashboardState.COMPOSED}
)


def can_transition(source: DashboardState, target: DashboardState) -> bool:
    """Return ``True`` if moving from ``source`` to ``target`` is permitted."""
    if source == target and target in _REENTRANT:
        return True
    return target in VALID_TRANSITIONS.get(source, frozenset())
