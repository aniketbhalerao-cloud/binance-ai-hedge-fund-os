"""Integration tests for the Execution Framework via the DI container."""

from __future__ import annotations

import unittest

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from execution import (
    DefaultExecutionEngine,
    ExecutionCompleted,
    ExecutionStarted,
    ExecutionStatus,
    register_execution,
)
from market_data import register_market_data
from order_management import register_order_management
from risk import register_risk
from strategies import register_strategies
from tests.support.execution_fakes import make_execution_context
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.market_data_fakes import FakeMarketDataProvider
from trading import register_trading_engine


class ExecutionIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _container(self) -> ServiceContainer:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_trading_engine(container)
        register_market_data(container, provider=FakeMarketDataProvider())
        register_strategies(container)
        register_risk(container)
        register_order_management(container)
        register_execution(container)
        return container

    async def test_order_ready_to_execution_flow(self) -> None:
        container = self._container()
        engine = container.resolve(DefaultExecutionEngine)
        bus = container.resolve(EventBus)
        started, completed = FakeSubscriber(), FakeSubscriber()
        bus.subscribe(ExecutionStarted, started.handle)
        bus.subscribe(ExecutionCompleted, completed.handle)

        # A ready OrderResult (in the context) -> coordinated, ready-for-adapter.
        result = await engine.process(make_execution_context())

        self.assertEqual(result.status, ExecutionStatus.READY)
        self.assertEqual(len(started.received), 1)
        self.assertEqual(len(completed.received), 1)

    async def test_full_pipeline_deterministic(self) -> None:
        container = self._container()
        engine = container.resolve(DefaultExecutionEngine)
        results = [
            await engine.process(make_execution_context(symbol=s))
            for s in ("BTCUSDT", "ETHUSDT")
        ]
        self.assertTrue(all(r.ready for r in results))
        self.assertEqual(results[1].request.symbol, "ETHUSDT")  # type: ignore[union-attr]

    async def test_engine_singleton_via_container(self) -> None:
        container = self._container()
        self.assertIs(
            container.resolve(DefaultExecutionEngine),
            container.resolve(DefaultExecutionEngine),
        )


if __name__ == "__main__":
    unittest.main()
