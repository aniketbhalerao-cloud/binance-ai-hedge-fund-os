"""Trading engine lifecycle: state machine and lifecycle events.

Two closely-related concerns:

* :class:`LifecycleManager` — a thread-safe finite-state machine that validates
  and applies :class:`~trading.state.EngineState` transitions, preventing
  invalid ones. It holds no coordination or trading logic.
* The engine lifecycle **events** (:class:`EngineInitializing`,
  :class:`EngineStarted`, …) — immutable events, inheriting the existing
  :class:`events.base.Event`, that the engine publishes on the shared event bus
  as its lifecycle progresses.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

from events.base import Event
from trading.exceptions import LifecycleTransitionError
from trading.state import EngineState, can_transition

__all__ = [
    "LifecycleManager",
    "EngineLifecycleEvent",
    "EngineInitializing",
    "EngineStarting",
    "EngineStarted",
    "EnginePaused",
    "EngineResumed",
    "EngineStopping",
    "EngineStopped",
    "EngineFailed",
]


class LifecycleManager:
    """A thread-safe finite-state machine over :class:`EngineState`.

    Args:
        initial: The state to start in (defaults to ``CREATED``).
    """

    def __init__(self, initial: EngineState = EngineState.CREATED) -> None:
        self._initial = initial
        self._state = initial
        self._lock = Lock()

    def current_state(self) -> EngineState:
        """Return the current lifecycle state."""
        with self._lock:
            return self._state

    @property
    def state(self) -> EngineState:
        """Return the current lifecycle state (property form)."""
        return self.current_state()

    @property
    def is_running(self) -> bool:
        """Return ``True`` if the engine is in the ``RUNNING`` state."""
        return self.current_state() is EngineState.RUNNING

    def can_transition(self, target: EngineState) -> bool:
        """Return ``True`` if moving to ``target`` is currently permitted."""
        with self._lock:
            return can_transition(self._state, target)

    def transition(self, target: EngineState) -> EngineState:
        """Move to ``target`` if the transition is legal.

        Args:
            target: The state to move to.

        Returns:
            The new (now current) state.

        Raises:
            LifecycleTransitionError: If the transition is not permitted.
        """
        with self._lock:
            if not can_transition(self._state, target):
                raise LifecycleTransitionError(self._state, target)
            self._state = target
            return self._state

    def fail(self) -> EngineState:
        """Force the engine into the ``FAILED`` state from any state."""
        with self._lock:
            self._state = EngineState.FAILED
            return self._state

    def reset(self) -> EngineState:
        """Reset the machine back to its initial state."""
        with self._lock:
            self._state = self._initial
            return self._state


# ---------------------------------------------------------------------------
# Engine lifecycle events (published on the shared event bus)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class EngineLifecycleEvent(Event):
    """Base class for trading-engine lifecycle events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class EngineInitializing(EngineLifecycleEvent):
    """Emitted when the engine begins initialization."""


@dataclass(frozen=True, slots=True, kw_only=True)
class EngineStarting(EngineLifecycleEvent):
    """Emitted when the engine begins starting its services."""


@dataclass(frozen=True, slots=True, kw_only=True)
class EngineStarted(EngineLifecycleEvent):
    """Emitted when the engine has fully started (RUNNING)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class EnginePaused(EngineLifecycleEvent):
    """Emitted when the engine is paused."""


@dataclass(frozen=True, slots=True, kw_only=True)
class EngineResumed(EngineLifecycleEvent):
    """Emitted when the engine resumes from a paused state."""


@dataclass(frozen=True, slots=True, kw_only=True)
class EngineStopping(EngineLifecycleEvent):
    """Emitted when the engine begins stopping."""


@dataclass(frozen=True, slots=True, kw_only=True)
class EngineStopped(EngineLifecycleEvent):
    """Emitted when the engine has fully stopped."""


@dataclass(frozen=True, slots=True, kw_only=True)
class EngineFailed(EngineLifecycleEvent):
    """Emitted when the engine enters the FAILED state.

    Attributes:
        reason: Optional human-readable failure description.
    """

    reason: str | None = None
