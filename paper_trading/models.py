"""Paper Trading Framework domain models.

Immutable, exchange-independent value objects. The rest of the application
consumes only these standardized models. Money/quantities use
:class:`~decimal.Decimal`; timestamps are timezone-aware UTC. Every state change
produces a **new** object — nothing here is ever mutated.

``SessionParameters`` configures the deterministic broker (slippage, commission,
latency, initial cash); ``PaperFill`` is the broker's output; ``PaperSession`` is
the durable, registry-owned running state of one live session; the metrics /
summary / snapshot / history / result models describe the session and its
per-update outcome.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from market_data.models import OHLCV
from models import OrderSide
from paper_trading.state import SessionState
from portfolio.models import PortfolioResult
from positions.models import PositionResult
from trades.models import Trade, TradeResult

__all__ = [
    "PaperTradingResultStatus",
    "SessionParameters",
    "PaperFill",
    "PaperTradingHistory",
    "PaperSession",
    "PaperTradingMetrics",
    "PaperTradingSummary",
    "PaperTradingSnapshot",
    "PaperTradingResult",
]

_ZERO = Decimal("0")


class PaperTradingResultStatus(str, Enum):
    """Coarse outcome of processing one live update."""

    PROCESSED = "processed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class SessionParameters:
    """Deterministic paper-trading configuration.

    Attributes:
        initial_cash: Starting cash for the simulated portfolio.
        slippage_bps: Slippage applied to the fill price, in basis points.
        commission_bps: Commission charged on notional, in basis points.
        latency_steps: Simulated latency, recorded as an integer step offset.
        window: Rolling recent-candle window size handed to the strategy.
        cancel_after_updates: Optional update count after which the session cancels.
    """

    initial_cash: Decimal = Decimal("100000")
    slippage_bps: Decimal = _ZERO
    commission_bps: Decimal = _ZERO
    latency_steps: int = 0
    window: int = 128
    cancel_after_updates: int | None = None


@dataclass(frozen=True, slots=True)
class PaperFill:
    """The Paper Broker's output: a deterministic simulated live fill."""

    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Decimal
    commission: Decimal
    slippage: Decimal
    latency_steps: int
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class PaperTradingHistory:
    """Append-only record of a session's simulated fills (execution timeline)."""

    session_id: str
    fills: tuple[PaperFill, ...] = ()

    def append(self, fill: PaperFill) -> PaperTradingHistory:
        """Return a new history with ``fill`` appended (never mutates)."""
        return PaperTradingHistory(self.session_id, self.fills + (fill,))


@dataclass(frozen=True, slots=True)
class PaperSession:
    """The durable, immutable running state of one live paper-trading session.

    The Registry owns the current ``PaperSession``; the Manager loads it,
    processes one live update, and writes back a **new** ``PaperSession``.
    """

    id: str
    exchange: str
    symbol: str
    state: SessionState
    portfolio_result: PortfolioResult | None = None
    position_result: PositionResult | None = None
    trade_result: TradeResult | None = None
    recent_candles: tuple[OHLCV, ...] = ()
    equity_curve: tuple[Decimal, ...] = ()
    returns: tuple[Decimal, ...] = ()
    trades: tuple[Trade, ...] = ()
    history: PaperTradingHistory = field(
        default_factory=lambda: PaperTradingHistory("")
    )
    total_commission: Decimal = _ZERO
    update_count: int = 0
    fill_count: int = 0
    started_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PaperTradingMetrics:
    """Derived live performance metrics for a session."""

    total_return: Decimal = _ZERO
    realized_pnl: Decimal = _ZERO
    unrealized_pnl: Decimal = _ZERO
    sharpe_ratio: Decimal = _ZERO
    max_drawdown: Decimal = _ZERO
    win_rate: Decimal = _ZERO
    profit_factor: Decimal = _ZERO
    average_trade: Decimal = _ZERO
    average_holding_time: Decimal = _ZERO
    expectancy: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class PaperTradingSummary:
    """Compact session summary (counts, commission, equity)."""

    total_updates: int = 0
    total_fills: int = 0
    total_trades: int = 0
    total_commission: Decimal = _ZERO
    initial_equity: Decimal = _ZERO
    final_equity: Decimal = _ZERO
    net_profit: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class PaperTradingSnapshot:
    """A complete, immutable record of one session at one update."""

    session: PaperSession
    metrics: PaperTradingMetrics
    summary: PaperTradingSummary
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class PaperTradingResult:
    """The immutable outcome of processing one live update."""

    status: PaperTradingResultStatus
    session: PaperSession | None = None
    snapshot: PaperTradingSnapshot | None = None
    fill: PaperFill | None = None
    metrics: PaperTradingMetrics | None = None
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Return ``True`` when the update was processed without failure."""
        return self.status in (
            PaperTradingResultStatus.PROCESSED,
            PaperTradingResultStatus.COMPLETED,
        )
