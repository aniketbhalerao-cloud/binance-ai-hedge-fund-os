"""Backtesting Framework interfaces.

Protocols only — no implementations. Components depend on these abstractions so
future backtesting capabilities (new fill models, schedulers, metric families)
plug in without modification (Open/Closed). DI binds the ``Default*`` /
``InMemory*`` concretes to these keys (Dependency Inversion).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from backtesting.context import BacktestingContext
from backtesting.models import (
    BacktestHistory,
    BacktestMetrics,
    BacktestResult,
    BacktestSnapshot,
    SimulatedFill,
    SimulationParameters,
    SimulationStep,
)
from execution.models import ExecutionResult
from market_data.models import OHLCV
from performance.models import PerformanceResult
from trades.models import Trade

__all__ = [
    "Scheduler",
    "Simulator",
    "BacktestMetricsCalculator",
    "BacktestHistoryService",
    "BacktestRegistry",
    "BacktestManager",
    "BacktestEngine",
]


@runtime_checkable
class Scheduler(Protocol):
    """Iterates the historical timeline (stateless, no business logic)."""

    def iterate(
        self, candles: Sequence[OHLCV], replay_speed: int
    ) -> list[tuple[int, OHLCV]]: ...


@runtime_checkable
class Simulator(Protocol):
    """Simulates a historical fill from a ready execution (stateless)."""

    def simulate(
        self,
        execution_result: ExecutionResult,
        candle: OHLCV,
        parameters: SimulationParameters,
    ) -> SimulatedFill: ...


@runtime_checkable
class BacktestMetricsCalculator(Protocol):
    """Derives backtest metrics from performance + trades (stateless)."""

    def calculate(
        self,
        performance_result: PerformanceResult | None,
        trades: Sequence[Trade],
        equity_curve: Sequence[object],
        total_commission: object,
    ) -> BacktestMetrics: ...


@runtime_checkable
class BacktestHistoryService(Protocol):
    """Appends steps to an append-only history (stateless)."""

    def append(
        self, history: BacktestHistory, step: SimulationStep
    ) -> BacktestHistory: ...


@runtime_checkable
class BacktestRegistry(Protocol):
    """Thread-safe store of backtest snapshots (never creates them)."""

    def register(self, snapshot: BacktestSnapshot) -> None: ...
    def unregister(self, backtest_id: str) -> None: ...
    def get(self, backtest_id: str) -> BacktestSnapshot: ...
    def exists(self, backtest_id: str) -> bool: ...
    def list(self) -> list[BacktestSnapshot]: ...
    def clear(self) -> None: ...


@runtime_checkable
class BacktestManager(Protocol):
    """Coordinates the backtest run pipeline and publishes events."""

    async def run(self, context: BacktestingContext) -> BacktestResult: ...


@runtime_checkable
class BacktestEngine(Protocol):
    """Public entry point coordinating backtest runs."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def run_backtest(self, context: BacktestingContext) -> BacktestResult: ...
