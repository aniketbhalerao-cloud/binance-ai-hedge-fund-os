"""Unit tests for the Portfolio Management Framework."""

from __future__ import annotations

import dataclasses
import unittest
from decimal import Decimal

from core.container import ServiceContainer
from events.base import Event
from events.bus import EventBus
from models import OrderSide
from portfolio import (
    DefaultCashManager,
    DefaultHoldingsManager,
    DefaultPortfolioAccounting,
    DefaultPortfolioAllocation,
    DefaultPortfolioEngine,
    DefaultPortfolioManager,
    DefaultPortfolioPerformance,
    DefaultPortfolioValuation,
    HoldingsUpdated,
    InMemoryPortfolioRegistry,
    Portfolio,
    PortfolioCash,
    PortfolioError,
    PortfolioManager,
    PortfolioPosition,
    PortfolioResultStatus,
    register_portfolio,
)
from portfolio.exceptions import CashError, HoldingsError, PortfolioNotFoundError
from portfolio.state import PortfolioState, can_transition
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.portfolio_fakes import make_portfolio_context


class StateModelTests(unittest.TestCase):
    def test_transitions(self) -> None:
        self.assertTrue(can_transition(PortfolioState.EMPTY, PortfolioState.ACTIVE))
        self.assertFalse(can_transition(PortfolioState.CLOSED, PortfolioState.ACTIVE))

    def test_models_immutable(self) -> None:
        cash = PortfolioCash(Decimal("100"))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            cash.available = Decimal("0")  # type: ignore[misc]


class HoldingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.h = DefaultHoldingsManager()

    def test_buy_then_average(self) -> None:
        p = self.h.apply(None, "BTC", OrderSide.BUY, Decimal("1"), Decimal("100"))
        assert p is not None
        p = self.h.apply(p, "BTC", OrderSide.BUY, Decimal("1"), Decimal("200"))
        assert p is not None
        self.assertEqual(p.quantity, Decimal("2"))
        self.assertEqual(p.average_cost, Decimal("150"))

    def test_sell_realizes_and_closes(self) -> None:
        p = self.h.apply(None, "BTC", OrderSide.BUY, Decimal("2"), Decimal("100"))
        p = self.h.apply(p, "BTC", OrderSide.SELL, Decimal("1"), Decimal("120"))
        assert p is not None
        self.assertEqual(p.realized_pnl, Decimal("20"))
        closed = self.h.apply(p, "BTC", OrderSide.SELL, Decimal("1"), Decimal("120"))
        self.assertIsNone(closed)

    def test_oversell_raises(self) -> None:
        with self.assertRaises(HoldingsError):
            self.h.apply(None, "BTC", OrderSide.SELL, Decimal("1"), Decimal("100"))


class CashTests(unittest.TestCase):
    def test_apply_and_withdraw(self) -> None:
        c = DefaultCashManager()
        cash = PortfolioCash(Decimal("1000"))
        cash = c.apply(cash, OrderSide.BUY, Decimal("1"), Decimal("100"))
        self.assertEqual(cash.available, Decimal("900"))
        cash = c.apply(cash, OrderSide.SELL, Decimal("1"), Decimal("110"))
        self.assertEqual(cash.available, Decimal("1010"))
        with self.assertRaises(CashError):
            c.withdraw(cash, Decimal("999999"))


class ValuationAllocationPerformanceTests(unittest.TestCase):
    def _portfolio(self) -> Portfolio:
        return Portfolio(
            id="p",
            positions=(PortfolioPosition("BTC", Decimal("1"), Decimal("100")),),
            cash=PortfolioCash(Decimal("50")),
        )

    def test_valuation(self) -> None:
        value = DefaultPortfolioValuation().value(
            self._portfolio(), {"BTC": Decimal("120")}
        )
        self.assertEqual(value.holdings_value, Decimal("120"))
        self.assertEqual(value.unrealized_pnl, Decimal("20"))
        self.assertEqual(value.total_value, Decimal("170"))

    def test_allocation_and_performance(self) -> None:
        value = DefaultPortfolioValuation().value(
            self._portfolio(), {"BTC": Decimal("120")}
        )
        alloc = DefaultPortfolioAllocation().allocate(self._portfolio(), value)
        self.assertIn("BTC", alloc.weights)
        perf = DefaultPortfolioPerformance().measure(value, None)
        self.assertEqual(perf.roi, Decimal("20") / Decimal("100"))


class RegistryTests(unittest.TestCase):
    def test_register_get_missing(self) -> None:
        reg = InMemoryPortfolioRegistry()
        reg.register(Portfolio(id="p"))
        self.assertTrue(reg.exists("p"))
        self.assertEqual(len(reg.list()), 1)
        with self.assertRaises(PortfolioNotFoundError):
            reg.get("missing")


class AccountingTests(unittest.TestCase):
    def test_entry(self) -> None:
        entry = DefaultPortfolioAccounting().entry(make_portfolio_context())
        self.assertEqual(entry.symbol, "BTCUSDT")
        self.assertEqual(entry.side, OrderSide.BUY)


class EventExceptionTests(unittest.TestCase):
    def test_event_inherits(self) -> None:
        self.assertIsInstance(HoldingsUpdated(portfolio_id="p", symbol="X"), Event)

    def test_exception_hierarchy(self) -> None:
        self.assertTrue(issubclass(CashError, PortfolioError))


class ManagerTests(unittest.IsolatedAsyncioTestCase):
    def _manager(self) -> tuple[DefaultPortfolioManager, EventBus]:
        bus = EventBus()
        manager = DefaultPortfolioManager(
            bus,
            InMemoryPortfolioRegistry(),
            DefaultPortfolioAccounting(),
            DefaultHoldingsManager(),
            DefaultCashManager(),
            DefaultPortfolioValuation(),
            DefaultPortfolioAllocation(),
            DefaultPortfolioPerformance(),
            logger=FakeLoggerFactory(),
        )
        return manager, bus

    async def test_buy_then_sell_updates_state(self) -> None:
        manager, bus = self._manager()
        updated = FakeSubscriber()
        bus.subscribe(HoldingsUpdated, updated.handle)

        buy = await manager.update(make_portfolio_context(side=OrderSide.BUY))
        self.assertEqual(buy.status, PortfolioResultStatus.SUCCESS)
        assert buy.portfolio is not None
        self.assertEqual(buy.portfolio.cash.available, Decimal("900"))

        sell = await manager.update(
            make_portfolio_context(
                side=OrderSide.SELL,
                price=Decimal("110"),
                prices={"BTCUSDT": Decimal("110")},
            )
        )
        assert sell.snapshot is not None
        self.assertEqual(sell.snapshot.value.realized_pnl, Decimal("10"))
        self.assertEqual(sell.portfolio.cash.available, Decimal("1010"))  # type: ignore[union-attr]
        self.assertEqual(len(updated.received), 2)

    async def test_closed_portfolio_fails(self) -> None:
        manager, bus = self._manager()
        await manager.update(make_portfolio_context())
        await manager.close("pf-1")
        result = await manager.update(make_portfolio_context())
        self.assertEqual(result.status, PortfolioResultStatus.FAILED)


class DependencyInjectionTests(unittest.TestCase):
    def test_registration_resolves_singletons(self) -> None:
        container = ServiceContainer()
        register_portfolio(container)
        engine = container.resolve(DefaultPortfolioEngine)
        self.assertIs(container.resolve(DefaultPortfolioEngine), engine)
        self.assertIsInstance(
            container.resolve(PortfolioManager), DefaultPortfolioManager
        )


if __name__ == "__main__":
    unittest.main()
