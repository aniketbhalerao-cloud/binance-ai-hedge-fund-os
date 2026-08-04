"""Learning metrics.

:class:`DefaultLearningMetrics` derives aggregate metrics from a learning record:
outcome counts, overall win rate, average score and P&L, the best and worst
strategy by score, an improvement rate (recent vs. earlier realized P&L), and the
feedback count. It is stateless and pure — metrics are always derived from the
record, never stored — and all arithmetic is :class:`~decimal.Decimal`.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from learning.exceptions import MetricsError
from learning.models import JournalEntry, LearningMetrics, LearningRecord

__all__ = ["DefaultLearningMetrics"]

_ZERO = Decimal("0")


class DefaultLearningMetrics:
    """Stateless learning metrics derived from a record."""

    def calculate(self, record: LearningRecord) -> LearningMetrics:
        """Return :class:`LearningMetrics` for ``record``.

        Raises:
            MetricsError: If an unexpected failure occurs.
        """
        try:
            return self._calculate(record)
        except MetricsError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise MetricsError(str(exc)) from exc

    def _calculate(self, record: LearningRecord) -> LearningMetrics:
        entries = record.history.entries
        total = len(entries)
        if total == 0:
            return LearningMetrics(feedback_count=len(record.feedback))

        n = Decimal(total)
        wins = sum(1 for e in entries if e.outcome.won)
        total_pnl = sum((e.outcome.realized_pnl for e in entries), _ZERO)

        strategies = record.strategy_evaluations
        if strategies:
            best = max(strategies, key=lambda s: s.score)
            worst = min(strategies, key=lambda s: s.score)
            avg_score = sum((s.score for s in strategies), _ZERO) / Decimal(
                len(strategies)
            )
            best_name, worst_name = best.strategy_name, worst.strategy_name
        else:
            avg_score, best_name, worst_name = _ZERO, "", ""

        return LearningMetrics(
            total_outcomes=total,
            win_rate=Decimal(wins) / n,
            average_score=avg_score,
            average_pnl=total_pnl / n,
            best_strategy=best_name,
            worst_strategy=worst_name,
            improvement_rate=_improvement(entries),
            feedback_count=len(record.feedback),
        )


def _improvement(entries: Sequence[JournalEntry]) -> Decimal:
    """Recent-vs-earlier average realized P&L (positive = improving)."""
    n = len(entries)
    if n < 2:
        return _ZERO
    mid = n // 2
    earlier = entries[:mid]
    recent = entries[mid:]
    return _avg_pnl(recent) - _avg_pnl(earlier)


def _avg_pnl(entries: Sequence[JournalEntry]) -> Decimal:
    if not entries:
        return _ZERO
    total = sum((e.outcome.realized_pnl for e in entries), _ZERO)
    return total / Decimal(len(entries))
