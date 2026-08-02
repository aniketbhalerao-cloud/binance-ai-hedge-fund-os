"""Execution lifecycle state machine.

:class:`ExecutionLifecycle` validates and applies
:class:`~execution.state.ExecutionState` transitions, preventing invalid ones.
It is thread-safe and holds no execution or broker logic — one instance tracks a
single execution's state as the manager coordinates it.
"""

from __future__ import annotations

from threading import Lock

from execution.exceptions import ExecutionLifecycleError
from execution.state import ExecutionState, can_transition

__all__ = ["ExecutionLifecycle"]


class ExecutionLifecycle:
    """A thread-safe finite-state machine over :class:`ExecutionState`.

    Args:
        initial: The state to start in (defaults to ``CREATED``).
    """

    def __init__(self, initial: ExecutionState = ExecutionState.CREATED) -> None:
        self._initial = initial
        self._state = initial
        self._lock = Lock()

    def current_state(self) -> ExecutionState:
        """Return the current lifecycle state."""
        with self._lock:
            return self._state

    def can_transition(self, target: ExecutionState) -> bool:
        """Return ``True`` if moving to ``target`` is currently permitted."""
        with self._lock:
            return can_transition(self._state, target)

    def transition(self, target: ExecutionState) -> ExecutionState:
        """Move to ``target`` if the transition is legal.

        Raises:
            ExecutionLifecycleError: If the transition is not permitted.
        """
        with self._lock:
            if not can_transition(self._state, target):
                raise ExecutionLifecycleError(
                    f"Illegal execution transition: "
                    f"{self._state.value} -> {target.value}."
                )
            self._state = target
            return self._state

    def reset(self) -> ExecutionState:
        """Reset the machine back to its initial state."""
        with self._lock:
            self._state = self._initial
            return self._state
