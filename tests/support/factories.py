"""Deterministic sample-model factories for tests.

Each factory returns a valid domain model with sensible defaults that any field
can override. Identifiers come from a monotonic counter so generated models are
unique and reproducible within a test run; timestamps are left to the models'
own defaults and should not be asserted upon.
"""

from __future__ import annotations

import itertools
from decimal import Decimal

from models import (
    Order,
    OrderSide,
    OrderType,
    Position,
    PositionSide,
    Trade,
)

_ids = itertools.count(1)


def _next_id(prefix: str) -> str:
    """Return a unique, reproducible identifier for ``prefix``."""
    return f"{prefix}-{next(_ids)}"


def make_order(
    *,
    id: str | None = None,
    symbol: str = "BTCUSDT",
    side: OrderSide = OrderSide.BUY,
    type: OrderType = OrderType.LIMIT,
    quantity: Decimal = Decimal("1"),
    price: Decimal | None = Decimal("100"),
) -> Order:
    """Build a valid :class:`~models.order.Order` for tests."""
    return Order(
        id=id or _next_id("order"),
        symbol=symbol,
        side=side,
        type=type,
        quantity=quantity,
        price=price,
    )


def make_trade(
    *,
    id: str | None = None,
    order_id: str = "order-1",
    symbol: str = "BTCUSDT",
    side: OrderSide = OrderSide.BUY,
    quantity: Decimal = Decimal("1"),
    price: Decimal = Decimal("100"),
    fee: Decimal = Decimal("0.1"),
    fee_currency: str = "USDT",
) -> Trade:
    """Build a valid :class:`~models.trade.Trade` for tests."""
    return Trade(
        id=id or _next_id("trade"),
        order_id=order_id,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        fee=fee,
        fee_currency=fee_currency,
    )


def make_position(
    *,
    symbol: str = "BTCUSDT",
    side: PositionSide = PositionSide.LONG,
    quantity: Decimal = Decimal("1"),
    entry_price: Decimal = Decimal("100"),
) -> Position:
    """Build a valid :class:`~models.position.Position` for tests."""
    return Position(
        symbol=symbol,
        side=side,
        quantity=quantity,
        entry_price=entry_price,
    )
