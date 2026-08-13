"""Model Provider Gateway Framework — deterministic, immutable model
invocation requests from the system.

Consumes standardized outputs produced by the existing system (agent
decisions, memory records, learning records, and optimization plans,
assembled into a :class:`ModelGatewayContext`), collects a batch, plans it
into model invocation entries, deterministically routes each to a declared
:class:`ModelProviderProfile` candidate, and produces deterministic model
invocation requests and metrics. The Registry owns the running
:class:`ModelInvocationRecord`; the Manager loads it, processes one input
atomically, and writes back a new immutable record. It publishes model
gateway events on the shared event bus, is exchange-independent, and **only
plans and routes domain objects** — it never connects to Binance or any
exchange, calls an AI provider, imports a provider SDK, performs model
inference, computes an embedding, accesses a vector database, makes a
network request, handles or stores an API key, exposes a credential, writes
to a database, writes a file, opens a socket, executes a trade, modifies a
strategy, agent, learning, optimization, or portfolio state, trains a
model, or modifies any other framework. New collectors, planners, and
routing policies plug in without changing the framework (Open/Closed).

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from model_gateway.collector import DefaultCollector
from model_gateway.context import ModelGatewayContext
from model_gateway.dispatcher import DefaultDispatcher
from model_gateway.engine import DefaultModelGatewayEngine
from model_gateway.events import (
    InvocationsCollected,
    InvocationsPlanned,
    ModelGatewayCancelled,
    ModelGatewayCompleted,
    ModelGatewayErrorOccurred,
    ModelGatewayEvent,
    ModelGatewayMetricsUpdated,
    ModelGatewaySnapshotCreated,
    ModelGatewayStarted,
    RequestsDispatched,
)
from model_gateway.exceptions import (
    CollectionError,
    DispatchError,
    MetricsError,
    ModelGatewayCancelledError,
    ModelGatewayError,
    PlanningError,
    RegistryError,
)
from model_gateway.interfaces import (
    Collector,
    Dispatcher,
    ModelGatewayEngine,
    ModelGatewayManager,
    ModelGatewayMetricsCalculator,
    ModelGatewayRegistry,
    Planner,
)
from model_gateway.manager import DefaultModelGatewayManager
from model_gateway.metrics import DefaultModelGatewayMetrics
from model_gateway.models import (
    ModelGatewayHistory,
    ModelGatewayMetrics,
    ModelGatewayParameters,
    ModelGatewayResult,
    ModelGatewayResultStatus,
    ModelGatewaySnapshot,
    ModelInvocationBatch,
    ModelInvocationEntry,
    ModelInvocationRecord,
    ModelInvocationRequest,
    ModelInvocationSource,
    ModelProviderProfile,
)
from model_gateway.planner import DefaultPlanner
from model_gateway.registry import InMemoryModelGatewayRegistry
from model_gateway.state import ModelGatewayState

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = [
    # context & state
    "ModelGatewayContext",
    "ModelGatewayState",
    "ModelGatewayResultStatus",
    # models
    "ModelGatewayParameters",
    "ModelInvocationSource",
    "ModelProviderProfile",
    "ModelInvocationEntry",
    "ModelInvocationBatch",
    "ModelInvocationRequest",
    "ModelGatewayHistory",
    "ModelInvocationRecord",
    "ModelGatewayMetrics",
    "ModelGatewaySnapshot",
    "ModelGatewayResult",
    # interfaces
    "Collector",
    "Planner",
    "Dispatcher",
    "ModelGatewayMetricsCalculator",
    "ModelGatewayRegistry",
    "ModelGatewayManager",
    "ModelGatewayEngine",
    # implementations
    "DefaultCollector",
    "DefaultPlanner",
    "DefaultDispatcher",
    "DefaultModelGatewayMetrics",
    "InMemoryModelGatewayRegistry",
    "DefaultModelGatewayManager",
    "DefaultModelGatewayEngine",
    # events
    "ModelGatewayEvent",
    "ModelGatewayStarted",
    "InvocationsCollected",
    "InvocationsPlanned",
    "RequestsDispatched",
    "ModelGatewaySnapshotCreated",
    "ModelGatewayMetricsUpdated",
    "ModelGatewayCompleted",
    "ModelGatewayCancelled",
    "ModelGatewayErrorOccurred",
    # exceptions
    "ModelGatewayError",
    "CollectionError",
    "PlanningError",
    "DispatchError",
    "MetricsError",
    "RegistryError",
    "ModelGatewayCancelledError",
    # wiring
    "register_model_gateway",
]


def register_model_gateway(container: Container) -> None:
    """Register the Model Provider Gateway Framework services into a DI container.

    Registers the stateless collector/planner/dispatcher/metrics, the
    thread-safe registry, the manager, and the engine as singletons, bound
    to their abstractions (Dependency Inversion). ``EventBus`` is registered
    on demand; ``LoggerFactory`` is injected only if already registered. The
    framework never instantiates a model, provider, provider SDK, or
    network client.

    Args:
        container: The DI container to register into.
    """
    if not container.has(EventBus):
        container.register_class(EventBus)

    container.register_class(Collector, DefaultCollector)
    container.register_class(Planner, DefaultPlanner)
    container.register_class(Dispatcher, DefaultDispatcher)
    container.register_class(
        ModelGatewayMetricsCalculator, DefaultModelGatewayMetrics
    )
    container.register_class(ModelGatewayRegistry, InMemoryModelGatewayRegistry)

    def _build_manager(resolver: Resolver) -> DefaultModelGatewayManager:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultModelGatewayManager(
            resolver.resolve(EventBus),
            resolver.resolve(ModelGatewayRegistry),
            resolver.resolve(Collector),
            resolver.resolve(Planner),
            resolver.resolve(Dispatcher),
            resolver.resolve(ModelGatewayMetricsCalculator),
            logger=logger,
        )

    container.register_singleton(DefaultModelGatewayManager, _build_manager)
    container.register_singleton(
        ModelGatewayManager, lambda r: r.resolve(DefaultModelGatewayManager)
    )

    def _build_engine(resolver: Resolver) -> DefaultModelGatewayEngine:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultModelGatewayEngine(
            resolver.resolve(ModelGatewayManager), logger=logger
        )

    container.register_singleton(DefaultModelGatewayEngine, _build_engine)
    container.register_singleton(
        ModelGatewayEngine, lambda r: r.resolve(DefaultModelGatewayEngine)
    )
