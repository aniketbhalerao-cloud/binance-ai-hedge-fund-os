"""Trade lifecycle management.

:class:`DefaultTradeLifecycle` derives the target state from a match result (plus
whether the underlying position has closed) and validates transitions. It is
separated from tracking and matching so state rules can evolve without touching
quantity math or correlation. Invalid transitions raise a framework exception.
"""

from __future__ import annotations

from decimal import Decimal

from trades.exceptions import InvalidTradeStateError
from trades.models import TradeMatch
from trades.state import TradeState, can_transition

__all__ = ["DefaultTradeLifecycle"]

_ZERO = Decimal("0")


class DefaultTradeLifecycle:
    """Derives and validates trade lifecycle state."""

    def derive_state(self, match: TradeMatch, position_closed: bool) -> TradeState:
        """Return the target state implied by ``match`` and position closure."""
        if match.entry_quantity <= _ZERO:
            return TradeState.PENDING
        if position_closed:
            return TradeState.CLOSED
        if match.completed:
            return TradeState.FILLED
        if match.exit_quantity > _ZERO:
            return TradeState.PARTIALLY_FILLED
        return TradeState.OPEN

    def validate(self, source: TradeState, target: TradeState) -> None:
        """Validate a transition.

        Raises:
            InvalidTradeStateError: If the transition is not permitted.
        """
        if not can_transition(source, target):
            raise InvalidTradeStateError(
                f"illegal trade transition: {source.value} -> {target.value}"
            )
