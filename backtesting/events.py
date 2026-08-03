"""Backtesting Framework events.

Each inherits the existing :class:`events.base.Event` and is immutable. The
framework publishes **only** these — never strategy, risk, order, execution,
portfolio, position, trade, or performance events. Events are published only
after a consistent state (a completed step or a completed/failed run).
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event

__all__ = [
    "BacktestEvent",
    "BacktestStarted",
    "BacktestProgress",
    "BacktestPaused",
    "BacktestResumed",
    "BacktestCompleted",
    "BacktestCancelled",
    "SimulationStepCompleted",
    "BacktestSnapshotCreated",
    "BacktestMetricsUpdated",
    "BacktestErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class BacktestEvent(Event):
    """Base class for all backtest events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class BacktestStarted(BacktestEvent):
    """A backtest run has started."""

    backtest_id: str
    symbol: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BacktestProgress(BacktestEvent):
    """Progress update for a running backtest."""

    backtest_id: str
    step: int
    total: int


@dataclass(frozen=True, slots=True, kw_only=True)
class BacktestPaused(BacktestEvent):
    """A backtest run was paused."""

    backtest_id: str
    step: int


@dataclass(frozen=True, slots=True, kw_only=True)
class BacktestResumed(BacktestEvent):
    """A backtest run was resumed."""

    backtest_id: str
    step: int


@dataclass(frozen=True, slots=True, kw_only=True)
class BacktestCompleted(BacktestEvent):
    """A backtest run completed successfully."""

    backtest_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BacktestCancelled(BacktestEvent):
    """A backtest run was cancelled."""

    backtest_id: str
    step: int


@dataclass(frozen=True, slots=True, kw_only=True)
class SimulationStepCompleted(BacktestEvent):
    """A single simulation step completed."""

    backtest_id: str
    step: int


@dataclass(frozen=True, slots=True, kw_only=True)
class BacktestSnapshotCreated(BacktestEvent):
    """A backtest snapshot was created and registered."""

    backtest_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BacktestMetricsUpdated(BacktestEvent):
    """A backtest's metrics were computed."""

    backtest_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BacktestErrorOccurred(BacktestEvent):
    """A backtest run failed and was isolated by the manager."""

    backtest_id: str
    message: str
