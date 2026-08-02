"""Execution lifecycle states.

Pure data: the finite set of execution lifecycle states plus the legal
transition table. This framework coordinates the lifecycle up to ``READY``
(ready to hand off to a future Exchange Adapter); the later states
(``EXECUTING`` … ``COMPLETED``) are declared for that future adapter. No broker
communication happens here.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["ExecutionState", "can_transition", "VALID_TRANSITIONS"]


class ExecutionState(str, Enum):
    """Lifecycle state of an execution."""

    CREATED = "created"
    QUEUED = "queued"
    READY = "ready"
    EXECUTING = "executing"
    EXECUTED = "executed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    COMPLETED = "completed"


#: Allowed forward transitions.
VALID_TRANSITIONS: dict[ExecutionState, frozenset[ExecutionState]] = {
    ExecutionState.CREATED: frozenset(
        {ExecutionState.QUEUED, ExecutionState.FAILED, ExecutionState.CANCELLED}
    ),
    ExecutionState.QUEUED: frozenset(
        {ExecutionState.READY, ExecutionState.FAILED, ExecutionState.CANCELLED}
    ),
    ExecutionState.READY: frozenset(
        {ExecutionState.EXECUTING, ExecutionState.FAILED, ExecutionState.CANCELLED}
    ),
    ExecutionState.EXECUTING: frozenset(
        {
            ExecutionState.EXECUTED,
            ExecutionState.RETRYING,
            ExecutionState.FAILED,
            ExecutionState.CANCELLED,
        }
    ),
    ExecutionState.RETRYING: frozenset(
        {ExecutionState.EXECUTING, ExecutionState.FAILED, ExecutionState.CANCELLED}
    ),
    ExecutionState.EXECUTED: frozenset({ExecutionState.COMPLETED}),
    ExecutionState.COMPLETED: frozenset(),
    ExecutionState.FAILED: frozenset(),
    ExecutionState.CANCELLED: frozenset(),
}


def can_transition(source: ExecutionState, target: ExecutionState) -> bool:
    """Return ``True`` if moving from ``source`` to ``target`` is permitted."""
    return target in VALID_TRANSITIONS.get(source, frozenset())
