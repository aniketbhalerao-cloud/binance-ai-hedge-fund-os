"""Execution Framework — coordinates execution up to the Exchange Adapter.

Receives orders that are ready for execution (via an :class:`ExecutionContext`
built from an :class:`~order_management.models.OrderResult`), validates and routes
them, coordinates the execution lifecycle, and publishes execution events on the
shared event bus for the future Exchange Adapter. It never connects to a broker,
implements broker SDKs/REST/WebSockets, or executes live orders — actual broker
communication is delegated to future adapters. New executors/routers plug in
without changing the framework (Open/Closed).

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from execution.context import ExecutionContext
from execution.engine import DefaultExecutionEngine
from execution.events import (
    ExecutionCancelled,
    ExecutionCompleted,
    ExecutionEngineStarted,
    ExecutionEngineStopped,
    ExecutionErrorOccurred,
    ExecutionEvent,
    ExecutionFailed,
    ExecutionQueued,
    ExecutionRetried,
    ExecutionStarted,
    ExecutionValidated,
)
from execution.exceptions import (
    ExecutionEngineError,
    ExecutionError,
    ExecutionLifecycleError,
    ExecutionRoutingError,
    ExecutionValidationError,
    InvalidExecutionRequest,
)
from execution.executor import DefaultExecutionExecutor
from execution.interfaces import (
    ExecutionEngine,
    ExecutionExecutor,
    ExecutionManager,
    ExecutionRouter,
    ExecutionValidator,
)
from execution.lifecycle import ExecutionLifecycle
from execution.manager import DefaultExecutionManager
from execution.models import (
    ExecutionIdentifier,
    ExecutionMetadata,
    ExecutionRequest,
    ExecutionResult,
    ExecutionRoute,
    ExecutionStatus,
    ExecutionValidationResult,
)
from execution.routing import DefaultExecutionRouter
from execution.state import ExecutionState
from execution.validator import DefaultExecutionValidator

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = [
    # context & state
    "ExecutionContext",
    "ExecutionState",
    "ExecutionStatus",
    # models
    "ExecutionIdentifier",
    "ExecutionMetadata",
    "ExecutionRequest",
    "ExecutionValidationResult",
    "ExecutionRoute",
    "ExecutionResult",
    # interfaces
    "ExecutionExecutor",
    "ExecutionValidator",
    "ExecutionRouter",
    "ExecutionManager",
    "ExecutionEngine",
    # implementations
    "DefaultExecutionExecutor",
    "DefaultExecutionValidator",
    "DefaultExecutionRouter",
    "DefaultExecutionManager",
    "DefaultExecutionEngine",
    "ExecutionLifecycle",
    # events
    "ExecutionEvent",
    "ExecutionStarted",
    "ExecutionQueued",
    "ExecutionValidated",
    "ExecutionCompleted",
    "ExecutionFailed",
    "ExecutionCancelled",
    "ExecutionRetried",
    "ExecutionEngineStarted",
    "ExecutionEngineStopped",
    "ExecutionErrorOccurred",
    # exceptions
    "ExecutionError",
    "ExecutionValidationError",
    "ExecutionRoutingError",
    "ExecutionLifecycleError",
    "ExecutionEngineError",
    "InvalidExecutionRequest",
    # wiring
    "register_execution",
]


def register_execution(container: Container) -> None:
    """Register the Execution Framework services into a DI container.

    Registers the executor, validator, router, manager, and engine as singletons,
    bound to their abstractions (Dependency Inversion). ``EventBus`` is registered
    on demand; ``LoggerFactory`` and the Trading/Strategy/Risk/Order components
    are injected only if already registered.

    Args:
        container: The DI container to register into.
    """
    if not container.has(EventBus):
        container.register_class(EventBus)

    container.register_class(ExecutionExecutor, DefaultExecutionExecutor)
    container.register_class(ExecutionValidator, DefaultExecutionValidator)
    container.register_class(ExecutionRouter, DefaultExecutionRouter)

    def _build_manager(resolver: Resolver) -> DefaultExecutionManager:
        logger = resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        return DefaultExecutionManager(
            resolver.resolve(EventBus),
            resolver.resolve(ExecutionExecutor),
            resolver.resolve(ExecutionValidator),
            resolver.resolve(ExecutionRouter),
            logger=logger,
        )

    container.register_singleton(DefaultExecutionManager, _build_manager)
    container.register_singleton(
        ExecutionManager, lambda r: r.resolve(DefaultExecutionManager)
    )

    def _build_engine(resolver: Resolver) -> DefaultExecutionEngine:
        from order_management.interfaces import OrderEngine
        from risk.interfaces import RiskEngine
        from strategies.interfaces import StrategyManager
        from trading.engine import TradingEngine

        logger = resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        return DefaultExecutionEngine(
            resolver.resolve(ExecutionManager),
            resolver.resolve(EventBus),
            logger=logger,
            trading_engine=(
                resolver.resolve(TradingEngine) if resolver.has(TradingEngine) else None
            ),
            strategy_manager=(
                resolver.resolve(StrategyManager)
                if resolver.has(StrategyManager)
                else None
            ),
            risk_engine=resolver.resolve(RiskEngine) if resolver.has(RiskEngine) else None,
            order_engine=(
                resolver.resolve(OrderEngine) if resolver.has(OrderEngine) else None
            ),
        )

    container.register_singleton(DefaultExecutionEngine, _build_engine)
    container.register_singleton(
        ExecutionEngine, lambda r: r.resolve(DefaultExecutionEngine)
    )
