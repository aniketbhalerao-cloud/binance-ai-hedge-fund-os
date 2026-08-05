"""Optimization Framework — deterministic optimization proposals from learning.

Consumes the Learning Framework outputs (strategy and agent evaluations, feedback,
and learning metrics, assembled into an :class:`OptimizationContext`), builds a
plan, resolves it, and produces deterministic recommendations and metrics. The
Registry owns the running :class:`OptimizationRecord`; the Manager loads it,
processes one input atomically, and writes back a new immutable record. It
publishes optimization events on the shared event bus, is exchange-independent, and
**only proposes** — it never applies a recommendation, modifies a strategy, agent,
or portfolio, trains a model, or makes a network/provider call. New planners,
optimizers, and recommendation policies plug in without changing the framework
(Open/Closed).

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from optimization.context import OptimizationContext
from optimization.engine import DefaultOptimizationEngine
from optimization.events import (
    OptimizationCancelled,
    OptimizationCompleted,
    OptimizationErrorOccurred,
    OptimizationEvaluated,
    OptimizationEvent,
    OptimizationMetricsUpdated,
    OptimizationSnapshotCreated,
    OptimizationStarted,
    PlanCreated,
    RecommendationsGenerated,
)
from optimization.exceptions import (
    MetricsError,
    OptimizationCancelledError,
    OptimizationError,
    OptimizerError,
    PlanningError,
    RecommendationError,
    RegistryError,
)
from optimization.interfaces import (
    OptimizationEngine,
    OptimizationManager,
    OptimizationMetricsCalculator,
    OptimizationRegistry,
    Optimizer,
    Planner,
    RecommendationGenerator,
)
from optimization.manager import DefaultOptimizationManager
from optimization.metrics import DefaultOptimizationMetrics
from optimization.models import (
    OptimizationHistory,
    OptimizationMetrics,
    OptimizationParameters,
    OptimizationPlan,
    OptimizationRecord,
    OptimizationResult,
    OptimizationResultStatus,
    OptimizationSnapshot,
    OptimizationStep,
    OptimizationTarget,
    Recommendation,
)
from optimization.optimizer import DefaultOptimizer
from optimization.planner import DefaultPlanner
from optimization.recommendations import DefaultRecommendations
from optimization.registry import InMemoryOptimizationRegistry
from optimization.state import OptimizationState

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = [
    # context & state
    "OptimizationContext",
    "OptimizationState",
    "OptimizationResultStatus",
    # models
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
    # interfaces
    "Planner",
    "Optimizer",
    "RecommendationGenerator",
    "OptimizationMetricsCalculator",
    "OptimizationRegistry",
    "OptimizationManager",
    "OptimizationEngine",
    # implementations
    "DefaultPlanner",
    "DefaultOptimizer",
    "DefaultRecommendations",
    "DefaultOptimizationMetrics",
    "InMemoryOptimizationRegistry",
    "DefaultOptimizationManager",
    "DefaultOptimizationEngine",
    # events
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
    # exceptions
    "OptimizationError",
    "PlanningError",
    "OptimizerError",
    "RecommendationError",
    "MetricsError",
    "RegistryError",
    "OptimizationCancelledError",
    # wiring
    "register_optimization",
]


def register_optimization(container: Container) -> None:
    """Register the Optimization Framework services into a DI container.

    Registers the stateless planner/optimizer/recommendations/metrics, the
    thread-safe registry, the manager, and the engine as singletons, bound to
    their abstractions (Dependency Inversion). ``EventBus`` is registered on
    demand; ``LoggerFactory`` is injected only if already registered. The framework
    never instantiates a model, provider, or network client.

    Args:
        container: The DI container to register into.
    """
    if not container.has(EventBus):
        container.register_class(EventBus)

    container.register_class(Planner, DefaultPlanner)
    container.register_class(Optimizer, DefaultOptimizer)
    container.register_class(RecommendationGenerator, DefaultRecommendations)
    container.register_class(
        OptimizationMetricsCalculator, DefaultOptimizationMetrics
    )
    container.register_class(OptimizationRegistry, InMemoryOptimizationRegistry)

    def _build_manager(resolver: Resolver) -> DefaultOptimizationManager:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultOptimizationManager(
            resolver.resolve(EventBus),
            resolver.resolve(OptimizationRegistry),
            resolver.resolve(Planner),
            resolver.resolve(Optimizer),
            resolver.resolve(RecommendationGenerator),
            resolver.resolve(OptimizationMetricsCalculator),
            logger=logger,
        )

    container.register_singleton(DefaultOptimizationManager, _build_manager)
    container.register_singleton(
        OptimizationManager, lambda r: r.resolve(DefaultOptimizationManager)
    )

    def _build_engine(resolver: Resolver) -> DefaultOptimizationEngine:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultOptimizationEngine(
            resolver.resolve(OptimizationManager), logger=logger
        )

    container.register_singleton(DefaultOptimizationEngine, _build_engine)
    container.register_singleton(
        OptimizationEngine, lambda r: r.resolve(DefaultOptimizationEngine)
    )
