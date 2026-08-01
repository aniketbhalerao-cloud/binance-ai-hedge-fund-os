"""Market-data service.

:class:`MarketDataPipelineService` is the coordination point of the pipeline. It
wires the injected provider, normalizer, cache, event bus, and logger together:

    raw payload → provider → normalizer → domain model → cache → market event → bus

It performs orchestration only — no trading, strategy, risk, persistence, or
exchange logic. Every dependency is injected; nothing is constructed here.
Failures are isolated: a normalization/provider error is logged and published as
a :class:`ProviderErrorOccurred` event, never raised into the Trading Engine.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from market_data.events import (
    CandleClosed,
    CandleOpened,
    CandleUpdated,
    MarketDataReceived,
    MarketEvent,
    OrderBookUpdated,
    PriceUpdated,
    ProviderConnected,
    ProviderDisconnected,
    ProviderErrorOccurred,
    TradeReceived,
)
from market_data.exceptions import MarketDataError
from market_data.interfaces import (
    MarketDataCache,
    MarketDataNormalizer,
    MarketDataProvider,
    NormalizedData,
    RawPayload,
)
from market_data.models import (
    OHLCV,
    CacheKey,
    MarketSnapshot,
    OrderBookSnapshot,
    PriceTick,
    TradeTick,
)

if TYPE_CHECKING:
    from trading.engine import TradingEngine

__all__ = ["MarketDataPipelineService"]


class MarketDataPipelineService:
    """Coordinates the market-data pipeline stages.

    Args:
        provider: The raw-data source (abstraction).
        normalizer: Converts raw payloads to domain models (abstraction).
        cache: Latest-snapshot store (abstraction).
        bus: The shared event bus used to publish market events.
        logger: Optional logger factory for infrastructure logs.
        engine: Optional reference to the Trading Engine (public interface only);
            held for wiring, never driven — the engine consumes market events via
            the event bus, not by direct calls.
    """

    def __init__(
        self,
        provider: MarketDataProvider,
        normalizer: MarketDataNormalizer,
        cache: MarketDataCache,
        bus: EventBus,
        logger: LoggerFactory | None = None,
        engine: TradingEngine | None = None,
    ) -> None:
        self._provider = provider
        self._normalizer = normalizer
        self._cache = cache
        self._bus = bus
        self._engine = engine
        self._log = logger.get_logger("market_data.service") if logger else None
        # The provider pushes raw payloads to us; we own the processing pipeline.
        self._provider.on_data(self._on_raw)

    # -- lifecycle ----------------------------------------------------------

    async def start(self) -> None:
        """Connect the provider and announce it on the bus."""
        try:
            await self._provider.connect()
        except Exception as exc:  # isolate provider failures
            self._error("unknown", f"connect failed: {exc}")
            return
        self._info("Provider connected")
        await self._bus.publish(ProviderConnected(exchange=self._exchange_hint()))

    async def stop(self) -> None:
        """Disconnect the provider and announce it on the bus."""
        try:
            await self._provider.disconnect()
        finally:
            self._info("Provider disconnected")
            await self._bus.publish(
                ProviderDisconnected(exchange=self._exchange_hint())
            )

    def get_snapshot(self, key: CacheKey) -> MarketSnapshot | None:
        """Return the latest cached snapshot for ``key``."""
        return self._cache.get(key)

    # -- pipeline -----------------------------------------------------------

    async def _on_raw(self, raw: RawPayload) -> None:
        """Process one raw payload through the full pipeline, isolating errors."""
        exchange = raw.get("exchange", "unknown") if isinstance(raw, dict) else "unknown"
        symbol = raw.get("symbol", "unknown") if isinstance(raw, dict) else "unknown"
        await self._bus.publish(MarketDataReceived(exchange=exchange, symbol=symbol))

        try:
            model = self._normalizer.normalize(raw)
        except MarketDataError as exc:
            self._error(exchange, f"normalization failed: {exc}")
            await self._bus.publish(
                ProviderErrorOccurred(exchange=exchange, message=str(exc))
            )
            return

        key = self._key(model)
        existed = self._cache.exists(key)
        try:
            snapshot = self._merge(key, model)
            self._cache.update(key, snapshot)
        except MarketDataError as exc:
            self._error(exchange, f"cache update failed: {exc}")
            await self._bus.publish(
                ProviderErrorOccurred(exchange=exchange, message=str(exc))
            )
            return
        self._debug("Cache updated", symbol=symbol)

        event = self._event_for(model, existed=existed)
        await self._bus.publish(event)
        self._debug("Market event published", event=type(event).__name__)

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _key(model: NormalizedData) -> CacheKey:
        timeframe = model.timeframe if isinstance(model, OHLCV) else None
        return CacheKey(model.exchange, model.symbol, timeframe)

    def _merge(self, key: CacheKey, model: NormalizedData) -> MarketSnapshot:
        current = self._cache.get(key)
        now = datetime.now(UTC)
        base = current or MarketSnapshot(
            exchange=key.exchange, symbol=key.symbol, timeframe=key.timeframe
        )
        if isinstance(model, PriceTick):
            return _replace(base, now, last_price=model.price, last_tick=model)
        if isinstance(model, TradeTick):
            return _replace(base, now, last_price=model.price, last_trade=model)
        if isinstance(model, OHLCV):
            return _replace(base, now, ohlcv=model, last_price=model.close)
        if isinstance(model, OrderBookSnapshot):
            return _replace(base, now, order_book=model)
        raise MarketDataError(f"Unknown normalized model: {type(model).__name__}.")

    @staticmethod
    def _event_for(model: NormalizedData, *, existed: bool) -> MarketEvent:
        if isinstance(model, PriceTick):
            return PriceUpdated(tick=model)
        if isinstance(model, TradeTick):
            return TradeReceived(trade=model)
        if isinstance(model, OrderBookSnapshot):
            return OrderBookUpdated(order_book=model)
        if isinstance(model, OHLCV):
            if not existed:
                return CandleOpened(candle=model)
            return CandleClosed(candle=model) if model.is_closed else CandleUpdated(
                candle=model
            )
        raise MarketDataError(f"Unknown normalized model: {type(model).__name__}.")

    def _exchange_hint(self) -> str:
        return "provider"

    # -- logging ------------------------------------------------------------

    def _info(self, message: str) -> None:
        if self._log is not None:
            self._log.info(message)

    def _debug(self, message: str, **fields: object) -> None:
        if self._log is not None:
            self._log.debug(message, extra=fields)

    def _error(self, exchange: str, message: str) -> None:
        if self._log is not None:
            self._log.error(message, extra={"exchange": exchange})


def _replace(base: MarketSnapshot, now: datetime, **changes: object) -> MarketSnapshot:
    """Return a copy of ``base`` with ``changes`` and ``updated_at`` applied."""
    import dataclasses

    return dataclasses.replace(base, updated_at=now, **changes)  # type: ignore[arg-type]
