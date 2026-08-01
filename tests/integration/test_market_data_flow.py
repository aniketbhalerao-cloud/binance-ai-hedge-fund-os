"""Integration tests: the market-data pipeline wired via the DI container.

Exercises the full flow (provider → normalizer → cache → event → bus) and its
integration with the Trading Engine, all resolved from the real container.
Deterministic; no timing assertions or sleeps.
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from market_data import (
    CacheKey,
    MarketDataPipelineService,
    PriceUpdated,
    register_market_data,
)
from trading import TradingEngine, register_trading_engine
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.market_data_fakes import FakeMarketDataProvider, make_tick_payload


class MarketDataIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _wire(
        self, provider: FakeMarketDataProvider
    ) -> tuple[ServiceContainer, EventBus]:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_trading_engine(container)
        register_market_data(container, provider=provider)
        return container, container.resolve(EventBus)

    async def test_provider_to_normalizer_to_cache_to_bus(self) -> None:
        provider = FakeMarketDataProvider()
        container, bus = self._wire(provider)
        service = container.resolve(MarketDataPipelineService)
        prices = FakeSubscriber()
        bus.subscribe(PriceUpdated, prices.handle)

        await service.start()
        await provider.push(make_tick_payload(price="200"))

        self.assertEqual(len(prices.received), 1)
        snap = service.get_snapshot(CacheKey("sim", "BTCUSDT"))
        assert snap is not None
        self.assertEqual(snap.last_price, Decimal("200"))

    async def test_replay_compatibility_same_interface(self) -> None:
        # A replay source is just a provider satisfying the same interface.
        payloads = [make_tick_payload(price=str(p)) for p in (100, 101, 102)]
        provider = FakeMarketDataProvider(payloads)
        container, bus = self._wire(provider)
        service = container.resolve(MarketDataPipelineService)
        prices = FakeSubscriber()
        bus.subscribe(PriceUpdated, prices.handle)

        await service.start()
        await provider.replay()

        self.assertEqual(len(prices.received), 3)  # deterministic replay

    async def test_market_data_and_trading_engine_share_the_bus(self) -> None:
        provider = FakeMarketDataProvider()
        container, bus = self._wire(provider)
        engine = container.resolve(TradingEngine)
        service = container.resolve(MarketDataPipelineService)

        # Both are wired through the same container/bus; the engine consumes
        # market events via the bus, never by talking to the provider directly.
        self.assertIsInstance(engine, TradingEngine)
        observed = FakeSubscriber()
        bus.subscribe(PriceUpdated, observed.handle)
        await engine.start()
        await service.start()
        await provider.push(make_tick_payload())
        self.assertEqual(len(observed.received), 1)
        await engine.stop()


if __name__ == "__main__":
    unittest.main()
