"""Optimizer.

:class:`DefaultOptimizer` resolves a plan into its actionable proposals: it drops
no-op (``hold``) steps and keeps the proposed adjustments, so the plan that flows
downstream contains only the steps worth recommending. It is deterministic and
stateless, and it **never applies** any change — it only resolves proposals.
"""

from __future__ import annotations

from optimization.context import OptimizationContext
from optimization.exceptions import OptimizerError
from optimization.models import OptimizationPlan

__all__ = ["DefaultOptimizer"]


class DefaultOptimizer:
    """Stateless plan resolution (proposals only, never applied)."""

    def optimize(
        self, plan: OptimizationPlan, context: OptimizationContext
    ) -> OptimizationPlan:
        """Return the resolved plan (actionable steps only).

        Raises:
            OptimizerError: If an unexpected failure occurs.
        """
        try:
            actionable = tuple(s for s in plan.steps if s.action != "hold")
            return OptimizationPlan(targets=plan.targets, steps=actionable)
        except OptimizerError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise OptimizerError(str(exc)) from exc
