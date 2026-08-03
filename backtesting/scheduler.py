"""Backtest scheduler.

:class:`DefaultScheduler` progresses the historical timeline: it iterates the
candle series in order, applying the configured replay speed (a candle stride),
and pairs each emitted candle with its original index for timestamp
synchronization. It is stateless and holds no business logic — it decides only
*which candle comes next*, never what to do with it.
"""

from __future__ import annotations

from collections.abc import Sequence

from backtesting.exceptions import SchedulerError
from market_data.models import OHLCV

__all__ = ["DefaultScheduler"]


class DefaultScheduler:
    """Stateless historical timeline iteration."""

    def iterate(
        self, candles: Sequence[OHLCV], replay_speed: int
    ) -> list[tuple[int, OHLCV]]:
        """Return ``(index, candle)`` pairs honouring ``replay_speed``.

        A ``replay_speed`` of 1 emits every candle; a higher value strides over
        the series (emitting every Nth candle), always in chronological order.

        Raises:
            SchedulerError: If ``replay_speed`` is not a positive integer.
        """
        if replay_speed < 1:
            raise SchedulerError("replay_speed must be a positive integer")
        return [(i, candles[i]) for i in range(0, len(candles), replay_speed)]
