"""Helpers for Learning Framework tests.

Standalone support module (existing support files unchanged). Builds deterministic
learning outcomes and contexts from standardized upstream results (decision, trade,
performance). No network, no sleeps, no randomness, and no model training.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from agents.models import (
    AgentRole,
    Decision,
    DecisionResult,
    DecisionResultStatus,
)
from learning.context import LearningContext
from learning.models import LearningParameters
from strategies.signals import SignalDirection
from trades.models import TradeResult, TradeResultStatus

__all__ = [
    "FIXED_TIME",
    "make_decision_result",
    "make_trade_result",
    "make_context",
]

FIXED_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def make_decision_result(
    direction: SignalDirection = SignalDirection.BUY,
    approved: bool = True,
    confidence: str = "0.8",
) -> DecisionResult:
    """Build a decision result carrying a single decision."""
    decision = Decision(
        id="dec-1",
        symbol="BTCUSDT",
        direction=direction,
        confidence=Decimal(confidence),
        approved=approved,
        opinions=(),
        timestamp=FIXED_TIME,
    )
    return DecisionResult(status=DecisionResultStatus.SUCCESS, decision=decision)


def make_trade_result(realized_pnl: str = "10") -> TradeResult:
    """Build a minimal trade result with a realized-P&L trade."""
    from positions.models import PositionSide
    from trades.models import Trade
    from trades.state import TradeState

    trade = Trade(
        id="pos-1",
        symbol="BTCUSDT",
        side=PositionSide.LONG,
        state=TradeState.CLOSED,
        realized_pnl=Decimal(realized_pnl),
    )
    return TradeResult(status=TradeResultStatus.SUCCESS, trade=trade)


def make_context(
    *,
    learning_id: str = "lrn-1",
    strategy_name: str = "ema",
    agent_role: AgentRole = AgentRole.STRATEGY,
    realized_pnl: str = "10",
    direction: SignalDirection = SignalDirection.BUY,
    approved: bool = True,
    parameters: LearningParameters | None = None,
    cancel: bool = False,
) -> LearningContext:
    """Build a deterministic learning context for one outcome."""
    metadata = {"cancel": True} if cancel else {}
    return LearningContext(
        learning_id=learning_id,
        strategy_name=strategy_name,
        agent_role=agent_role,
        realized_pnl=Decimal(realized_pnl),
        decision_result=make_decision_result(direction, approved),
        trade_result=make_trade_result(realized_pnl),
        parameters=parameters or LearningParameters(),
        correlation_id="lrn-corr",
        metadata=metadata,
    )
