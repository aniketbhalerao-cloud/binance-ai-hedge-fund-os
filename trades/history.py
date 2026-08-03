"""Trade history.

:class:`DefaultTradeHistory` appends fills to an append-only
:class:`~trades.models.TradeHistory`. It is stateless — it returns a new history
and never mutates existing records, so historical records are immutable and the
trade timeline can never be rewritten.
"""

from __future__ import annotations

from trades.models import TradeFill, TradeHistory

__all__ = ["DefaultTradeHistory"]


class DefaultTradeHistory:
    """Stateless, append-only fill-history service."""

    def append(self, history: TradeHistory, fill: TradeFill) -> TradeHistory:
        """Return a new history with ``fill`` appended."""
        return history.append(fill)
