"""Workflow Orchestration Framework — deterministic, immutable, declarative
multi-step workflow composition.

Consumes declarative :class:`~workflows.models.WorkflowDefinition` objects
supplied on a :class:`~workflows.context.WorkflowContext`, collects a batch,
validates each definition's independent dependency graph, deterministically
orders workflows and their steps into a :class:`~workflows.models.WorkflowPlan`,
and produces deterministic :class:`~workflows.models.WorkflowRequest`
handoff-intent objects only. The Registry owns the running
:class:`~workflows.models.WorkflowRecord`; the Manager loads it, processes
one input atomically, and writes back a new immutable record. It publishes
workflow events on the shared event bus, and **only validates, orders, and
plans domain objects** — it never executes a workflow step, triggers an
Agent, calls ``ModelGatewayManager.invoke()``, ``SchedulerManager.schedule()``,
or ``WorkerManager.enqueue()``, executes a trade, performs inference, makes a
network request, spawns a thread or process, sleeps, writes a file or
database, or mutates any other framework's state. New collectors, planners,
and ordering policies plug in without changing the framework (Open/Closed).

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from workflows.collector import DefaultCollector
from workflows.context import WorkflowContext
from workflows.dispatcher import DefaultDispatcher
from workflows.engine import DefaultWorkflowEngine
from workflows.events import (
    RequestsDispatched,
    StepsCollected,
    WorkflowCancelled,
    WorkflowCompleted,
    WorkflowErrorOccurred,
    WorkflowEvent,
    WorkflowMetricsUpdated,
    WorkflowPlanned,
    WorkflowSnapshotCreated,
    WorkflowStarted,
)
from workflows.exceptions import (
    CollectionError,
    DispatchError,
    MetricsError,
    PlanningError,
    RegistryError,
    WorkflowCancelledError,
    WorkflowError,
)
from workflows.interfaces import (
    Collector,
    Dispatcher,
    Planner,
    WorkflowEngine,
    WorkflowManager,
    WorkflowMetricsCalculator,
    WorkflowRegistry,
)
from workflows.manager import DefaultWorkflowManager
from workflows.metrics import DefaultWorkflowMetrics
from workflows.models import (
    WorkflowBatch,
    WorkflowDefinition,
    WorkflowDependency,
    WorkflowHistory,
    WorkflowMetrics,
    WorkflowParameters,
    WorkflowPlan,
    WorkflowPlanEntry,
    WorkflowRecord,
    WorkflowRequest,
    WorkflowResult,
    WorkflowResultStatus,
    WorkflowSnapshot,
    WorkflowStep,
)
from workflows.planner import DefaultPlanner
from workflows.registry import InMemoryWorkflowRegistry
from workflows.state import WorkflowState

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = [
    # context & state
    "WorkflowContext",
    "WorkflowState",
    "WorkflowResultStatus",
    # models
    "WorkflowParameters",
    "WorkflowStep",
    "WorkflowDependency",
    "WorkflowDefinition",
    "WorkflowBatch",
    "WorkflowPlanEntry",
    "WorkflowPlan",
    "WorkflowRequest",
    "WorkflowHistory",
    "WorkflowRecord",
    "WorkflowMetrics",
    "WorkflowSnapshot",
    "WorkflowResult",
    # interfaces
    "Collector",
    "Planner",
    "Dispatcher",
    "WorkflowMetricsCalculator",
    "WorkflowRegistry",
    "WorkflowManager",
    "WorkflowEngine",
    # implementations
    "DefaultCollector",
    "DefaultPlanner",
    "DefaultDispatcher",
    "DefaultWorkflowMetrics",
    "InMemoryWorkflowRegistry",
    "DefaultWorkflowManager",
    "DefaultWorkflowEngine",
    # events
    "WorkflowEvent",
    "WorkflowStarted",
    "StepsCollected",
    "WorkflowPlanned",
    "RequestsDispatched",
    "WorkflowSnapshotCreated",
    "WorkflowMetricsUpdated",
    "WorkflowCompleted",
    "WorkflowCancelled",
    "WorkflowErrorOccurred",
    # exceptions
    "WorkflowError",
    "CollectionError",
    "PlanningError",
    "DispatchError",
    "MetricsError",
    "RegistryError",
    "WorkflowCancelledError",
    # wiring
    "register_workflows",
]


def register_workflows(container: Container) -> None:
    """Register the Workflow Orchestration Framework services into a DI container.

    Registers the stateless collector/planner/dispatcher/metrics, the
    thread-safe registry, the manager, and the engine as singletons, bound
    to their abstractions (Dependency Inversion). ``EventBus`` is registered
    on demand; ``LoggerFactory`` is injected only if already registered. The
    framework never instantiates an Agent, Scheduler, Worker, or Model
    Gateway manager or engine, a network client, or a database client.

    Args:
        container: The DI container to register into.
    """
    if not container.has(EventBus):
        container.register_class(EventBus)

    container.register_class(Collector, DefaultCollector)
    container.register_class(Planner, DefaultPlanner)
    container.register_class(Dispatcher, DefaultDispatcher)
    container.register_class(WorkflowMetricsCalculator, DefaultWorkflowMetrics)
    container.register_class(WorkflowRegistry, InMemoryWorkflowRegistry)

    def _build_manager(resolver: Resolver) -> DefaultWorkflowManager:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultWorkflowManager(
            resolver.resolve(EventBus),
            resolver.resolve(WorkflowRegistry),
            resolver.resolve(Collector),
            resolver.resolve(Planner),
            resolver.resolve(Dispatcher),
            resolver.resolve(WorkflowMetricsCalculator),
            logger=logger,
        )

    container.register_singleton(DefaultWorkflowManager, _build_manager)
    container.register_singleton(
        WorkflowManager, lambda r: r.resolve(DefaultWorkflowManager)
    )

    def _build_engine(resolver: Resolver) -> DefaultWorkflowEngine:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultWorkflowEngine(
            resolver.resolve(WorkflowManager), logger=logger
        )

    container.register_singleton(DefaultWorkflowEngine, _build_engine)
    container.register_singleton(
        WorkflowEngine, lambda r: r.resolve(DefaultWorkflowEngine)
    )
