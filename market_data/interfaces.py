"""Abstractions for the market-data pipeline.

Protocols only — no implementations. Every stage of the pipeline (provider,
normalizer, cache, service) is defined here so the :class:`MarketDataService`
and future components depend on abstractions rather than concrete classes
(Dependency Inversion). Any future provider (Binance, Zerodha, CSV, replay,
backtest, …) that satisfies :class:`MarketDataProvider` plugs in without the
service changing.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol, runtime_checkable

from market_data.models import (
    OHLCV,
    CacheKey,
    MarketSnapshot,
    OrderBookSnapshot,
    PriceTick,
    TradeTick,
)

__all__ = [
    "RawPayload",
    "RawHandler",
    "NormalizedData",
    "MarketDataProvider",
    "MarketDataNormalizer",
    "MarketDataCache",
    "MarketDataService",
]

#: A raw, un-normalized payload as delivered by a provider/source.
RawPayload = object

#: Async callback a provider invokes with each raw payload.
RawHandler = Callable[[RawPayload], Awaitable[None]]

#: The union of normalized domain models a normalizer may produce.
NormalizedData = PriceTick | TradeTick | OHLCV | OrderBookSnapshot


@runtime_checkable
class MarketDataProvider(Protocol):
    """A source of raw market data.

    A provider only *receives and relays* raw payloads — it does not parse,
    cache, or publish events. It pushes each raw payload to the handler
    registered via :meth:`on_data`.
    """

    @property
    def is_connected(self) -> bool:
        """Return ``True`` while the provider is connected."""
        ...

    def on_data(self, handler: RawHandler) -> None:
        """Register the async ``handler`` that receives raw payloads."""
        ...

    async def connect(self) -> None:
        """Establish the provider's connection/session."""
        ...

    async def disconnect(self) -> None:
        """Close the provider's connection/session."""
        ...


@runtime_checkable
class MarketDataNormalizer(Protocol):
    """Converts raw provider payloads into normalized domain models."""

    def normalize(self, raw: RawPayload) -> NormalizedData:
        """Return a normalized domain model for ``raw``.

        Raises:
            NormalizationError: If ``raw`` cannot be normalized.
        """
        ...


@runtime_checkable
class MarketDataCache(Protocol):
    """In-memory store of the latest normalized :class:`MarketSnapshot`."""

    def update(self, key: CacheKey, snapshot: MarketSnapshot) -> None:
        """Store (replace) the snapshot for ``key``."""
        ...

    def get(self, key: CacheKey) -> MarketSnapshot | None:
        """Return the snapshot for ``key`` if present."""
        ...

    def exists(self, key: CacheKey) -> bool:
        """Return ``True`` if a snapshot exists for ``key``."""
        ...

    def clear(self) -> None:
        """Remove all cached snapshots."""
        ...

    def snapshot(self) -> dict[CacheKey, MarketSnapshot]:
        """Return a shallow copy of all cached snapshots."""
        ...


@runtime_checkable
class MarketDataService(Protocol):
    """Coordinates provider → normalizer → cache → event bus."""

    async def start(self) -> None:
        """Connect the provider and begin processing."""
        ...

    async def stop(self) -> None:
        """Disconnect the provider and stop processing."""
        ...

    def get_snapshot(self, key: CacheKey) -> MarketSnapshot | None:
        """Return the latest cached snapshot for ``key``."""
        ...
