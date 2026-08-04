"""Paper Trading Framework events.

Each inherits the existing :class:`events.base.Event` and is immutable. The
framework publishes **only** these — never strategy, risk, order, execution,
portfolio, position, trade, performance, or backtesting events. Events are
published only after a consistent state (a processed update, or a
completed/cancelled session).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from events.base import Event

__all__ = [
    "PaperTradingEvent",
    "PaperTradingStarted",
    "PaperTradingStopped",
    "MarketDataProcessed",
    "PaperOrderFilled",
    "PaperTradeExecuted",
    "PaperSnapshotCreated",
    "PaperMetricsUpdated",
    "PaperSessionCompleted",
    "PaperSessionCancelled",
    "PaperTradingErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class PaperTradingEvent(Event):
    """Base class for all paper-trading events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class PaperTradingStarted(PaperTradingEvent):
    """The paper-trading engine was started."""


@dataclass(frozen=True, slots=True, kw_only=True)
class PaperTradingStopped(PaperTradingEvent):
    """The paper-trading engine was stopped."""


@dataclass(frozen=True, slots=True, kw_only=True)
class MarketDataProcessed(PaperTradingEvent):
    """A live market update was processed for a session."""

    session_id: str
    symbol: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PaperOrderFilled(PaperTradingEvent):
    """The paper broker simulated a fill for a session."""

    session_id: str
    symbol: str
    quantity: Decimal
    price: Decimal


@dataclass(frozen=True, slots=True, kw_only=True)
class PaperTradeExecuted(PaperTradingEvent):
    """A trade lifecycle update resulted from a simulated fill."""

    session_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PaperSnapshotCreated(PaperTradingEvent):
    """A session snapshot was created."""

    session_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PaperMetricsUpdated(PaperTradingEvent):
    """A session's live metrics were recomputed."""

    session_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PaperSessionCompleted(PaperTradingEvent):
    """A session completed gracefully."""

    session_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PaperSessionCancelled(PaperTradingEvent):
    """A session was cancelled."""

    session_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PaperTradingErrorOccurred(PaperTradingEvent):
    """A live update failed and was isolated by the manager."""

    session_id: str
    message: str
