"""Monitoring record lifecycle states.

Pure data: the finite states a monitoring record passes through plus the legal
transition table. No collection, diagnostics, or alerting logic here — those live
in the dedicated components.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["MonitoringState", "can_transition", "VALID_TRANSITIONS"]


class MonitoringState(str, Enum):
    """Lifecycle state of a monitoring record."""

    CREATED = "created"
    COLLECTING = "collecting"
    EVALUATED = "evaluated"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


#: Allowed transitions. ``COLLECTING`` and ``EVALUATED`` re-enter as more inputs are
#: observed; a record may complete, cancel, or fail.
VALID_TRANSITIONS: dict[MonitoringState, frozenset[MonitoringState]] = {
    MonitoringState.CREATED: frozenset(
        {MonitoringState.COLLECTING, MonitoringState.CANCELLED}
    ),
    MonitoringState.COLLECTING: frozenset(
        {
            MonitoringState.COLLECTING,
            MonitoringState.EVALUATED,
            MonitoringState.COMPLETED,
            MonitoringState.CANCELLED,
            MonitoringState.FAILED,
        }
    ),
    MonitoringState.EVALUATED: frozenset(
        {
            MonitoringState.COLLECTING,
            MonitoringState.EVALUATED,
            MonitoringState.COMPLETED,
            MonitoringState.CANCELLED,
            MonitoringState.FAILED,
        }
    ),
    MonitoringState.COMPLETED: frozenset(),
    MonitoringState.CANCELLED: frozenset(),
    MonitoringState.FAILED: frozenset(),
}

_REENTRANT: frozenset[MonitoringState] = frozenset(
    {MonitoringState.COLLECTING, MonitoringState.EVALUATED}
)


def can_transition(source: MonitoringState, target: MonitoringState) -> bool:
    """Return ``True`` if moving from ``source`` to ``target`` is permitted."""
    if source == target and target in _REENTRANT:
        return True
    return target in VALID_TRANSITIONS.get(source, frozenset())
