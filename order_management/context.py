"""Order creation context.

An :class:`OrderContext` is the single, immutable input the framework uses to
create and validate an order. It bundles the upstream decision and supporting
snapshots (assembled from other layers' domain models) so order components never
access infrastructure directly.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from market_data.models import MarketSnapshot
from risk.context import RiskContext
from risk.models import RiskDecision
from strategies.context import StrategyContext
from strategies.signals import TradingSignal

__all__ = ["OrderContext"]


@dataclass(frozen=True, slots=True)
class OrderContext:
    """Immutable input for order creation and validation.

    Attributes:
        risk_decision: The approved risk decision driving this order.
        signal: The originating trading signal.
        exchange: Neutral exchange label.
        symbol: Instrument to trade.
        strategy_context: Optional originating strategy context.
        risk_context: Optional originating risk context.
        market_snapshot: Optional latest market snapshot.
        timeframe: Timeframe, where applicable.
        timestamp: When the context was assembled (UTC).
        metadata: Optional read-only extra context (e.g. sizing hints).
    """

    risk_decision: RiskDecision
    signal: TradingSignal
    exchange: str
    symbol: str
    strategy_context: StrategyContext | None = None
    risk_context: RiskContext | None = None
    market_snapshot: MarketSnapshot | None = None
    timeframe: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
