"""Standardized, generic order models.

Typed, immutable representations of the common order kinds (market, limit, stop,
stop-limit). They are exchange-independent and carry no venue-specific format;
each converts to the canonical :class:`~order_management.models.OrderRequest`.
No exchange-specific order formats are implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from models import OrderSide, OrderType, TimeInForce

from order_management.models import OrderIdentifier, OrderMetadata, OrderRequest

__all__ = ["MarketOrder", "LimitOrder", "StopOrder", "StopLimitOrder"]


@dataclass(frozen=True, slots=True)
class MarketOrder:
    """A generic market order."""

    symbol: str
    side: OrderSide
    quantity: Decimal

    def to_request(
        self,
        identifier: OrderIdentifier | None = None,
        metadata: OrderMetadata | None = None,
    ) -> OrderRequest:
        return OrderRequest(
            identifier=identifier or OrderIdentifier(),
            symbol=self.symbol,
            side=self.side,
            order_type=OrderType.MARKET,
            quantity=self.quantity,
            metadata=metadata or OrderMetadata(),
        )


@dataclass(frozen=True, slots=True)
class LimitOrder:
    """A generic limit order."""

    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Decimal
    time_in_force: TimeInForce = TimeInForce.GTC

    def to_request(
        self,
        identifier: OrderIdentifier | None = None,
        metadata: OrderMetadata | None = None,
    ) -> OrderRequest:
        return OrderRequest(
            identifier=identifier or OrderIdentifier(),
            symbol=self.symbol,
            side=self.side,
            order_type=OrderType.LIMIT,
            quantity=self.quantity,
            price=self.price,
            time_in_force=self.time_in_force,
            metadata=metadata or OrderMetadata(),
        )


@dataclass(frozen=True, slots=True)
class StopOrder:
    """A generic stop (stop-market) order."""

    symbol: str
    side: OrderSide
    quantity: Decimal
    stop_price: Decimal

    def to_request(
        self,
        identifier: OrderIdentifier | None = None,
        metadata: OrderMetadata | None = None,
    ) -> OrderRequest:
        return OrderRequest(
            identifier=identifier or OrderIdentifier(),
            symbol=self.symbol,
            side=self.side,
            order_type=OrderType.STOP,
            quantity=self.quantity,
            stop_price=self.stop_price,
            metadata=metadata or OrderMetadata(),
        )


@dataclass(frozen=True, slots=True)
class StopLimitOrder:
    """A generic stop-limit order."""

    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Decimal
    stop_price: Decimal
    time_in_force: TimeInForce = TimeInForce.GTC

    def to_request(
        self,
        identifier: OrderIdentifier | None = None,
        metadata: OrderMetadata | None = None,
    ) -> OrderRequest:
        return OrderRequest(
            identifier=identifier or OrderIdentifier(),
            symbol=self.symbol,
            side=self.side,
            order_type=OrderType.STOP_LIMIT,
            quantity=self.quantity,
            price=self.price,
            stop_price=self.stop_price,
            time_in_force=self.time_in_force,
            metadata=metadata or OrderMetadata(),
        )
