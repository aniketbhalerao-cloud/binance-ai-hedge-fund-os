"""Strategy Framework — coordinates strategies and produces trading signals.

The framework consumes normalized market data (via a :class:`StrategyContext`),
executes registered strategies, and publishes standardized signals on the shared
event bus. It is strategy-independent and contains no technical analysis, risk,
execution, or exchange logic — individual strategies (added later) hold that
business logic. New strategies plug in by subclassing :class:`BaseStrategy` and
registering, with no changes to the framework (Open/Closed).

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from strategies.base import BaseStrategy, StrategyMetadata
from strategies.context import StrategyContext
from strategies.events import (
    SignalGenerated,
    StrategyDisabled,
    StrategyEnabled,
    StrategyErrorOccurred,
    StrategyEvent,
    StrategyRegistered,
    StrategyStarted,
    StrategyStopped,
)
from strategies.exceptions import (
    DuplicateStrategyError,
    InvalidStrategyError,
    StrategyDisabledError,
    StrategyError,
    StrategyExecutionError,
    StrategyRegistrationError,
)
from strategies.factory import DefaultStrategyFactory
from strategies.interfaces import (
    SignalPublisher,
    Strategy,
    StrategyFactory,
    StrategyManager,
    StrategyRegistry,
)
from strategies.manager import StrategyExecutionManager
from strategies.registry import InMemoryStrategyRegistry
from strategies.signals import SignalDirection, SignalMetadata, TradingSignal

if TYPE_CHECKING:
    from core.interfaces import Container

__all__ = [
    # signals & context
    "SignalDirection",
    "SignalMetadata",
    "TradingSignal",
    "StrategyContext",
    # base
    "BaseStrategy",
    "StrategyMetadata",
    # interfaces (abstractions)
    "Strategy",
    "StrategyRegistry",
    "StrategyFactory",
    "StrategyManager",
    "SignalPublisher",
    # implementations
    "InMemoryStrategyRegistry",
    "DefaultStrategyFactory",
    "StrategyExecutionManager",
    # events
    "StrategyEvent",
    "StrategyRegistered",
    "StrategyEnabled",
    "StrategyDisabled",
    "StrategyStarted",
    "StrategyStopped",
    "SignalGenerated",
    "StrategyErrorOccurred",
    # exceptions
    "StrategyError",
    "StrategyRegistrationError",
    "StrategyExecutionError",
    "InvalidStrategyError",
    "DuplicateStrategyError",
    "StrategyDisabledError",
    # wiring
    "register_strategies",
]


def register_strategies(container: Container) -> None:
    """Register the Strategy Framework services into a DI container.

    Registers the registry, factory, and manager as singletons, bound to their
    abstractions (Dependency Inversion). ``EventBus`` is registered on demand;
    ``LoggerFactory``, ``TradingEngine``, and ``MarketDataService`` are injected
    only if already registered.

    Args:
        container: The DI container (a ``core.container.ServiceContainer``).
    """
    from core.container import ServiceContainer
    from core.interfaces import Resolver

    assert isinstance(container, ServiceContainer)

    if not container.has(EventBus):
        container.register_class(EventBus)

    container.register_class(StrategyRegistry, InMemoryStrategyRegistry)
    container.register_singleton(
        StrategyFactory, lambda _r: DefaultStrategyFactory(container)
    )

    def _build_manager(resolver: Resolver) -> StrategyExecutionManager:
        from market_data.interfaces import MarketDataService
        from trading.engine import TradingEngine

        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        engine = (
            resolver.resolve(TradingEngine) if resolver.has(TradingEngine) else None
        )
        market_data = (
            resolver.resolve(MarketDataService)
            if resolver.has(MarketDataService)
            else None
        )
        return StrategyExecutionManager(
            resolver.resolve(EventBus),
            resolver.resolve(StrategyRegistry),
            resolver.resolve(StrategyFactory),
            logger=logger,
            engine=engine,
            market_data=market_data,
        )

    container.register_singleton(StrategyExecutionManager, _build_manager)
    container.register_singleton(
        StrategyManager, lambda r: r.resolve(StrategyExecutionManager)
    )
