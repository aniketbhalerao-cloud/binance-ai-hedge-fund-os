"""Integration tests for the Order Management Framework via the DI container."""

from __future__ import annotations

import unittest

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from market_data import register_market_data
from order_management import (
    DefaultOrderEngine,
    OrderCreated,
    OrderReadyForExecution,
    OrderState,
    register_order_management,
)
from risk import register_risk
from strategies import register_strategies
from trading import register_trading_engine
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.market_data_fakes import FakeMarketDataProvider
from tests.support.order_fakes import make_order_context


class OrderIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _container(self) -> ServiceContainer:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_trading_engine(container)
        register_market_data(container, provider=FakeMarketDataProvider())
        register_strategies(container)
        register_risk(container)
        register_order_management(container)
        return container

    async def test_risk_decision_to_order_flow(self) -> None:
        container = self._container()
        engine = container.resolve(DefaultOrderEngine)
        bus = container.resolve(EventBus)
        created, ready = FakeSubscriber(), FakeSubscriber()
        bus.subscribe(OrderCreated, created.handle)
        bus.subscribe(OrderReadyForExecution, ready.handle)

        # Approved RiskDecision (in the context) -> ready-for-execution order.
        result = await engine.process(make_order_context())

        self.assertEqual(result.state, OrderState.READY_FOR_EXECUTION)
        self.assertEqual(len(created.received), 1)
        self.assertEqual(len(ready.received), 1)

    async def test_full_pipeline_deterministic(self) -> None:
        container = self._container()
        engine = container.resolve(DefaultOrderEngine)
        results = [
            await engine.process(make_order_context(symbol=s))
            for s in ("BTCUSDT", "ETHUSDT")
        ]
        self.assertTrue(all(r.ready for r in results))
        self.assertEqual(results[1].request.symbol, "ETHUSDT")  # type: ignore[union-attr]

    async def test_engine_singleton_via_container(self) -> None:
        container = self._container()
        self.assertIs(
            container.resolve(DefaultOrderEngine), container.resolve(DefaultOrderEngine)
        )


if __name__ == "__main__":
    unittest.main()
