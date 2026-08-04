"""Paper trading engine — the public entry point of the Paper Trading Framework.

:class:`DefaultPaperTradingEngine` receives one live-update
:class:`~paper_trading.context.PaperTradingContext` at a time and delegates
processing to an injected :class:`~paper_trading.interfaces.PaperTradingManager`.
It publishes engine lifecycle events and performs no feed, broker, or metrics work
itself. It never contacts an exchange and never places a real order.
"""

from __future__ import annotations

from core.logging import LoggerFactory
from events.bus import EventBus
from paper_trading.context import PaperTradingContext
from paper_trading.events import PaperTradingStarted, PaperTradingStopped
from paper_trading.interfaces import PaperTradingManager
from paper_trading.models import PaperTradingResult

__all__ = ["DefaultPaperTradingEngine"]


class DefaultPaperTradingEngine:
    """Public paper-trading engine coordinating live sessions.

    Args:
        bus: Shared event bus (for engine lifecycle events).
        manager: The paper-trading manager that processes updates (abstraction).
        logger: Optional logger factory for framework logs.
    """

    def __init__(
        self,
        bus: EventBus,
        manager: PaperTradingManager,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._bus = bus
        self._manager = manager
        self._log = logger.get_logger("paper_trading.engine") if logger else None

    async def start(self) -> None:
        """Start the engine and publish a lifecycle event (no external I/O)."""
        if self._log is not None:
            self._log.info("Paper trading engine started")
        await self._bus.publish(PaperTradingStarted())

    async def stop(self) -> None:
        """Stop the engine and publish a lifecycle event (no external I/O)."""
        if self._log is not None:
            self._log.info("Paper trading engine stopped")
        await self._bus.publish(PaperTradingStopped())

    async def process(self, context: PaperTradingContext) -> PaperTradingResult:
        """Process one live market update through the pipeline."""
        return await self._manager.process(context)
