"""AI decision lifecycle states.

Pure data: the finite states a single decision passes through plus the legal
transition table. No agent, consensus, or metrics logic here — those live in the
dedicated components.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["DecisionState", "can_transition", "VALID_TRANSITIONS"]


class DecisionState(str, Enum):
    """Lifecycle state of a single decision."""

    REQUESTED = "requested"
    EVALUATING = "evaluating"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    FAILED = "failed"


#: Allowed transitions for one decision run.
VALID_TRANSITIONS: dict[DecisionState, frozenset[DecisionState]] = {
    DecisionState.REQUESTED: frozenset(
        {DecisionState.EVALUATING, DecisionState.FAILED}
    ),
    DecisionState.EVALUATING: frozenset(
        {DecisionState.RESOLVED, DecisionState.REJECTED, DecisionState.FAILED}
    ),
    DecisionState.RESOLVED: frozenset(),
    DecisionState.REJECTED: frozenset(),
    DecisionState.FAILED: frozenset(),
}


def can_transition(source: DecisionState, target: DecisionState) -> bool:
    """Return ``True`` if moving from ``source`` to ``target`` is permitted."""
    return target in VALID_TRANSITIONS.get(source, frozenset())
