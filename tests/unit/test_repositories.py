"""Unit tests for repository behaviour, exercised through the fake repositories.

The fakes honour the same :class:`~database.interfaces.Repository` contract as
the production in-memory repositories, so these tests validate the contract that
every implementation (in-memory today, SQLite/PostgreSQL later) must satisfy.
"""

from __future__ import annotations

import unittest

from tests.support import (
    FakeOrderRepository,
    FakePositionRepository,
    make_order,
    make_position,
)


class OrderRepositoryContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = FakeOrderRepository()

    def test_add_then_get_returns_entity(self) -> None:
        order = make_order(id="o1")
        self.repo.add(order)
        self.assertIs(self.repo.get("o1"), order)

    def test_get_missing_returns_none(self) -> None:
        self.assertIsNone(self.repo.get("absent"))

    def test_add_replaces_existing_key(self) -> None:
        self.repo.add(make_order(id="o1", symbol="BTCUSDT"))
        self.repo.add(make_order(id="o1", symbol="ETHUSDT"))
        self.assertEqual(len(self.repo.list()), 1)
        self.assertEqual(self.repo.get("o1").symbol, "ETHUSDT")

    def test_remove_reports_whether_present(self) -> None:
        self.repo.add(make_order(id="o1"))
        self.assertTrue(self.repo.remove("o1"))
        self.assertFalse(self.repo.remove("o1"))

    def test_list_by_symbol_filters(self) -> None:
        self.repo.add(make_order(id="o1", symbol="BTCUSDT"))
        self.repo.add(make_order(id="o2", symbol="ETHUSDT"))
        self.repo.add(make_order(id="o3", symbol="BTCUSDT"))
        symbols = {o.id for o in self.repo.list_by_symbol("BTCUSDT")}
        self.assertEqual(symbols, {"o1", "o3"})

    def test_clear_empties_the_store(self) -> None:
        self.repo.add(make_order())
        self.repo.clear()
        self.assertEqual(self.repo.list(), [])


class PositionRepositoryKeyingTests(unittest.TestCase):
    def test_position_is_keyed_by_symbol(self) -> None:
        repo = FakePositionRepository()
        repo.add(make_position(symbol="BTCUSDT"))
        self.assertIsNotNone(repo.get("BTCUSDT"))


if __name__ == "__main__":
    unittest.main()
