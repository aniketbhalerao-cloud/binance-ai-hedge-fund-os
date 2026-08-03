"""Backtest simulation lifecycle states.

Pure data: the finite simulation-run states plus the legal transition table. No
scheduling, simulation, or metrics logic here — those live in the dedicated
components. A backtest run advances through these states as the manager drives
the historical simulation.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["SimulationState", "can_transition", "VALID_TRANSITIONS"]


class SimulationState(str, Enum):
    """Lifecycle state of a backtest run."""

    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


#: Allowed transitions. ``RUNNING`` may re-enter itself as steps advance, and may
#: pause/resume, complete, cancel, or fail.
VALID_TRANSITIONS: dict[SimulationState, frozenset[SimulationState]] = {
    SimulationState.CREATED: frozenset(
        {SimulationState.RUNNING, SimulationState.CANCELLED}
    ),
    SimulationState.RUNNING: frozenset(
        {
            SimulationState.RUNNING,
            SimulationState.PAUSED,
            SimulationState.COMPLETED,
            SimulationState.CANCELLED,
            SimulationState.FAILED,
        }
    ),
    SimulationState.PAUSED: frozenset(
        {
            SimulationState.RUNNING,
            SimulationState.CANCELLED,
            SimulationState.FAILED,
        }
    ),
    SimulationState.COMPLETED: frozenset(),
    SimulationState.CANCELLED: frozenset(),
    SimulationState.FAILED: frozenset(),
}


def can_transition(source: SimulationState, target: SimulationState) -> bool:
    """Return ``True`` if moving from ``source`` to ``target`` is permitted."""
    if source == target and target is SimulationState.RUNNING:
        return True
    return target in VALID_TRANSITIONS.get(source, frozenset())
