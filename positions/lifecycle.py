"""Position lifecycle management.

:class:`DefaultPositionLifecycle` derives the target state from a calculation and
validates transitions. It is separated from tracking so state rules can evolve
without touching quantity/ownership math. Invalid transitions raise a framework
exception.
"""

from __future__ import annotations

from decimal import Decimal

from positions.exceptions import InvalidPositionStateError
from positions.models import PositionCalculation
from positions.state import PositionState, can_transition

__all__ = ["DefaultPositionLifecycle"]

_ZERO = Decimal("0")


class DefaultPositionLifecycle:
    """Derives and validates position lifecycle state."""

    def derive_state(self, calculation: PositionCalculation) -> PositionState:
        """Return the target state implied by ``calculation``."""
        if calculation.quantity <= _ZERO:
            return PositionState.CLOSED
        if calculation.exit_count > 0:
            return PositionState.PARTIALLY_CLOSED
        return PositionState.OPEN

    def validate(self, source: PositionState, target: PositionState) -> None:
        """Validate a transition.

        Raises:
            InvalidPositionStateError: If the transition is not permitted.
        """
        if not can_transition(source, target):
            raise InvalidPositionStateError(
                f"illegal position transition: {source.value} -> {target.value}"
            )
