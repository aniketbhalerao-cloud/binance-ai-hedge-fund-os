"""In-memory market-data cache.

:class:`InMemoryMarketDataCache` stores only the *latest* normalized
:class:`~market_data.models.MarketSnapshot` per :class:`~market_data.models.CacheKey`.
It is memory-only and thread-safe. It is **not** persistence — nothing here
touches a database; durable storage is the persistence layer's concern.
"""

from __future__ import annotations

from threading import Lock

from market_data.exceptions import CacheError
from market_data.models import CacheKey, MarketSnapshot

__all__ = ["InMemoryMarketDataCache"]


class InMemoryMarketDataCache:
    """A thread-safe, memory-only latest-snapshot cache."""

    def __init__(self) -> None:
        self._store: dict[CacheKey, MarketSnapshot] = {}
        self._lock = Lock()

    def update(self, key: CacheKey, snapshot: MarketSnapshot) -> None:
        """Store (replace) the snapshot for ``key``.

        Raises:
            CacheError: If ``snapshot`` is not a :class:`MarketSnapshot`.
        """
        if not isinstance(snapshot, MarketSnapshot):
            raise CacheError("Cache.update requires a MarketSnapshot instance.")
        with self._lock:
            self._store[key] = snapshot

    def get(self, key: CacheKey) -> MarketSnapshot | None:
        """Return the snapshot for ``key`` if present, else ``None``."""
        with self._lock:
            return self._store.get(key)

    def exists(self, key: CacheKey) -> bool:
        """Return ``True`` if a snapshot exists for ``key``."""
        with self._lock:
            return key in self._store

    def clear(self) -> None:
        """Remove all cached snapshots."""
        with self._lock:
            self._store.clear()

    def snapshot(self) -> dict[CacheKey, MarketSnapshot]:
        """Return a shallow copy of all cached snapshots."""
        with self._lock:
            return dict(self._store)
