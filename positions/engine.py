"""Position engine — the public entry point of the Position Framework.

:class:`DefaultPositionEngine` receives completed portfolio updates (as a
:class:`PositionContext`) and delegates the position update to an injected
:class:`PositionManager`. It holds references to the upstream frameworks for
integration but never executes trades, evaluates risk, values portfolios, or
talks to exchanges.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from positions.context import PositionContext
from positions.interfaces import PositionManager
from positions.models import PositionResult

if TYPE_CHECKING:
    from portfolio.interfaces import PortfolioEngine
    from trading.engine import TradingEngine

__all__ = ["DefaultPositionEngine"]


class DefaultPositionEngine:
    """Public position engine coordinating updates.

    Args:
        manager: The position manager that runs the pipeline (abstraction).
        logger: Optional logger factory for framework logs.
        trading_engine: Optional Trading Engine reference (integration only).
        portfolio_engine: Optional Portfolio Engine reference (integration only).
    """

    def __init__(
        self,
        manager: PositionManager,
        logger: LoggerFactory | None = None,
        trading_engine: TradingEngine | None = None,
        portfolio_engine: PortfolioEngine | None = None,
    ) -> None:
        self._manager = manager
        self._trading_engine = trading_engine
        self._portfolio_engine = portfolio_engine
        self._log = logger.get_logger("positions.engine") if logger else None

    async def start(self) -> None:
        """Start the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Position engine started")

    async def stop(self) -> None:
        """Stop the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Position engine stopped")

    async def process(self, context: PositionContext) -> PositionResult:
        """Update the position for the completed portfolio update in ``context``."""
        return await self._manager.update(context)
