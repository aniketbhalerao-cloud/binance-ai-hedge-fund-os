"""AI decision context.

An immutable input carrying the standardized results the agents reason over — a
market snapshot, strategy signals, a risk decision, and portfolio / position /
performance results — plus the decision parameters. It represents everything
required to make one decision. Agents operate **only** from this context and never
access infrastructure, exchanges, or AI providers directly.

For CEO arbitration the manager assembles an enriched context carrying the analyst
opinions (``agent_opinions``); a fresh context leaves that tuple empty.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from agents.models import AgentOpinion, DecisionParameters
from market_data.models import MarketSnapshot
from performance.models import PerformanceResult
from portfolio.models import PortfolioResult
from positions.models import PositionResult
from risk.models import RiskDecision
from strategies.signals import TradingSignal

__all__ = ["DecisionContext"]


@dataclass(frozen=True, slots=True)
class DecisionContext:
    """Immutable input for one decision.

    Attributes:
        symbol: Instrument under decision.
        exchange: Neutral exchange label.
        market_snapshot: Latest normalized market snapshot, if available.
        signals: Strategy signals under consideration.
        risk_decision: The latest risk decision, if available.
        portfolio_result: Latest portfolio result, if available.
        position_result: Latest position result, if available.
        performance_result: Latest performance result, if available.
        parameters: Deterministic consensus parameters.
        agent_opinions: Analyst opinions (populated only for CEO arbitration).
        correlation_id: Optional correlation id propagated to events.
        timestamp: When the context was assembled (UTC).
        metadata: Optional read-only extra context.
    """

    symbol: str = "BTCUSDT"
    exchange: str = "neutral"
    market_snapshot: MarketSnapshot | None = None
    signals: tuple[TradingSignal, ...] = ()
    risk_decision: RiskDecision | None = None
    portfolio_result: PortfolioResult | None = None
    position_result: PositionResult | None = None
    performance_result: PerformanceResult | None = None
    parameters: DecisionParameters = field(default_factory=DecisionParameters)
    agent_opinions: tuple[AgentOpinion, ...] = ()
    correlation_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "signals", tuple(self.signals))
        object.__setattr__(self, "agent_opinions", tuple(self.agent_opinions))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def with_opinions(self, opinions: Sequence[AgentOpinion]) -> DecisionContext:
        """Return a copy carrying ``opinions`` (for CEO arbitration)."""
        from dataclasses import replace

        return replace(self, agent_opinions=tuple(opinions))
