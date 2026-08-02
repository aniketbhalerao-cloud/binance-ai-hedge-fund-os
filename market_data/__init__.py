"""Market Data Pipeline — exchange-agnostic market-data infrastructure.

Receives raw data (via a provider), normalizes it into domain models, keeps the
latest snapshot in an in-memory cache, and publishes standardized market events
on the shared event bus for the Trading Engine (and future components) to
consume. It contains no trading, strategy, risk, exchange, persistence, or
notification logic.

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from market_data.cache import InMemoryMarketDataCache
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
    ProviderReconnectAttempt,
    TradeReceived,
)
from market_data.exceptions import (
    CacheError,
    MarketDataConnectionError,
    MarketDataError,
    NormalizationError,
    ProviderError,
)
from market_data.interfaces import (
    MarketDataCache,
    MarketDataNormalizer,
    MarketDataProvider,
    MarketDataService,
)
from market_data.models import (
    OHLCV,
    CacheKey,
    ConnectionStatus,
    MarketSnapshot,
    OrderBookSnapshot,
    PriceTick,
    TradeTick,
)
from market_data.normalizer import DefaultNormalizer
from market_data.provider import BaseMarketDataProvider
from market_data.service import MarketDataPipelineService

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = [
    # models
    "ConnectionStatus",
    "CacheKey",
    "PriceTick",
    "TradeTick",
    "OHLCV",
    "OrderBookSnapshot",
    "MarketSnapshot",
    # interfaces
    "MarketDataProvider",
    "MarketDataNormalizer",
    "MarketDataCache",
    "MarketDataService",
    # implementations
    "BaseMarketDataProvider",
    "DefaultNormalizer",
    "InMemoryMarketDataCache",
    "MarketDataPipelineService",
    # events
    "MarketEvent",
    "MarketDataReceived",
    "PriceUpdated",
    "CandleOpened",
    "CandleUpdated",
    "CandleClosed",
    "OrderBookUpdated",
    "TradeReceived",
    "ProviderConnected",
    "ProviderDisconnected",
    "ProviderReconnectAttempt",
    "ProviderErrorOccurred",
    # exceptions
    "MarketDataError",
    "ProviderError",
    "NormalizationError",
    "CacheError",
    "MarketDataConnectionError",
    # wiring
    "register_market_data",
]


def register_market_data(
    container: Container, *, provider: MarketDataProvider | None = None
) -> None:
    """Register the market-data pipeline into ``container``.

    Registers the default normalizer and in-memory cache (bound to their
    abstractions) and the :class:`MarketDataPipelineService` as a singleton. The
    ``EventBus`` is registered on demand if absent. ``LoggerFactory`` and the
    ``TradingEngine`` are injected only if already registered.

    The provider is exchange-specific and therefore supplied by the caller: pass
    a concrete ``provider`` instance, or register one under
    :class:`MarketDataProvider` before calling this. No provider is created here.

    Args:
        container: The DI container to register into.
        provider: Optional provider instance to register under the
            :class:`MarketDataProvider` abstraction.
    """
    if not container.has(EventBus):
        container.register_class(EventBus)

    container.register_class(MarketDataNormalizer, DefaultNormalizer)
    container.register_class(MarketDataCache, InMemoryMarketDataCache)

    if provider is not None:
        container.register_instance(MarketDataProvider, provider)

    def _build_service(resolver: Resolver) -> MarketDataPipelineService:
        from trading.engine import TradingEngine

        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        engine = (
            resolver.resolve(TradingEngine) if resolver.has(TradingEngine) else None
        )
        return MarketDataPipelineService(
            resolver.resolve(MarketDataProvider),
            resolver.resolve(MarketDataNormalizer),
            resolver.resolve(MarketDataCache),
            resolver.resolve(EventBus),
            logger=logger,
            engine=engine,
        )

    container.register_singleton(MarketDataPipelineService, _build_service)
    container.register_singleton(
        MarketDataService, lambda r: r.resolve(MarketDataPipelineService)
    )
