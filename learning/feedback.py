"""Learning feedback.

:class:`DefaultFeedback` turns evaluations into deterministic recommendations to
adjust a subject's weight or confidence. The policy is pure and rule-based: a
subject with enough samples and a score above the threshold is recommended an
*increase*; below the threshold, a *decrease*; otherwise *hold*. There is no model
training, randomness, or network involved.

Stateless and pure: all arithmetic is :class:`~decimal.Decimal`.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from learning.exceptions import FeedbackError
from learning.models import (
    AgentEvaluation,
    FeedbackRecommendation,
    LearningParameters,
    StrategyEvaluation,
)

__all__ = ["DefaultFeedback"]

_ZERO = Decimal("0")


class DefaultFeedback:
    """Stateless, deterministic feedback generation from evaluations."""

    def generate(
        self,
        strategies: Sequence[StrategyEvaluation],
        agents: Sequence[AgentEvaluation],
        parameters: LearningParameters,
    ) -> tuple[FeedbackRecommendation, ...]:
        """Return recommendations for subjects with enough samples.

        Raises:
            FeedbackError: If an unexpected failure occurs.
        """
        try:
            recommendations: list[FeedbackRecommendation] = []
            for strategy in strategies:
                rec = self._recommend(
                    strategy.strategy_name, "strategy", strategy.samples,
                    strategy.score, parameters,
                )
                if rec is not None:
                    recommendations.append(rec)
            for agent in agents:
                rec = self._recommend(
                    agent.role.value, "agent", agent.samples, agent.score, parameters
                )
                if rec is not None:
                    recommendations.append(rec)
            return tuple(recommendations)
        except FeedbackError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise FeedbackError(str(exc)) from exc

    @staticmethod
    def _recommend(
        subject: str,
        kind: str,
        samples: int,
        score: object,
        parameters: LearningParameters,
    ) -> FeedbackRecommendation | None:
        if samples < parameters.min_samples:
            return None
        step = parameters.adjustment_step
        if score > parameters.win_threshold:  # type: ignore[operator]
            action, adjustment, rationale = "increase", step, "positive expectancy"
        elif score < parameters.win_threshold:  # type: ignore[operator]
            action, adjustment, rationale = "decrease", -step, "negative expectancy"
        else:
            action, adjustment, rationale = "hold", _ZERO, "neutral"
        return FeedbackRecommendation(
            subject=subject,
            kind=kind,
            action=action,
            adjustment=adjustment,
            rationale=rationale,
        )
