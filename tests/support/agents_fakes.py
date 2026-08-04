"""Helpers for AI Decision Engine tests.

Standalone support module (existing support files unchanged). Builds deterministic
standardized inputs (market snapshot, strategy signals, risk decision) assembled
into a :class:`DecisionContext`, plus a controllable fake agent. No network, no
sleeps, no randomness, and no model/provider calls.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from agents.context import DecisionContext
from agents.models import AgentOpinion, AgentRole, DecisionParameters
from market_data.models import OHLCV, MarketSnapshot
from performance.models import PerformanceResult
from risk.models import RiskDecision, RiskDecisionType
from strategies.signals import SignalDirection, TradingSignal

__all__ = [
    "FIXED_TIME",
    "make_candle",
    "make_snapshot",
    "make_signal",
    "make_risk_decision",
    "make_decision_context",
    "FakeAgent",
]

FIXED_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def make_candle(open_: str, close: str, symbol: str = "BTCUSDT") -> OHLCV:
    """Build a deterministic candle with the given open/close."""
    o, c = Decimal(open_), Decimal(close)
    return OHLCV(
        exchange="neutral",
        symbol=symbol,
        timeframe="1m",
        open=o,
        high=max(o, c),
        low=min(o, c),
        close=c,
        volume=Decimal("1"),
        open_time=FIXED_TIME,
        close_time=FIXED_TIME + timedelta(minutes=1),
        is_closed=True,
    )


def make_snapshot(
    open_: str = "100", close: str = "110", symbol: str = "BTCUSDT"
) -> MarketSnapshot:
    """Build a market snapshot carrying one candle."""
    candle = make_candle(open_, close, symbol)
    return MarketSnapshot(
        exchange="neutral",
        symbol=symbol,
        timeframe="1m",
        last_price=candle.close,
        ohlcv=candle,
        updated_at=FIXED_TIME,
    )


def make_signal(
    direction: SignalDirection = SignalDirection.BUY,
    confidence: float = 0.9,
    symbol: str = "BTCUSDT",
) -> TradingSignal:
    """Build a strategy signal."""
    return TradingSignal(
        id="sig-1",
        strategy_name="fake",
        symbol=symbol,
        direction=direction,
        confidence=confidence,
    )


def make_risk_decision(approved: bool = True) -> RiskDecision:
    """Build a risk decision (approved or rejected)."""
    decision_type = (
        RiskDecisionType.APPROVED if approved else RiskDecisionType.REJECTED
    )
    return RiskDecision(id="rd-1", decision_type=decision_type)


def make_decision_context(
    *,
    symbol: str = "BTCUSDT",
    open_: str = "100",
    close: str = "110",
    signals: Sequence[TradingSignal] | None = None,
    risk_approved: bool = True,
    performance: PerformanceResult | None = None,
    parameters: DecisionParameters | None = None,
) -> DecisionContext:
    """Build a deterministic decision context."""
    return DecisionContext(
        symbol=symbol,
        market_snapshot=make_snapshot(open_, close, symbol),
        signals=tuple(signals) if signals is not None else (make_signal(),),
        risk_decision=make_risk_decision(risk_approved),
        performance_result=performance,
        parameters=parameters or DecisionParameters(),
        correlation_id="dec-corr",
    )


class FakeAgent:
    """An agent that always returns a fixed opinion (implements ``Agent``)."""

    def __init__(
        self,
        role: AgentRole,
        direction: SignalDirection = SignalDirection.HOLD,
        confidence: str = "1",
        approve: bool = True,
    ) -> None:
        self._role = role
        self._direction = direction
        self._confidence = Decimal(confidence)
        self._approve = approve

    @property
    def role(self) -> AgentRole:
        return self._role

    async def evaluate(self, context: DecisionContext) -> AgentOpinion:
        return AgentOpinion(
            role=self._role,
            direction=self._direction,
            confidence=self._confidence,
            approve=self._approve,
        )
