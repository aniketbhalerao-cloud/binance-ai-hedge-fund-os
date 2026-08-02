"""Standardized trading signals.

A :class:`TradingSignal` is an immutable statement of *intent* produced by a
strategy. It represents a decision only — it never executes trades, modifies
positions, accesses exchanges, or persists anything, and it carries no
exchange-specific fields.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from types import MappingProxyType
from typing import Any

__all__ = ["SignalDirection", "SignalMetadata", "TradingSignal"]


class SignalDirection(str, Enum):
    """The direction/intent a signal expresses."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE = "close"
    REDUCE = "reduce"
    INCREASE = "increase"


@dataclass(frozen=True, slots=True)
class SignalMetadata:
    """Immutable, free-form metadata attached to a signal.

    Wraps an arbitrary mapping in a read-only view so a signal stays fully
    immutable while still carrying strategy-specific context (never
    exchange-specific fields).
    """

    data: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        # Store a read-only snapshot so callers cannot mutate it afterwards.
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))

    def get(self, key: str, default: Any = None) -> Any:
        """Return the metadata value for ``key`` (or ``default``)."""
        return self.data.get(key, default)


@dataclass(frozen=True, slots=True)
class TradingSignal:
    """An immutable trading decision emitted by a strategy.

    Attributes:
        id: Unique identifier for the signal.
        strategy_name: Name of the strategy that produced it.
        symbol: The instrument the signal refers to.
        direction: The intended action.
        confidence: Strength of the signal, in ``[0.0, 1.0]``.
        timestamp: When the signal was produced (UTC).
        metadata: Optional strategy-specific metadata.

    Raises:
        ValueError: If ``confidence`` is outside ``[0.0, 1.0]``.
    """

    id: str
    strategy_name: str
    symbol: str
    direction: SignalDirection
    confidence: float = 1.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: SignalMetadata = field(default_factory=SignalMetadata)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("TradingSignal.confidence must be within [0.0, 1.0].")
