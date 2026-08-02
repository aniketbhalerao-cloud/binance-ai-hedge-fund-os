"""Risk Framework events.

Each inherits the existing :class:`events.base.Event` and is immutable. The
framework publishes **only** these — never orders, trades, portfolio updates,
strategy events, or execution events.
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event
from risk.models import RiskDecision

__all__ = [
    "RiskEvent",
    "RiskEvaluationStarted",
    "RiskEvaluationCompleted",
    "RiskRulePassed",
    "RiskRuleFailed",
    "RiskDecisionApproved",
    "RiskDecisionRejected",
    "RiskEngineStarted",
    "RiskEngineStopped",
    "RiskErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskEvent(Event):
    """Base class for all risk events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskEvaluationStarted(RiskEvent):
    """A risk evaluation began for a symbol."""

    symbol: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskEvaluationCompleted(RiskEvent):
    """A risk evaluation finished, yielding a decision."""

    decision: RiskDecision


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskRulePassed(RiskEvent):
    """A single rule passed."""

    rule: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskRuleFailed(RiskEvent):
    """A single rule produced a violation."""

    rule: str
    message: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskDecisionApproved(RiskEvent):
    """The evaluation approved the signal."""

    decision: RiskDecision


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskDecisionRejected(RiskEvent):
    """The evaluation rejected the signal."""

    decision: RiskDecision


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskEngineStarted(RiskEvent):
    """The risk engine started."""


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskEngineStopped(RiskEvent):
    """The risk engine stopped."""


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskErrorOccurred(RiskEvent):
    """A rule raised an error during evaluation."""

    rule: str
    message: str
