"""Normalized market-data domain models.

These are exchange-agnostic, immutable value objects. They contain **no**
exchange-specific fields or names — every provider (Binance, Zerodha, CSV,
replay, …) is normalized into exactly these shapes before its data travels any
further, so downstream components never see a venue's raw format.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from models import OrderSide

__all__ = [
    "ConnectionStatus",
    "CacheKey",
    "PriceTick",
    "TradeTick",
    "OHLCV",
    "OrderBookSnapshot",
    "MarketSnapshot",
]


class ConnectionStatus(str, Enum):
    """Connection state of a market-data provider."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class CacheKey:
    """Address of a cached market snapshot.

    Keyed by a neutral ``exchange`` label, ``symbol``, and optional
    ``timeframe`` (used only for candle data).
    """

    exchange: str
    symbol: str
    timeframe: str | None = None


@dataclass(frozen=True, slots=True)
class PriceTick:
    """A single normalized price observation."""

    exchange: str
    symbol: str
    price: Decimal
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class TradeTick:
    """A single normalized public trade."""

    exchange: str
    symbol: str
    price: Decimal
    quantity: Decimal
    side: OrderSide
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class OHLCV:
    """A normalized candle for a given ``timeframe``."""

    exchange: str
    symbol: str
    timeframe: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    open_time: datetime
    close_time: datetime
    is_closed: bool = False


@dataclass(frozen=True, slots=True)
class OrderBookSnapshot:
    """A normalized order-book snapshot.

    ``bids`` and ``asks`` are immutable ``(price, quantity)`` tuples in the order
    supplied by the provider; this model does not re-sort or interpret them.
    """

    exchange: str
    symbol: str
    bids: tuple[tuple[Decimal, Decimal], ...]
    asks: tuple[tuple[Decimal, Decimal], ...]
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    """The latest normalized market state for one ``(exchange, symbol[, tf])``.

    Fields not relevant to the most recent update remain ``None``. This is the
    value stored in the cache.
    """

    exchange: str
    symbol: str
    timeframe: str | None = None
    last_price: Decimal | None = None
    last_tick: PriceTick | None = None
    last_trade: TradeTick | None = None
    ohlcv: OHLCV | None = None
    order_book: OrderBookSnapshot | None = None
    updated_at: datetime | None = None
