"""Integration tests for the Trade Framework via the DI container.

Drives the real Position → Trade handoff: the Position Engine produces a
completed ``PositionResult``, which is wrapped in a ``TradeContext`` and fed to
the Trade Engine. No network, no sleeps — fully deterministic.
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from execution import register_execution
from market_data import register_market_data
from models import OrderSide
from order_management import register_order_management
from portfolio import register_portfolio
from positions import DefaultPositionEngine, register_positions
from risk import register_risk
from strategies import register_strategies
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.market_data_fakes import FakeMarketDataProvider
from tests.support.position_fakes import make_position_context
from trades import (
    DefaultTradeEngine,
    TradeClosed,
    TradeEvent,
    TradeMatched,
    TradeOpened,
    TradeResultStatus,
    TradeState,
    register_trades,
)
from trades.context import TradeContext
from trading import register_trading_engine


class TradeIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _container(self) -> ServiceContainer:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_trading_engine(container)
        register_market_data(container, provider=FakeMarketDataProvider())
        register_strategies(container)
        register_risk(container)
        register_order_management(container)
        register_execution(container)
        register_portfolio(container)
        register_positions(container)
        register_trades(container)
        return container

    async def _pos(
        self, container: ServiceContainer, *, side: OrderSide, price: str
    ):
        engine = container.resolve(DefaultPositionEngine)
        return await engine.process(
            make_position_context(
                side=side, quantity=Decimal("1"), price=Decimal(price)
            )
        )

    async def test_position_to_trade_opens(self) -> None:
        container = self._container()
        trade_engine = container.resolve(DefaultTradeEngine)
        bus = container.resolve(EventBus)
        opened = FakeSubscriber()
        bus.subscribe(TradeOpened, opened.handle)

        pos = await self._pos(container, side=OrderSide.BUY, price="100")
        result = await trade_engine.process(TradeContext(position_result=pos))

        self.assertEqual(result.status, TradeResultStatus.SUCCESS)
        assert result.trade is not None
        self.assertEqual(result.trade.state, TradeState.OPEN)
        self.assertEqual(result.trade.entry_quantity, Decimal("1"))
        self.assertEqual(len(opened.received), 1)

    async def test_complete_trade_lifecycle_workflow(self) -> None:
        container = self._container()
        trade_engine = container.resolve(DefaultTradeEngine)
        bus = container.resolve(EventBus)
        closed = FakeSubscriber()
        matched = FakeSubscriber()
        bus.subscribe(TradeClosed, closed.handle)
        bus.subscribe(TradeMatched, matched.handle)

        pos_open = await self._pos(container, side=OrderSide.BUY, price="100")
        await trade_engine.process(TradeContext(position_result=pos_open))

        pos_close = await self._pos(container, side=OrderSide.SELL, price="110")
        result = await trade_engine.process(TradeContext(position_result=pos_close))

        self.assertEqual(result.status, TradeResultStatus.SUCCESS)
        assert result.trade is not None
        self.assertEqual(result.trade.state, TradeState.CLOSED)
        self.assertEqual(result.trade.exit_quantity, Decimal("1"))
        self.assertEqual(result.trade.realized_pnl, Decimal("10"))
        assert result.snapshot is not None
        self.assertTrue(result.snapshot.analytics.won)
        self.assertEqual(result.snapshot.analytics.gross_profit, Decimal("10"))
        self.assertEqual(len(closed.received), 1)
        self.assertEqual(len(matched.received), 2)  # one per fill

    async def test_manager_publishes_ordered_events_to_bus(self) -> None:
        container = self._container()
        trade_engine = container.resolve(DefaultTradeEngine)
        bus = container.resolve(EventBus)
        allev = FakeSubscriber()
        bus.subscribe(TradeEvent, allev.handle)

        pos = await self._pos(container, side=OrderSide.BUY, price="100")
        await trade_engine.process(TradeContext(position_result=pos))

        names = [type(e).__name__ for e in allev.received]
        self.assertEqual(names[0], "TradeOpened")
        self.assertIn("TradeMatched", names)
        self.assertIn("TradeHistoryUpdated", names)
        self.assertIn("TradeAnalyticsUpdated", names)

    async def test_registry_tracks_trade_across_updates(self) -> None:
        container = self._container()
        trade_engine = container.resolve(DefaultTradeEngine)
        from trades import TradeRegistry

        registry = container.resolve(TradeRegistry)

        pos_open = await self._pos(container, side=OrderSide.BUY, price="100")
        await trade_engine.process(TradeContext(position_result=pos_open))
        self.assertEqual(len(registry.list()), 1)

        pos_close = await self._pos(container, side=OrderSide.SELL, price="110")
        await trade_engine.process(TradeContext(position_result=pos_close))
        # Same symbol → same trade updated in place, not a new one.
        self.assertEqual(len(registry.list()), 1)
        self.assertEqual(registry.get("BTCUSDT").state, TradeState.CLOSED)


if __name__ == "__main__":
    unittest.main()
