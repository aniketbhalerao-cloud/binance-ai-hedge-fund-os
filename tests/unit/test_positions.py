"""Unit tests for the Position Management Framework."""

from __future__ import annotations

import dataclasses
import unittest
from datetime import UTC, datetime
from decimal import Decimal

from core.container import ServiceContainer
from events.base import Event
from events.bus import EventBus
from models import OrderSide
from positions import (
    DefaultPositionCalculator,
    DefaultPositionEngine,
    DefaultPositionHistory,
    DefaultPositionLifecycle,
    DefaultPositionManager,
    DefaultPositionMetrics,
    DefaultPositionTracker,
    InMemoryPositionRegistry,
    Position,
    PositionClosed,
    PositionHistory,
    PositionManager,
    PositionOpened,
    PositionResultStatus,
    PositionSide,
    PositionState,
    PositionTrade,
    register_positions,
)
from positions.exceptions import (
    PositionCalculationError,
    PositionError,
    PositionNotFoundError,
)
from positions.state import can_transition
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.position_fakes import FIXED_TIME, make_position_context


def _trade(side: OrderSide, qty: str, price: str) -> PositionTrade:
    return PositionTrade("BTC", side, Decimal(qty), Decimal(price), FIXED_TIME)


class StateModelTests(unittest.TestCase):
    def test_transitions(self) -> None:
        self.assertTrue(can_transition(PositionState.OPEN, PositionState.CLOSED))
        self.assertFalse(can_transition(PositionState.CLOSED, PositionState.OPEN))

    def test_position_immutable(self) -> None:
        pos = Position(
            id="p", symbol="BTC", side=PositionSide.LONG, state=PositionState.OPEN
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            pos.quantity = Decimal("1")  # type: ignore[misc]


class CalculatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.c = DefaultPositionCalculator()
        self.now = datetime(2026, 1, 1, 0, 1, tzinfo=UTC)

    def test_buy_then_partial_sell(self) -> None:
        trades = [_trade(OrderSide.BUY, "2", "100"), _trade(OrderSide.SELL, "1", "120")]
        calc = self.c.calculate(trades, {"BTC": Decimal("120")}, self.now)
        self.assertEqual(calc.side, PositionSide.LONG)
        self.assertEqual(calc.quantity, Decimal("1"))
        self.assertEqual(calc.average_entry, Decimal("100"))
        self.assertEqual(calc.realized_pnl, Decimal("20"))
        self.assertEqual(calc.unrealized_pnl, Decimal("20"))  # 1*(120-100)

    def test_short_position(self) -> None:
        trades = [_trade(OrderSide.SELL, "1", "100")]
        calc = self.c.calculate(trades, {"BTC": Decimal("90")}, self.now)
        self.assertEqual(calc.side, PositionSide.SHORT)
        self.assertEqual(calc.unrealized_pnl, Decimal("10"))  # 1*(100-90)

    def test_oversell_raises(self) -> None:
        trades = [_trade(OrderSide.BUY, "1", "100"), _trade(OrderSide.SELL, "2", "120")]
        with self.assertRaises(PositionCalculationError):
            self.c.calculate(trades, {}, self.now)


class ComponentTests(unittest.TestCase):
    def test_lifecycle_derive(self) -> None:
        lc = DefaultPositionLifecycle()
        calc = DefaultPositionCalculator().calculate(
            [_trade(OrderSide.BUY, "1", "100")], {}, datetime.now(UTC)
        )
        self.assertEqual(lc.derive_state(calc), PositionState.OPEN)

    def test_history_append_is_immutable(self) -> None:
        h = PositionHistory("BTC")
        h2 = DefaultPositionHistory().append(h, _trade(OrderSide.BUY, "1", "100"))
        self.assertEqual(len(h.trades), 0)  # original unchanged
        self.assertEqual(len(h2.trades), 1)

    def test_tracker_build(self) -> None:
        calc = DefaultPositionCalculator().calculate(
            [_trade(OrderSide.BUY, "1", "100")], {}, datetime.now(UTC)
        )
        pos = DefaultPositionTracker().build(
            "BTC", "BTC", calc, PositionState.OPEN, FIXED_TIME, datetime.now(UTC)
        )
        self.assertEqual(pos.quantity, Decimal("1"))

    def test_metrics(self) -> None:
        trades = [_trade(OrderSide.BUY, "1", "100"), _trade(OrderSide.SELL, "1", "120")]
        calc = DefaultPositionCalculator().calculate(trades, {}, datetime.now(UTC))
        m = DefaultPositionMetrics().compute(
            PositionHistory("BTC", tuple(trades)), calc
        )
        self.assertEqual(m.win_rate, Decimal("1"))
        self.assertEqual(m.trade_count, 2)


class RegistryTests(unittest.TestCase):
    def test_register_and_missing(self) -> None:
        reg = InMemoryPositionRegistry()
        reg.register(
            Position(
                id="BTC", symbol="BTC", side=PositionSide.LONG, state=PositionState.OPEN
            ),
            PositionHistory("BTC"),
        )
        self.assertTrue(reg.exists("BTC"))
        with self.assertRaises(PositionNotFoundError):
            reg.get("missing")


class EventExceptionTests(unittest.TestCase):
    def test_event_inherits(self) -> None:
        self.assertIsInstance(PositionOpened(position_id="p", symbol="X"), Event)

    def test_exception_hierarchy(self) -> None:
        self.assertTrue(issubclass(PositionCalculationError, PositionError))


class ManagerTests(unittest.IsolatedAsyncioTestCase):
    def _manager(self) -> tuple[DefaultPositionManager, EventBus]:
        bus = EventBus()
        manager = DefaultPositionManager(
            bus,
            InMemoryPositionRegistry(),
            DefaultPositionTracker(),
            DefaultPositionLifecycle(),
            DefaultPositionCalculator(),
            DefaultPositionHistory(),
            DefaultPositionMetrics(),
            logger=FakeLoggerFactory(),
        )
        return manager, bus

    async def test_open_partial_close_flow(self) -> None:
        manager, bus = self._manager()
        opened, closed = FakeSubscriber(), FakeSubscriber()
        bus.subscribe(PositionOpened, opened.handle)
        bus.subscribe(PositionClosed, closed.handle)

        r1 = await manager.update(
            make_position_context(
                side=OrderSide.BUY, quantity=Decimal("2"), price=Decimal("100")
            )
        )
        self.assertEqual(r1.position.state, PositionState.OPEN)  # type: ignore[union-attr]
        self.assertEqual(len(opened.received), 1)

        await manager.update(
            make_position_context(
                side=OrderSide.SELL,
                quantity=Decimal("1"),
                price=Decimal("120"),
                prices={"BTCUSDT": Decimal("120")},
            )
        )
        r3 = await manager.update(
            make_position_context(
                side=OrderSide.SELL,
                quantity=Decimal("1"),
                price=Decimal("130"),
                prices={"BTCUSDT": Decimal("130")},
            )
        )
        self.assertEqual(r3.position.state, PositionState.CLOSED)  # type: ignore[union-attr]
        self.assertEqual(r3.position.realized_pnl, Decimal("50"))  # type: ignore[union-attr]
        self.assertEqual(len(closed.received), 1)

    async def test_no_trade_fails(self) -> None:
        from portfolio.models import PortfolioResult, PortfolioResultStatus
        from positions.context import PositionContext

        ctx = PositionContext(
            portfolio_result=PortfolioResult(status=PortfolioResultStatus.FAILED)
        )
        result = await manager_update_safe(self._manager()[0], ctx)
        self.assertEqual(result.status, PositionResultStatus.FAILED)


async def manager_update_safe(manager: DefaultPositionManager, ctx: object):
    return await manager.update(ctx)  # type: ignore[arg-type]


class DependencyInjectionTests(unittest.TestCase):
    def test_registration_resolves_singletons(self) -> None:
        container = ServiceContainer()
        register_positions(container)
        engine = container.resolve(DefaultPositionEngine)
        self.assertIs(container.resolve(DefaultPositionEngine), engine)
        self.assertIsInstance(
            container.resolve(PositionManager), DefaultPositionManager
        )


if __name__ == "__main__":
    unittest.main()
