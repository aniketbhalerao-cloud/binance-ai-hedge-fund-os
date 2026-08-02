"""Integration tests: Binance adapter plugged into the Exchange Framework."""

from __future__ import annotations

import unittest

from adapters.binance import (
    BINANCE_ADAPTER_NAME,
    BinanceSpotAdapter,
    register_binance_adapter,
)
from adapters.binance.events import BinanceOrderSubmitted
from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from exchange_adapters import (
    DefaultExchangeEngine,
    ExchangeRegistry,
    ExchangeStatus,
    register_exchange_adapters,
)
from tests.support.binance_fakes import (
    FakeHttpTransport,
    make_config,
    make_exchange_request,
)
from tests.support.exchange_fakes import make_exchange_context
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber


class BinanceIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _container(
        self, transport: FakeHttpTransport | None = None
    ) -> ServiceContainer:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_exchange_adapters(container)
        register_binance_adapter(
            container, make_config(), transport=transport or FakeHttpTransport()
        )
        return container

    async def test_adapter_registered_in_framework(self) -> None:
        container = self._container()
        registry = container.resolve(ExchangeRegistry)
        self.assertTrue(registry.exists(BINANCE_ADAPTER_NAME))
        self.assertIsInstance(registry.get(BINANCE_ADAPTER_NAME), BinanceSpotAdapter)

    async def test_exchange_framework_routes_to_binance(self) -> None:
        container = self._container()
        bus = container.resolve(EventBus)
        submitted = FakeSubscriber()
        bus.subscribe(BinanceOrderSubmitted, submitted.handle)

        engine = container.resolve(DefaultExchangeEngine)
        # Route to the binance adapter via context metadata.
        result = await engine.process(
            make_exchange_context(exchange="binance", adapter=BINANCE_ADAPTER_NAME)
        )
        self.assertEqual(result.status, ExchangeStatus.READY)
        self.assertEqual(len(submitted.received), 1)

    async def test_direct_order_submission_flow(self) -> None:
        container = self._container()
        adapter = container.resolve(BinanceSpotAdapter)
        response = await adapter.submit(make_exchange_request())
        self.assertTrue(response.accepted)

    async def test_order_cancellation_flow(self) -> None:
        container = self._container()
        adapter = container.resolve(BinanceSpotAdapter)
        response = await adapter.cancel_order("BTCUSDT", "123")
        self.assertTrue(response.accepted)


if __name__ == "__main__":
    unittest.main()
