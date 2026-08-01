"""Trading engine runtime state.

Two concerns live here, both pure data (no coordination or trading logic):

* :class:`EngineState` — the finite set of lifecycle states plus the legal
  transition table; the state machine that applies these rules is
  :class:`~trading.lifecycle.LifecycleManager`.
* :class:`RuntimeState` — an immutable snapshot of the engine's runtime status
  (lifecycle state, timestamps, last error, and processing counters). The engine
  owns the ``RuntimeState``; other components may read it but never mutate it.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

__all__ = ["EngineState", "RuntimeState", "can_transition", "VALID_TRANSITIONS"]


class EngineState(str, Enum):
    """Lifecycle state of the trading engine."""

    CREATED = "created"
    INITIALIZING = "initializing"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


#: Allowed forward transitions. ``FAILED`` is reachable from any state via an
#: explicit failure and is therefore handled separately by the lifecycle
#: manager rather than being listed on every entry here.
VALID_TRANSITIONS: dict[EngineState, frozenset[EngineState]] = {
    EngineState.CREATED: frozenset({EngineState.INITIALIZING}),
    EngineState.INITIALIZING: frozenset({EngineState.STARTING, EngineState.FAILED}),
    EngineState.STARTING: frozenset({EngineState.RUNNING, EngineState.FAILED}),
    EngineState.RUNNING: frozenset(
        {EngineState.PAUSED, EngineState.STOPPING, EngineState.FAILED}
    ),
    EngineState.PAUSED: frozenset(
        {EngineState.RUNNING, EngineState.STOPPING, EngineState.FAILED}
    ),
    EngineState.STOPPING: frozenset({EngineState.STOPPED, EngineState.FAILED}),
    EngineState.STOPPED: frozenset({EngineState.INITIALIZING}),
    EngineState.FAILED: frozenset({EngineState.INITIALIZING}),
}


def can_transition(source: EngineState, target: EngineState) -> bool:
    """Return ``True`` if moving from ``source`` to ``target`` is permitted."""
    return target in VALID_TRANSITIONS.get(source, frozenset())


@dataclass(frozen=True, slots=True)
class RuntimeState:
    """Immutable snapshot of the engine's runtime status.

    Attributes:
        state: The current lifecycle state.
        started_at: When the engine last entered ``RUNNING`` (UTC), if ever.
        last_activity_at: When the engine last changed state (UTC), if ever.
        last_error: Message of the most recent failure, if any.
        orders_processed: Count of orders processed (for future use).
        trades_processed: Count of trades processed (for future use).
        signals_processed: Count of signals processed (for future use).
    """

    state: EngineState = EngineState.CREATED
    started_at: datetime | None = None
    last_activity_at: datetime | None = None
    last_error: str | None = None
    orders_processed: int = 0
    trades_processed: int = 0
    signals_processed: int = 0

    def with_state(self, state: EngineState, *, now: datetime) -> RuntimeState:
        """Return a copy with ``state`` and ``last_activity_at`` updated."""
        return dataclasses.replace(self, state=state, last_activity_at=now)

    def mark_started(self, *, now: datetime) -> RuntimeState:
        """Return a copy with ``started_at`` recorded (RUNNING entered)."""
        return dataclasses.replace(self, started_at=now, last_activity_at=now)

    def with_error(self, message: str, *, now: datetime) -> RuntimeState:
        """Return a copy recording a failure message."""
        return dataclasses.replace(
            self,
            state=EngineState.FAILED,
            last_error=message,
            last_activity_at=now,
        )

    def statistics(self) -> dict[str, int]:
        """Return the processing counters as a plain mapping."""
        return {
            "orders_processed": self.orders_processed,
            "trades_processed": self.trades_processed,
            "signals_processed": self.signals_processed,
        }
