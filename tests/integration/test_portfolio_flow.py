"""Integration tests for the Portfolio Framework via the DI container."""

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
from portfolio import (
    DefaultPortfolioEngine,
    PortfolioResultStatus,
    PortfolioUpdated,
    PortfolioValuationCompleted,
    register_portfolio,
)
from risk import register_risk
from strategies import register_strategies
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.market_data_fakes import FakeMarketDataProvider
from tests.support.portfolio_fakes import make_portfolio_context
from trading import register_trading_engine


class PortfolioIntegrationTests(unittest.IsolatedAsyncioTestCase):
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
        return container

    async def test_execution_to_portfolio_flow(self) -> None:
        container = self._container()
        engine = container.resolve(DefaultPortfolioEngine)
        bus = container.resolve(EventBus)
        updated, valued = FakeSubscriber(), FakeSubscriber()
        bus.subscribe(PortfolioUpdated, updated.handle)
        bus.subscribe(PortfolioValuationCompleted, valued.handle)

        result = await engine.process(make_portfolio_context())

        self.assertEqual(result.status, PortfolioResultStatus.SUCCESS)
        self.assertEqual(len(updated.received), 1)
        self.assertEqual(len(valued.received), 1)

    async def test_full_buy_sell_cycle(self) -> None:
        container = self._container()
        engine = container.resolve(DefaultPortfolioEngine)
        await engine.process(make_portfolio_context(side=OrderSide.BUY))
        result = await engine.process(
            make_portfolio_context(
                side=OrderSide.SELL,
                price=Decimal("130"),
                prices={"BTCUSDT": Decimal("130")},
            )
        )
        assert result.snapshot is not None
        self.assertEqual(result.snapshot.value.realized_pnl, Decimal("30"))
        self.assertEqual(result.portfolio.cash.available, Decimal("1030"))  # type: ignore[union-attr]

    async def test_engine_singleton(self) -> None:
        container = self._container()
        self.assertIs(
            container.resolve(DefaultPortfolioEngine),
            container.resolve(DefaultPortfolioEngine),
        )


if __name__ == "__main__":
    unittest.main()
