"""Learning Framework — continuous improvement from completed trading activity.

Consumes the standardized outcomes the existing frameworks produce (a decision
result, a trade result, and a performance result for one completed activity),
records them in an append-only journal, evaluates strategy and agent performance,
generates deterministic feedback, and produces learning metrics — closing the
improvement loop. The Registry owns the running :class:`LearningRecord`; the
Manager loads it, processes one outcome atomically, and writes back a new
immutable record. It publishes learning events on the shared event bus, is
exchange-independent, and never trains a model, makes a network call, or uses an
external ML library. New evaluators, feedback policies, and metric families plug
in without changing the framework (Open/Closed).

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from learning.context import LearningContext
from learning.engine import DefaultLearningEngine
from learning.evaluator import DefaultEvaluator
from learning.events import (
    AgentEvaluated,
    FeedbackGenerated,
    LearningCancelled,
    LearningCompleted,
    LearningErrorOccurred,
    LearningEvent,
    LearningMetricsUpdated,
    LearningSnapshotCreated,
    LearningStarted,
    OutcomeRecorded,
    StrategyEvaluated,
)
from learning.exceptions import (
    EvaluationError,
    FeedbackError,
    JournalError,
    LearningCancelledError,
    LearningError,
    MetricsError,
    RegistryError,
)
from learning.feedback import DefaultFeedback
from learning.interfaces import (
    Evaluator,
    FeedbackGenerator,
    Journal,
    LearningEngine,
    LearningManager,
    LearningMetricsCalculator,
    LearningRegistry,
)
from learning.journal import DefaultJournal
from learning.manager import DefaultLearningManager
from learning.metrics import DefaultLearningMetrics
from learning.models import (
    AgentEvaluation,
    FeedbackRecommendation,
    JournalEntry,
    LearningHistory,
    LearningMetrics,
    LearningOutcome,
    LearningParameters,
    LearningRecord,
    LearningResult,
    LearningResultStatus,
    LearningSnapshot,
    StrategyEvaluation,
)
from learning.registry import InMemoryLearningRegistry
from learning.state import LearningState

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = [
    # context & state
    "LearningContext",
    "LearningState",
    "LearningResultStatus",
    # models
    "LearningParameters",
    "LearningOutcome",
    "JournalEntry",
    "StrategyEvaluation",
    "AgentEvaluation",
    "FeedbackRecommendation",
    "LearningHistory",
    "LearningRecord",
    "LearningMetrics",
    "LearningSnapshot",
    "LearningResult",
    # interfaces
    "Journal",
    "Evaluator",
    "FeedbackGenerator",
    "LearningMetricsCalculator",
    "LearningRegistry",
    "LearningManager",
    "LearningEngine",
    # implementations
    "DefaultJournal",
    "DefaultEvaluator",
    "DefaultFeedback",
    "DefaultLearningMetrics",
    "InMemoryLearningRegistry",
    "DefaultLearningManager",
    "DefaultLearningEngine",
    # events
    "LearningEvent",
    "LearningStarted",
    "OutcomeRecorded",
    "StrategyEvaluated",
    "AgentEvaluated",
    "FeedbackGenerated",
    "LearningSnapshotCreated",
    "LearningMetricsUpdated",
    "LearningCompleted",
    "LearningCancelled",
    "LearningErrorOccurred",
    # exceptions
    "LearningError",
    "JournalError",
    "EvaluationError",
    "FeedbackError",
    "MetricsError",
    "RegistryError",
    "LearningCancelledError",
    # wiring
    "register_learning",
]


def register_learning(container: Container) -> None:
    """Register the Learning Framework services into a DI container.

    Registers the stateless journal/evaluator/feedback/metrics, the thread-safe
    registry, the manager, and the engine as singletons, bound to their
    abstractions (Dependency Inversion). ``EventBus`` is registered on demand;
    ``LoggerFactory`` is injected only if already registered. The framework never
    instantiates a model, trainer, provider, or network client.

    Args:
        container: The DI container to register into.
    """
    if not container.has(EventBus):
        container.register_class(EventBus)

    container.register_class(Journal, DefaultJournal)
    container.register_class(Evaluator, DefaultEvaluator)
    container.register_class(FeedbackGenerator, DefaultFeedback)
    container.register_class(LearningMetricsCalculator, DefaultLearningMetrics)
    container.register_class(LearningRegistry, InMemoryLearningRegistry)

    def _build_manager(resolver: Resolver) -> DefaultLearningManager:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultLearningManager(
            resolver.resolve(EventBus),
            resolver.resolve(LearningRegistry),
            resolver.resolve(Journal),
            resolver.resolve(Evaluator),
            resolver.resolve(FeedbackGenerator),
            resolver.resolve(LearningMetricsCalculator),
            logger=logger,
        )

    container.register_singleton(DefaultLearningManager, _build_manager)
    container.register_singleton(
        LearningManager, lambda r: r.resolve(DefaultLearningManager)
    )

    def _build_engine(resolver: Resolver) -> DefaultLearningEngine:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultLearningEngine(resolver.resolve(LearningManager), logger=logger)

    container.register_singleton(DefaultLearningEngine, _build_engine)
    container.register_singleton(
        LearningEngine, lambda r: r.resolve(DefaultLearningEngine)
    )
