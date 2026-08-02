"""Position tracker.

:class:`DefaultPositionTracker` assembles a durable :class:`Position` from a
calculation and the resolved lifecycle state, managing quantity, ownership, and
open/close timestamps. It does **not** value positions or read market data — the
price-dependent figures come from the calculator.
"""

from __future__ import annotations

from datetime import datetime

from positions.models import Position, PositionCalculation
from positions.state import PositionState

__all__ = ["DefaultPositionTracker"]


class DefaultPositionTracker:
    """Builds the durable position record (quantity / ownership / timestamps)."""

    def build(
        self,
        position_id: str,
        symbol: str,
        calculation: PositionCalculation,
        state: PositionState,
        opened_at: datetime,
        now: datetime,
    ) -> Position:
        """Assemble the updated :class:`Position`."""
        closed_at = now if state is PositionState.CLOSED else None
        return Position(
            id=position_id,
            symbol=symbol,
            side=calculation.side,
            state=state,
            quantity=calculation.quantity,
            average_entry=calculation.average_entry,
            average_exit=calculation.average_exit,
            realized_pnl=calculation.realized_pnl,
            total_bought=calculation.total_bought,
            total_sold=calculation.total_sold,
            opened_at=opened_at,
            closed_at=closed_at,
            updated_at=now,
        )
