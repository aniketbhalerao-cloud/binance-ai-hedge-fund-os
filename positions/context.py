"""Position update context.

An immutable input carrying a completed :class:`~portfolio.models.PortfolioResult`
(whose latest ledger entry is the trade to apply) plus standardized market prices
for the unrealized-P&L calculation. Position components never access
infrastructure directly.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from portfolio.models import PortfolioResult

__all__ = ["PositionContext"]


@dataclass(frozen=True, slots=True)
class PositionContext:
    """Immutable input for one position update.

    Attributes:
        portfolio_result: The completed portfolio update (holds the trade).
        prices: Standardized latest prices per symbol (for unrealized P&L).
        timestamp: When the context was assembled (UTC).
        metadata: Optional read-only extra context.
    """

    portfolio_result: PortfolioResult
    prices: Mapping[str, Decimal] = field(default_factory=lambda: MappingProxyType({}))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "prices", MappingProxyType(dict(self.prices)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
