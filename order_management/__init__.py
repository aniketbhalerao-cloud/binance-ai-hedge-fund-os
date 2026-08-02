"""Order Management Framework — prepares approved decisions for execution.

Receives approved :class:`~risk.models.RiskDecision` s (via an
:class:`OrderContext`), creates standardized immutable order requests, validates
them, prepares routing, and publishes order events on the shared event bus for
the future Execution Layer. It never connects to an exchange, submits live
orders, or executes anything — it prepares orders only. New order types and
routers plug in without changing the framework (Open/Closed).

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from order_management.context import OrderContext
from order_management.engine import DefaultOrderEngine
from order_management.events import (
    OrderCreated,
    OrderEngineStarted,
    OrderEngineStopped,
    OrderErrorOccurred,
    OrderEvent,
    OrderReadyForExecution,
    OrderRejected,
    OrderRouted,
    OrderValidated,
    OrderValidationFailed,
)
from order_management.exceptions import (
    InvalidOrderRequest,
    OrderEngineError,
    OrderError,
    OrderFactoryError,
    OrderRoutingError,
    OrderValidationError,
)
from order_management.factory import DefaultOrderFactory
from order_management.interfaces import (
    OrderEngine,
    OrderFactory,
    OrderManager,
    OrderRouter,
    OrderValidator,
)
from order_management.manager import DefaultOrderManager
from order_management.models import (
    OrderIdentifier,
    OrderMetadata,
    OrderRequest,
    OrderResult,
    OrderRoute,
    OrderValidationResult,
)
from order_management.orders import (
    LimitOrder,
    MarketOrder,
    StopLimitOrder,
    StopOrder,
)
from order_management.routing import DefaultOrderRouter
from order_management.state import OrderState
from order_management.validator import DefaultOrderValidator

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = [
    # context & state
    "OrderContext",
    "OrderState",
    # models
    "OrderIdentifier",
    "OrderMetadata",
    "OrderRequest",
    "OrderValidationResult",
    "OrderRoute",
    "OrderResult",
    # order types
    "MarketOrder",
    "LimitOrder",
    "StopOrder",
    "StopLimitOrder",
    # interfaces
    "OrderFactory",
    "OrderValidator",
    "OrderRouter",
    "OrderManager",
    "OrderEngine",
    # implementations
    "DefaultOrderFactory",
    "DefaultOrderValidator",
    "DefaultOrderRouter",
    "DefaultOrderManager",
    "DefaultOrderEngine",
    # events
    "OrderEvent",
    "OrderCreated",
    "OrderValidated",
    "OrderValidationFailed",
    "OrderRouted",
    "OrderReadyForExecution",
    "OrderRejected",
    "OrderEngineStarted",
    "OrderEngineStopped",
    "OrderErrorOccurred",
    # exceptions
    "OrderError",
    "OrderValidationError",
    "OrderRoutingError",
    "OrderFactoryError",
    "OrderEngineError",
    "InvalidOrderRequest",
    # wiring
    "register_order_management",
]


def register_order_management(container: Container) -> None:
    """Register the Order Framework services into a DI container.

    Registers the factory, validator, router, manager, and engine as singletons,
    bound to their abstractions (Dependency Inversion). ``EventBus`` is
    registered on demand; ``LoggerFactory`` and the Trading/Strategy/Risk
    components are injected only if already registered.

    Args:
        container: The DI container to register into.
    """
    if not container.has(EventBus):
        container.register_class(EventBus)

    container.register_class(OrderFactory, DefaultOrderFactory)
    container.register_class(OrderValidator, DefaultOrderValidator)
    container.register_class(OrderRouter, DefaultOrderRouter)

    def _build_manager(resolver: Resolver) -> DefaultOrderManager:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultOrderManager(
            resolver.resolve(EventBus),
            resolver.resolve(OrderFactory),
            resolver.resolve(OrderValidator),
            resolver.resolve(OrderRouter),
            logger=logger,
        )

    container.register_singleton(DefaultOrderManager, _build_manager)
    container.register_singleton(OrderManager, lambda r: r.resolve(DefaultOrderManager))

    def _build_engine(resolver: Resolver) -> DefaultOrderEngine:
        from risk.interfaces import RiskEngine
        from strategies.interfaces import StrategyManager
        from trading.engine import TradingEngine

        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        trading_engine = (
            resolver.resolve(TradingEngine) if resolver.has(TradingEngine) else None
        )
        strategy_manager = (
            resolver.resolve(StrategyManager) if resolver.has(StrategyManager) else None
        )
        risk_engine = resolver.resolve(RiskEngine) if resolver.has(RiskEngine) else None
        return DefaultOrderEngine(
            resolver.resolve(OrderManager),
            resolver.resolve(EventBus),
            logger=logger,
            trading_engine=trading_engine,
            strategy_manager=strategy_manager,
            risk_engine=risk_engine,
        )

    container.register_singleton(DefaultOrderEngine, _build_engine)
    container.register_singleton(OrderEngine, lambda r: r.resolve(DefaultOrderEngine))
