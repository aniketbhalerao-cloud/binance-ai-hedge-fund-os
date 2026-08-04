"""Default AI agents.

Each agent reasons **deterministically** over the standardized inputs in a
:class:`~agents.context.DecisionContext` and produces an immutable
:class:`~agents.models.AgentOpinion`. These defaults are rule-based (no model,
provider, or network call) so the framework core is deterministic and testable;
model-backed agents plug in later by implementing the ``Agent`` protocol and being
injected through the container — the framework never changes.

Agents are stateless and never log.
"""

from __future__ import annotations

from decimal import Decimal

from agents.context import DecisionContext
from agents.models import AgentOpinion, AgentRole
from strategies.signals import SignalDirection

__all__ = [
    "BaseAgent",
    "DefaultMarketAgent",
    "DefaultStrategyAgent",
    "DefaultRiskAgent",
    "DefaultPortfolioAgent",
    "DefaultCEOAgent",
]

_ZERO = Decimal("0")
_ONE = Decimal("1")


def _bucket(direction: SignalDirection) -> SignalDirection:
    """Collapse a signal direction into BUY / SELL / HOLD for voting."""
    if direction in (SignalDirection.BUY, SignalDirection.INCREASE):
        return SignalDirection.BUY
    if direction in (
        SignalDirection.SELL,
        SignalDirection.CLOSE,
        SignalDirection.REDUCE,
    ):
        return SignalDirection.SELL
    return SignalDirection.HOLD


def _clamp(value: Decimal) -> Decimal:
    if value < _ZERO:
        return _ZERO
    return _ONE if value > _ONE else value


class BaseAgent:
    """Small base providing the role and an opinion factory."""

    def __init__(self, role: AgentRole) -> None:
        self._role = role

    @property
    def role(self) -> AgentRole:
        return self._role

    def _opinion(
        self,
        direction: SignalDirection,
        confidence: Decimal,
        approve: bool = True,
        rationale: str = "",
    ) -> AgentOpinion:
        return AgentOpinion(
            role=self._role,
            direction=direction,
            confidence=_clamp(confidence),
            approve=approve,
            rationale=rationale,
        )


class DefaultMarketAgent(BaseAgent):
    """Reads the latest candle: up-bar → BUY, down-bar → SELL."""

    def __init__(self) -> None:
        super().__init__(AgentRole.MARKET)

    async def evaluate(self, context: DecisionContext) -> AgentOpinion:
        snapshot = context.market_snapshot
        candle = snapshot.ohlcv if snapshot is not None else None
        if candle is None or candle.open <= _ZERO:
            return self._opinion(
                SignalDirection.HOLD, _ZERO, rationale="no market data"
            )
        move = (candle.close - candle.open) / candle.open
        confidence = _clamp(abs(move) * Decimal("10"))
        if move > _ZERO:
            return self._opinion(SignalDirection.BUY, confidence, rationale="up bar")
        if move < _ZERO:
            return self._opinion(SignalDirection.SELL, confidence, rationale="down bar")
        return self._opinion(SignalDirection.HOLD, _ZERO, rationale="flat bar")


class DefaultStrategyAgent(BaseAgent):
    """Aggregates strategy signals by confidence-weighted direction."""

    def __init__(self) -> None:
        super().__init__(AgentRole.STRATEGY)

    async def evaluate(self, context: DecisionContext) -> AgentOpinion:
        buckets: dict[SignalDirection, Decimal] = {
            SignalDirection.BUY: _ZERO,
            SignalDirection.SELL: _ZERO,
            SignalDirection.HOLD: _ZERO,
        }
        for signal in context.signals:
            buckets[_bucket(signal.direction)] += Decimal(str(signal.confidence))
        total = sum(buckets.values(), _ZERO)
        if total <= _ZERO:
            return self._opinion(SignalDirection.HOLD, _ZERO, rationale="no signals")
        direction = max(buckets, key=lambda d: buckets[d])
        return self._opinion(
            direction, buckets[direction] / total, rationale="signal vote"
        )


class DefaultRiskAgent(BaseAgent):
    """Gates the decision: approves only when the risk decision approved."""

    def __init__(self) -> None:
        super().__init__(AgentRole.RISK)

    async def evaluate(self, context: DecisionContext) -> AgentOpinion:
        decision = context.risk_decision
        approved = decision is not None and decision.approved
        confidence = _ONE if decision is not None else _ZERO
        rationale = "risk approved" if approved else "risk veto"
        return self._opinion(
            SignalDirection.HOLD, confidence, approve=approved, rationale=rationale
        )


class DefaultPortfolioAgent(BaseAgent):
    """Conservative participant: risk-off when performance is negative."""

    def __init__(self) -> None:
        super().__init__(AgentRole.PORTFOLIO)

    async def evaluate(self, context: DecisionContext) -> AgentOpinion:
        result = context.performance_result
        if result is None or result.metrics is None:
            return self._opinion(
                SignalDirection.HOLD, _ZERO, rationale="no performance"
            )
        total_return = result.metrics.returns.total_return
        if total_return < _ZERO:
            return self._opinion(
                SignalDirection.HOLD, Decimal("0.6"), rationale="drawdown caution"
            )
        return self._opinion(
            SignalDirection.HOLD, Decimal("0.3"), rationale="stable performance"
        )


class DefaultCEOAgent(BaseAgent):
    """Arbitrates over the analyst opinions carried by the enriched context."""

    def __init__(self) -> None:
        super().__init__(AgentRole.CEO)

    async def evaluate(self, context: DecisionContext) -> AgentOpinion:
        opinions = [op for op in context.agent_opinions if op.role is not AgentRole.CEO]
        if not opinions:
            return self._opinion(SignalDirection.HOLD, _ZERO, rationale="no opinions")
        buckets: dict[SignalDirection, Decimal] = {
            SignalDirection.BUY: _ZERO,
            SignalDirection.SELL: _ZERO,
            SignalDirection.HOLD: _ZERO,
        }
        for op in opinions:
            buckets[_bucket(op.direction)] += op.confidence
        direction = max(buckets, key=lambda d: buckets[d])
        confidence = sum((op.confidence for op in opinions), _ZERO) / Decimal(
            len(opinions)
        )
        approve = all(op.approve for op in opinions)
        return self._opinion(
            direction, confidence, approve=approve, rationale="arbitration"
        )
