"""Recommendation generator.

:class:`DefaultRecommendations` turns the resolved plan's steps into deterministic
:class:`~optimization.models.Recommendation` proposals — a subject, a proposed
action, and a proposed adjustment. It is stateless and deterministic, and it
**never modifies** strategies, agents, or portfolios and never executes a
recommendation; it only proposes.
"""

from __future__ import annotations

from optimization.context import OptimizationContext
from optimization.exceptions import RecommendationError
from optimization.models import OptimizationPlan, Recommendation

__all__ = ["DefaultRecommendations"]


class DefaultRecommendations:
    """Stateless, deterministic recommendation generation (proposals only)."""

    def generate(
        self, plan: OptimizationPlan, context: OptimizationContext
    ) -> tuple[Recommendation, ...]:
        """Return one recommendation per actionable step in ``plan``.

        Raises:
            RecommendationError: If an unexpected failure occurs.
        """
        try:
            return tuple(
                Recommendation(
                    subject=step.target.subject,
                    kind=step.target.kind,
                    action=step.action,
                    adjustment=step.adjustment,
                    score=step.target.score,
                    rationale=step.rationale,
                )
                for step in plan.steps
            )
        except RecommendationError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise RecommendationError(str(exc)) from exc
