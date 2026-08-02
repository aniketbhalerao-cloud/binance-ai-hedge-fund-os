"""Position Framework interfaces.

Protocols only — no implementations. Components depend on these abstractions so
future position modules plug in without modification (Open/Closed).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Protocol, runtime_checkable

from positions.context import PositionContext
from positions.models import (
    Position,
    PositionCalculation,
    PositionHistory,
    PositionMetrics,
    PositionResult,
    PositionTrade,
)
from positions.state import PositionState

__all__ = [
    "PositionTracker",
    "PositionLifecycle",
    "PositionCalculator",
    "PositionHistoryService",
    "PositionMetricsService",
    "PositionRegistry",
    "PositionManager",
    "PositionEngine",
]


@runtime_checkable
class PositionTracker(Protocol):
    """Assembles a durable position from a calculation and lifecycle state."""

    def build(
        self,
        position_id: str,
        symbol: str,
        calculation: PositionCalculation,
        state: PositionState,
        opened_at: datetime,
        now: datetime,
    ) -> Position: ...


@runtime_checkable
class PositionLifecycle(Protocol):
    """Derives and validates position lifecycle transitions."""

    def derive_state(self, calculation: PositionCalculation) -> PositionState: ...
    def validate(self, source: PositionState, target: PositionState) -> None: ...


@runtime_checkable
class PositionCalculator(Protocol):
    """Computes position figures from trades + prices (stateless)."""

    def calculate(
        self,
        trades: Sequence[PositionTrade],
        prices: Mapping[str, Decimal],
        now: datetime,
    ) -> PositionCalculation: ...


@runtime_checkable
class PositionHistoryService(Protocol):
    """Appends trades to an append-only history (stateless)."""

    def append(
        self, history: PositionHistory, trade: PositionTrade
    ) -> PositionHistory: ...


@runtime_checkable
class PositionMetricsService(Protocol):
    """Derives metrics from a position's history (stateless)."""

    def compute(
        self, history: PositionHistory, calculation: PositionCalculation
    ) -> PositionMetrics: ...


@runtime_checkable
class PositionRegistry(Protocol):
    """Thread-safe store of positions and their histories (never creates them)."""

    def register(self, position: Position, history: PositionHistory) -> None: ...
    def get(self, position_id: str) -> Position: ...
    def history(self, position_id: str) -> PositionHistory: ...
    def exists(self, position_id: str) -> bool: ...
    def list(self) -> list[Position]: ...
    def remove(self, position_id: str) -> None: ...


@runtime_checkable
class PositionManager(Protocol):
    """Coordinates the position update pipeline and publishes events."""

    async def update(self, context: PositionContext) -> PositionResult: ...


@runtime_checkable
class PositionEngine(Protocol):
    """Public entry point coordinating position updates."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def process(self, context: PositionContext) -> PositionResult: ...
