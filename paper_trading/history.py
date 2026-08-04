"""Paper trading history.

:class:`DefaultPaperTradingHistory` appends simulated fills to an append-only
:class:`~paper_trading.models.PaperTradingHistory`. It is stateless — it returns a
new history and never mutates existing records, so a session's execution timeline
is immutable and can never be rewritten.
"""

from __future__ import annotations

from paper_trading.models import PaperFill, PaperTradingHistory

__all__ = ["DefaultPaperTradingHistory"]


class DefaultPaperTradingHistory:
    """Stateless, append-only fill-history service."""

    def append(
        self, history: PaperTradingHistory, fill: PaperFill
    ) -> PaperTradingHistory:
        """Return a new history with ``fill`` appended."""
        return history.append(fill)
