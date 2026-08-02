"""Integration tests for the Exchange Adapter Framework via the DI container."""

from __future__ import annotations

import unittest

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from exchange_adapters import (
    DefaultExchangeEngine,
    ExchangeAdapterRegistry,
    ExchangeRegistry,
    ExchangeRoutingCompleted,
    ExchangeStatus,
    register_exchange_adapters,
)
from execution import register_execution
from market_data import register_market_data
from order_management import register_order_management
from risk import register_risk
from strategies import register_strategies
from tests.support.exchange_fakes import FakeExchangeAdapter, make_exchange_context
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.market_data_fakes import FakeMarketDataProvider
from trading import register_trading_engine


class ExchangeIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _container(self) -> ServiceContainer:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_trading_engine(container)
        register_market_data(container, provider=FakeMarketDataProvider())
        register_strategies(container)
        register_risk(container)
        register_order_management(container)
        register_execution(container)
        register_exchange_adapters(container)
        return container

    async def test_execution_to_exchange_flow(self) -> None:
        container = self._container()
        engine = container.resolve(DefaultExchangeEngine)
        bus = container.resolve(EventBus)
        routed = FakeSubscriber()
        bus.subscribe(ExchangeRoutingCompleted, routed.handle)

        # ready ExecutionResult -> coordinated, ready-for-broker-adapter.
        result = await engine.process(make_exchange_context())

        self.assertEqual(result.status, ExchangeStatus.READY)
        self.assertEqual(len(routed.received), 1)

    async def test_registry_to_manager_adapter_submit(self) -> None:
        container = self._container()
        # Registry -> Manager: a registered adapter receives the request.
        registry = container.resolve(ExchangeRegistry)
        adapter = FakeExchangeAdapter("default")
        registry.register(adapter)
        engine = container.resolve(DefaultExchangeEngine)
        result = await engine.process(make_exchange_context())
        self.assertEqual(result.status, ExchangeStatus.READY)
        self.assertEqual(len(adapter.submitted), 1)

    async def test_engine_singleton_via_container(self) -> None:
        container = self._container()
        self.assertIs(
            container.resolve(DefaultExchangeEngine),
            container.resolve(DefaultExchangeEngine),
        )
        self.assertIsInstance(
            container.resolve(ExchangeRegistry), ExchangeAdapterRegistry
        )


if __name__ == "__main__":
    unittest.main()
