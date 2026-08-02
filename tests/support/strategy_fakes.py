"""Fake strategies and helpers for Strategy Framework tests.

A new, standalone support module (existing support files are unchanged). These
are test doubles only — no RSI/EMA/MACD or any real indicator logic.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from market_data.models import MarketSnapshot
from strategies.base import BaseStrategy, StrategyMetadata
from strategies.context import StrategyContext
from strategies.signals import SignalDirection, TradingSignal

__all__ = [
    "FakeStrategy",
    "FailingStrategy",
    "BuyStrategy",
    "make_context",
]

_FIXED = datetime(2026, 1, 1, tzinfo=UTC)


class FakeStrategy(BaseStrategy):
    """A configurable strategy that emits one signal of a fixed direction."""

    def __init__(
        self,
        name: str = "fake",
        direction: SignalDirection = SignalDirection.BUY,
        *,
        emit: bool = True,
    ) -> None:
        super().__init__(StrategyMetadata(name))
        self._direction = direction
        self._emit = emit
        self.evaluate_calls = 0

    async def generate_signals(
        self, context: StrategyContext
    ) -> Sequence[TradingSignal]:
        self.evaluate_calls += 1
        if not self._emit:
            return []
        return [
            self.make_signal(
                symbol=context.symbol, direction=self._direction, confidence=0.5
            )
        ]


class FailingStrategy(BaseStrategy):
    """A strategy that always raises, to test error isolation."""

    def __init__(self, name: str = "boom") -> None:
        super().__init__(StrategyMetadata(name))

    async def generate_signals(
        self, context: StrategyContext
    ) -> Sequence[TradingSignal]:
        raise RuntimeError("strategy exploded")


class BuyStrategy(BaseStrategy):
    """A zero-dependency strategy, constructible by the factory/DI container."""

    def __init__(self) -> None:
        super().__init__(StrategyMetadata("buy"))

    async def generate_signals(
        self, context: StrategyContext
    ) -> Sequence[TradingSignal]:
        return [self.make_signal(symbol=context.symbol, direction=SignalDirection.BUY)]


def make_context(*, exchange: str = "sim", symbol: str = "BTCUSDT") -> StrategyContext:
    """Build a deterministic StrategyContext with a market snapshot."""
    snapshot = MarketSnapshot(
        exchange=exchange,
        symbol=symbol,
        last_price=Decimal("100"),
        updated_at=_FIXED,
    )
    return StrategyContext(
        exchange=exchange,
        symbol=symbol,
        market_snapshot=snapshot,
        timestamp=_FIXED,
    )
