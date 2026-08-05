"""Optimization record lifecycle states.

Pure data: the finite states an optimization record passes through plus the legal
transition table. No planning, optimizing, or recommendation logic here — those
live in the dedicated components.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["OptimizationState", "can_transition", "VALID_TRANSITIONS"]


class OptimizationState(str, Enum):
    """Lifecycle state of an optimization record."""

    CREATED = "created"
    PLANNING = "planning"
    OPTIMIZED = "optimized"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


#: Allowed transitions. ``PLANNING`` and ``OPTIMIZED`` re-enter as more inputs are
#: optimized; a record may complete, cancel, or fail.
VALID_TRANSITIONS: dict[OptimizationState, frozenset[OptimizationState]] = {
    OptimizationState.CREATED: frozenset(
        {OptimizationState.PLANNING, OptimizationState.CANCELLED}
    ),
    OptimizationState.PLANNING: frozenset(
        {
            OptimizationState.PLANNING,
            OptimizationState.OPTIMIZED,
            OptimizationState.COMPLETED,
            OptimizationState.CANCELLED,
            OptimizationState.FAILED,
        }
    ),
    OptimizationState.OPTIMIZED: frozenset(
        {
            OptimizationState.PLANNING,
            OptimizationState.OPTIMIZED,
            OptimizationState.COMPLETED,
            OptimizationState.CANCELLED,
            OptimizationState.FAILED,
        }
    ),
    OptimizationState.COMPLETED: frozenset(),
    OptimizationState.CANCELLED: frozenset(),
    OptimizationState.FAILED: frozenset(),
}

_REENTRANT: frozenset[OptimizationState] = frozenset(
    {OptimizationState.PLANNING, OptimizationState.OPTIMIZED}
)


def can_transition(source: OptimizationState, target: OptimizationState) -> bool:
    """Return ``True`` if moving from ``source`` to ``target`` is permitted."""
    if source == target and target in _REENTRANT:
        return True
    return target in VALID_TRANSITIONS.get(source, frozenset())
