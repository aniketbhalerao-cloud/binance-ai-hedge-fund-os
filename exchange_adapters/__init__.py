"""Exchange Adapter Framework — abstraction between execution and brokers.

Provides the reusable, broker-independent framework that coordinates
authentication, connection, validation, translation, routing, and adapter
lifecycle, publishing exchange events on the shared event bus for future broker
adapters. It contains no Binance/Zerodha/IB code, no REST/WebSocket/SDK, no API
keys/OAuth/JWT/signatures. Future broker adapters inherit
:class:`BaseExchangeAdapter` and register — with no changes to the framework
(Open/Closed).

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from exchange_adapters.adapter import BaseExchangeAdapter
from exchange_adapters.authentication import DefaultExchangeAuthentication
from exchange_adapters.connection import DefaultExchangeConnection
from exchange_adapters.context import ExchangeContext
from exchange_adapters.engine import DefaultExchangeEngine
from exchange_adapters.events import (
    ExchangeAdapterRegistered,
    ExchangeAdapterUnregistered,
    ExchangeAuthenticationFailed,
    ExchangeAuthenticationStarted,
    ExchangeAuthenticationSucceeded,
    ExchangeConnectionClosed,
    ExchangeConnectionOpened,
    ExchangeEngineStarted,
    ExchangeEngineStopped,
    ExchangeErrorOccurred,
    ExchangeEvent,
    ExchangeRoutingCompleted,
    ExchangeValidationFailed,
    ExchangeValidationSucceeded,
)
from exchange_adapters.exceptions import (
    DuplicateAdapterError,
    ExchangeAuthenticationError,
    ExchangeConnectionError,
    ExchangeEngineError,
    ExchangeError,
    ExchangeRegistrationError,
    ExchangeRoutingError,
    ExchangeValidationError,
    InvalidExchangeRequest,
)
from exchange_adapters.interfaces import (
    ExchangeAdapter,
    ExchangeAuthentication,
    ExchangeConnection,
    ExchangeEngine,
    ExchangeManager,
    ExchangeRegistry,
    ExchangeRouter,
    ExchangeValidator,
)
from exchange_adapters.manager import DefaultExchangeManager
from exchange_adapters.models import (
    ExchangeIdentifier,
    ExchangeMetadata,
    ExchangeRequest,
    ExchangeResponse,
    ExchangeResult,
    ExchangeRoute,
    ExchangeStatus,
    ExchangeValidationResult,
)
from exchange_adapters.registry import ExchangeAdapterRegistry
from exchange_adapters.routing import DefaultExchangeRouter
from exchange_adapters.state import (
    AdapterState,
    AuthenticationState,
    ConnectionState,
)
from exchange_adapters.validator import DefaultExchangeValidator

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = [
    # context & state
    "ExchangeContext",
    "AdapterState",
    "ConnectionState",
    "AuthenticationState",
    # models
    "ExchangeStatus",
    "ExchangeIdentifier",
    "ExchangeMetadata",
    "ExchangeRequest",
    "ExchangeResponse",
    "ExchangeValidationResult",
    "ExchangeRoute",
    "ExchangeResult",
    # interfaces
    "ExchangeAuthentication",
    "ExchangeConnection",
    "ExchangeAdapter",
    "ExchangeValidator",
    "ExchangeRouter",
    "ExchangeRegistry",
    "ExchangeManager",
    "ExchangeEngine",
    # implementations
    "BaseExchangeAdapter",
    "DefaultExchangeAuthentication",
    "DefaultExchangeConnection",
    "DefaultExchangeValidator",
    "DefaultExchangeRouter",
    "ExchangeAdapterRegistry",
    "DefaultExchangeManager",
    "DefaultExchangeEngine",
    # events
    "ExchangeEvent",
    "ExchangeAdapterRegistered",
    "ExchangeAdapterUnregistered",
    "ExchangeAuthenticationStarted",
    "ExchangeAuthenticationSucceeded",
    "ExchangeAuthenticationFailed",
    "ExchangeConnectionOpened",
    "ExchangeConnectionClosed",
    "ExchangeValidationSucceeded",
    "ExchangeValidationFailed",
    "ExchangeRoutingCompleted",
    "ExchangeEngineStarted",
    "ExchangeEngineStopped",
    "ExchangeErrorOccurred",
    # exceptions
    "ExchangeError",
    "ExchangeAuthenticationError",
    "ExchangeConnectionError",
    "ExchangeValidationError",
    "ExchangeRoutingError",
    "ExchangeRegistrationError",
    "ExchangeEngineError",
    "InvalidExchangeRequest",
    "DuplicateAdapterError",
    # wiring
    "register_exchange_adapters",
]


def register_exchange_adapters(container: Container) -> None:
    """Register the Exchange Adapter Framework services into a DI container.

    Registers authentication, connection, validator, router, registry, manager,
    and engine as singletons, bound to their abstractions (Dependency Inversion).
    ``EventBus`` is registered on demand; ``LoggerFactory``, ``TradingEngine``,
    and ``ExecutionEngine`` are injected only if already registered.

    Args:
        container: The DI container to register into.
    """
    if not container.has(EventBus):
        container.register_class(EventBus)

    container.register_class(ExchangeAuthentication, DefaultExchangeAuthentication)
    container.register_class(ExchangeConnection, DefaultExchangeConnection)
    container.register_class(ExchangeValidator, DefaultExchangeValidator)
    container.register_class(ExchangeRouter, DefaultExchangeRouter)
    container.register_class(ExchangeRegistry, ExchangeAdapterRegistry)

    def _build_manager(resolver: Resolver) -> DefaultExchangeManager:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultExchangeManager(
            resolver.resolve(EventBus),
            resolver.resolve(ExchangeAuthentication),
            resolver.resolve(ExchangeConnection),
            resolver.resolve(ExchangeValidator),
            resolver.resolve(ExchangeRouter),
            resolver.resolve(ExchangeRegistry),
            logger=logger,
        )

    container.register_singleton(DefaultExchangeManager, _build_manager)
    container.register_singleton(
        ExchangeManager, lambda r: r.resolve(DefaultExchangeManager)
    )

    def _build_engine(resolver: Resolver) -> DefaultExchangeEngine:
        from execution.interfaces import ExecutionEngine
        from trading.engine import TradingEngine

        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultExchangeEngine(
            resolver.resolve(ExchangeManager),
            resolver.resolve(EventBus),
            logger=logger,
            trading_engine=(
                resolver.resolve(TradingEngine) if resolver.has(TradingEngine) else None
            ),
            execution_engine=(
                resolver.resolve(ExecutionEngine)
                if resolver.has(ExecutionEngine)
                else None
            ),
        )

    container.register_singleton(DefaultExchangeEngine, _build_engine)
    container.register_singleton(
        ExchangeEngine, lambda r: r.resolve(DefaultExchangeEngine)
    )
