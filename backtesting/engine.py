"""Backtest engine — the public entry point of the Backtesting Framework.

:class:`DefaultBacktestEngine` receives an assembled
:class:`~backtesting.context.BacktestingContext` and delegates the run to an
injected :class:`~backtesting.interfaces.BacktestManager`. It performs no
simulation, scheduling, or metrics work itself — it only starts, stops, and
coordinates. All historical simulation and framework orchestration happens in the
manager; the engine never contacts an exchange.
"""

from __future__ import annotations

from backtesting.context import BacktestingContext
from backtesting.interfaces import BacktestManager
from backtesting.models import BacktestResult
from core.logging import LoggerFactory

__all__ = ["DefaultBacktestEngine"]


class DefaultBacktestEngine:
    """Public backtest engine coordinating runs.

    Args:
        manager: The backtest manager that runs the pipeline (abstraction).
        logger: Optional logger factory for framework logs.
    """

    def __init__(
        self, manager: BacktestManager, logger: LoggerFactory | None = None
    ) -> None:
        self._manager = manager
        self._log = logger.get_logger("backtesting.engine") if logger else None

    async def start(self) -> None:
        """Start the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Backtest engine started")

    async def stop(self) -> None:
        """Stop the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Backtest engine stopped")

    async def run_backtest(self, context: BacktestingContext) -> BacktestResult:
        """Run the backtest described by ``context`` and return the result."""
        return await self._manager.run(context)
