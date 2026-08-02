"""Abstract base class for all strategies.

:class:`BaseStrategy` defines the common lifecycle, the standard execution
interface, shared validation hooks, and strategy metadata. Every future strategy
(RSI, EMA, MACD, AI, …) inherits from it and implements
:meth:`generate_signals`. This module contains **no** concrete trading logic.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from strategies.context import StrategyContext
from strategies.exceptions import StrategyExecutionError
from strategies.signals import SignalDirection, SignalMetadata, TradingSignal

__all__ = ["StrategyMetadata", "BaseStrategy"]


@dataclass(frozen=True, slots=True)
class StrategyMetadata:
    """Immutable descriptive metadata for a strategy."""

    name: str
    version: str = "1.0"
    description: str = ""


class BaseStrategy(ABC):
    """Base class implementing the :class:`~strategies.interfaces.Strategy` contract.

    Subclasses implement :meth:`generate_signals` with their decision logic and
    may override :meth:`validate_context` and the lifecycle hooks. They must not
    perform I/O, exchange access, persistence, or risk/order logic.
    """

    def __init__(self, metadata: StrategyMetadata) -> None:
        self._metadata = metadata

    @property
    def metadata(self) -> StrategyMetadata:
        """Return this strategy's metadata."""
        return self._metadata

    @property
    def name(self) -> str:
        """Return this strategy's unique name."""
        return self._metadata.name

    # -- lifecycle hooks (overridable, no-op by default) --------------------

    async def on_start(self) -> None:
        """Invoked when the strategy starts. No-op by default."""

    async def on_stop(self) -> None:
        """Invoked when the strategy stops. No-op by default."""

    # -- validation hook (overridable) --------------------------------------

    def validate_context(self, context: StrategyContext) -> None:
        """Validate ``context`` before evaluation.

        Raises:
            StrategyExecutionError: If the context is unusable.
        """
        if context.symbol == "":
            raise StrategyExecutionError("StrategyContext.symbol must be set.")

    # -- standard execution interface ---------------------------------------

    async def evaluate(self, context: StrategyContext) -> Sequence[TradingSignal]:
        """Validate the context then produce signals (template method)."""
        self.validate_context(context)
        return await self.generate_signals(context)

    @abstractmethod
    async def generate_signals(
        self, context: StrategyContext
    ) -> Sequence[TradingSignal]:
        """Produce zero or more signals from ``context`` (subclass logic)."""

    # -- convenience for subclasses -----------------------------------------

    def make_signal(
        self,
        *,
        symbol: str,
        direction: SignalDirection,
        confidence: float = 1.0,
        metadata: SignalMetadata | None = None,
    ) -> TradingSignal:
        """Build a :class:`TradingSignal` stamped with this strategy's name."""
        return TradingSignal(
            id=uuid.uuid4().hex,
            strategy_name=self.name,
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            timestamp=datetime.now(UTC),
            metadata=metadata or SignalMetadata(),
        )
