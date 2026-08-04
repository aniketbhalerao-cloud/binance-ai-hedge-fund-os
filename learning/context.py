"""Learning context.

An immutable input carrying the standardized outcomes to learn from — a decision
result, a trade result, and a performance result — plus the attribution keys
(strategy name, agent role) and the realized P&L. It represents one completed
activity. Learning components never access infrastructure directly; they read only
from this context and the models it carries.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from agents.models import AgentRole, DecisionResult
from learning.models import LearningOutcome, LearningParameters
from performance.models import PerformanceResult
from strategies.signals import SignalDirection
from trades.models import TradeResult

__all__ = ["LearningContext"]

_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class LearningContext:
    """Immutable input for learning from one completed outcome.

    Attributes:
        learning_id: Identifier of the learning record to update.
        strategy_name: Strategy the outcome is attributed to.
        agent_role: Agent role the outcome is attributed to.
        realized_pnl: Realized profit/loss of the outcome.
        decision_result: The AI decision result, if available.
        trade_result: The trade lifecycle result, if available.
        performance_result: The performance analytics result, if available.
        parameters: Deterministic learning parameters.
        correlation_id: Optional correlation id propagated to events.
        timestamp: When the context was assembled (UTC).
        metadata: Optional read-only extra context.
    """

    learning_id: str = "learning"
    strategy_name: str = "default"
    agent_role: AgentRole = AgentRole.STRATEGY
    realized_pnl: Decimal = _ZERO
    decision_result: DecisionResult | None = None
    trade_result: TradeResult | None = None
    performance_result: PerformanceResult | None = None
    parameters: LearningParameters = field(default_factory=LearningParameters)
    correlation_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_outcome(self, timestamp: datetime) -> LearningOutcome:
        """Derive the standardized :class:`LearningOutcome` for this context.

        The realized P&L is taken from the context (falling back to the trade
        result); the direction and approval are taken from the decision result.
        """
        realized = self.realized_pnl
        if realized == _ZERO and self.trade_result and self.trade_result.trade:
            realized = self.trade_result.trade.realized_pnl

        direction = SignalDirection.HOLD
        approved = False
        if self.decision_result is not None and self.decision_result.decision:
            direction = self.decision_result.decision.direction
            approved = self.decision_result.decision.approved

        return LearningOutcome(
            strategy_name=self.strategy_name,
            agent_role=self.agent_role,
            direction=direction,
            realized_pnl=realized,
            won=realized > _ZERO,
            approved=approved,
            timestamp=timestamp,
        )
