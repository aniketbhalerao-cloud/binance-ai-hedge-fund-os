"""Learning record lifecycle states.

Pure data: the finite states a learning record passes through plus the legal
transition table. No journal, evaluation, or feedback logic here — those live in
the dedicated components. A record advances through these states as the manager
processes outcomes.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["LearningState", "can_transition", "VALID_TRANSITIONS"]


class LearningState(str, Enum):
    """Lifecycle state of a learning record."""

    CREATED = "created"
    RECORDING = "recording"
    EVALUATED = "evaluated"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


#: Allowed transitions. ``RECORDING`` and ``EVALUATED`` re-enter as more outcomes
#: are learned; a record may complete, cancel, or fail.
VALID_TRANSITIONS: dict[LearningState, frozenset[LearningState]] = {
    LearningState.CREATED: frozenset(
        {LearningState.RECORDING, LearningState.CANCELLED}
    ),
    LearningState.RECORDING: frozenset(
        {
            LearningState.RECORDING,
            LearningState.EVALUATED,
            LearningState.COMPLETED,
            LearningState.CANCELLED,
            LearningState.FAILED,
        }
    ),
    LearningState.EVALUATED: frozenset(
        {
            LearningState.RECORDING,
            LearningState.EVALUATED,
            LearningState.COMPLETED,
            LearningState.CANCELLED,
            LearningState.FAILED,
        }
    ),
    LearningState.COMPLETED: frozenset(),
    LearningState.CANCELLED: frozenset(),
    LearningState.FAILED: frozenset(),
}

#: The states in which re-entering the same state (another outcome) is legal.
_REENTRANT: frozenset[LearningState] = frozenset(
    {LearningState.RECORDING, LearningState.EVALUATED}
)


def can_transition(source: LearningState, target: LearningState) -> bool:
    """Return ``True`` if moving from ``source`` to ``target`` is permitted."""
    if source == target and target in _REENTRANT:
        return True
    return target in VALID_TRANSITIONS.get(source, frozenset())
