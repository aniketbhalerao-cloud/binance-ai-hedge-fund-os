"""Paper trading feed.

:class:`DefaultFeed` is the live analog of a historical scheduler. Instead of
iterating a fixed series, it normalizes the *current* live market update into the
:class:`~strategies.context.StrategyContext` the pipeline consumes, synchronizing
the timestamp and attaching the rolling recent-candle window supplied by the
manager.

It is completely stateless — it holds no rolling window and no session state (the
Registry-owned :class:`~paper_trading.models.PaperSession` holds those) — and it
contains no business logic beyond normalization.
"""

from __future__ import annotations

from collections.abc import Sequence

from market_data.models import OHLCV
from paper_trading.context import PaperTradingContext
from paper_trading.exceptions import FeedError
from strategies.context import StrategyContext

__all__ = ["DefaultFeed"]


class DefaultFeed:
    """Stateless normalization of one live market update."""

    def normalize(
        self, context: PaperTradingContext, recent_candles: Sequence[OHLCV]
    ) -> StrategyContext:
        """Return the :class:`StrategyContext` for the live update in ``context``.

        Raises:
            FeedError: If the update carries no live candle.
        """
        if context.candle is None:
            raise FeedError("no live market data in update")
        return StrategyContext(
            exchange=context.exchange,
            symbol=context.symbol,
            timeframe=context.candle.timeframe,
            market_snapshot=context.market_snapshot,
            latest_candle=context.candle,
            recent_candles=tuple(recent_candles),
        )
