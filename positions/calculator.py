"""Position calculator.

:class:`DefaultPositionCalculator` derives the position figures from the trade
history and standardized prices: average entry/exit, realized and unrealized
P&L, remaining quantity, and duration. It is stateless and consumes only
standardized position models — no exchange-specific calculation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal

from models import OrderSide

from positions.exceptions import PositionCalculationError
from positions.models import PositionCalculation, PositionSide, PositionTrade

__all__ = ["DefaultPositionCalculator"]

_ZERO = Decimal("0")


class DefaultPositionCalculator:
    """Stateless calculation of position figures from trades + prices."""

    def calculate(
        self,
        trades: Sequence[PositionTrade],
        prices: Mapping[str, Decimal],
        now: datetime,
    ) -> PositionCalculation:
        """Return the :class:`PositionCalculation` for ``trades`` at ``now``.

        Raises:
            PositionCalculationError: If trades are empty or oversold.
        """
        if not trades:
            raise PositionCalculationError("no trades to calculate")

        opening_side = trades[0].side
        side = PositionSide.LONG if opening_side is OrderSide.BUY else PositionSide.SHORT

        entry_qty = _ZERO
        entry_notional = _ZERO
        exit_qty = _ZERO
        exit_notional = _ZERO
        total_bought = _ZERO
        total_sold = _ZERO
        exit_count = 0
        for trade in trades:
            if trade.side is OrderSide.BUY:
                total_bought += trade.quantity
            else:
                total_sold += trade.quantity
            if trade.side is opening_side:
                entry_qty += trade.quantity
                entry_notional += trade.quantity * trade.price
            else:
                exit_qty += trade.quantity
                exit_notional += trade.quantity * trade.price
                exit_count += 1

        if exit_qty > entry_qty:
            raise PositionCalculationError("closed more than opened")

        average_entry = entry_notional / entry_qty if entry_qty > 0 else _ZERO
        average_exit = exit_notional / exit_qty if exit_qty > 0 else _ZERO
        quantity = entry_qty - exit_qty

        if side is PositionSide.LONG:
            realized = exit_qty * (average_exit - average_entry)
        else:
            realized = exit_qty * (average_entry - average_exit)

        unrealized = _ZERO
        price = prices.get(trades[0].symbol)
        if quantity > 0 and price is not None:
            if side is PositionSide.LONG:
                unrealized = quantity * (price - average_entry)
            else:
                unrealized = quantity * (average_entry - price)

        duration = Decimal(str((now - trades[0].timestamp).total_seconds()))

        return PositionCalculation(
            side=side,
            quantity=quantity,
            total_bought=total_bought,
            total_sold=total_sold,
            average_entry=average_entry,
            average_exit=average_exit,
            realized_pnl=realized,
            unrealized_pnl=unrealized,
            duration_seconds=duration,
            exit_count=exit_count,
        )
