"""Request translation: standardized ExchangeRequest → Binance request model.

Stateless mapping from the framework's
:class:`~exchange_adapters.models.ExchangeRequest` (carrying an order-management
``OrderRequest``) into a :class:`~adapters.binance.requests.BinanceOrderRequest`.
No business logic — field mapping only.
"""

from __future__ import annotations

from adapters.binance.models import (
    BinanceOrderType,
    BinanceSide,
    BinanceTimeInForce,
)
from adapters.binance.requests import BinanceOrderRequest
from exchange_adapters.models import ExchangeRequest
from models import OrderSide, OrderType, TimeInForce

__all__ = ["BinanceRequestTranslator"]

_SIDE: dict[OrderSide, BinanceSide] = {
    OrderSide.BUY: BinanceSide.BUY,
    OrderSide.SELL: BinanceSide.SELL,
}
_TYPE: dict[OrderType, BinanceOrderType] = {
    OrderType.MARKET: BinanceOrderType.MARKET,
    OrderType.LIMIT: BinanceOrderType.LIMIT,
    OrderType.STOP: BinanceOrderType.STOP_LOSS,
    OrderType.STOP_LIMIT: BinanceOrderType.STOP_LOSS_LIMIT,
}
_TIF: dict[TimeInForce, BinanceTimeInForce] = {
    TimeInForce.GTC: BinanceTimeInForce.GTC,
    TimeInForce.IOC: BinanceTimeInForce.IOC,
    TimeInForce.FOK: BinanceTimeInForce.FOK,
}


class BinanceRequestTranslator:
    """Translates a standardized exchange request into a Binance order request."""

    def translate(self, request: ExchangeRequest) -> BinanceOrderRequest:
        """Map ``request`` to a :class:`BinanceOrderRequest`."""
        order = request.execution_request.order_request
        binance_type = _TYPE[order.order_type]
        # Binance requires timeInForce only for limit-style orders.
        tif = (
            _TIF[order.time_in_force]
            if binance_type
            in {
                BinanceOrderType.LIMIT,
                BinanceOrderType.STOP_LOSS_LIMIT,
            }
            else None
        )
        return BinanceOrderRequest(
            symbol=order.symbol,
            side=_SIDE[order.side],
            type=binance_type,
            quantity=order.quantity,
            price=order.price,
            time_in_force=tif,
            new_client_order_id=order.identifier.id,
        )
