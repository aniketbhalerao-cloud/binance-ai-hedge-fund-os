"""Optimization context.

An immutable input carrying the Learning Framework outputs to optimize over —
strategy and agent evaluations, feedback recommendations, and learning metrics —
plus the optimization parameters. Optimization components never access
infrastructure directly; they read only from this context and the models it
carries, and they never modify any subject.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from learning.models import (
    AgentEvaluation,
    FeedbackRecommendation,
    LearningMetrics,
    StrategyEvaluation,
)
from optimization.models import OptimizationParameters

__all__ = ["OptimizationContext"]


@dataclass(frozen=True, slots=True)
class OptimizationContext:
    """Immutable input for optimizing over learning outputs.

    Attributes:
        optimization_id: Identifier of the optimization record to update.
        strategy_evaluations: Learning strategy evaluations to optimize over.
        agent_evaluations: Learning agent evaluations to optimize over.
        feedback: Learning feedback recommendations (context only).
        learning_metrics: Learning metrics, if available.
        parameters: Deterministic optimization parameters.
        correlation_id: Optional correlation id propagated to events.
        timestamp: When the context was assembled (UTC).
        metadata: Optional read-only extra context.
    """

    optimization_id: str = "optimization"
    strategy_evaluations: tuple[StrategyEvaluation, ...] = ()
    agent_evaluations: tuple[AgentEvaluation, ...] = ()
    feedback: tuple[FeedbackRecommendation, ...] = ()
    learning_metrics: LearningMetrics | None = None
    parameters: OptimizationParameters = field(
        default_factory=OptimizationParameters
    )
    correlation_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "strategy_evaluations", tuple(self.strategy_evaluations)
        )
        object.__setattr__(self, "agent_evaluations", tuple(self.agent_evaluations))
        object.__setattr__(self, "feedback", tuple(self.feedback))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
