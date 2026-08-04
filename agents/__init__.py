"""AI Decision Engine — autonomous agents that reason over standardized results.

Coordinates a set of specialised agents (Market, Strategy, Risk, Portfolio, and a
coordinating CEO) that reason **deterministically** over the standardized results
the existing frameworks produce (assembled into a :class:`DecisionContext`),
aggregates their opinions into a single immutable :class:`Decision`, and publishes
decision events on the shared event bus. It is exchange-independent and
AI-provider-independent: agents are injected abstractions and the framework core
never calls a model, provider, or network client. New agents plug in without
changing the framework (Open/Closed).

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agents.agent import (
    BaseAgent,
    DefaultCEOAgent,
    DefaultMarketAgent,
    DefaultPortfolioAgent,
    DefaultRiskAgent,
    DefaultStrategyAgent,
)
from agents.consensus import DefaultConsensus
from agents.context import DecisionContext
from agents.engine import DefaultDecisionEngine
from agents.events import (
    AgentErrorOccurred,
    AgentEvaluated,
    ConsensusReached,
    DecisionCancelled,
    DecisionErrorOccurred,
    DecisionEvent,
    DecisionMade,
    DecisionMetricsUpdated,
    DecisionRejected,
    DecisionRequested,
    DecisionSnapshotCreated,
)
from agents.exceptions import (
    AgentError,
    AgentNotFoundError,
    ConsensusError,
    DecisionError,
    DecisionRejectedError,
    HistoryError,
    MetricsError,
    RegistryError,
)
from agents.history import DefaultDecisionHistory
from agents.interfaces import (
    Agent,
    AgentRegistry,
    ConsensusResolver,
    DecisionEngine,
    DecisionHistoryService,
    DecisionManager,
    DecisionMetricsCalculator,
)
from agents.manager import DefaultDecisionManager
from agents.metrics import DefaultDecisionMetrics
from agents.models import (
    AgentOpinion,
    AgentRole,
    ConsensusResult,
    Decision,
    DecisionHistory,
    DecisionMetrics,
    DecisionParameters,
    DecisionResult,
    DecisionResultStatus,
    DecisionSnapshot,
    DecisionSummary,
)
from agents.registry import InMemoryAgentRegistry
from agents.state import DecisionState
from core.logging import LoggerFactory
from events.bus import EventBus

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = [
    # context & state
    "DecisionContext",
    "DecisionState",
    "DecisionResultStatus",
    # models
    "AgentRole",
    "AgentOpinion",
    "DecisionParameters",
    "ConsensusResult",
    "Decision",
    "DecisionSummary",
    "DecisionMetrics",
    "DecisionSnapshot",
    "DecisionHistory",
    "DecisionResult",
    # interfaces
    "Agent",
    "ConsensusResolver",
    "DecisionMetricsCalculator",
    "DecisionHistoryService",
    "AgentRegistry",
    "DecisionManager",
    "DecisionEngine",
    # implementations
    "BaseAgent",
    "DefaultMarketAgent",
    "DefaultStrategyAgent",
    "DefaultRiskAgent",
    "DefaultPortfolioAgent",
    "DefaultCEOAgent",
    "DefaultConsensus",
    "DefaultDecisionMetrics",
    "DefaultDecisionHistory",
    "InMemoryAgentRegistry",
    "DefaultDecisionManager",
    "DefaultDecisionEngine",
    # events
    "DecisionEvent",
    "DecisionRequested",
    "AgentEvaluated",
    "ConsensusReached",
    "DecisionMade",
    "DecisionRejected",
    "DecisionSnapshotCreated",
    "DecisionMetricsUpdated",
    "DecisionCancelled",
    "AgentErrorOccurred",
    "DecisionErrorOccurred",
    # exceptions
    "DecisionError",
    "AgentError",
    "ConsensusError",
    "MetricsError",
    "HistoryError",
    "RegistryError",
    "AgentNotFoundError",
    "DecisionRejectedError",
    # wiring
    "register_agents",
]


def register_agents(container: Container) -> None:
    """Register the AI Decision Engine services into a DI container.

    Registers the stateless resolver/metrics/history, the thread-safe agent
    registry (pre-populated with the deterministic default agents), the manager,
    and the engine as singletons, bound to their abstractions (Dependency
    Inversion). ``EventBus`` is registered on demand; ``LoggerFactory`` is injected
    only if already registered. Concrete agents are injected through the registry;
    the framework never instantiates a model, provider, or network client.

    Args:
        container: The DI container to register into.
    """
    if not container.has(EventBus):
        container.register_class(EventBus)

    container.register_class(ConsensusResolver, DefaultConsensus)
    container.register_class(DecisionMetricsCalculator, DefaultDecisionMetrics)
    container.register_class(DecisionHistoryService, DefaultDecisionHistory)

    def _build_registry(_resolver: Resolver) -> InMemoryAgentRegistry:
        registry = InMemoryAgentRegistry()
        registry.register(DefaultMarketAgent())
        registry.register(DefaultStrategyAgent())
        registry.register(DefaultRiskAgent())
        registry.register(DefaultPortfolioAgent())
        registry.register(DefaultCEOAgent())
        return registry

    container.register_singleton(InMemoryAgentRegistry, _build_registry)
    container.register_singleton(
        AgentRegistry, lambda r: r.resolve(InMemoryAgentRegistry)
    )

    def _build_manager(resolver: Resolver) -> DefaultDecisionManager:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultDecisionManager(
            resolver.resolve(EventBus),
            resolver.resolve(AgentRegistry),
            resolver.resolve(ConsensusResolver),
            resolver.resolve(DecisionMetricsCalculator),
            resolver.resolve(DecisionHistoryService),
            logger=logger,
        )

    container.register_singleton(DefaultDecisionManager, _build_manager)
    container.register_singleton(
        DecisionManager, lambda r: r.resolve(DefaultDecisionManager)
    )

    def _build_engine(resolver: Resolver) -> DefaultDecisionEngine:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultDecisionEngine(resolver.resolve(DecisionManager), logger=logger)

    container.register_singleton(DefaultDecisionEngine, _build_engine)
    container.register_singleton(
        DecisionEngine, lambda r: r.resolve(DefaultDecisionEngine)
    )
