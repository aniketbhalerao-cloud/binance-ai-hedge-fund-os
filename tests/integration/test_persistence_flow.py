"""Integration tests: PersistenceService + Repository + Logger via the container.

These wire the *real* DI container and the *real* in-memory repositories, plus a
fake logger registered as the ``LoggerFactory``, and verify that the components
collaborate correctly end to end. No real exchange, API, or database is touched.
"""

from __future__ import annotations

import unittest

from core.container import ServiceContainer
from core.logging import LoggerFactory
from database import (
    OrderRepository,
    PersistenceService,
    PositionRepository,
    register_persistence,
)
from database.memory import InMemoryOrderRepository
from tests.support import FakeLoggerFactory, make_order, make_position


class PersistenceIntegrationTests(unittest.TestCase):
    def test_default_wiring_persists_through_real_repositories(self) -> None:
        container = ServiceContainer()
        register_persistence(container)

        service = container.resolve(PersistenceService)
        order = make_order(id="o1", symbol="BTCUSDT")
        service.save_order(order)
        service.save_position(make_position(symbol="BTCUSDT"))

        # The repository resolved from the container holds what the service saved.
        orders = container.resolve(OrderRepository)
        self.assertIsInstance(orders, InMemoryOrderRepository)
        self.assertIs(orders.get("o1"), order)
        self.assertEqual(container.resolve(PositionRepository).get("BTCUSDT").symbol,
                         "BTCUSDT")

    def test_service_repository_and_logger_collaborate(self) -> None:
        container = ServiceContainer()
        logger_factory = FakeLoggerFactory()
        # Register the fake as the LoggerFactory the persistence layer will use.
        container.register_instance(LoggerFactory, logger_factory)  # type: ignore[arg-type]
        register_persistence(container, enable_logging=True)

        service = container.resolve(PersistenceService)
        service.save_order(make_order(id="o1"))

        # Repository stored the entity ...
        self.assertIsNotNone(container.resolve(OrderRepository).get("o1"))
        # ... and the logger recorded the operation.
        self.assertIn("save_order",
                      [message for _, message, _ in logger_factory.records])

    def test_persistence_service_is_singleton(self) -> None:
        container = ServiceContainer()
        register_persistence(container)
        self.assertIs(
            container.resolve(PersistenceService),
            container.resolve(PersistenceService),
        )


if __name__ == "__main__":
    unittest.main()
