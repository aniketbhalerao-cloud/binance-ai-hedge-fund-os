"""Optimization metrics.

:class:`DefaultOptimizationMetrics` derives aggregate metrics from an optimization
record: plan and recommendation counts, average target score, best and worst
target, the improvement potential of the pending proposals, and the applied /
pending split. It is stateless and pure — metrics are always derived from the
record — and all arithmetic is :class:`~decimal.Decimal`.

``applied_count`` is always zero by design: the framework only proposes, it never
applies a recommendation.
"""

from __future__ import annotations

from decimal import Decimal

from optimization.exceptions import MetricsError
from optimization.models import OptimizationMetrics, OptimizationRecord

__all__ = ["DefaultOptimizationMetrics"]

_ZERO = Decimal("0")


class DefaultOptimizationMetrics:
    """Stateless optimization metrics derived from a record."""

    def calculate(self, record: OptimizationRecord) -> OptimizationMetrics:
        """Return :class:`OptimizationMetrics` for ``record``.

        Raises:
            MetricsError: If an unexpected failure occurs.
        """
        try:
            return self._calculate(record)
        except MetricsError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise MetricsError(str(exc)) from exc

    def _calculate(self, record: OptimizationRecord) -> OptimizationMetrics:
        targets = record.plan.targets
        pending = len(record.recommendations)
        potential = sum(
            (abs(step.adjustment) for step in record.plan.steps), _ZERO
        )

        if targets:
            best = max(targets, key=lambda t: t.score)
            worst = min(targets, key=lambda t: t.score)
            avg_score = sum((t.score for t in targets), _ZERO) / Decimal(len(targets))
            best_name, worst_name = best.subject, worst.subject
        else:
            avg_score, best_name, worst_name = _ZERO, "", ""

        return OptimizationMetrics(
            total_plans=record.plan_count,
            total_recommendations=record.recommendation_count,
            average_score=avg_score,
            best_target=best_name,
            worst_target=worst_name,
            improvement_potential=potential,
            applied_count=0,  # proposals are never applied
            pending_count=pending,
        )
