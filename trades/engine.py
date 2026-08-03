"""Trade engine — the public entry point of the Trade Framework.

:class:`DefaultTradeEngine` receives completed position updates (as a
:class:`~trades.context.TradeContext`) and delegates the trade update to an
injected :class:`~trades.interfaces.TradeManager`. It holds references to the
upstream frameworks for integration but never executes trades, values
portfolios, performs position calculations, or talks to exchanges.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from trades.context import TradeContext
from trades.interfaces import TradeManager
from trades.models import TradeResult

if TYPE_CHECKING:
    from positions.interfaces import PositionEngine
    from trading.engine import TradingEngine

__all__ = ["DefaultTradeEngine"]


class DefaultTradeEngine:
    """Public trade engine coordinating trade updates.

    Args:
        manager: The trade manager that runs the pipeline (abstraction).
        logger: Optional logger factory for framework logs.
        position_engine: Optional Position Engine reference (integration only).
        trading_engine: Optional Trading Engine reference (integration only).
    """

    def __init__(
        self,
        manager: TradeManager,
        logger: LoggerFactory | None = None,
        position_engine: PositionEngine | None = None,
        trading_engine: TradingEngine | None = None,
    ) -> None:
        self._manager = manager
        self._position_engine = position_engine
        self._trading_engine = trading_engine
        self._log = logger.get_logger("trades.engine") if logger else None

    async def start(self) -> None:
        """Start the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Trade engine started")

    async def stop(self) -> None:
        """Stop the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Trade engine stopped")

    async def process(self, context: TradeContext) -> TradeResult:
        """Update the trade for the completed position update in ``context``."""
        return await self._manager.update(context)
