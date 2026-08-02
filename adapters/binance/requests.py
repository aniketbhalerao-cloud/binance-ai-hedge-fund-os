"""Binance Spot request models and request validation.

Defines the Binance-shaped order/cancel request objects (Binance field names) and
a stateless validator that checks a request before transmission. No business
logic, risk checks, or network access here.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from adapters.binance.models import (
    BinanceOrderType,
    BinanceSide,
    BinanceTimeInForce,
)

__all__ = ["BinanceOrderRequest", "BinanceCancelRequest", "BinanceRequestValidator"]

_PRICE_REQUIRED = {BinanceOrderType.LIMIT, BinanceOrderType.STOP_LOSS_LIMIT}


@dataclass(frozen=True, slots=True)
class BinanceOrderRequest:
    """A Binance Spot ``POST /api/v3/order`` request model."""

    symbol: str
    side: BinanceSide
    type: BinanceOrderType
    quantity: Decimal
    price: Decimal | None = None
    time_in_force: BinanceTimeInForce | None = None
    new_client_order_id: str | None = None

    def to_params(self) -> dict[str, Any]:
        """Return the Binance API parameter mapping (omitting empty fields)."""
        params: dict[str, Any] = {
            "symbol": self.symbol,
            "side": self.side.value,
            "type": self.type.value,
            "quantity": format(self.quantity, "f"),
        }
        if self.price is not None:
            params["price"] = format(self.price, "f")
        if self.time_in_force is not None:
            params["timeInForce"] = self.time_in_force.value
        if self.new_client_order_id is not None:
            params["newClientOrderId"] = self.new_client_order_id
        return params


@dataclass(frozen=True, slots=True)
class BinanceCancelRequest:
    """A Binance Spot ``DELETE /api/v3/order`` request model."""

    symbol: str
    order_id: str

    def to_params(self) -> dict[str, Any]:
        return {"symbol": self.symbol, "orderId": self.order_id}


class BinanceRequestValidator:
    """Stateless validator for :class:`BinanceOrderRequest` objects."""

    def validate(self, request: BinanceOrderRequest) -> tuple[str, ...]:
        """Return a tuple of validation error messages (empty when valid)."""
        errors: list[str] = []
        if not request.symbol:
            errors.append("symbol is required")
        if request.quantity <= 0:
            errors.append("quantity must be greater than 0")
        if request.type in _PRICE_REQUIRED:
            if request.price is None or request.price <= 0:
                errors.append(f"{request.type.value} requires a positive price")
            if request.time_in_force is None:
                errors.append(f"{request.type.value} requires timeInForce")
        return tuple(errors)
