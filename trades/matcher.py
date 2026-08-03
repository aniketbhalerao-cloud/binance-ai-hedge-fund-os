"""Trade matcher.

:class:`DefaultTradeMatcher` correlates entries against exits for a trade: it
reports how much of the entered quantity has been matched by exits and whether
the trade is a completed round trip. It is kept separate from tracking so the
correlation policy can evolve (e.g. FIFO/LIFO lot matching, multi-leg) without
touching quantity aggregation, and separate from analytics so matching stays a
pure structural fact independent of P&L.

Stateless and pure: it reads only the standardized position aggregates and the
triggering fill.
"""

from __future__ import annotations

from decimal import Decimal

from models import OrderSide
from positions.models import Position
from trades.models import TradeFill, TradeMatch

__all__ = ["DefaultTradeMatcher"]

_ZERO = Decimal("0")


class DefaultTradeMatcher:
    """Stateless entry/exit correlation for a trade."""

    def match(self, position: Position, fill: TradeFill) -> TradeMatch:
        """Return the :class:`TradeMatch` for the current position + fill."""
        entry = position.total_bought
        exit_ = position.total_sold
        matched = exit_ if exit_ < entry else entry
        completed = entry > _ZERO and exit_ >= entry
        return TradeMatch(
            entry_quantity=entry,
            exit_quantity=exit_,
            matched_quantity=matched,
            is_entry=fill.side is OrderSide.BUY,
            is_exit=fill.side is OrderSide.SELL,
            completed=completed,
        )
