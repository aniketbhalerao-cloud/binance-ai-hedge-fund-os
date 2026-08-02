"""Order factory.

:class:`DefaultOrderFactory` converts an approved :class:`RiskDecision` (carried
in an :class:`~order_management.context.OrderContext`) into a standardized,
immutable :class:`~order_management.models.OrderRequest`, applying default
values. It is stateless. It never validates, routes, executes, or talks to
exchanges.
"""

from __future__ import annotations

from decimal import Decimal

from models import OrderSide, OrderType, TimeInForce
from order_management.context import OrderContext
from order_management.exceptions import OrderFactoryError
from order_management.models import (
    OrderIdentifier,
    OrderMetadata,
    OrderRequest,
)
from order_management.state import OrderState
from strategies.signals import SignalDirection

__all__ = ["DefaultOrderFactory"]

#: Signal directions that map to a concrete order side.
_SIDE_BY_DIRECTION: dict[SignalDirection, OrderSide] = {
    SignalDirection.BUY: OrderSide.BUY,
    SignalDirection.INCREASE: OrderSide.BUY,
    SignalDirection.SELL: OrderSide.SELL,
    SignalDirection.REDUCE: OrderSide.SELL,
    SignalDirection.CLOSE: OrderSide.SELL,
}


class DefaultOrderFactory:
    """Builds an :class:`OrderRequest` from an approved order context."""

    def create(self, context: OrderContext) -> OrderRequest:
        """Create a standardized order request.

        Raises:
            OrderFactoryError: If the decision is not approved or the signal
                direction does not correspond to an order (e.g. ``HOLD``).
        """
        if not context.risk_decision.approved:
            raise OrderFactoryError(
                "Cannot create an order from an unapproved decision."
            )

        direction = context.signal.direction
        side = _SIDE_BY_DIRECTION.get(direction)
        if side is None:
            raise OrderFactoryError(
                f"Signal direction {direction.value!r} does not map to an order."
            )

        meta = context.metadata
        order_type = meta.get("order_type", OrderType.MARKET)
        quantity = meta.get("quantity", Decimal("1"))
        price = meta.get("price")
        stop_price = meta.get("stop_price")
        time_in_force = meta.get("time_in_force", TimeInForce.GTC)

        return OrderRequest(
            identifier=OrderIdentifier(),
            symbol=context.symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            time_in_force=time_in_force,
            state=OrderState.CREATED,
            metadata=OrderMetadata({"strategy": context.signal.strategy_name}),
        )
