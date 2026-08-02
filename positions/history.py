"""Position history.

:class:`DefaultPositionHistory` appends trades to an append-only
:class:`~positions.models.PositionHistory`. It is stateless — it returns a new
history and never mutates existing records, so historical records are immutable.
"""

from __future__ import annotations

from positions.models import PositionHistory, PositionTrade

__all__ = ["DefaultPositionHistory"]


class DefaultPositionHistory:
    """Stateless, append-only history service."""

    def append(self, history: PositionHistory, trade: PositionTrade) -> PositionHistory:
        """Return a new history with ``trade`` appended."""
        return history.append(trade)
