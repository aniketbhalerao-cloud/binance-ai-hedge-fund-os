"""Portfolio accounting and holdings math.

Two stateless components co-located because both record the effect of a
completed execution:

* :class:`DefaultPortfolioAccounting` produces a ledger entry (extracting the
  symbol/side/quantity/price from the execution).
* :class:`DefaultHoldingsManager` applies an execution to a position (add,
  average-cost update, or close), tracking realized P&L.

Neither performs valuation or performance. Both are pure — safe for concurrent use.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from models import OrderSide
from portfolio.context import PortfolioContext
from portfolio.exceptions import AccountingError, HoldingsError
from portfolio.models import LedgerEntry, PortfolioPosition

__all__ = ["DefaultPortfolioAccounting", "DefaultHoldingsManager", "execution_fields"]

_ZERO = Decimal("0")


def execution_fields(
    context: PortfolioContext,
) -> tuple[str, OrderSide, Decimal, Decimal]:
    """Extract ``(symbol, side, quantity, price)`` from a completed execution.

    Raises:
        AccountingError: If the execution is not usable or lacks a price.
    """
    result = context.execution_result
    if result.request is None or not result.ready:
        raise AccountingError("execution is not ready")
    order = result.request.order_request
    price = order.price
    if price is None:
        price = context.prices.get(order.symbol)
    if price is None:
        raise AccountingError(f"no price available for {order.symbol}")
    return order.symbol, order.side, order.quantity, price


class DefaultPortfolioAccounting:
    """Stateless accounting: turns an execution into a ledger entry."""

    def entry(self, context: PortfolioContext) -> LedgerEntry:
        """Return the :class:`LedgerEntry` for the execution in ``context``."""
        symbol, side, quantity, price = execution_fields(context)
        return LedgerEntry(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            timestamp=datetime.now(UTC),
        )


class DefaultHoldingsManager:
    """Stateless holdings math: apply a fill to a position."""

    def apply(
        self,
        position: PortfolioPosition | None,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        price: Decimal,
    ) -> PortfolioPosition | None:
        """Return the position after applying a fill (``None`` when closed).

        Raises:
            HoldingsError: On an oversized sell or invalid quantity.
        """
        if quantity <= 0:
            raise HoldingsError("quantity must be positive")

        if side is OrderSide.BUY:
            if position is None:
                return PortfolioPosition(symbol, quantity, price)
            new_qty = position.quantity + quantity
            new_cost = (position.cost_basis + quantity * price) / new_qty
            return PortfolioPosition(symbol, new_qty, new_cost, position.realized_pnl)

        # SELL
        if position is None or quantity > position.quantity:
            raise HoldingsError("cannot sell more than held")
        realized = position.realized_pnl + quantity * (price - position.average_cost)
        remaining = position.quantity - quantity
        if remaining == _ZERO:
            return None
        return PortfolioPosition(symbol, remaining, position.average_cost, realized)
