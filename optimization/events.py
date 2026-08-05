"""Optimization Framework events.

Each inherits the existing :class:`events.base.Event` and is immutable. The
framework publishes **only** these — never learning, strategy, agent, or any other
framework's events. Events are published only after a consistent record update (or
an isolated failure).
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event

__all__ = [
    "OptimizationEvent",
    "OptimizationStarted",
    "PlanCreated",
    "OptimizationEvaluated",
    "RecommendationsGenerated",
    "OptimizationSnapshotCreated",
    "OptimizationMetricsUpdated",
    "OptimizationCompleted",
    "OptimizationCancelled",
    "OptimizationErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class OptimizationEvent(Event):
    """Base class for all optimization events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class OptimizationStarted(OptimizationEvent):
    """An optimization update was requested for a record."""

    optimization_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PlanCreated(OptimizationEvent):
    """An optimization plan was created."""

    optimization_id: str
    targets: int


@dataclass(frozen=True, slots=True, kw_only=True)
class OptimizationEvaluated(OptimizationEvent):
    """The plan was scored and resolved."""

    optimization_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RecommendationsGenerated(OptimizationEvent):
    """Recommendations were generated (proposed, not applied)."""

    optimization_id: str
    count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class OptimizationSnapshotCreated(OptimizationEvent):
    """An optimization snapshot was created."""

    optimization_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class OptimizationMetricsUpdated(OptimizationEvent):
    """Optimization metrics were recomputed."""

    optimization_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class OptimizationCompleted(OptimizationEvent):
    """An optimization update completed successfully."""

    optimization_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class OptimizationCancelled(OptimizationEvent):
    """An optimization session was cancelled."""

    optimization_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class OptimizationErrorOccurred(OptimizationEvent):
    """An optimization update failed and was isolated by the manager."""

    optimization_id: str
    message: str
