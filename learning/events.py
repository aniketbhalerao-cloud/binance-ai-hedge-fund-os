"""Learning Framework events.

Each inherits the existing :class:`events.base.Event` and is immutable. The
framework publishes **only** these — never strategy, risk, trade, performance,
decision, backtesting, or paper-trading events. Events are published only after a
consistent record update (or an isolated failure).
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event

__all__ = [
    "LearningEvent",
    "LearningStarted",
    "OutcomeRecorded",
    "StrategyEvaluated",
    "AgentEvaluated",
    "FeedbackGenerated",
    "LearningSnapshotCreated",
    "LearningMetricsUpdated",
    "LearningCompleted",
    "LearningCancelled",
    "LearningErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class LearningEvent(Event):
    """Base class for all learning events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class LearningStarted(LearningEvent):
    """A learning update was requested for a record."""

    learning_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class OutcomeRecorded(LearningEvent):
    """An outcome was appended to the journal."""

    learning_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyEvaluated(LearningEvent):
    """Strategy evaluations were recomputed."""

    learning_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentEvaluated(LearningEvent):
    """Agent evaluations were recomputed."""

    learning_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class FeedbackGenerated(LearningEvent):
    """Feedback recommendations were generated."""

    learning_id: str
    count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class LearningSnapshotCreated(LearningEvent):
    """A learning snapshot was created."""

    learning_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class LearningMetricsUpdated(LearningEvent):
    """Learning metrics were recomputed."""

    learning_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class LearningCompleted(LearningEvent):
    """A learning update completed successfully."""

    learning_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class LearningCancelled(LearningEvent):
    """A learning session was cancelled."""

    learning_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class LearningErrorOccurred(LearningEvent):
    """A learning update failed and was isolated by the manager."""

    learning_id: str
    message: str
