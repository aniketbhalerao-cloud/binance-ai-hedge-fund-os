"""Trade registry.

:class:`InMemoryTradeRegistry` is a thread-safe store of trades and their
histories, keyed by trade id. It never creates trades (creation is the
manager's/DI's job) — it only registers, looks up, lists, and removes them.
Mutable state is guarded by a :class:`threading.Lock`.
"""

from __future__ import annotations

from threading import Lock

from trades.exceptions import TradeNotFoundError
from trades.models import Trade, TradeHistory

__all__ = ["InMemoryTradeRegistry"]


class InMemoryTradeRegistry:
    """A thread-safe registry of trades + histories, keyed by id."""

    def __init__(self) -> None:
        self._trades: dict[str, Trade] = {}
        self._histories: dict[str, TradeHistory] = {}
        self._lock = Lock()

    def register(self, trade: Trade, history: TradeHistory) -> None:
        """Store ``trade`` and its ``history`` (insert or replace)."""
        with self._lock:
            self._trades[trade.id] = trade
            self._histories[trade.id] = history

    def exists(self, trade_id: str) -> bool:
        """Return ``True`` if ``trade_id`` is registered."""
        with self._lock:
            return trade_id in self._trades

    def get(self, trade_id: str) -> Trade:
        """Return the trade for ``trade_id``.

        Raises:
            TradeNotFoundError: If it is not registered.
        """
        with self._lock:
            trade = self._trades.get(trade_id)
        if trade is None:
            raise TradeNotFoundError(f"trade {trade_id!r} not found")
        return trade

    def history(self, trade_id: str) -> TradeHistory:
        """Return the history for ``trade_id`` (empty if none yet)."""
        with self._lock:
            return self._histories.get(trade_id, TradeHistory(trade_id))

    def list(self) -> list[Trade]:
        """Return all registered trades."""
        with self._lock:
            return list(self._trades.values())

    def remove(self, trade_id: str) -> None:
        """Remove ``trade_id`` (trade + history) if present."""
        with self._lock:
            self._trades.pop(trade_id, None)
            self._histories.pop(trade_id, None)
