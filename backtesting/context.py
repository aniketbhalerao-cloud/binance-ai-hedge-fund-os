"""Backtesting run context.

An immutable input carrying the historical market data, the strategy under test,
the simulation parameters, and optional seed results. It represents one complete
backtest configuration. Backtesting components never access infrastructure
directly — the manager drives the injected framework engines using the data this
context carries.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from backtesting.models import SimulationParameters
from market_data.models import OHLCV
from performance.models import PerformanceResult
from portfolio.models import PortfolioResult
from positions.models import PositionResult
from strategies.interfaces import Strategy
from trades.models import TradeResult

__all__ = ["BacktestingContext"]


@dataclass(frozen=True, slots=True)
class BacktestingContext:
    """Immutable input for one backtest run.

    Attributes:
        candles: Historical market data to replay (oldest→newest).
        strategy: The strategy under test (its ``evaluate`` is called per candle).
        parameters: Deterministic simulation parameters.
        exchange: Neutral exchange label.
        symbol: Instrument being backtested.
        portfolio_id: Identifier of the simulated portfolio.
        timeframe: Candle timeframe, where applicable.
        portfolio_result: Optional seed portfolio result.
        position_result: Optional seed position result.
        trade_result: Optional seed trade result.
        performance_result: Optional seed performance result.
        correlation_id: Optional correlation id propagated to events/snapshot.
        timestamp: When the context was assembled (UTC).
        metadata: Optional read-only extra context.
    """

    candles: Sequence[OHLCV]
    strategy: Strategy | None = None
    parameters: SimulationParameters = field(default_factory=SimulationParameters)
    exchange: str = "backtest"
    symbol: str = "BTCUSDT"
    portfolio_id: str = "backtest-pf"
    timeframe: str | None = None
    portfolio_result: PortfolioResult | None = None
    position_result: PositionResult | None = None
    trade_result: TradeResult | None = None
    performance_result: PerformanceResult | None = None
    correlation_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "candles", tuple(self.candles))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
