"""Exceptions raised by the trading engine coordination layer.

Definitions only — no handling logic. These describe *coordination* failures
(invalid lifecycle transitions, starting an already-running engine, service
registration problems, …) and carry no trading, exchange, or risk semantics.
"""

from __future__ import annotations

from trading.state import EngineState

__all__ = [
    "TradingEngineError",
    "EngineAlreadyRunningError",
    "EngineNotRunningError",
    "EngineInitializationError",
    "LifecycleTransitionError",
    "CoordinatorError",
    "ServiceRegistrationError",
]


class TradingEngineError(Exception):
    """Base class for all trading engine errors."""


class EngineAlreadyRunningError(TradingEngineError):
    """Raised when :meth:`start` is called on an already-running engine."""


class EngineNotRunningError(TradingEngineError):
    """Raised when an operation requires a running engine but it is not."""


class EngineInitializationError(TradingEngineError):
    """Raised when the engine fails during initialization/start-up."""


class LifecycleTransitionError(TradingEngineError):
    """Raised when an illegal lifecycle transition is attempted.

    Attributes:
        source: The state the engine was in.
        target: The state that was illegally requested.
    """

    def __init__(self, source: EngineState, target: EngineState) -> None:
        self.source = source
        self.target = target
        super().__init__(
            f"Illegal engine state transition: {source.value} -> {target.value}."
        )


class CoordinatorError(TradingEngineError):
    """Raised when the coordinator fails while orchestrating services."""


class ServiceRegistrationError(TradingEngineError):
    """Raised when a service cannot be registered or unregistered."""
