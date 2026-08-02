"""Unit tests for the market-data pipeline."""

from __future__ import annotations

import unittest
from decimal import Decimal

from core.container import ServiceContainer
from events.base import Event
from events.bus import EventBus
from market_data import (
    CacheKey,
    CandleClosed,
    CandleOpened,
    DefaultNormalizer,
    InMemoryMarketDataCache,
    MarketDataPipelineService,
    MarketDataService,
    MarketSnapshot,
    PriceUpdated,
    ProviderConnected,
    ProviderErrorOccurred,
    register_market_data,
)
from market_data.exceptions import CacheError, MarketDataError, NormalizationError
from market_data.models import OHLCV, PriceTick
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.market_data_fakes import (
    FakeMarketDataProvider,
    make_ohlcv_payload,
    make_order_book_payload,
    make_tick_payload,
    make_trade_payload,
)


class CacheTests(unittest.TestCase):
    def _snap(self) -> MarketSnapshot:
        return MarketSnapshot(exchange="sim", symbol="BTCUSDT")

    def test_update_get_exists_clear_snapshot(self) -> None:
        cache = InMemoryMarketDataCache()
        key = CacheKey("sim", "BTCUSDT")
        self.assertFalse(cache.exists(key))
        self.assertIsNone(cache.get(key))
        cache.update(key, self._snap())
        self.assertTrue(cache.exists(key))
        self.assertEqual(len(cache.snapshot()), 1)
        cache.clear()
        self.assertFalse(cache.exists(key))

    def test_update_rejects_bad_type(self) -> None:
        with self.assertRaises(CacheError):
            InMemoryMarketDataCache().update(CacheKey("s", "x"), object())  # type: ignore[arg-type]


class NormalizerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.n = DefaultNormalizer()

    def test_normalizes_each_kind(self) -> None:
        self.assertIsInstance(self.n.normalize(make_tick_payload()), PriceTick)
        self.assertEqual(self.n.normalize(make_tick_payload()).price, Decimal("100"))
        self.assertIsInstance(self.n.normalize(make_ohlcv_payload()), OHLCV)
        trade = self.n.normalize(make_trade_payload(side="sell"))
        self.assertEqual(trade.side.value, "sell")
        book = self.n.normalize(make_order_book_payload())
        self.assertEqual(book.bids[0], (Decimal("99"), Decimal("1")))

    def test_unknown_kind_raises(self) -> None:
        with self.assertRaises(NormalizationError):
            self.n.normalize({"kind": "nope", "exchange": "s", "symbol": "x"})

    def test_non_mapping_and_bad_decimal_raise(self) -> None:
        with self.assertRaises(NormalizationError):
            self.n.normalize(["not", "a", "mapping"])
        bad = make_tick_payload()
        bad["price"] = "not-a-number"
        with self.assertRaises(NormalizationError):
            self.n.normalize(bad)


class EventAndExceptionTests(unittest.TestCase):
    def test_market_events_inherit_event(self) -> None:
        tick = PriceTick(
            "sim", "BTCUSDT", Decimal("1"), __import__("datetime").datetime.now()
        )
        self.assertIsInstance(PriceUpdated(tick=tick), Event)

    def test_exception_hierarchy(self) -> None:
        self.assertTrue(issubclass(NormalizationError, MarketDataError))
        self.assertTrue(issubclass(CacheError, MarketDataError))


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_relays_and_tracks_connection(self) -> None:
        provider = FakeMarketDataProvider()
        received: list[object] = []

        async def handler(raw: object) -> None:
            received.append(raw)

        provider.on_data(handler)
        self.assertFalse(provider.is_connected)
        await provider.connect()
        self.assertTrue(provider.is_connected)
        await provider.push({"hello": "world"})
        self.assertEqual(received, [{"hello": "world"}])
        await provider.disconnect()
        self.assertFalse(provider.is_connected)


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    def _service(
        self,
    ) -> tuple[MarketDataPipelineService, EventBus, FakeMarketDataProvider]:
        bus = EventBus()
        provider = FakeMarketDataProvider()
        service = MarketDataPipelineService(
            provider,
            DefaultNormalizer(),
            InMemoryMarketDataCache(),
            bus,
            logger=FakeLoggerFactory(),
        )
        return service, bus, provider

    async def test_tick_is_normalized_cached_and_published(self) -> None:
        service, bus, provider = self._service()
        sub = FakeSubscriber()
        bus.subscribe(PriceUpdated, sub.handle)

        await provider.push(make_tick_payload(price="123"))

        self.assertEqual(len(sub.received), 1)
        snapshot = service.get_snapshot(CacheKey("sim", "BTCUSDT"))
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.last_price, Decimal("123"))

    async def test_normalization_failure_is_isolated(self) -> None:
        service, bus, provider = self._service()
        errors = FakeSubscriber()
        bus.subscribe(ProviderErrorOccurred, errors.handle)

        await provider.push({"kind": "bogus", "exchange": "sim", "symbol": "x"})

        self.assertEqual(len(errors.received), 1)  # published, did not raise

    async def test_candle_opened_then_closed(self) -> None:
        service, bus, provider = self._service()
        opened, closed = FakeSubscriber(), FakeSubscriber()
        bus.subscribe(CandleOpened, opened.handle)
        bus.subscribe(CandleClosed, closed.handle)

        await provider.push(make_ohlcv_payload(is_closed=False))
        await provider.push(make_ohlcv_payload(is_closed=True))

        self.assertEqual(len(opened.received), 1)
        self.assertEqual(len(closed.received), 1)

    async def test_start_stop_publishes_connection_events(self) -> None:
        service, bus, provider = self._service()
        connected = FakeSubscriber()
        bus.subscribe(ProviderConnected, connected.handle)
        await service.start()
        self.assertEqual(provider.connect_calls, 1)
        self.assertEqual(len(connected.received), 1)
        await service.stop()
        self.assertEqual(provider.disconnect_calls, 1)


class DependencyInjectionTests(unittest.TestCase):
    def test_registration_resolves_singleton(self) -> None:
        container = ServiceContainer()
        provider = FakeMarketDataProvider()
        register_market_data(container, provider=provider)

        service = container.resolve(MarketDataPipelineService)
        self.assertIs(container.resolve(MarketDataPipelineService), service)
        self.assertIs(container.resolve(MarketDataService), service)


if __name__ == "__main__":
    unittest.main()
