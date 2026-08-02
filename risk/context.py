"""Risk evaluation context.

A :class:`RiskContext` is the single, immutable input to a risk evaluation. It
carries everything a rule needs to decide — the signal under review plus the
relevant account/market state — assembled from normalized domain models, so risk
components never access the market-data cache, repositories, or exchanges
directly.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from market_data.models import MarketSnapshot
from models import Order, Position
from strategies.signals import TradingSignal

__all__ = ["RiskContext"]


@dataclass(frozen=True, slots=True)
class RiskContext:
    """Immutable snapshot of everything required to evaluate one signal.

    Attributes:
        signal: The trading signal under review.
        exchange: Neutral exchange label.
        symbol: The instrument the signal refers to.
        timeframe: Timeframe, where applicable.
        market_snapshot: Latest normalized market snapshot, if available.
        position: Current position for the symbol, if any.
        exposure: Current exposure figure, if provided.
        available_capital: Capital available to deploy, if provided.
        account_balance: Account balance, if provided.
        open_orders: Currently open orders (immutable tuple).
        timestamp: When the context was assembled (UTC).
        metadata: Optional read-only extra context.
    """

    signal: TradingSignal
    exchange: str
    symbol: str
    timeframe: str | None = None
    market_snapshot: MarketSnapshot | None = None
    position: Position | None = None
    exposure: Decimal | None = None
    available_capital: Decimal | None = None
    account_balance: Decimal | None = None
    open_orders: tuple[Order, ...] = ()
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
