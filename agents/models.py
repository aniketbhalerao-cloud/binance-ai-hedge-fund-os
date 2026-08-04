"""AI Decision Engine domain models.

Immutable, exchange-independent value objects. The rest of the application
consumes only these standardized models. Confidences, weights, and monetary
figures use :class:`~decimal.Decimal`; timestamps are timezone-aware UTC. Every
model is frozen — decisions and opinions are never mutated.

Directional intent reuses :class:`~strategies.signals.SignalDirection` rather than
introducing a new enum (reuse over duplication).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any

from strategies.signals import SignalDirection

__all__ = [
    "AgentRole",
    "DecisionResultStatus",
    "AgentOpinion",
    "DecisionParameters",
    "ConsensusResult",
    "Decision",
    "DecisionSummary",
    "DecisionMetrics",
    "DecisionSnapshot",
    "DecisionHistory",
    "DecisionResult",
]

_ZERO = Decimal("0")
_ONE = Decimal("1")


class AgentRole(str, Enum):
    """The analytical role an agent plays in a decision."""

    MARKET = "market"
    STRATEGY = "strategy"
    RISK = "risk"
    PORTFOLIO = "portfolio"
    CEO = "ceo"


class DecisionResultStatus(str, Enum):
    """Coarse outcome of a decision run."""

    SUCCESS = "success"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class AgentOpinion:
    """An immutable opinion produced by one agent.

    Attributes:
        role: The role of the agent that produced it.
        direction: The directional stance (``HOLD`` for non-directional agents).
        confidence: Strength of the opinion, in ``[0, 1]``.
        approve: Whether the agent approves acting (a risk agent vetoes with
            ``False``); non-gating agents leave it ``True``.
        rationale: Short, non-sensitive explanation.
        metadata: Optional read-only extra context.
    """

    role: AgentRole
    direction: SignalDirection
    confidence: Decimal = _ZERO
    approve: bool = True
    rationale: str = ""
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DecisionParameters:
    """Deterministic consensus configuration.

    Attributes:
        min_confidence: Minimum aggregate confidence to approve a directional
            decision.
        risk_veto: When ``True``, any agent that disapproves blocks approval.
        weights: Per-role weights applied to the directional vote.
    """

    min_confidence: Decimal = Decimal("0.5")
    risk_veto: bool = True
    weights: Mapping[AgentRole, Decimal] = field(
        default_factory=lambda: MappingProxyType(
            {
                AgentRole.MARKET: _ONE,
                AgentRole.STRATEGY: _ONE,
                AgentRole.RISK: _ZERO,
                AgentRole.PORTFOLIO: Decimal("0.5"),
                AgentRole.CEO: Decimal("2"),
            }
        )
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "weights", MappingProxyType(dict(self.weights)))

    def weight_for(self, role: AgentRole) -> Decimal:
        """Return the directional weight for ``role`` (default ``1``)."""
        return self.weights.get(role, _ONE)


@dataclass(frozen=True, slots=True)
class ConsensusResult:
    """The output of the consensus resolver."""

    direction: SignalDirection
    confidence: Decimal
    approved: bool
    agreement_rate: Decimal
    buy_weight: Decimal = _ZERO
    sell_weight: Decimal = _ZERO
    hold_weight: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class Decision:
    """An immutable resolved decision."""

    id: str
    symbol: str
    direction: SignalDirection
    confidence: Decimal
    approved: bool
    opinions: tuple[AgentOpinion, ...]
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class DecisionSummary:
    """Compact summary of one decision's opinion set."""

    agent_count: int = 0
    buy_votes: int = 0
    sell_votes: int = 0
    hold_votes: int = 0
    approved: bool = False
    average_confidence: Decimal = _ZERO
    agreement_rate: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class DecisionMetrics:
    """Derived metrics over a set of decisions."""

    total_decisions: int = 0
    approval_rate: Decimal = _ZERO
    rejection_rate: Decimal = _ZERO
    agreement_rate: Decimal = _ZERO
    average_confidence: Decimal = _ZERO
    buy_decisions: int = 0
    sell_decisions: int = 0
    hold_decisions: int = 0
    average_agent_count: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class DecisionSnapshot:
    """A complete, immutable record of one decision."""

    decision: Decision
    summary: DecisionSummary
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class DecisionHistory:
    """Append-only record of resolved decisions."""

    decisions: tuple[Decision, ...] = ()

    def append(self, decision: Decision) -> DecisionHistory:
        """Return a new history with ``decision`` appended (never mutates)."""
        return DecisionHistory(self.decisions + (decision,))


@dataclass(frozen=True, slots=True)
class DecisionResult:
    """The immutable outcome of a decision run."""

    status: DecisionResultStatus
    decision: Decision | None = None
    snapshot: DecisionSnapshot | None = None
    metrics: DecisionMetrics | None = None
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Return ``True`` when the decision run completed successfully."""
        return self.status is DecisionResultStatus.SUCCESS
