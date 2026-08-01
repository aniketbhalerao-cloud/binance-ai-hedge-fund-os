"""Market-data events.

Trading-independent events describing market activity and provider connectivity.
Each inherits the existing :class:`events.base.Event` (gaining ``event_id`` /
``timestamp``) and is immutable. The pipeline publishes **only** these — never
trading signals, orders, portfolio, or risk events.
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event
from market_data.models import (
    OHLCV,
    OrderBookSnapshot,
    PriceTick,
    TradeTick,
)

__all__ = [
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
]


@dataclass(frozen=True, slots=True, kw_only=True)
class MarketEvent(Event):
    """Base class for all market-data events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class MarketDataReceived(MarketEvent):
    """Raw data was received for a symbol (before/around normalization)."""

    exchange: str
    symbol: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PriceUpdated(MarketEvent):
    """A new price tick was normalized."""

    tick: PriceTick


@dataclass(frozen=True, slots=True, kw_only=True)
class CandleOpened(MarketEvent):
    """The first candle for a symbol/timeframe was observed."""

    candle: OHLCV


@dataclass(frozen=True, slots=True, kw_only=True)
class CandleUpdated(MarketEvent):
    """An in-progress candle was updated."""

    candle: OHLCV


@dataclass(frozen=True, slots=True, kw_only=True)
class CandleClosed(MarketEvent):
    """A candle finalized (closed)."""

    candle: OHLCV


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderBookUpdated(MarketEvent):
    """A new order-book snapshot was normalized."""

    order_book: OrderBookSnapshot


@dataclass(frozen=True, slots=True, kw_only=True)
class TradeReceived(MarketEvent):
    """A public trade was normalized."""

    trade: TradeTick


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderConnected(MarketEvent):
    """A provider established its connection."""

    exchange: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderDisconnected(MarketEvent):
    """A provider connection was closed or lost."""

    exchange: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderReconnectAttempt(MarketEvent):
    """A provider is attempting to reconnect."""

    exchange: str
    attempt: int = 1


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderErrorOccurred(MarketEvent):
    """A provider or normalization error occurred."""

    exchange: str
    message: str
