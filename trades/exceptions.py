"""Trade Framework exceptions.

Definitions only. Internal failures are translated into these so no
implementation detail escapes the framework; the manager always returns a
:class:`~trades.models.TradeResult`.
"""

from __future__ import annotations

__all__ = [
    "TradeError",
    "TradeNotFoundError",
    "TradeClosedError",
    "InvalidTradeStateError",
    "TradeTrackerError",
    "TradeMatchingError",
    "TradeHistoryError",
    "TradeAnalyticsError",
]


class TradeError(Exception):
    """Base class for all Trade Framework errors."""


class TradeNotFoundError(TradeError):
    """Raised when a trade id is not registered."""


class TradeClosedError(TradeError):
    """Raised when updating a trade that is already closed or cancelled."""


class InvalidTradeStateError(TradeError):
    """Raised on an illegal trade state transition."""


class TradeTrackerError(TradeError):
    """Raised when trade tracking / fill aggregation fails."""


class TradeMatchingError(TradeError):
    """Raised when entry/exit matching fails."""


class TradeHistoryError(TradeError):
    """Raised when a history update fails."""


class TradeAnalyticsError(TradeError):
    """Raised when an analytics calculation fails."""
