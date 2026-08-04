"""Paper Trading Framework interfaces.

Protocols only — no implementations. Components depend on these abstractions so
future paper-trading capabilities (new fill models, feeds, metric families) plug
in without modification (Open/Closed). DI binds the ``Default*`` / ``InMemory*``
concretes to these keys (Dependency Inversion).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from execution.models import ExecutionResult
from market_data.models import OHLCV
from paper_trading.context import PaperTradingContext
from paper_trading.models import (
    PaperFill,
    PaperSession,
    PaperTradingHistory,
    PaperTradingMetrics,
    PaperTradingResult,
    SessionParameters,
)
from performance.models import PerformanceResult
from strategies.context import StrategyContext
from trades.models import Trade

__all__ = [
    "Feed",
    "Broker",
    "PaperTradingMetricsCalculator",
    "PaperTradingHistoryService",
    "PaperTradingRegistry",
    "PaperTradingManager",
    "PaperTradingEngine",
]


@runtime_checkable
class Feed(Protocol):
    """Normalizes one live market update into a strategy context (stateless)."""

    def normalize(
        self, context: PaperTradingContext, recent_candles: Sequence[OHLCV]
    ) -> StrategyContext: ...


@runtime_checkable
class Broker(Protocol):
    """Simulates a live fill from a ready execution (stateless, post-Execution)."""

    def fill(
        self,
        execution_result: ExecutionResult,
        candle: OHLCV,
        parameters: SessionParameters,
    ) -> PaperFill: ...


@runtime_checkable
class PaperTradingMetricsCalculator(Protocol):
    """Derives live metrics from performance + trades (stateless)."""

    def calculate(
        self,
        performance_result: PerformanceResult | None,
        trades: Sequence[Trade],
        equity_curve: Sequence[object],
        total_commission: object,
    ) -> PaperTradingMetrics: ...


@runtime_checkable
class PaperTradingHistoryService(Protocol):
    """Appends fills to an append-only history (stateless)."""

    def append(
        self, history: PaperTradingHistory, fill: PaperFill
    ) -> PaperTradingHistory: ...


@runtime_checkable
class PaperTradingRegistry(Protocol):
    """Thread-safe store that owns the running sessions (never creates them)."""

    def register(self, session: PaperSession) -> None: ...
    def unregister(self, session_id: str) -> None: ...
    def get(self, session_id: str) -> PaperSession: ...
    def exists(self, session_id: str) -> bool: ...
    def list(self) -> list[PaperSession]: ...
    def clear(self) -> None: ...


@runtime_checkable
class PaperTradingManager(Protocol):
    """Processes one live update atomically and publishes events."""

    async def process(self, context: PaperTradingContext) -> PaperTradingResult: ...


@runtime_checkable
class PaperTradingEngine(Protocol):
    """Public entry point coordinating live paper trading."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def process(self, context: PaperTradingContext) -> PaperTradingResult: ...
