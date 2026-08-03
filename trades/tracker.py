"""Trade tracker.

:class:`DefaultTradeTracker` maintains individual trades: it derives the
incremental fill from a completed position update (comparing the position's
aggregate bought/sold against what the trade has already tracked) and assembles
the durable :class:`~trades.models.Trade` — quantities, averages, ownership, and
open/close timestamps.

It is stateless (the "previous" trade is passed in, never held) and it does
**not** calculate profit/loss narratives or read market data — the P&L figure it
copies comes from the upstream position calculation.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from models import OrderSide
from positions.models import Position
from trades.exceptions import TradeTrackerError
from trades.models import Trade, TradeFill
from trades.state import TradeState

__all__ = ["DefaultTradeTracker"]

_ZERO = Decimal("0")


class DefaultTradeTracker:
    """Stateless tracking of individual trades (fill aggregation + quantities)."""

    def derive_fill(
        self, previous: Trade | None, position: Position, now: datetime
    ) -> TradeFill:
        """Return the incremental :class:`TradeFill` implied by this update.

        The fill is the delta between the position's cumulative bought/sold and
        what ``previous`` already tracked. Exactly one side normally changes per
        upstream position update (a single directional fill).

        Raises:
            TradeTrackerError: If the update carries no new fill quantity.
        """
        prev_bought = previous.entry_quantity if previous else _ZERO
        prev_sold = previous.exit_quantity if previous else _ZERO
        prev_realized = previous.realized_pnl if previous else _ZERO

        delta_bought = position.total_bought - prev_bought
        delta_sold = position.total_sold - prev_sold
        delta_realized = position.realized_pnl - prev_realized

        buy = delta_bought > _ZERO
        sell = delta_sold > _ZERO
        if not buy and not sell:
            raise TradeTrackerError(
                f"no fill delta in position update for {position.id!r}"
            )

        # A single position update reflects one directional fill; if both sides
        # moved, attribute the fill to the larger delta (deterministic tie-break
        # favours the entry side).
        if buy and (not sell or delta_bought >= delta_sold):
            side, quantity, price = OrderSide.BUY, delta_bought, position.average_entry
        else:
            side, quantity, price = OrderSide.SELL, delta_sold, position.average_exit

        return TradeFill(
            symbol=position.symbol,
            side=side,
            quantity=quantity,
            price=price,
            realized_pnl=delta_realized,
            timestamp=now,
        )

    def build(
        self,
        trade_id: str,
        previous: Trade | None,
        position: Position,
        state: TradeState,
        opened_at: datetime,
        now: datetime,
    ) -> Trade:
        """Assemble the updated :class:`Trade` from the position aggregates."""
        if position.quantity < _ZERO:
            raise TradeTrackerError(f"negative trade quantity for {trade_id!r}")

        fill_count = (previous.fill_count if previous else 0) + 1
        closed_at = now if state is TradeState.CLOSED else None
        return Trade(
            id=trade_id,
            symbol=position.symbol,
            side=position.side,
            state=state,
            entry_quantity=position.total_bought,
            exit_quantity=position.total_sold,
            average_entry=position.average_entry,
            average_exit=position.average_exit,
            realized_pnl=position.realized_pnl,
            fill_count=fill_count,
            opened_at=opened_at,
            closed_at=closed_at,
            updated_at=now,
        )
