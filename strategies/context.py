"""Strategy execution context.

A :class:`StrategyContext` is the single, immutable input a strategy receives.
It carries everything required to make a decision — assembled from normalized
market-data models — so strategies never read from the market-data cache, the
trading engine, repositories, or databases directly.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from market_data.models import (
    OHLCV,
    MarketSnapshot,
    OrderBookSnapshot,
    TradeTick,
)

__all__ = ["StrategyContext"]


@dataclass(frozen=True, slots=True)
class StrategyContext:
    """Immutable snapshot of everything a strategy needs to decide.

    Attributes:
        exchange: Neutral exchange label.
        symbol: The instrument under evaluation.
        timeframe: Candle timeframe, where applicable.
        market_snapshot: The latest normalized market snapshot.
        latest_candle: The most recent candle, if any.
        recent_candles: A window of recent candles (oldest→newest).
        recent_trades: A window of recent public trades.
        order_book: The latest order-book snapshot, if any.
        timestamp: When the context was assembled (UTC).
        metadata: Optional read-only extra context.
    """

    exchange: str
    symbol: str
    timeframe: str | None = None
    market_snapshot: MarketSnapshot | None = None
    latest_candle: OHLCV | None = None
    recent_candles: tuple[OHLCV, ...] = ()
    recent_trades: tuple[TradeTick, ...] = ()
    order_book: OrderBookSnapshot | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
