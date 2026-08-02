"""Portfolio engine — the public entry point of the Portfolio Framework.

:class:`DefaultPortfolioEngine` receives completed executions (as a
:class:`PortfolioContext`) and delegates the update to an injected
:class:`PortfolioManager`. It holds references to the upstream frameworks for
integration but never executes trades, evaluates risk/strategies, or talks to
exchanges.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from portfolio.context import PortfolioContext
from portfolio.interfaces import PortfolioManager
from portfolio.models import PortfolioResult

if TYPE_CHECKING:
    from exchange_adapters.interfaces import ExchangeEngine
    from execution.interfaces import ExecutionEngine
    from trading.engine import TradingEngine

__all__ = ["DefaultPortfolioEngine"]


class DefaultPortfolioEngine:
    """Public portfolio engine coordinating updates.

    Args:
        manager: The portfolio manager that runs the pipeline (abstraction).
        logger: Optional logger factory for framework logs.
        trading_engine: Optional Trading Engine reference (integration only).
        execution_engine: Optional Execution Engine reference (integration only).
        exchange_engine: Optional Exchange Engine reference (integration only).
    """

    def __init__(
        self,
        manager: PortfolioManager,
        logger: LoggerFactory | None = None,
        trading_engine: TradingEngine | None = None,
        execution_engine: ExecutionEngine | None = None,
        exchange_engine: ExchangeEngine | None = None,
    ) -> None:
        self._manager = manager
        self._trading_engine = trading_engine
        self._execution_engine = execution_engine
        self._exchange_engine = exchange_engine
        self._log = logger.get_logger("portfolio.engine") if logger else None

    async def start(self) -> None:
        """Start the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Portfolio engine started")

    async def stop(self) -> None:
        """Stop the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Portfolio engine stopped")

    async def process(self, context: PortfolioContext) -> PortfolioResult:
        """Update the portfolio for the completed execution in ``context``."""
        return await self._manager.update(context)
