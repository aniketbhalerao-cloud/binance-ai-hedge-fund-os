"""Paper trading update context.

An immutable input carrying one live market update (a normalized ``OHLCV``
candle, and optionally a market snapshot), the strategy under test, the session
parameters, and optional seed results. It represents a single live tick of a
session. Paper-trading components never access infrastructure directly — the
manager drives the injected framework engines using the data this context
carries, and the durable session state lives in the Registry, not here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from market_data.models import OHLCV, MarketSnapshot
from paper_trading.models import SessionParameters
from performance.models import PerformanceResult
from portfolio.models import PortfolioResult
from positions.models import PositionResult
from strategies.interfaces import Strategy
from trades.models import TradeResult

__all__ = ["PaperTradingContext"]


@dataclass(frozen=True, slots=True)
class PaperTradingContext:
    """Immutable input for processing one live market update.

    Attributes:
        session_id: Identifier of the session (and its simulated portfolio).
        candle: The live market update to process (normalized candle).
        strategy: The strategy under test (its ``evaluate`` is called per update).
        parameters: Deterministic session parameters.
        exchange: Neutral exchange label.
        symbol: Instrument being traded.
        market_snapshot: Optional latest normalized market snapshot.
        final: Whether this update gracefully completes the session.
        portfolio_result: Optional seed portfolio result.
        position_result: Optional seed position result.
        trade_result: Optional seed trade result.
        performance_result: Optional seed performance result.
        correlation_id: Optional correlation id propagated to events.
        timestamp: When the context was assembled (UTC).
        metadata: Optional read-only extra context.
    """

    session_id: str
    candle: OHLCV
    strategy: Strategy | None = None
    parameters: SessionParameters = field(default_factory=SessionParameters)
    exchange: str = "paper"
    symbol: str = "BTCUSDT"
    market_snapshot: MarketSnapshot | None = None
    final: bool = False
    portfolio_result: PortfolioResult | None = None
    position_result: PositionResult | None = None
    trade_result: TradeResult | None = None
    performance_result: PerformanceResult | None = None
    correlation_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
