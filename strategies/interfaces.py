"""Strategy Framework interfaces.

Protocols only — no implementations. The framework depends on these abstractions
so any future strategy or component plugs in without modification (Open/Closed).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from strategies.context import StrategyContext
from strategies.signals import TradingSignal

__all__ = [
    "Strategy",
    "StrategyRegistry",
    "StrategyFactory",
    "StrategyManager",
    "SignalPublisher",
]


@runtime_checkable
class Strategy(Protocol):
    """A single trading strategy: pure decision logic over a context."""

    @property
    def name(self) -> str:
        """Unique strategy name."""
        ...

    async def on_start(self) -> None:
        """Lifecycle hook invoked when the strategy starts."""
        ...

    async def on_stop(self) -> None:
        """Lifecycle hook invoked when the strategy stops."""
        ...

    async def evaluate(self, context: StrategyContext) -> Sequence[TradingSignal]:
        """Evaluate ``context`` and return zero or more signals."""
        ...


@runtime_checkable
class StrategyRegistry(Protocol):
    """Manages the set of available strategies and their enabled state."""

    def register(self, strategy: Strategy) -> None: ...
    def unregister(self, name: str) -> None: ...
    def enable(self, name: str) -> None: ...
    def disable(self, name: str) -> None: ...
    def exists(self, name: str) -> bool: ...
    def list(self) -> list[Strategy]: ...
    def list_enabled(self) -> list[Strategy]: ...
    def get(self, name: str) -> Strategy: ...


@runtime_checkable
class StrategyFactory(Protocol):
    """Constructs strategy instances (with dependency injection)."""

    def create(self, strategy_cls: type[Strategy]) -> Strategy: ...


@runtime_checkable
class StrategyManager(Protocol):
    """Coordinates strategy execution and signal publication."""

    async def execute(self, context: StrategyContext) -> list[TradingSignal]: ...


@runtime_checkable
class SignalPublisher(Protocol):
    """Publishes generated signals (extension point for future routing)."""

    async def publish_signal(self, signal: TradingSignal) -> None: ...
