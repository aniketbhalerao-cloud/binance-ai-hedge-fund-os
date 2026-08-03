"""Trade update context.

An immutable input carrying a completed
:class:`~positions.models.PositionResult` (the durable position whose aggregate
figures the framework derives the incremental fill from) plus standardized
market prices. Trade components never access infrastructure directly — they read
only from this context and the standardized models it carries.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from positions.models import PositionResult

__all__ = ["TradeContext"]


@dataclass(frozen=True, slots=True)
class TradeContext:
    """Immutable input for one trade update.

    Attributes:
        position_result: The completed position update (holds the durable
            :class:`~positions.models.Position` to derive the fill from).
        prices: Standardized latest prices per symbol (for downstream use).
        timestamp: When the context was assembled (UTC).
        metadata: Optional read-only extra context (e.g. correlation id).
    """

    position_result: PositionResult
    prices: Mapping[str, Decimal] = field(default_factory=lambda: MappingProxyType({}))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "prices", MappingProxyType(dict(self.prices)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
