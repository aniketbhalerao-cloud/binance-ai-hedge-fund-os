"""Portfolio update context.

An immutable input carrying a completed :class:`~execution.models.ExecutionResult`
plus the standardized market prices needed for valuation. Portfolio components
never access market-data infrastructure directly — prices are supplied here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from execution.models import ExecutionResult

__all__ = ["PortfolioContext"]


@dataclass(frozen=True, slots=True)
class PortfolioContext:
    """Immutable input for one portfolio update.

    Attributes:
        portfolio_id: The portfolio to update.
        execution_result: The completed execution to account for.
        prices: Standardized latest prices per symbol (for valuation).
        initial_cash: Starting cash used when creating a new portfolio.
        timestamp: When the context was assembled (UTC).
        metadata: Optional read-only extra context.
    """

    portfolio_id: str
    execution_result: ExecutionResult
    prices: Mapping[str, Decimal] = field(default_factory=lambda: MappingProxyType({}))
    initial_cash: Decimal = Decimal("0")
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "prices", MappingProxyType(dict(self.prices)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
