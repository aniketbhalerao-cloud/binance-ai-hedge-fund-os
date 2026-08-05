"""Optimization Framework domain models.

Immutable, exchange-independent value objects. The rest of the application
consumes only these standardized models. Scores use :class:`~decimal.Decimal`;
timestamps are timezone-aware UTC. Every model is frozen — plans, recommendations,
and the running record are never mutated; each optimized input produces a **new**
record.

The framework only *proposes*: recommendations carry proposed adjustments and are
never applied to strategies, agents, or portfolios.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from optimization.state import OptimizationState

__all__ = [
    "OptimizationResultStatus",
    "OptimizationParameters",
    "OptimizationTarget",
    "OptimizationStep",
    "OptimizationPlan",
    "Recommendation",
    "OptimizationHistory",
    "OptimizationRecord",
    "OptimizationMetrics",
    "OptimizationSnapshot",
    "OptimizationResult",
]

_ZERO = Decimal("0")


class OptimizationResultStatus(str, Enum):
    """Coarse outcome of optimizing one input."""

    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class OptimizationParameters:
    """Deterministic optimization configuration.

    Attributes:
        score_threshold: Score at or below which a target is underperforming.
        max_targets: Maximum number of targets to plan per input.
        adjustment_step: Magnitude of a proposed weight/confidence change.
    """

    score_threshold: Decimal = _ZERO
    max_targets: int = 5
    adjustment_step: Decimal = Decimal("0.1")


@dataclass(frozen=True, slots=True)
class OptimizationTarget:
    """A subject (strategy or agent) selected for optimization."""

    subject: str
    kind: str
    score: Decimal = _ZERO
    samples: int = 0


@dataclass(frozen=True, slots=True)
class OptimizationStep:
    """A single proposed optimization step for a target (never applied)."""

    target: OptimizationTarget
    action: str
    adjustment: Decimal
    rationale: str = ""


@dataclass(frozen=True, slots=True)
class OptimizationPlan:
    """An immutable plan: the ranked targets and their proposed steps."""

    targets: tuple[OptimizationTarget, ...] = ()
    steps: tuple[OptimizationStep, ...] = ()


@dataclass(frozen=True, slots=True)
class Recommendation:
    """A deterministic recommendation (a proposed change, never applied)."""

    subject: str
    kind: str
    action: str
    adjustment: Decimal
    score: Decimal = _ZERO
    rationale: str = ""


@dataclass(frozen=True, slots=True)
class OptimizationHistory:
    """Append-only record of produced plans."""

    plans: tuple[OptimizationPlan, ...] = ()

    def append(self, plan: OptimizationPlan) -> OptimizationHistory:
        """Return a new history with ``plan`` appended (never mutates)."""
        return OptimizationHistory(self.plans + (plan,))


@dataclass(frozen=True, slots=True)
class OptimizationRecord:
    """The durable, immutable running state of one optimization session.

    The Registry owns the current ``OptimizationRecord``; the Manager loads it,
    processes one input, and writes back a **new** ``OptimizationRecord``.
    """

    id: str
    state: OptimizationState
    history: OptimizationHistory = field(default_factory=OptimizationHistory)
    plan: OptimizationPlan = field(default_factory=OptimizationPlan)
    recommendations: tuple[Recommendation, ...] = ()
    plan_count: int = 0
    recommendation_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class OptimizationMetrics:
    """Derived metrics over an optimization record."""

    total_plans: int = 0
    total_recommendations: int = 0
    average_score: Decimal = _ZERO
    best_target: str = ""
    worst_target: str = ""
    improvement_potential: Decimal = _ZERO
    applied_count: int = 0
    pending_count: int = 0


@dataclass(frozen=True, slots=True)
class OptimizationSnapshot:
    """A complete, immutable record of one optimization update."""

    record: OptimizationRecord
    metrics: OptimizationMetrics
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    """The immutable outcome of optimizing one input."""

    status: OptimizationResultStatus
    record: OptimizationRecord | None = None
    snapshot: OptimizationSnapshot | None = None
    plan: OptimizationPlan | None = None
    recommendations: tuple[Recommendation, ...] = ()
    metrics: OptimizationMetrics | None = None
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Return ``True`` when the input was optimized successfully."""
        return self.status is OptimizationResultStatus.SUCCESS
