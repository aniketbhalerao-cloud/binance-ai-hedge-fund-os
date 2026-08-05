"""Helpers for Optimization Framework tests.

Standalone support module (existing support files unchanged). Builds deterministic
optimization contexts from Learning Framework evaluation models. No network, no
sleeps, no randomness, and no model training.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from agents.models import AgentRole
from learning.models import AgentEvaluation, StrategyEvaluation
from optimization.context import OptimizationContext
from optimization.models import OptimizationParameters

__all__ = [
    "make_strategy_eval",
    "make_agent_eval",
    "make_context",
]


def make_strategy_eval(name: str, score: str, samples: int = 5) -> StrategyEvaluation:
    """Build a learning strategy evaluation with a given score."""
    return StrategyEvaluation(
        strategy_name=name, samples=samples, score=Decimal(score)
    )


def make_agent_eval(
    role: AgentRole = AgentRole.STRATEGY, score: str = "1", samples: int = 5
) -> AgentEvaluation:
    """Build a learning agent evaluation with a given score."""
    return AgentEvaluation(role=role, samples=samples, score=Decimal(score))


def make_context(
    *,
    optimization_id: str = "opt-1",
    strategies: Sequence[StrategyEvaluation] | None = None,
    agents: Sequence[AgentEvaluation] | None = None,
    parameters: OptimizationParameters | None = None,
    cancel: bool = False,
) -> OptimizationContext:
    """Build a deterministic optimization context."""
    metadata = {"cancel": True} if cancel else {}
    return OptimizationContext(
        optimization_id=optimization_id,
        strategy_evaluations=tuple(strategies) if strategies is not None
        else (make_strategy_eval("ema", "5"), make_strategy_eval("rsi", "-3")),
        agent_evaluations=tuple(agents) if agents is not None else (),
        parameters=parameters or OptimizationParameters(),
        correlation_id="opt-corr",
        metadata=metadata,
    )
