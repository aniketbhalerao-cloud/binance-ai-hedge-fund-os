"""Trade analytics.

:class:`DefaultTradeAnalytics` derives statistics from a completed trade's
durable figures and its append-only fill history: holding time, trade duration,
gross/net profit, win/loss status, and quantity statistics. It is stateless —
analytics are always derived from the historical records, never stored — so a
recomputation is deterministic and side-effect free.

Fees are not modelled in this framework, so ``net_profit`` equals
``gross_profit`` (the realized P&L reported by the upstream position). A future
fee/attribution service can plug in without changing this component.
"""

from __future__ import annotations

from decimal import Decimal

from trades.models import Trade, TradeAnalytics, TradeHistory

__all__ = ["DefaultTradeAnalytics"]

_ZERO = Decimal("0")


class DefaultTradeAnalytics:
    """Stateless analytics derived from a trade + its fill history."""

    def compute(self, trade: Trade, history: TradeHistory) -> TradeAnalytics:
        """Return :class:`TradeAnalytics` for ``trade``."""
        realized = trade.realized_pnl
        won = trade.exit_quantity > _ZERO and realized > _ZERO
        return TradeAnalytics(
            holding_time_seconds=self._holding_time(trade),
            duration_seconds=self._fill_span(history),
            gross_profit=realized,
            net_profit=realized,  # no fees modelled; net == gross
            won=won,
            fill_count=len(history.fills),
            entry_quantity=trade.entry_quantity,
            exit_quantity=trade.exit_quantity,
        )

    @staticmethod
    def _holding_time(trade: Trade) -> Decimal:
        """Seconds from the trade's open until close (or last update)."""
        end = trade.closed_at or trade.updated_at
        if trade.opened_at is None or end is None:
            return _ZERO
        return Decimal(str((end - trade.opened_at).total_seconds()))

    @staticmethod
    def _fill_span(history: TradeHistory) -> Decimal:
        """Seconds spanned by the recorded fills (first to last)."""
        if len(history.fills) < 2:
            return _ZERO
        first = history.fills[0].timestamp
        last = history.fills[-1].timestamp
        return Decimal(str((last - first).total_seconds()))
