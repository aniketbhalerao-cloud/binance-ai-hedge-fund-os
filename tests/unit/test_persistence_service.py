"""Unit tests for :class:`~database.service.PersistenceService`.

The service is tested in isolation with fake repositories (to assert it
delegates correctly) and a fake logger (to assert it logs when configured).
"""

from __future__ import annotations

import unittest

from database.service import PersistenceService
from tests.support import (
    FakeLoggerFactory,
    FakeOrderRepository,
    FakePositionRepository,
    FakeTradeRepository,
    make_order,
    make_position,
    make_trade,
)


class PersistenceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.orders = FakeOrderRepository()
        self.trades = FakeTradeRepository()
        self.positions = FakePositionRepository()
        self.service = PersistenceService(self.orders, self.trades, self.positions)

    def test_save_order_delegates_to_repository(self) -> None:
        order = make_order(id="o1")
        self.service.save_order(order)
        self.assertEqual(self.orders.calls, [("add", order)])
        self.assertIs(self.service.get_order("o1"), order)

    def test_record_trade_delegates_to_repository(self) -> None:
        trade = make_trade(id="t1")
        self.service.record_trade(trade)
        self.assertIn(("add", trade), self.trades.calls)

    def test_save_position_delegates_to_repository(self) -> None:
        position = make_position(symbol="BTCUSDT")
        self.service.save_position(position)
        self.assertIs(self.service.get_position("BTCUSDT"), position)

    def test_without_logger_no_logging_occurs(self) -> None:
        # The default service has no logger; operations must still succeed.
        self.service.save_order(make_order())
        self.assertIsNone(self.service._log)


class PersistenceServiceLoggingTests(unittest.TestCase):
    def test_service_logs_via_injected_logger(self) -> None:
        logger_factory = FakeLoggerFactory()
        service = PersistenceService(
            FakeOrderRepository(),
            FakeTradeRepository(),
            FakePositionRepository(),
            logger=logger_factory,
        )

        service.save_order(make_order(id="o1"))

        levels = {level for level, _, _ in logger_factory.records}
        messages = [message for _, message, _ in logger_factory.records]
        extras = [extra for _, _, extra in logger_factory.records]
        self.assertIn("save_order", messages)
        self.assertEqual(levels, {"DEBUG"})
        self.assertEqual(extras[0]["order_id"], "o1")


if __name__ == "__main__":
    unittest.main()
