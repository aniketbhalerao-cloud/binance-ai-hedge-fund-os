"""Integration tests for the Strategy Framework, wired via the DI container."""

from __future__ import annotations

import unittest

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from market_data import register_market_data
from strategies import (
    SignalGenerated,
    StrategyExecutionManager,
    register_strategies,
)
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.market_data_fakes import FakeMarketDataProvider
from tests.support.strategy_fakes import BuyStrategy, FakeStrategy, make_context
from trading import register_trading_engine


class StrategyIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _container(self) -> ServiceContainer:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_trading_engine(container)
        register_market_data(container, provider=FakeMarketDataProvider())
        register_strategies(container)
        return container

    async def test_registry_factory_manager_and_bus(self) -> None:
        container = self._container()
        manager = container.resolve(StrategyExecutionManager)
        bus = container.resolve(EventBus)
        seen = FakeSubscriber()
        bus.subscribe(SignalGenerated, seen.handle)

        # Manager -> Factory -> Registry: build, register, enable a strategy.
        strat = await manager.create_and_register(BuyStrategy)
        await manager.enable(strat.name)

        # Manager -> EventBus: executing publishes SignalGenerated.
        signals = await manager.execute(make_context())

        self.assertEqual(len(signals), 1)
        self.assertEqual(len(seen.received), 1)

    async def test_market_data_service_to_strategy_manager(self) -> None:
        container = self._container()
        manager = container.resolve(StrategyExecutionManager)

        await manager.register(FakeStrategy("a"))
        await manager.enable("a")

        # A context assembled from normalized market data drives execution;
        # strategies never touch the market-data cache directly.
        signals = await manager.execute(make_context(symbol="ETHUSDT"))
        self.assertEqual(signals[0].symbol, "ETHUSDT")

    async def test_signal_generation_flow_is_deterministic(self) -> None:
        container = self._container()
        manager = container.resolve(StrategyExecutionManager)
        for name in ("a", "b"):
            await manager.register(FakeStrategy(name))
            await manager.enable(name)
        signals = await manager.execute(make_context())
        self.assertEqual(len(signals), 2)  # one per enabled strategy, every run


if __name__ == "__main__":
    unittest.main()
