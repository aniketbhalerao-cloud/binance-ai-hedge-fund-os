"""Fakes and payload builders for market-data tests.

A new, standalone support module (existing support files are unchanged). The
:class:`FakeMarketDataProvider` satisfies the ``MarketDataProvider`` interface
and can push payloads on demand or replay a list — the same interface a future
Binance/CSV/replay provider would implement, which is what makes the replay
tests possible without any exchange code.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from market_data.provider import BaseMarketDataProvider

__all__ = [
    "FakeMarketDataProvider",
    "make_tick_payload",
    "make_trade_payload",
    "make_ohlcv_payload",
    "make_order_book_payload",
    "FIXED_TIME",
]

#: A fixed timestamp so tests never depend on the wall clock.
FIXED_TIME = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)


class FakeMarketDataProvider(BaseMarketDataProvider):
    """A provider that emits pre-seeded payloads on demand or via replay."""

    def __init__(self, payloads: list[Any] | None = None) -> None:
        super().__init__()
        self._payloads = list(payloads or [])
        self.connect_calls = 0
        self.disconnect_calls = 0

    async def _on_connect(self) -> None:
        self.connect_calls += 1

    async def _on_disconnect(self) -> None:
        self.disconnect_calls += 1

    async def push(self, raw: Any) -> None:
        """Emit a single raw payload through the pipeline."""
        await self._emit(raw)

    async def replay(self) -> None:
        """Emit every seeded payload in order (replay-source behaviour)."""
        for payload in self._payloads:
            await self._emit(payload)


def make_tick_payload(
    *, exchange: str = "sim", symbol: str = "BTCUSDT", price: str = "100"
) -> dict[str, Any]:
    return {
        "kind": "tick",
        "exchange": exchange,
        "symbol": symbol,
        "price": price,
        "timestamp": FIXED_TIME,
    }


def make_trade_payload(
    *, exchange: str = "sim", symbol: str = "BTCUSDT", side: str = "buy"
) -> dict[str, Any]:
    return {
        "kind": "trade",
        "exchange": exchange,
        "symbol": symbol,
        "price": "100",
        "quantity": "1",
        "side": side,
        "timestamp": FIXED_TIME,
    }


def make_ohlcv_payload(
    *,
    exchange: str = "sim",
    symbol: str = "BTCUSDT",
    timeframe: str = "1m",
    is_closed: bool = False,
) -> dict[str, Any]:
    return {
        "kind": "ohlcv",
        "exchange": exchange,
        "symbol": symbol,
        "timeframe": timeframe,
        "open": "100",
        "high": "110",
        "low": "95",
        "close": "105",
        "volume": "10",
        "open_time": FIXED_TIME,
        "close_time": FIXED_TIME,
        "is_closed": is_closed,
    }


def make_order_book_payload(
    *, exchange: str = "sim", symbol: str = "BTCUSDT"
) -> dict[str, Any]:
    return {
        "kind": "order_book",
        "exchange": exchange,
        "symbol": symbol,
        "bids": [[Decimal("99"), Decimal("1")]],
        "asks": [[Decimal("101"), Decimal("2")]],
        "timestamp": FIXED_TIME,
    }
