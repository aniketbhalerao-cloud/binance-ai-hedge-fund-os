"""Trading engine — the orchestration layer.

The trading engine coordinates the project's Sprint 1 infrastructure (event bus,
logging, persistence, exchange adapter) through interfaces and dependency
injection. It manages the application's start/stop/pause/resume lifecycle and
announces lifecycle changes on the event bus — it contains no strategy, risk,
exchange, execution, portfolio, or notification logic.

This module re-exports the primary public classes only.
"""

from __future__ import annotations

from trading.coordinator import TradingCoordinator
from trading.engine import TradingEngine, register_trading_engine
from trading.exceptions import (
    CoordinatorError,
    EngineAlreadyRunningError,
    EngineInitializationError,
    EngineNotRunningError,
    LifecycleTransitionError,
    ServiceRegistrationError,
    TradingEngineError,
)
from trading.lifecycle import (
    EngineFailed,
    EngineInitializing,
    EnginePaused,
    EngineResumed,
    EngineStarted,
    EngineStarting,
    EngineStopped,
    EngineStopping,
    LifecycleManager,
)
from trading.state import EngineState, RuntimeState

__all__ = [
    # Engine + orchestration
    "TradingEngine",
    "TradingCoordinator",
    "LifecycleManager",
    "register_trading_engine",
    # State
    "EngineState",
    "RuntimeState",
    # Lifecycle events
    "EngineInitializing",
    "EngineStarting",
    "EngineStarted",
    "EnginePaused",
    "EngineResumed",
    "EngineStopping",
    "EngineStopped",
    "EngineFailed",
    # Exceptions
    "TradingEngineError",
    "EngineAlreadyRunningError",
    "EngineNotRunningError",
    "EngineInitializationError",
    "LifecycleTransitionError",
    "CoordinatorError",
    "ServiceRegistrationError",
]
