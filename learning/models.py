"""Learning Framework domain models.

Immutable, exchange-independent value objects. The rest of the application
consumes only these standardized models. Money/scores use
:class:`~decimal.Decimal`; timestamps are timezone-aware UTC. Every model is
frozen — evaluations, feedback, and the running record are never mutated; each
learned outcome produces a **new** record.

Directional intent reuses :class:`~strategies.signals.SignalDirection` and agent
identity reuses :class:`~agents.models.AgentRole` (reuse over duplication).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from agents.models import AgentRole
from learning.state import LearningState
from strategies.signals import SignalDirection

__all__ = [
    "LearningResultStatus",
    "LearningParameters",
    "LearningOutcome",
    "JournalEntry",
    "StrategyEvaluation",
    "AgentEvaluation",
    "FeedbackRecommendation",
    "LearningHistory",
    "LearningRecord",
    "LearningMetrics",
    "LearningSnapshot",
    "LearningResult",
]

_ZERO = Decimal("0")


class LearningResultStatus(str, Enum):
    """Coarse outcome of processing one learned outcome."""

    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class LearningParameters:
    """Deterministic learning configuration.

    Attributes:
        min_samples: Minimum recorded outcomes for a subject before feedback.
        improvement_window: Trailing outcome count used for the improvement rate.
        adjustment_step: Magnitude of a weight/confidence recommendation.
        win_threshold: Score above which feedback recommends an increase.
    """

    min_samples: int = 3
    improvement_window: int = 10
    adjustment_step: Decimal = Decimal("0.1")
    win_threshold: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class LearningOutcome:
    """A single completed outcome to learn from (derived from a context)."""

    strategy_name: str
    agent_role: AgentRole
    direction: SignalDirection
    realized_pnl: Decimal
    won: bool
    approved: bool
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class JournalEntry:
    """An immutable, indexed journal entry wrapping one outcome."""

    index: int
    outcome: LearningOutcome


@dataclass(frozen=True, slots=True)
class StrategyEvaluation:
    """Derived evaluation for one strategy."""

    strategy_name: str
    samples: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: Decimal = _ZERO
    total_pnl: Decimal = _ZERO
    average_pnl: Decimal = _ZERO
    score: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class AgentEvaluation:
    """Derived evaluation for one agent role."""

    role: AgentRole
    samples: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: Decimal = _ZERO
    total_pnl: Decimal = _ZERO
    average_pnl: Decimal = _ZERO
    score: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class FeedbackRecommendation:
    """A deterministic recommendation to adjust a subject's weight/confidence."""

    subject: str
    kind: str
    action: str
    adjustment: Decimal
    rationale: str = ""


@dataclass(frozen=True, slots=True)
class LearningHistory:
    """Append-only journal of learned outcomes."""

    entries: tuple[JournalEntry, ...] = ()

    def append(self, entry: JournalEntry) -> LearningHistory:
        """Return a new history with ``entry`` appended (never mutates)."""
        return LearningHistory(self.entries + (entry,))


@dataclass(frozen=True, slots=True)
class LearningRecord:
    """The durable, immutable running state of one learning session.

    The Registry owns the current ``LearningRecord``; the Manager loads it,
    processes one outcome, and writes back a **new** ``LearningRecord``.
    """

    id: str
    state: LearningState
    history: LearningHistory = field(default_factory=LearningHistory)
    strategy_evaluations: tuple[StrategyEvaluation, ...] = ()
    agent_evaluations: tuple[AgentEvaluation, ...] = ()
    feedback: tuple[FeedbackRecommendation, ...] = ()
    outcome_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class LearningMetrics:
    """Derived metrics over a learning record."""

    total_outcomes: int = 0
    win_rate: Decimal = _ZERO
    average_score: Decimal = _ZERO
    average_pnl: Decimal = _ZERO
    best_strategy: str = ""
    worst_strategy: str = ""
    improvement_rate: Decimal = _ZERO
    feedback_count: int = 0


@dataclass(frozen=True, slots=True)
class LearningSnapshot:
    """A complete, immutable record of one learning update."""

    record: LearningRecord
    metrics: LearningMetrics
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class LearningResult:
    """The immutable outcome of processing one learned outcome."""

    status: LearningResultStatus
    record: LearningRecord | None = None
    snapshot: LearningSnapshot | None = None
    feedback: tuple[FeedbackRecommendation, ...] = ()
    metrics: LearningMetrics | None = None
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Return ``True`` when the outcome was learned successfully."""
        return self.status is LearningResultStatus.SUCCESS
