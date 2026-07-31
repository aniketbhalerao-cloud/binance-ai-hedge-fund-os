"""Unit tests for the domain models: validation and immutability."""

from __future__ import annotations

import dataclasses
import unittest
from decimal import Decimal

from models import Order, OrderSide, OrderType
from tests.support import make_order, make_position, make_trade


class OrderValidationTests(unittest.TestCase):
    def test_valid_order_is_constructed(self) -> None:
        order = make_order(quantity=Decimal("2"), price=Decimal("50"))
        self.assertEqual(order.quantity, Decimal("2"))
        self.assertEqual(order.status.value, "pending")

    def test_non_positive_quantity_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            make_order(quantity=Decimal("0"))

    def test_limit_order_requires_price(self) -> None:
        with self.assertRaises(ValueError):
            Order(
                id="o1",
                symbol="BTCUSDT",
                side=OrderSide.SELL,
                type=OrderType.LIMIT,
                quantity=Decimal("1"),
                price=None,
            )

    def test_order_is_immutable(self) -> None:
        order = make_order()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            order.quantity = Decimal("5")  # type: ignore[misc]


class TradeAndPositionTests(unittest.TestCase):
    def test_trade_rejects_non_positive_price(self) -> None:
        with self.assertRaises(ValueError):
            make_trade(price=Decimal("0"))

    def test_position_rejects_negative_quantity(self) -> None:
        with self.assertRaises(ValueError):
            make_position(quantity=Decimal("-1"))

    def test_models_use_decimal_for_money(self) -> None:
        trade = make_trade()
        position = make_position()
        self.assertIsInstance(trade.price, Decimal)
        self.assertIsInstance(position.entry_price, Decimal)


if __name__ == "__main__":
    unittest.main()
