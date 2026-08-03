"""Helpers for Backtesting Framework tests.

Standalone support module (existing support files unchanged). Builds a
deterministic historical candle series, a controllable fake strategy, and fake
upstream engines (risk/order/execution) that approve and make ready a market
order — so the post-Execution pipeline (Simulator → Portfolio → Position → Trade
→ Performance) can be exercised deterministically without depending on the real
upstream engines' default sizing/approval behaviour. No network, no sleeps, no
randomness.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backtesting.context import BacktestingContext
from backtesting.models import SimulationParameters
from execution.context import ExecutionContext
from execution.models import (
    ExecutionIdentifier,
    ExecutionRequest,
    ExecutionResult,
    ExecutionState,
    ExecutionStatus,
)
from market_data.models import OHLCV
from models import OrderSide, OrderType
from order_management.context import OrderContext
from order_management.models import (
    OrderIdentifier,
    OrderRequest,
    OrderResult,
    OrderRoute,
)
from order_management.state import OrderState
from risk.context import RiskContext
from risk.models import RiskDecision, RiskDecisionType
from strategies.context import StrategyContext
from strategies.signals import SignalDirection, TradingSignal

__all__ = [
    "FIXED_TIME",
    "make_candle",
    "make_candles",
    "FakeStrategy",
    "FakeRiskEngine",
    "FakeOrderEngine",
    "FakeExecutionEngine",
    "make_backtesting_context",
]

FIXED_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def make_candle(index: int, close: str, symbol: str = "BTCUSDT") -> OHLCV:
    """Build a deterministic 1-minute candle at ``index`` with a flat OHLC."""
    price = Decimal(close)
    return OHLCV(
        exchange="backtest",
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
    """Build a candle series from a sequence of closing prices."""
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


class FakeRiskEngine:
    """Approves every signal."""

    async def evaluate(self, context: RiskContext) -> RiskDecision:
        return RiskDecision(id="rd", decision_type=RiskDecisionType.APPROVED)


class FakeOrderEngine:
    """Produces a ready market order for the signalled side."""

    def __init__(self, quantity: str = "1") -> None:
        self._quantity = Decimal(quantity)

    async def process(self, context: OrderContext) -> OrderResult:
        buy = context.signal.direction is SignalDirection.BUY
        side = OrderSide.BUY if buy else OrderSide.SELL
        request = OrderRequest(
            identifier=OrderIdentifier(),
            symbol=context.symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=self._quantity,
        )
        return OrderResult(
            state=OrderState.READY_FOR_EXECUTION,
            request=request,
            route=OrderRoute(destination="simulated"),
        )


class FakeExecutionEngine:
    """Coordinates the order into a ready execution (no exchange contact)."""

    async def process(self, context: ExecutionContext) -> ExecutionResult:
        request = ExecutionRequest(
            identifier=ExecutionIdentifier(),
            order_request=context.order_result.request,
            exchange=context.exchange,
            symbol=context.symbol,
        )
        return ExecutionResult(
            status=ExecutionStatus.READY,
            state=ExecutionState.READY,
            request=request,
        )


def make_backtesting_context(
    *,
    closes: Sequence[str] = ("100", "110", "120"),
    buy_on: Sequence[int] = (0,),
    sell_on: Sequence[int] = (),
    parameters: SimulationParameters | None = None,
    strategy: object | None = None,
    symbol: str = "BTCUSDT",
) -> BacktestingContext:
    """Build a deterministic backtesting context."""
    return BacktestingContext(
        candles=make_candles(closes, symbol),
        strategy=strategy
        if strategy is not None
        else FakeStrategy(buy_on=buy_on, sell_on=sell_on, symbol=symbol),  # type: ignore[arg-type]
        parameters=parameters or SimulationParameters(),
        symbol=symbol,
        correlation_id="bt-corr",
    )
