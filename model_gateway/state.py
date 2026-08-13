"""Model Gateway record lifecycle states.

Pure data: the finite states a model gateway record passes through plus the
legal transition table. No collection, planning, or dispatch logic here —
those live in the dedicated components.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["ModelGatewayState", "can_transition", "VALID_TRANSITIONS"]


# (str, Enum) matches the project-wide convention used by every sibling
# framework and 50+ other enums in this codebase; StrEnum has zero
# precedent here, and adopting it only in this one file would be the
# inconsistency, not the fix.
class ModelGatewayState(str, Enum):  # noqa: UP042
    """Lifecycle state of a model gateway record."""

    CREATED = "created"
    COLLECTING = "collecting"
    PLANNED = "planned"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


#: Allowed transitions. ``COLLECTING`` and ``PLANNED`` re-enter as more
#: inputs are invoked; a record may complete, cancel, or fail.
VALID_TRANSITIONS: dict[ModelGatewayState, frozenset[ModelGatewayState]] = {
    ModelGatewayState.CREATED: frozenset(
        {ModelGatewayState.COLLECTING, ModelGatewayState.CANCELLED}
    ),
    ModelGatewayState.COLLECTING: frozenset(
        {
            ModelGatewayState.COLLECTING,
            ModelGatewayState.PLANNED,
            ModelGatewayState.COMPLETED,
            ModelGatewayState.CANCELLED,
            ModelGatewayState.FAILED,
        }
    ),
    ModelGatewayState.PLANNED: frozenset(
        {
            ModelGatewayState.COLLECTING,
            ModelGatewayState.PLANNED,
            ModelGatewayState.COMPLETED,
            ModelGatewayState.CANCELLED,
            ModelGatewayState.FAILED,
        }
    ),
    ModelGatewayState.COMPLETED: frozenset(),
    ModelGatewayState.CANCELLED: frozenset(),
    ModelGatewayState.FAILED: frozenset(),
}

_REENTRANT: frozenset[ModelGatewayState] = frozenset(
    {ModelGatewayState.COLLECTING, ModelGatewayState.PLANNED}
)


def can_transition(source: ModelGatewayState, target: ModelGatewayState) -> bool:
    """Return ``True`` if moving from ``source`` to ``target`` is permitted."""
    if source == target and target in _REENTRANT:
        return True
    return target in VALID_TRANSITIONS.get(source, frozenset())
