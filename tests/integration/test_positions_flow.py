"""Integration tests for the Position Framework via the DI container."""

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
from positions import (
    DefaultPositionEngine,
    PositionClosed,
    PositionOpened,
    PositionResultStatus,
    PositionState,
    register_positions,
)
from risk import register_risk
from strategies import register_strategies
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.market_data_fakes import FakeMarketDataProvider
from tests.support.position_fakes import make_position_context
from trading import register_trading_engine


class PositionIntegrationTests(unittest.IsolatedAsyncioTestCase):
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
        return container

    async def test_portfolio_to_position_flow(self) -> None:
        container = self._container()
        engine = container.resolve(DefaultPositionEngine)
        bus = container.resolve(EventBus)
        opened = FakeSubscriber()
        bus.subscribe(PositionOpened, opened.handle)

        result = await engine.process(
            make_position_context(
                side=OrderSide.BUY, quantity=Decimal("1"), price=Decimal("100")
            )
        )
        self.assertEqual(result.status, PositionResultStatus.SUCCESS)
        assert result.position is not None
        self.assertEqual(result.position.state, PositionState.OPEN)
        self.assertEqual(len(opened.received), 1)

    async def test_full_lifecycle(self) -> None:
        container = self._container()
        engine = container.resolve(DefaultPositionEngine)
        bus = container.resolve(EventBus)
        closed = FakeSubscriber()
        bus.subscribe(PositionClosed, closed.handle)

        await engine.process(
            make_position_context(
                side=OrderSide.BUY, quantity=Decimal("1"), price=Decimal("100")
            )
        )
        result = await engine.process(
            make_position_context(
                side=OrderSide.SELL,
                quantity=Decimal("1"),
                price=Decimal("140"),
                prices={"BTCUSDT": Decimal("140")},
            )
        )
        assert result.position is not None
        self.assertEqual(result.position.state, PositionState.CLOSED)
        self.assertEqual(result.position.realized_pnl, Decimal("40"))
        self.assertEqual(len(closed.received), 1)

    async def test_engine_singleton(self) -> None:
        container = self._container()
        self.assertIs(
            container.resolve(DefaultPositionEngine),
            container.resolve(DefaultPositionEngine),
        )


if __name__ == "__main__":
    unittest.main()
