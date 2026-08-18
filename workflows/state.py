"""Workflow record lifecycle states.

Pure data: the finite states a workflow record passes through plus the legal
transition table. No collection, planning, or dispatch logic here — those
live in the dedicated components.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["WorkflowState", "can_transition", "VALID_TRANSITIONS"]


# (str, Enum) matches the project-wide convention used by every sibling
# framework and 50+ other enums in this codebase; StrEnum has zero
# precedent here, and adopting it only in this one file would be the
# inconsistency, not the fix.
class WorkflowState(str, Enum):  # noqa: UP042
    """Lifecycle state of a workflow record."""

    CREATED = "created"
    COLLECTING = "collecting"
    PLANNED = "planned"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


#: Allowed transitions. ``COLLECTING`` and ``PLANNED`` re-enter as more
#: inputs are composed; a record may complete, cancel, or fail.
VALID_TRANSITIONS: dict[WorkflowState, frozenset[WorkflowState]] = {
    WorkflowState.CREATED: frozenset(
        {WorkflowState.COLLECTING, WorkflowState.CANCELLED}
    ),
    WorkflowState.COLLECTING: frozenset(
        {
            WorkflowState.COLLECTING,
            WorkflowState.PLANNED,
            WorkflowState.COMPLETED,
            WorkflowState.CANCELLED,
            WorkflowState.FAILED,
        }
    ),
    WorkflowState.PLANNED: frozenset(
        {
            WorkflowState.COLLECTING,
            WorkflowState.PLANNED,
            WorkflowState.COMPLETED,
            WorkflowState.CANCELLED,
            WorkflowState.FAILED,
        }
    ),
    WorkflowState.COMPLETED: frozenset(),
    WorkflowState.CANCELLED: frozenset(),
    WorkflowState.FAILED: frozenset(),
}

_REENTRANT: frozenset[WorkflowState] = frozenset(
    {WorkflowState.COLLECTING, WorkflowState.PLANNED}
)


def can_transition(source: WorkflowState, target: WorkflowState) -> bool:
    """Return ``True`` if moving from ``source`` to ``target`` is permitted."""
    if source == target and target in _REENTRANT:
        return True
    return target in VALID_TRANSITIONS.get(source, frozenset())
