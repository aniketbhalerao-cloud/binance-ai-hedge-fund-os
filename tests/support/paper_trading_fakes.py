"""Helpers for Paper Trading Framework tests.

Standalone support module (existing support files unchanged). Builds deterministic
live candles, a controllable fake strategy, and fake upstream engines
(risk/order/execution) that approve and make ready a market order — so the
post-Execution pipeline (Paper Broker → Portfolio → Position → Trade →
Performance) can be exercised deterministically without depending on the real
upstream engines' default sizing/approval behaviour. No network, no sleeps, no
randomness.

The risk/order/execution fakes are re-exported from ``backtesting_fakes`` so the
two frameworks share one fake-engine definition.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from market_data.models import OHLCV
from paper_trading.context import PaperTradingContext
from paper_trading.models import SessionParameters
from strategies.context import StrategyContext
from strategies.signals import SignalDirection, TradingSignal
from tests.support.backtesting_fakes import (
    FakeExecutionEngine,
    FakeOrderEngine,
    FakeRiskEngine,
)

__all__ = [
    "FIXED_TIME",
    "make_candle",
    "make_candles",
    "FakeStrategy",
    "FakeRiskEngine",
    "FakeOrderEngine",
    "FakeExecutionEngine",
    "make_context",
]

FIXED_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def make_candle(index: int, close: str, symbol: str = "BTCUSDT") -> OHLCV:
    """Build a deterministic 1-minute live candle at ``index``."""
    price = Decimal(close)
    return OHLCV(
        exchange="paper",
        symbol=symbol,
        timeframe="1m",
        open=price,
        high=price,
        low=price,
        close=price,
        volume=Decimal("1"),
        open_time=FIXED_TIME + timedelta(minutes=index),
        close_time=FIXED_TIME + timedelta(minutes=index + 1),
        is_closed=True,
    )


def make_candles(closes: Sequence[str], symbol: str = "BTCUSDT") -> tuple[OHLCV, ...]:
    """Build a live candle series from a sequence of closing prices."""
    return tuple(make_candle(i, c, symbol) for i, c in enumerate(closes))


def _step_index(candle: OHLCV) -> int:
    return int((candle.open_time - FIXED_TIME).total_seconds() // 60)


class FakeStrategy:
    """Emits a BUY at configured candle indices and a CLOSE at others (stateless)."""

    def __init__(
        self,
        buy_on: Sequence[int] = (0,),
        sell_on: Sequence[int] = (),
        symbol: str = "BTCUSDT",
    ) -> None:
        self._buy_on = set(buy_on)
        self._sell_on = set(sell_on)
        self._symbol = symbol

    async def on_start(self) -> None:
        return None

    async def on_stop(self) -> None:
        return None

    async def evaluate(self, context: StrategyContext) -> list[TradingSignal]:
        candle = context.latest_candle
        if candle is None:
            return []
        idx = _step_index(candle)
        if idx in self._buy_on:
            direction = SignalDirection.BUY
        elif idx in self._sell_on:
            direction = SignalDirection.CLOSE
        else:
            return []
        return [
            TradingSignal(
                id=f"sig-{idx}",
                strategy_name="fake",
                symbol=self._symbol,
                direction=direction,
            )
        ]


def make_context(
    *,
    session_id: str = "sess-1",
    candle: OHLCV | None = None,
    index: int = 0,
    close: str = "100",
    strategy: object | None = None,
    buy_on: Sequence[int] = (0,),
    sell_on: Sequence[int] = (),
    parameters: SessionParameters | None = None,
    final: bool = False,
    symbol: str = "BTCUSDT",
) -> PaperTradingContext:
    """Build a deterministic paper-trading context for one live update."""
    return PaperTradingContext(
        session_id=session_id,
        candle=candle if candle is not None else make_candle(index, close, symbol),
        strategy=strategy
        if strategy is not None
        else FakeStrategy(buy_on=buy_on, sell_on=sell_on, symbol=symbol),  # type: ignore[arg-type]
        parameters=parameters or SessionParameters(),
        symbol=symbol,
        final=final,
        correlation_id="pt-corr",
    )
