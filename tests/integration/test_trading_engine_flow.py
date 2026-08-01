"""Integration tests: the trading engine wired via the real DI container.

Exercises collaboration between the TradingEngine and the real EventBus, an
injected LoggerFactory (fake), and the PersistenceService — all resolved from
the container, with deterministic assertions and no timing dependencies.
"""

from __future__ import annotations

import unittest

from core.container import ServiceContainer
from core.logging import LoggerFactory
from database.registration import register_persistence
from database.service import PersistenceService
from events.bus import EventBus
from trading import (
    EngineStarted,
    EngineStopped,
    TradingCoordinator,
    TradingEngine,
    register_trading_engine,
)
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber


class TradingEngineIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _container(self) -> tuple[ServiceContainer, FakeLoggerFactory]:
        container = ServiceContainer()
        logger = FakeLoggerFactory()
        # Register infrastructure exactly as production would, but with a fake
        # logger so logging can be asserted deterministically.
        container.register_instance(LoggerFactory, logger)  # type: ignore[arg-type]
        register_persistence(container)
        register_trading_engine(container)
        return container, logger

    async def test_engine_and_event_bus(self) -> None:
        container, _ = self._container()
        bus = container.resolve(EventBus)
        started, stopped = FakeSubscriber(), FakeSubscriber()
        bus.subscribe(EngineStarted, started.handle)
        bus.subscribe(EngineStopped, stopped.handle)

        engine = container.resolve(TradingEngine)
        await engine.start()
        await engine.stop()

        self.assertEqual(len(started.received), 1)
        self.assertEqual(len(stopped.received), 1)

    async def test_engine_and_logger(self) -> None:
        container, logger = self._container()
        engine = container.resolve(TradingEngine)
        await engine.start()
        await engine.stop()
        self.assertIn("Engine started", logger.logger.messages())

    async def test_engine_and_persistence_reference(self) -> None:
        container, _ = self._container()
        coordinator = container.resolve(TradingCoordinator)
        # The engine only keeps a reference to persistence in Task 11.
        self.assertIsInstance(coordinator.persistence, PersistenceService)

    async def test_engine_singleton_via_container(self) -> None:
        container, _ = self._container()
        self.assertIs(
            container.resolve(TradingEngine), container.resolve(TradingEngine)
        )


if __name__ == "__main__":
    unittest.main()
