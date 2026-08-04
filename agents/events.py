"""AI Decision Engine events.

Each inherits the existing :class:`events.base.Event` and is immutable. The
framework publishes **only** these — never strategy, risk, order, execution,
portfolio, position, trade, performance, backtesting, or paper-trading events.
Events are published only after a consistent decision (or an isolated failure).
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event

__all__ = [
    "DecisionEvent",
    "DecisionRequested",
    "AgentEvaluated",
    "ConsensusReached",
    "DecisionMade",
    "DecisionRejected",
    "DecisionSnapshotCreated",
    "DecisionMetricsUpdated",
    "DecisionCancelled",
    "AgentErrorOccurred",
    "DecisionErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionEvent(Event):
    """Base class for all decision events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionRequested(DecisionEvent):
    """A decision run was requested."""

    decision_id: str
    symbol: str


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentEvaluated(DecisionEvent):
    """An agent produced an opinion for a decision."""

    decision_id: str
    role: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ConsensusReached(DecisionEvent):
    """Consensus was resolved for a decision."""

    decision_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionMade(DecisionEvent):
    """A decision was made and approved."""

    decision_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionRejected(DecisionEvent):
    """A decision was resolved but not approved."""

    decision_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionSnapshotCreated(DecisionEvent):
    """A decision snapshot was created."""

    decision_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionMetricsUpdated(DecisionEvent):
    """Decision metrics were recomputed."""

    decision_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionCancelled(DecisionEvent):
    """A decision run was cancelled."""

    decision_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentErrorOccurred(DecisionEvent):
    """An agent failed during a decision run."""

    decision_id: str
    role: str
    message: str


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionErrorOccurred(DecisionEvent):
    """A decision run failed and was isolated by the manager."""

    decision_id: str
    message: str
