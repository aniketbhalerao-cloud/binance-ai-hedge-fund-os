"""Optimization planner.

:class:`DefaultPlanner` derives optimization targets from the learning evaluations
in a context, ranks them worst-first, and proposes an optimization step per target
(a direction and magnitude relative to the score threshold). It is deterministic
and stateless, and it only *proposes* — it never modifies any subject.
"""

from __future__ import annotations

from decimal import Decimal

from optimization.context import OptimizationContext
from optimization.exceptions import PlanningError
from optimization.models import (
    OptimizationParameters,
    OptimizationPlan,
    OptimizationStep,
    OptimizationTarget,
)

__all__ = ["DefaultPlanner"]

_ZERO = Decimal("0")


class DefaultPlanner:
    """Stateless target ranking and plan construction."""

    def plan(self, context: OptimizationContext) -> OptimizationPlan:
        """Return the :class:`OptimizationPlan` for ``context``.

        Raises:
            PlanningError: If an unexpected failure occurs.
        """
        try:
            targets = self._targets(context)
            steps = tuple(
                _step(t, context.parameters) for t in targets
            )
            return OptimizationPlan(targets=targets, steps=steps)
        except PlanningError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise PlanningError(str(exc)) from exc

    @staticmethod
    def _targets(
        context: OptimizationContext,
    ) -> tuple[OptimizationTarget, ...]:
        candidates = [
            OptimizationTarget(
                subject=s.strategy_name, kind="strategy", score=s.score,
                samples=s.samples,
            )
            for s in context.strategy_evaluations
        ]
        candidates += [
            OptimizationTarget(
                subject=a.role.value, kind="agent", score=a.score, samples=a.samples
            )
            for a in context.agent_evaluations
        ]
        # Worst-first, with a stable tiebreak by subject for determinism.
        candidates.sort(key=lambda t: (t.score, t.subject))
        return tuple(candidates[: context.parameters.max_targets])


def _step(
    target: OptimizationTarget, parameters: OptimizationParameters
) -> OptimizationStep:
    step = parameters.adjustment_step
    if target.score < parameters.score_threshold:
        action, adjustment, rationale = "decrease", -step, "below threshold"
    elif target.score > parameters.score_threshold:
        action, adjustment, rationale = "increase", step, "above threshold"
    else:
        action, adjustment, rationale = "hold", _ZERO, "at threshold"
    return OptimizationStep(
        target=target, action=action, adjustment=adjustment, rationale=rationale
    )
