"""Market-data exceptions.

Definitions only — no handling logic. These isolate market-data failures so a
provider or normalization problem never crashes the Trading Engine.
"""

from __future__ import annotations

__all__ = [
    "MarketDataError",
    "ProviderError",
    "NormalizationError",
    "CacheError",
    "MarketDataConnectionError",
]


class MarketDataError(Exception):
    """Base class for all market-data errors."""


class ProviderError(MarketDataError):
    """Raised when a provider fails to receive or relay data."""


class NormalizationError(MarketDataError):
    """Raised when a raw payload cannot be normalized into a domain model."""


class CacheError(MarketDataError):
    """Raised when a cache operation fails or receives invalid input."""


class MarketDataConnectionError(MarketDataError):
    """Raised when a provider connection cannot be established or is lost.

    Named to avoid shadowing the built-in :class:`ConnectionError`.
    """
