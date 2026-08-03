"""Backtesting Framework domain models.

Immutable, exchange-independent value objects. The rest of the application
consumes only these standardized models. Money/quantities use
:class:`~decimal.Decimal`; timestamps are timezone-aware UTC. Simulation produces
**new** objects — nothing here is ever mutated.

``SimulationParameters`` configures the deterministic simulation (slippage,
commission, latency, replay speed); ``SimulatedFill`` is the Simulator's output;
``SimulationStep`` records one point on the replay timeline; the ``Backtest`` /
``BacktestMetrics`` / ``BacktestSummary`` / ``BacktestSnapshot`` / ``BacktestResult``
models describe the run and its outcome.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from backtesting.state import SimulationState
from models import OrderSide

__all__ = [
    "BacktestResultStatus",
    "SimulationParameters",
    "SimulatedFill",
    "SimulationStep",
    "Backtest",
    "BacktestMetrics",
    "BacktestSummary",
    "BacktestSnapshot",
    "BacktestHistory",
    "BacktestResult",
]

_ZERO = Decimal("0")


class BacktestResultStatus(str, Enum):
    """Coarse outcome of a backtest run."""

    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class SimulationParameters:
    """Deterministic simulation configuration.

    Attributes:
        initial_cash: Starting cash for the simulated portfolio.
        slippage_bps: Slippage applied to the fill price, in basis points.
        commission_bps: Commission charged on notional, in basis points.
        latency_steps: Simulated latency, recorded as an integer step offset.
        replay_speed: Candle stride per step (1 = every candle).
        cancel_after_steps: Optional step count after which the run cancels.
        pause_at_step: Optional step index at which a pause/resume is emitted.
    """

    initial_cash: Decimal = Decimal("100000")
    slippage_bps: Decimal = _ZERO
    commission_bps: Decimal = _ZERO
    latency_steps: int = 0
    replay_speed: int = 1
    cancel_after_steps: int | None = None
    pause_at_step: int | None = None


@dataclass(frozen=True, slots=True)
class SimulatedFill:
    """The Simulator's output: a deterministic historical fill."""

    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Decimal
    commission: Decimal
    slippage: Decimal
    latency_steps: int
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class SimulationStep:
    """One point on the replay timeline (append-only history entry)."""

    index: int
    timestamp: datetime
    close: Decimal
    equity: Decimal
    fill: SimulatedFill | None = None


@dataclass(frozen=True, slots=True)
class Backtest:
    """An immutable description of a backtest run."""

    id: str
    exchange: str
    symbol: str
    state: SimulationState
    step_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class BacktestMetrics:
    """Derived performance metrics for a completed backtest."""

    cagr: Decimal = _ZERO
    annual_return: Decimal = _ZERO
    total_return: Decimal = _ZERO
    sharpe_ratio: Decimal = _ZERO
    sortino_ratio: Decimal = _ZERO
    max_drawdown: Decimal = _ZERO
    win_rate: Decimal = _ZERO
    profit_factor: Decimal = _ZERO
    recovery_factor: Decimal = _ZERO
    average_trade: Decimal = _ZERO
    average_holding_time: Decimal = _ZERO
    expectancy: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class BacktestSummary:
    """Compact run summary (counts, commission, equity)."""

    total_steps: int = 0
    total_fills: int = 0
    total_trades: int = 0
    total_commission: Decimal = _ZERO
    initial_equity: Decimal = _ZERO
    final_equity: Decimal = _ZERO
    net_profit: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class BacktestHistory:
    """Append-only record of a backtest's simulation steps."""

    backtest_id: str
    steps: tuple[SimulationStep, ...] = ()

    def append(self, step: SimulationStep) -> BacktestHistory:
        """Return a new history with ``step`` appended (never mutates)."""
        return BacktestHistory(self.backtest_id, self.steps + (step,))


@dataclass(frozen=True, slots=True)
class BacktestSnapshot:
    """A complete, immutable record of one backtest run."""

    backtest: Backtest
    metrics: BacktestMetrics
    summary: BacktestSummary
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """The immutable outcome of a backtest run."""

    status: BacktestResultStatus
    backtest: Backtest | None = None
    snapshot: BacktestSnapshot | None = None
    history: BacktestHistory | None = None
    metrics: BacktestMetrics | None = None
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Return ``True`` when the run completed successfully."""
        return self.status is BacktestResultStatus.COMPLETED
