"""Position metrics.

:class:`DefaultPositionMetrics` derives statistics from a position's completed
history and its calculation (holding time, win rate, average profit/loss, and
excursion placeholders). It is stateless — metrics are always derived from the
historical records, never stored.
"""

from __future__ import annotations

from decimal import Decimal

from positions.models import PositionCalculation, PositionHistory, PositionMetrics

__all__ = ["DefaultPositionMetrics"]

_ZERO = Decimal("0")
_ONE = Decimal("1")


class DefaultPositionMetrics:
    """Stateless metrics derived from history + calculation."""

    def compute(
        self, history: PositionHistory, calculation: PositionCalculation
    ) -> PositionMetrics:
        """Return :class:`PositionMetrics` for the position."""
        realized = calculation.realized_pnl
        # Win/profit/loss are known once realization has occurred (an exit).
        won = calculation.exit_count > 0 and realized > _ZERO
        return PositionMetrics(
            trade_count=len(history.trades),
            holding_time_seconds=calculation.duration_seconds,
            win_rate=_ONE if won else _ZERO,
            average_profit=realized if realized > _ZERO else _ZERO,
            average_loss=realized if realized < _ZERO else _ZERO,
            # Max favorable/adverse excursion require an intra-trade price path,
            # which this framework does not collect; left at zero for now.
            max_favorable_excursion=_ZERO,
            max_adverse_excursion=_ZERO,
        )
