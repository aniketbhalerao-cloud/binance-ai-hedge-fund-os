"""Paper Trading Framework exceptions.

Definitions only. Internal failures are translated into these so no
implementation detail escapes; the manager always returns a
:class:`~paper_trading.models.PaperTradingResult`.
"""

from __future__ import annotations

__all__ = [
    "PaperTradingError",
    "FeedError",
    "BrokerError",
    "MetricsError",
    "HistoryError",
    "RegistryError",
    "PaperSessionCancelledError",
]


class PaperTradingError(Exception):
    """Base class for all Paper Trading Framework errors."""


class FeedError(PaperTradingError):
    """Raised when a live market update cannot be normalized."""


class BrokerError(PaperTradingError):
    """Raised when the paper broker cannot produce a fill."""


class MetricsError(PaperTradingError):
    """Raised when a metrics calculation fails."""


class HistoryError(PaperTradingError):
    """Raised when a history update fails."""


class RegistryError(PaperTradingError):
    """Raised when a registry operation fails."""


class PaperSessionCancelledError(PaperTradingError):
    """Raised internally to unwind a session that was cancelled."""
