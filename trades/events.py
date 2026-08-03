"""Trade Framework events.

Each inherits the existing :class:`events.base.Event` and is immutable. The
framework publishes **only** these — never strategy, risk, order, execution,
exchange, portfolio, or position events. Events are published only after a fully
consistent trade update (never on partial state).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from events.base import Event
from trades.state import TradeState

__all__ = [
    "TradeEvent",
    "TradeOpened",
    "TradeUpdated",
    "TradeMatched",
    "TradePartiallyFilled",
    "TradeFilled",
    "TradeClosed",
    "TradeHistoryUpdated",
    "TradeAnalyticsUpdated",
    "TradeStateChanged",
    "TradeErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class TradeEvent(Event):
    """Base class for all trade events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class TradeOpened(TradeEvent):
    """A trade was opened (first entry fill)."""

    trade_id: str
    symbol: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TradeUpdated(TradeEvent):
    """An existing trade received a new fill."""

    trade_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TradeMatched(TradeEvent):
    """An entry and exit were correlated for a trade."""

    trade_id: str
    matched_quantity: Decimal


@dataclass(frozen=True, slots=True, kw_only=True)
class TradePartiallyFilled(TradeEvent):
    """A trade was partially exited."""

    trade_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TradeFilled(TradeEvent):
    """A trade's entry was fully matched by exits (round trip complete)."""

    trade_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TradeClosed(TradeEvent):
    """A trade was fully closed."""

    trade_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TradeHistoryUpdated(TradeEvent):
    """A trade's fill history was appended to."""

    trade_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TradeAnalyticsUpdated(TradeEvent):
    """A trade's analytics were recomputed."""

    trade_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TradeStateChanged(TradeEvent):
    """A trade transitioned from one lifecycle state to another."""

    trade_id: str
    previous: TradeState
    current: TradeState


@dataclass(frozen=True, slots=True, kw_only=True)
class TradeErrorOccurred(TradeEvent):
    """A trade update failed and was isolated by the manager."""

    trade_id: str
    message: str
