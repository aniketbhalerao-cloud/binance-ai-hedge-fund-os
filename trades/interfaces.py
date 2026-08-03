"""Trade Framework interfaces.

Protocols only — no implementations. Components depend on these abstractions so
future trade modules (multi-leg, options, futures, basket trades) plug in without
modification (Open/Closed). DI binds the ``Default*`` / ``InMemory*`` concretes to
these keys (Dependency Inversion).
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from positions.models import Position
from trades.context import TradeContext
from trades.models import (
    Trade,
    TradeAnalytics,
    TradeFill,
    TradeHistory,
    TradeMatch,
    TradeResult,
)
from trades.state import TradeState

__all__ = [
    "TradeTracker",
    "TradeMatcher",
    "TradeLifecycle",
    "TradeHistoryService",
    "TradeAnalyticsService",
    "TradeRegistry",
    "TradeManager",
    "TradeEngine",
]


@runtime_checkable
class TradeTracker(Protocol):
    """Derives incremental fills and assembles the durable trade (stateless)."""

    def derive_fill(
        self, previous: Trade | None, position: Position, now: datetime
    ) -> TradeFill: ...

    def build(
        self,
        trade_id: str,
        previous: Trade | None,
        position: Position,
        state: TradeState,
        opened_at: datetime,
        now: datetime,
    ) -> Trade: ...


@runtime_checkable
class TradeMatcher(Protocol):
    """Correlates entries against exits for a trade (stateless)."""

    def match(self, position: Position, fill: TradeFill) -> TradeMatch: ...


@runtime_checkable
class TradeLifecycle(Protocol):
    """Derives and validates trade lifecycle transitions."""

    def derive_state(self, match: TradeMatch, position_closed: bool) -> TradeState: ...
    def validate(self, source: TradeState, target: TradeState) -> None: ...


@runtime_checkable
class TradeHistoryService(Protocol):
    """Appends fills to an append-only history (stateless)."""

    def append(self, history: TradeHistory, fill: TradeFill) -> TradeHistory: ...


@runtime_checkable
class TradeAnalyticsService(Protocol):
    """Derives analytics from a trade's history + figures (stateless)."""

    def compute(self, trade: Trade, history: TradeHistory) -> TradeAnalytics: ...


@runtime_checkable
class TradeRegistry(Protocol):
    """Thread-safe store of trades and their histories (never creates them)."""

    def register(self, trade: Trade, history: TradeHistory) -> None: ...
    def get(self, trade_id: str) -> Trade: ...
    def history(self, trade_id: str) -> TradeHistory: ...
    def exists(self, trade_id: str) -> bool: ...
    def list(self) -> list[Trade]: ...
    def remove(self, trade_id: str) -> None: ...


@runtime_checkable
class TradeManager(Protocol):
    """Coordinates the trade update pipeline and publishes events."""

    async def update(self, context: TradeContext) -> TradeResult: ...


@runtime_checkable
class TradeEngine(Protocol):
    """Public entry point coordinating trade updates."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def process(self, context: TradeContext) -> TradeResult: ...
